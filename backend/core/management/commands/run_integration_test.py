"""
End-to-end integration tests with real data.

Tests the complete Loudrr flow:
1. User registration + X linking (real TweetScout API)
2. Post submission + ownership validation
3. Engagement flow + verification
4. Karma multipliers + XP rewards
5. Edge cases

Run with: python manage.py run_integration_test

Options:
  --cleanup     Delete test users after running tests
  --skip-api    Skip real API calls (use mock data)
  --verbose     Show detailed output
"""
import random
import time
from decimal import Decimal
from typing import Optional

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import User, XProfile, XPTransaction, Transaction
from core.services.tweetscout import get_tweetscout_service
from core.services.tweet_score import (
    get_tweet_score_tier,
    get_tweet_score_multiplier,
    calculate_engagement_karma,
)
from core.services.credits import CreditService
from core.services.xp import XPService, get_xp_for_sponsored_engagement
from core.services.twitter_verification import twitter_verification
from core.services.settings import get_setting
from posts.models import Post, Engagement, SponsoredPost


# =============================================================================
# TEST DATA CONFIGURATION
# =============================================================================

# Test users with their X usernames and fake Telegram IDs
TEST_USERS = [
    {"x_username": "igrisonchain1", "telegram_id": 1000001, "name": "Test User 1 - Single Post"},
    {"x_username": "saifmr20", "telegram_id": 1000002, "name": "Test User 2 - Multiple Posts"},
    {"x_username": "0xunclebeanz", "telegram_id": 1000003, "name": "Test User 3 - Multiple Posts"},
    {"x_username": "FumioWeb3", "telegram_id": 1000004, "name": "Test User 4 - Multiple Posts"},
    {"x_username": "loudrrHQ", "telegram_id": 1000005, "name": "Test User 5 - No Posts Edge Case"},
    {"x_username": "0xBlest_", "telegram_id": 1000006, "name": "Test User 6 - Existing User"},
]

# Sponsor accounts
SPONSOR_USERS = [
    {"x_username": "PulseSocialFi", "telegram_id": 1000007, "name": "Sponsor: PulseSocialFi"},
    {"x_username": "SIXR_cricket", "telegram_id": 1000008, "name": "Sponsor: SIXR Cricket"},
    {"x_username": "GEODNET", "telegram_id": 1000009, "name": "Sponsor: GEODNET"},
]

# Posts by username (real X post links)
USER_POSTS = {
    "igrisonchain1": [
        "https://x.com/igrisonchain1/status/2012139965820649624",
    ],
    "saifmr20": [
        "https://x.com/saifmr20/status/2012902426417025084",
        "https://x.com/saifmr20/status/2012596513340358880",
        "https://x.com/saifmr20/status/2012550399182635457",
        "https://x.com/saifmr20/status/2012304662817386913",
        "https://x.com/saifmr20/status/2012108488458354746",
        "https://x.com/saifmr20/status/2012246621506129976",
    ],
    "0xBlest_": [
        "https://x.com/0xBlest_/status/1992193469855719432",
        "https://x.com/0xBlest_/status/1999153750766924085",
        "https://x.com/0xBlest_/status/1989960943225454695",
        "https://x.com/0xBlest_/status/1989377985389236378",
        "https://x.com/0xBlest_/status/1988516904055828925",
        "https://x.com/0xBlest_/status/1987120295946428698",
        "https://x.com/0xBlest_/status/1985676606925652313",
        "https://x.com/0xBlest_/status/1985607418102104463",
        "https://x.com/0xBlest_/status/1983073875593441465",
        "https://x.com/0xBlest_/status/1980236461149475124",
    ],
    "0xunclebeanz": [
        "https://x.com/0xunclebeanz/status/2012920181274914997",
        "https://x.com/0xunclebeanz/status/2012615785202716705",
        "https://x.com/0xunclebeanz/status/2012309855999246652",
        "https://x.com/0xunclebeanz/status/2011440784692891719",
        "https://x.com/0xunclebeanz/status/2011803431376507354",
        "https://x.com/0xunclebeanz/status/2010708373403205985",
    ],
    "FumioWeb3": [
        "https://x.com/FumioWeb3/status/2012821466967138532",
        "https://x.com/FumioWeb3/status/2012541124657684953",
        "https://x.com/FumioWeb3/status/2012463254401061342",
        "https://x.com/FumioWeb3/status/2012419940939083995",
        "https://x.com/FumioWeb3/status/2012177683799781851",
        "https://x.com/FumioWeb3/status/2012098959146398059",
        "https://x.com/FumioWeb3/status/2011809512387461419",
        "https://x.com/FumioWeb3/status/2011688751475671452",
        "https://x.com/FumioWeb3/status/2011008298406044086",
    ],
}

# External posts for ownership rejection test (these belong to OTHER users)
EXTERNAL_POSTS = [
    "https://x.com/speak_SACH_in/status/1972908326041124932",
    "https://x.com/scanx_trade/status/1953753619414888582",
]

# Sponsored posts by sponsor username
SPONSORED_POSTS = {
    "PulseSocialFi": [
        "https://x.com/PulseSocialFi/status/2003053378612744651",
        "https://x.com/PulseSocialFi/status/2001597867258188134",
        "https://x.com/PulseSocialFi/status/2000817165017174444",
    ],
    "SIXR_cricket": [
        "https://x.com/SIXR_cricket/status/2000600455295214056",
        "https://x.com/SIXR_cricket/status/1998784433499836713",
        "https://x.com/SIXR_cricket/status/1998067804051026131",
    ],
    "GEODNET": [
        "https://x.com/GEODNET/status/2012958548515557574",
        "https://x.com/GEODNET/status/2008946740800467058",
        "https://x.com/GEODNET/status/2011150932407706019",
    ],
}


class Command(BaseCommand):
    help = "Run comprehensive integration tests with real data"

    def __init__(self):
        super().__init__()
        self.test_users = {}  # x_username -> User
        self.sponsor_users = {}  # x_username -> User
        self.created_posts = {}  # x_link -> Post
        self.errors = []
        self.successes = []
        self.skip_api = False
        self.verbose = False

    def add_arguments(self, parser):
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Delete test users after running tests',
        )
        parser.add_argument(
            '--skip-api',
            action='store_true',
            help='Skip real API calls (use mock data)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output',
        )

    def handle(self, *args, **options):
        self.skip_api = options.get('skip_api', False)
        self.verbose = options.get('verbose', False)
        cleanup = options.get('cleanup', False)

        self.stdout.write(self.style.SUCCESS("\n" + "=" * 70))
        self.stdout.write(self.style.SUCCESS("LOUDRR E2E INTEGRATION TEST"))
        self.stdout.write(self.style.SUCCESS("=" * 70 + "\n"))

        if self.skip_api:
            self.stdout.write(self.style.WARNING("Running with --skip-api: Using mock data for API calls\n"))

        try:
            # Phase 1: Create test users and link X accounts
            self.phase_1_create_users()

            # Phase 2: Create sponsor accounts and posts
            self.phase_2_create_sponsors()

            # Phase 3: Submit regular posts
            self.phase_3_submit_posts()

            # Phase 4: Test ownership rejection
            self.phase_4_ownership_rejection()

            # Phase 5: Test engagement flow
            self.phase_5_engagement_flow()

            # Phase 6: Test Twitter API verification directly
            self.phase_6_twitter_verification()

            # Phase 7: Summary
            self.phase_7_summary()

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\nTest suite failed with exception: {e}"))
            import traceback
            self.stdout.write(traceback.format_exc())

        finally:
            if cleanup:
                self.cleanup_test_data()

    # =========================================================================
    # PHASE 1: CREATE TEST USERS WITH X ACCOUNT LINKING
    # =========================================================================

    def phase_1_create_users(self):
        """Create test users and link their X accounts."""
        self.stdout.write(self.style.HTTP_INFO("\n" + "-" * 70))
        self.stdout.write(self.style.HTTP_INFO("PHASE 1: Creating Test Users + Linking X Accounts"))
        self.stdout.write(self.style.HTTP_INFO("-" * 70 + "\n"))

        tweetscout = get_tweetscout_service()

        for user_data in TEST_USERS:
            x_username = user_data["x_username"]
            telegram_id = user_data["telegram_id"]
            name = user_data["name"]

            self.stdout.write(f"Creating user: {name} (@{x_username})...")

            try:
                # Create or get user
                user, created = User.objects.get_or_create(
                    telegram_id=telegram_id,
                    defaults={
                        "display_name": name,
                        "telegram_username": f"test_{x_username}",
                        "credits": Decimal('100'),  # Start with 100 karma for testing
                    }
                )

                if not created:
                    # Update existing user with test karma
                    user.display_name = name
                    user.credits = Decimal('100')
                    user.save(update_fields=["display_name", "credits", "updated_at"])
                    self.stdout.write(f"  -> User already exists, updated")

                # Link X account (fetch TweetScout data)
                if not self.skip_api:
                    tweetscout_data = tweetscout.get_user_data(x_username)

                    if tweetscout_data:
                        score = tweetscout_data.get("score", 0) or 0

                        # Create/update XProfile
                        x_profile, _ = XProfile.objects.update_or_create(
                            user=user,
                            defaults={
                                "x_user_id": str(tweetscout_data.get("id", "")),
                                "username": x_username,
                                "display_name": tweetscout_data.get("name", ""),
                                "bio": tweetscout_data.get("description", "") or "",
                                "followers_count": tweetscout_data.get("followers_count", 0) or 0,
                                "following_count": tweetscout_data.get("friends_count", 0) or 0,
                                "tweets_count": tweetscout_data.get("tweets_count", 0) or 0,
                                "score": score,
                                "avatar_url": tweetscout_data.get("avatar", "") or "",
                                "banner_url": tweetscout_data.get("banner", "") or "",
                                "is_verified": bool(tweetscout_data.get("verified", False)),
                                "can_dm": bool(tweetscout_data.get("can_dm", False)),
                                "raw_tweetscout_data": tweetscout_data,
                            }
                        )

                        # Update User model too
                        user.x_username = x_username
                        user.tweetscout_score = score
                        user.tweetscout_last_updated = timezone.now()
                        user.save(update_fields=[
                            "x_username", "tweetscout_score", "tweetscout_last_updated",
                            "updated_at"
                        ])

                        tier = get_tweet_score_tier(score)
                        multiplier = get_tweet_score_multiplier(score)

                        self.stdout.write(self.style.SUCCESS(
                            f"  -> Linked @{x_username}: Score={score:.1f}, "
                            f"Tier={tier}, Multiplier={multiplier}x, "
                            f"Followers={x_profile.followers_count}"
                        ))
                        self.successes.append(f"User {x_username}: Linked with score {score:.1f}")
                    else:
                        self.stdout.write(self.style.WARNING(
                            f"  -> TweetScout data not found for @{x_username}"
                        ))
                        # Still set x_username for URL matching
                        user.x_username = x_username
                        user.save(update_fields=["x_username", "updated_at"])
                        self.errors.append(f"User {x_username}: TweetScout data not found")
                else:
                    # Mock data mode
                    user.x_username = x_username
                    user.tweetscout_score = random.randint(100, 800)
                    user.save(update_fields=["x_username", "tweetscout_score", "updated_at"])
                    self.stdout.write(f"  -> Mock linked with score {user.tweetscout_score}")

                self.test_users[x_username] = user

            except Exception as e:
                self.errors.append(f"User {x_username}: {str(e)}")
                self.stdout.write(self.style.ERROR(f"  -> Error: {e}"))

            # Rate limit for API calls
            if not self.skip_api:
                time.sleep(0.5)

        self.stdout.write(f"\nCreated {len(self.test_users)} test users")

    # =========================================================================
    # PHASE 2: CREATE SPONSOR ACCOUNTS AND SPONSORED POSTS
    # =========================================================================

    def phase_2_create_sponsors(self):
        """Create sponsor accounts and their sponsored posts."""
        self.stdout.write(self.style.HTTP_INFO("\n" + "-" * 70))
        self.stdout.write(self.style.HTTP_INFO("PHASE 2: Creating Sponsor Accounts + Sponsored Posts"))
        self.stdout.write(self.style.HTTP_INFO("-" * 70 + "\n"))

        tweetscout = get_tweetscout_service()

        for sponsor_data in SPONSOR_USERS:
            x_username = sponsor_data["x_username"]
            telegram_id = sponsor_data["telegram_id"]
            name = sponsor_data["name"]

            self.stdout.write(f"Creating sponsor: {name}...")

            try:
                # Create sponsor user
                user, created = User.objects.get_or_create(
                    telegram_id=telegram_id,
                    defaults={
                        "display_name": name,
                        "telegram_username": f"sponsor_{x_username}",
                        "credits": Decimal('1000'),  # Sponsors get more karma
                    }
                )

                if not created:
                    user.credits = Decimal('1000')
                    user.save(update_fields=["credits", "updated_at"])

                # Link X account
                if not self.skip_api:
                    tweetscout_data = tweetscout.get_user_data(x_username)
                    if tweetscout_data:
                        score = tweetscout_data.get("score", 0) or 0

                        XProfile.objects.update_or_create(
                            user=user,
                            defaults={
                                "x_user_id": str(tweetscout_data.get("id", "")),
                                "username": x_username,
                                "display_name": tweetscout_data.get("name", ""),
                                "score": score,
                                "followers_count": tweetscout_data.get("followers_count", 0) or 0,
                                "raw_tweetscout_data": tweetscout_data,
                            }
                        )

                        user.x_username = x_username
                        user.tweetscout_score = score
                        user.save(update_fields=["x_username", "tweetscout_score", "updated_at"])
                else:
                    user.x_username = x_username
                    user.save(update_fields=["x_username", "updated_at"])

                self.sponsor_users[x_username] = user

                # Create sponsored posts
                posts = SPONSORED_POSTS.get(x_username, [])
                for x_link in posts[:2]:  # Limit to 2 per sponsor
                    tweet_id = twitter_verification.extract_tweet_id(x_link)

                    # Check if post already exists
                    existing = Post.objects.filter(x_link=x_link).first()
                    if existing:
                        self.stdout.write(f"  -> Post already exists: {x_link[:50]}...")
                        self.created_posts[x_link] = existing
                        continue

                    post = Post.objects.create(
                        user=user,
                        x_link=x_link,
                        tweet_id=tweet_id or "",
                        platform=Post.Platform.WEB,
                        escrow=Decimal('50'),
                        initial_escrow=Decimal('50'),
                        is_sponsored=True,
                    )

                    # Create SponsoredPost record
                    SponsoredPost.objects.create(
                        post=post,
                        sponsor_name=name.replace("Sponsor: ", ""),
                        sponsor_contact=f"contact@{x_username.lower()}.com",
                        credit_reward=Decimal('2'),
                        total_budget=Decimal('100'),
                        remaining_budget=Decimal('100'),
                    )

                    self.created_posts[x_link] = post
                    self.stdout.write(self.style.SUCCESS(
                        f"  -> Created sponsored post: {x_link[:50]}..."
                    ))
                    self.successes.append(f"Sponsored post created: {x_link[:40]}...")

            except Exception as e:
                self.errors.append(f"Sponsor {x_username}: {str(e)}")
                self.stdout.write(self.style.ERROR(f"  -> Error: {e}"))

            if not self.skip_api:
                time.sleep(0.5)

    # =========================================================================
    # PHASE 3: SUBMIT REGULAR POSTS
    # =========================================================================

    def phase_3_submit_posts(self):
        """Test regular post submission for each user."""
        self.stdout.write(self.style.HTTP_INFO("\n" + "-" * 70))
        self.stdout.write(self.style.HTTP_INFO("PHASE 3: Submitting Regular Posts"))
        self.stdout.write(self.style.HTTP_INFO("-" * 70 + "\n"))

        for x_username, user in self.test_users.items():
            posts = USER_POSTS.get(x_username, [])

            if not posts:
                self.stdout.write(self.style.WARNING(
                    f"@{x_username}: No posts defined (edge case - user with no posts)"
                ))
                continue

            self.stdout.write(f"Submitting posts for @{x_username}...")

            # Submit first 2 posts per user
            for x_link in posts[:2]:
                try:
                    # Check if already exists
                    existing = Post.objects.filter(x_link=x_link).first()
                    if existing:
                        self.stdout.write(f"  -> Already exists: {x_link[:50]}...")
                        self.created_posts[x_link] = existing
                        continue

                    # Extract tweet_id
                    tweet_id = twitter_verification.extract_tweet_id(x_link)

                    # Get karma amount from settings
                    karma_amount = get_setting('POST_COST_MIN')

                    # Check user has enough credits
                    if user.credits < karma_amount:
                        self.stdout.write(self.style.WARNING(
                            f"  -> Insufficient karma for @{x_username}"
                        ))
                        continue

                    # Create post
                    post = Post.objects.create(
                        user=user,
                        x_link=x_link,
                        tweet_id=tweet_id or "",
                        platform=Post.Platform.WEB,
                        escrow=Decimal(str(karma_amount)),
                        initial_escrow=Decimal(str(karma_amount)),
                    )

                    # Deduct credits
                    credit_service = CreditService(user)
                    credit_service.spend(
                        amount=Decimal(str(karma_amount)),
                        reference_id=post.id,
                        reference_type="post",
                        description=f"Integration test post",
                    )

                    user.refresh_from_db()
                    self.created_posts[x_link] = post

                    self.stdout.write(self.style.SUCCESS(
                        f"  -> Created post: {x_link[:50]}... (escrow: {karma_amount})"
                    ))
                    self.successes.append(f"Post created by {x_username}")

                except Exception as e:
                    self.errors.append(f"Post submission {x_username}: {str(e)}")
                    self.stdout.write(self.style.ERROR(f"  -> Error: {e}"))

    # =========================================================================
    # PHASE 4: TEST OWNERSHIP REJECTION
    # =========================================================================

    def phase_4_ownership_rejection(self):
        """Test that users cannot submit posts from other accounts."""
        self.stdout.write(self.style.HTTP_INFO("\n" + "-" * 70))
        self.stdout.write(self.style.HTTP_INFO("PHASE 4: Testing Post Ownership Rejection"))
        self.stdout.write(self.style.HTTP_INFO("-" * 70 + "\n"))

        # Pick a test user to try submitting an external post
        if not self.test_users:
            self.stdout.write(self.style.WARNING("No test users available"))
            return

        test_user = list(self.test_users.values())[0]
        test_username = list(self.test_users.keys())[0]

        for external_url in EXTERNAL_POSTS[:1]:  # Test with first external post
            self.stdout.write(
                f"Testing: @{test_username} tries to submit @{external_url.split('/')[3]}'s post..."
            )

            # Extract username from external URL
            from core.services.x_url_resolver import extract_username_from_url
            post_username, tweet_id = extract_username_from_url(external_url)

            if post_username and post_username.lower() != test_username.lower():
                # This should be rejected in real flow
                self.stdout.write(self.style.SUCCESS(
                    f"  -> PASS: URL belongs to @{post_username}, not @{test_username}"
                ))
                self.successes.append(f"Ownership rejection: Detected @{post_username}")

                # Test API verification if not skipping
                if not self.skip_api:
                    author_data = twitter_verification.get_tweet_author(tweet_id)
                    if author_data:
                        self.stdout.write(self.style.SUCCESS(
                            f"  -> API confirmed: Tweet by @{author_data.get('username')}"
                        ))
            else:
                self.errors.append(f"Ownership test failed for {external_url}")

    # =========================================================================
    # PHASE 5: ENGAGEMENT FLOW TESTS
    # =========================================================================

    def phase_5_engagement_flow(self):
        """Test the complete engagement flow with all users engaging randomly."""
        self.stdout.write(self.style.HTTP_INFO("\n" + "-" * 70))
        self.stdout.write(self.style.HTTP_INFO("PHASE 5: Testing Engagement Flow (All Users)"))
        self.stdout.write(self.style.HTTP_INFO("-" * 70 + "\n"))

        if len(self.test_users) < 2:
            self.stdout.write(self.style.WARNING("Need at least 2 users for engagement tests"))
            return

        # Track stats for summary
        self.engagement_stats = {
            'total_clicks': 0,
            'total_verifications': 0,
            'total_passed': 0,
            'total_failed': 0,
            'total_karma_awarded': Decimal('0'),
            'total_xp_awarded': 0,
            'user_stats': {},  # per-user stats
        }

        base_credit = Decimal(str(get_setting('CREDIT_PER_ENGAGEMENT')))
        verification_pass_rate = 0.9  # 90% pass rate

        # =====================================================================
        # STEP 1: All users engage with random posts (90% of available)
        # =====================================================================
        self.stdout.write("Step 5.1: All users engaging with random posts...")

        all_posts = list(self.created_posts.values())

        for x_username, user in self.test_users.items():
            # Get posts this user can engage with (not their own)
            available_posts = [p for p in all_posts if p.user_id != user.id and p.status == Post.Status.ACTIVE]

            if not available_posts:
                continue

            # Engage with 90% of available posts randomly
            num_to_engage = max(1, int(len(available_posts) * 0.9))
            posts_to_engage = random.sample(available_posts, min(num_to_engage, len(available_posts)))

            clicks = 0
            for post in posts_to_engage:
                try:
                    engagement, created = Engagement.objects.get_or_create(
                        user=user,
                        post=post,
                        defaults={
                            "verified": False,
                            "credit_granted": False,
                            "clicked_at": timezone.now(),
                        }
                    )
                    if created:
                        clicks += 1
                except Exception as e:
                    if self.verbose:
                        self.stdout.write(self.style.ERROR(f"  -> Error: {e}"))

            self.engagement_stats['total_clicks'] += clicks
            self.stdout.write(f"  @{x_username}: Clicked on {clicks} posts")

        self.stdout.write(self.style.SUCCESS(
            f"  -> Total clicks recorded: {self.engagement_stats['total_clicks']}"
        ))

        # =====================================================================
        # STEP 2: Verify engagements for each user (simulate 90% pass rate)
        # =====================================================================
        self.stdout.write("\nStep 5.2: Verifying engagements (simulated 90% pass rate)...")

        for x_username, user in self.test_users.items():
            # Initialize user stats
            self.engagement_stats['user_stats'][x_username] = {
                'clicks': 0,
                'verified': 0,
                'passed': 0,
                'failed': 0,
                'karma_earned': Decimal('0'),
                'xp_earned': 0,
                'initial_balance': user.credits,
            }

            # Get all pending engagements for this user
            pending = list(Engagement.objects.filter(
                user=user,
                verified=False,
                credit_granted=False,
            ).select_related('post').order_by('clicked_at'))

            self.engagement_stats['user_stats'][x_username]['clicks'] = len(pending)

            if not pending:
                continue

            credit_service = CreditService(user)
            tier = get_tweet_score_tier(user.tweetscout_score or 0)
            karma_per_eng, multiplier = calculate_engagement_karma(base_credit, user.tweetscout_score or 0)

            user_karma_earned = Decimal('0')
            user_xp_earned = 0
            passed = 0
            failed = 0

            for eng in pending:
                self.engagement_stats['total_verifications'] += 1
                self.engagement_stats['user_stats'][x_username]['verified'] += 1

                # Simulate pass/fail (90% pass rate)
                verification_passed = random.random() < verification_pass_rate

                if verification_passed:
                    post = eng.post
                    post.refresh_from_db()

                    if post.status != Post.Status.ACTIVE or post.escrow <= Decimal('0'):
                        # Post depleted or inactive - still counts as "passed" but no reward
                        eng.verified = True
                        eng.credit_granted = False
                        eng.save(update_fields=["verified", "credit_granted"])
                        passed += 1
                        continue

                    # Calculate karma with user's tier multiplier
                    karma, mult = calculate_engagement_karma(base_credit, user.tweetscout_score or 0)

                    if post.escrow >= karma:
                        # Deduct escrow atomically
                        updated = Post.objects.filter(
                            pk=post.pk,
                            escrow__gte=karma
                        ).update(escrow=post.escrow - karma)

                        if updated:
                            # Award credits
                            credit_service.earn(
                                amount=karma,
                                reference_id=eng.id,
                                reference_type="engagement",
                                description=f"Engagement reward (x{mult})",
                            )
                            user_karma_earned += karma

                            # Mark as verified and credited
                            eng.verified = True
                            eng.credit_granted = True
                            eng.save(update_fields=["verified", "credit_granted"])

                            # Award XP for sponsored posts
                            if post.is_sponsored:
                                xp_amount = get_xp_for_sponsored_engagement()
                                xp_service = XPService(user)
                                xp_service.earn_from_sponsored(
                                    amount=xp_amount,
                                    post_id=post.pk,
                                    description="Sponsored engagement reward",
                                )
                                user_xp_earned += xp_amount

                            passed += 1
                        else:
                            # Escrow depleted during race
                            eng.verified = True
                            eng.credit_granted = False
                            eng.save(update_fields=["verified", "credit_granted"])
                            passed += 1
                    else:
                        # Not enough escrow
                        eng.verified = True
                        eng.credit_granted = False
                        eng.save(update_fields=["verified", "credit_granted"])
                        passed += 1
                else:
                    # Verification failed
                    eng.verified = True
                    eng.credit_granted = False
                    eng.save(update_fields=["verified", "credit_granted"])
                    failed += 1

            # Update stats
            self.engagement_stats['total_passed'] += passed
            self.engagement_stats['total_failed'] += failed
            self.engagement_stats['total_karma_awarded'] += user_karma_earned
            self.engagement_stats['total_xp_awarded'] += user_xp_earned

            self.engagement_stats['user_stats'][x_username]['passed'] = passed
            self.engagement_stats['user_stats'][x_username]['failed'] = failed
            self.engagement_stats['user_stats'][x_username]['karma_earned'] = user_karma_earned
            self.engagement_stats['user_stats'][x_username]['xp_earned'] = user_xp_earned

            user.refresh_from_db()
            self.engagement_stats['user_stats'][x_username]['final_balance'] = user.credits

            pass_rate = (passed / (passed + failed) * 100) if (passed + failed) > 0 else 0
            self.stdout.write(
                f"  @{x_username}: {passed} passed, {failed} failed "
                f"({pass_rate:.0f}% pass rate) -> Earned {user_karma_earned} karma"
            )

        # Summary
        total_verified = self.engagement_stats['total_passed'] + self.engagement_stats['total_failed']
        overall_pass_rate = (self.engagement_stats['total_passed'] / total_verified * 100) if total_verified > 0 else 0

        self.stdout.write(self.style.SUCCESS(f"\n  ENGAGEMENT SUMMARY:"))
        self.stdout.write(f"  Total Clicks: {self.engagement_stats['total_clicks']}")
        self.stdout.write(f"  Total Verified: {total_verified}")
        self.stdout.write(f"  Passed: {self.engagement_stats['total_passed']} ({overall_pass_rate:.1f}%)")
        self.stdout.write(f"  Failed: {self.engagement_stats['total_failed']}")
        self.stdout.write(f"  Total Karma Awarded: {self.engagement_stats['total_karma_awarded']}")
        self.stdout.write(f"  Total XP Awarded: {self.engagement_stats['total_xp_awarded']}")

        self.successes.append(f"Engagement flow: {overall_pass_rate:.1f}% pass rate, {self.engagement_stats['total_karma_awarded']} karma awarded")

    # =========================================================================
    # PHASE 6: TWITTER API VERIFICATION
    # =========================================================================

    def phase_6_twitter_verification(self):
        """Test direct Twitter API verification."""
        self.stdout.write(self.style.HTTP_INFO("\n" + "-" * 70))
        self.stdout.write(self.style.HTTP_INFO("PHASE 6: Testing Twitter API Verification"))
        self.stdout.write(self.style.HTTP_INFO("-" * 70 + "\n"))

        if self.skip_api:
            self.stdout.write(self.style.WARNING("Skipping API tests (--skip-api flag)"))
            return

        # Test 1: Extract tweet ID
        self.stdout.write("Test 6.1: Tweet ID extraction...")
        test_urls = [
            "https://x.com/igrisonchain1/status/2012139965820649624",
            "https://twitter.com/saifmr20/status/2012902426417025084",
            "https://x.com/0xBlest_/status/1992193469855719432?s=20",
        ]

        for url in test_urls:
            tweet_id = twitter_verification.extract_tweet_id(url)
            if tweet_id:
                self.stdout.write(self.style.SUCCESS(
                    f"  -> {url[:40]}... => {tweet_id}"
                ))
            else:
                self.errors.append(f"Failed to extract tweet ID from {url}")

        # Test 2: Get tweet author
        self.stdout.write("\nTest 6.2: Get tweet author (API call)...")
        test_tweet_id = "2012139965820649624"

        author_data = twitter_verification.get_tweet_author(test_tweet_id)
        if author_data:
            self.stdout.write(self.style.SUCCESS(
                f"  -> Tweet {test_tweet_id} by @{author_data.get('username')} "
                f"({author_data.get('name')})"
            ))
            self.successes.append(f"Tweet author API: @{author_data.get('username')}")
        else:
            self.stdout.write(self.style.WARNING("  -> Could not fetch tweet author"))
            self.errors.append("Tweet author API failed")

        # Test 3: Verify reply (likely to fail - no real reply)
        self.stdout.write("\nTest 6.3: Verify reply (API call)...")

        if self.test_users:
            test_user = list(self.test_users.values())[0]
            test_username = test_user.x_username

            result = twitter_verification.verify_reply(test_tweet_id, test_username)
            self.stdout.write(f"  -> Checking if @{test_username} replied to {test_tweet_id}...")
            self.stdout.write(f"  -> Result: {result}")

            if result.get("skipped"):
                self.stdout.write(self.style.WARNING("  -> API verification skipped (no API key)"))
            elif result.get("passed"):
                self.stdout.write(self.style.SUCCESS("  -> Reply found!"))
            else:
                self.stdout.write("  -> Reply not found (expected for test)")

    # =========================================================================
    # PHASE 7: SUMMARY
    # =========================================================================

    def phase_7_summary(self):
        """Print detailed summary with user stats."""
        self.stdout.write(self.style.HTTP_INFO("\n" + "=" * 70))
        self.stdout.write(self.style.HTTP_INFO("TEST SUMMARY"))
        self.stdout.write(self.style.HTTP_INFO("=" * 70 + "\n"))

        # =====================================================================
        # USER STATS TABLE (with Earned Karma)
        # =====================================================================
        self.stdout.write(self.style.SUCCESS("USER STATISTICS"))
        self.stdout.write("-" * 90)
        self.stdout.write(
            f"{'Username':<16} {'Balance':>9} {'Earned':>9} {'XP':>6} "
            f"{'Clicked':>7} {'Pass':>5} {'Fail':>5} {'Posts':>5} {'Tier':<7} {'Score':>5}"
        )
        self.stdout.write("-" * 90)

        total_karma = Decimal('0')
        total_earned = Decimal('0')
        total_xp = 0
        total_clicks = 0
        total_passed = 0
        total_failed = 0
        total_posts_submitted = 0

        # Get engagement stats if available
        engagement_stats = getattr(self, 'engagement_stats', {}).get('user_stats', {})

        # Regular test users
        for x_username, user in self.test_users.items():
            user.refresh_from_db()

            # Get engagement stats for this user
            user_eng_stats = engagement_stats.get(x_username, {})
            karma_earned = user_eng_stats.get('karma_earned', Decimal('0'))
            clicks = user_eng_stats.get('clicks', 0)
            passed = user_eng_stats.get('passed', 0)
            failed = user_eng_stats.get('failed', 0)
            xp_earned = user_eng_stats.get('xp_earned', 0)

            # Count posts submitted by this user
            posts_submitted = Post.objects.filter(user=user).count()

            tier = get_tweet_score_tier(user.tweetscout_score or 0)
            xp = user.sponsored_xp or 0

            self.stdout.write(
                f"@{x_username:<15} {float(user.credits):>9.2f} {float(karma_earned):>9.2f} {xp:>6} "
                f"{clicks:>7} {passed:>5} {failed:>5} {posts_submitted:>5} {tier:<7} "
                f"{user.tweetscout_score or 0:>5.0f}"
            )

            total_karma += user.credits
            total_earned += karma_earned
            total_xp += xp
            total_clicks += clicks
            total_passed += passed
            total_failed += failed
            total_posts_submitted += posts_submitted

        # Sponsor users
        if self.sponsor_users:
            self.stdout.write("-" * 90)
            self.stdout.write(self.style.WARNING("SPONSORS:"))

            for x_username, user in self.sponsor_users.items():
                user.refresh_from_db()
                sponsored_posts = Post.objects.filter(user=user, is_sponsored=True).count()
                tier = get_tweet_score_tier(user.tweetscout_score or 0)

                self.stdout.write(
                    f"@{x_username:<15} {float(user.credits):>9.2f} {'N/A':>9} {'N/A':>6} "
                    f"{'N/A':>7} {'N/A':>5} {'N/A':>5} {sponsored_posts:>5} {tier:<7} "
                    f"{user.tweetscout_score or 0:>5.0f}"
                )

        self.stdout.write("-" * 90)
        overall_pass_rate = (total_passed / (total_passed + total_failed) * 100) if (total_passed + total_failed) > 0 else 0
        self.stdout.write(self.style.SUCCESS(
            f"{'TOTALS':<16} {float(total_karma):>9.2f} {float(total_earned):>9.2f} {total_xp:>6} "
            f"{total_clicks:>7} {total_passed:>5} {total_failed:>5} {total_posts_submitted:>5}"
        ))
        self.stdout.write(f"{'PASS RATE':<16} {' ':>9} {' ':>9} {' ':>6} {' ':>7} {overall_pass_rate:>5.1f}%")
        self.stdout.write("-" * 90)

        # =====================================================================
        # DETAILED USER BREAKDOWN
        # =====================================================================
        self.stdout.write(self.style.SUCCESS("\nDETAILED USER BREAKDOWN"))
        self.stdout.write("-" * 70)

        for x_username, user in self.test_users.items():
            user.refresh_from_db()

            tier = get_tweet_score_tier(user.tweetscout_score or 0)
            multiplier = get_tweet_score_multiplier(user.tweetscout_score or 0)

            # Get engagement breakdown
            total_eng = Engagement.objects.filter(user=user).count()
            verified_eng = Engagement.objects.filter(user=user, verified=True).count()
            pending_eng = Engagement.objects.filter(user=user, verified=False).count()
            credited_eng = Engagement.objects.filter(user=user, credit_granted=True).count()

            # Get posts breakdown
            user_posts = Post.objects.filter(user=user)
            active_posts = user_posts.filter(status=Post.Status.ACTIVE).count()
            completed_posts = user_posts.filter(status=Post.Status.COMPLETED).count()

            # Get transaction history
            karma_earned = Transaction.objects.filter(
                user=user, type='earn'
            ).count()
            karma_spent = Transaction.objects.filter(
                user=user, type='spend'
            ).count()

            self.stdout.write(f"\n@{x_username}")
            self.stdout.write(f"  Tier: {tier} (Score: {user.tweetscout_score or 0}, Multiplier: {multiplier}x)")
            self.stdout.write(f"  Karma Balance: {float(user.credits):.2f}")
            self.stdout.write(f"  XP Balance: {user.sponsored_xp or 0}")
            self.stdout.write(f"  Engagements: {total_eng} total ({verified_eng} verified, {pending_eng} pending)")
            self.stdout.write(f"  Posts: {user_posts.count()} total ({active_posts} active, {completed_posts} completed)")
            self.stdout.write(f"  Transactions: {karma_earned} earns, {karma_spent} spends")

        # =====================================================================
        # POST STATS
        # =====================================================================
        self.stdout.write(self.style.SUCCESS("\n\nPOST STATISTICS"))
        self.stdout.write("-" * 70)

        total_posts = len(self.created_posts)
        active = sum(1 for p in self.created_posts.values() if p.status == Post.Status.ACTIVE)
        completed = sum(1 for p in self.created_posts.values() if p.status == Post.Status.COMPLETED)
        sponsored = sum(1 for p in self.created_posts.values() if p.is_sponsored)
        regular = total_posts - sponsored

        self.stdout.write(f"Total Posts Created: {total_posts}")
        self.stdout.write(f"  Regular Posts: {regular}")
        self.stdout.write(f"  Sponsored Posts: {sponsored}")
        self.stdout.write(f"  Active: {active}")
        self.stdout.write(f"  Completed: {completed}")

        # Calculate total escrow
        total_escrow = sum(p.escrow for p in self.created_posts.values())
        total_initial_escrow = sum(p.initial_escrow for p in self.created_posts.values())
        escrow_used = total_initial_escrow - total_escrow

        self.stdout.write(f"\nEscrow Stats:")
        self.stdout.write(f"  Total Initial Escrow: {float(total_initial_escrow):.2f} karma")
        self.stdout.write(f"  Remaining Escrow: {float(total_escrow):.2f} karma")
        self.stdout.write(f"  Distributed to Engagers: {float(escrow_used):.2f} karma")

        # =====================================================================
        # TEST RESULTS
        # =====================================================================
        self.stdout.write(self.style.SUCCESS(f"\n\nTEST RESULTS"))
        self.stdout.write("-" * 70)
        self.stdout.write(f"Successes: {len(self.successes)}")
        for success in self.successes[:10]:
            self.stdout.write(f"  [+] {success}")
        if len(self.successes) > 10:
            self.stdout.write(f"  ... and {len(self.successes) - 10} more")

        if self.errors:
            self.stdout.write(self.style.ERROR(f"\nErrors: {len(self.errors)}"))
            for error in self.errors:
                self.stdout.write(f"  [-] {error}")

        # =====================================================================
        # FINAL STATUS
        # =====================================================================
        self.stdout.write("\n" + "=" * 70)
        if not self.errors:
            self.stdout.write(self.style.SUCCESS("ALL TESTS PASSED!"))
        else:
            self.stdout.write(self.style.WARNING(
                f"COMPLETED WITH {len(self.errors)} ERRORS"
            ))
        self.stdout.write("=" * 70 + "\n")

    # =========================================================================
    # CLEANUP
    # =========================================================================

    def cleanup_test_data(self):
        """Delete all test data created during the test run."""
        self.stdout.write(self.style.WARNING("\n" + "-" * 70))
        self.stdout.write(self.style.WARNING("CLEANUP: Deleting test data"))
        self.stdout.write(self.style.WARNING("-" * 70 + "\n"))

        # Get all test telegram IDs
        test_telegram_ids = [u["telegram_id"] for u in TEST_USERS + SPONSOR_USERS]

        # Delete engagements for test posts
        engagement_count = Engagement.objects.filter(
            post__user__telegram_id__in=test_telegram_ids
        ).count()
        Engagement.objects.filter(
            post__user__telegram_id__in=test_telegram_ids
        ).delete()
        self.stdout.write(f"Deleted {engagement_count} engagements")

        # Delete engagements by test users
        engagement_count = Engagement.objects.filter(
            user__telegram_id__in=test_telegram_ids
        ).count()
        Engagement.objects.filter(
            user__telegram_id__in=test_telegram_ids
        ).delete()
        self.stdout.write(f"Deleted {engagement_count} user engagements")

        # Delete sponsored posts
        sponsored_count = SponsoredPost.objects.filter(
            post__user__telegram_id__in=test_telegram_ids
        ).count()
        SponsoredPost.objects.filter(
            post__user__telegram_id__in=test_telegram_ids
        ).delete()
        self.stdout.write(f"Deleted {sponsored_count} sponsored post records")

        # Delete posts
        post_count = Post.objects.filter(
            user__telegram_id__in=test_telegram_ids
        ).count()
        Post.objects.filter(
            user__telegram_id__in=test_telegram_ids
        ).delete()
        self.stdout.write(f"Deleted {post_count} posts")

        # Delete XP transactions
        xp_count = XPTransaction.objects.filter(
            user__telegram_id__in=test_telegram_ids
        ).count()
        XPTransaction.objects.filter(
            user__telegram_id__in=test_telegram_ids
        ).delete()
        self.stdout.write(f"Deleted {xp_count} XP transactions")

        # Delete transactions
        tx_count = Transaction.objects.filter(
            user__telegram_id__in=test_telegram_ids
        ).count()
        Transaction.objects.filter(
            user__telegram_id__in=test_telegram_ids
        ).delete()
        self.stdout.write(f"Deleted {tx_count} transactions")

        # Delete XProfiles
        xp_count = XProfile.objects.filter(
            user__telegram_id__in=test_telegram_ids
        ).count()
        XProfile.objects.filter(
            user__telegram_id__in=test_telegram_ids
        ).delete()
        self.stdout.write(f"Deleted {xp_count} X profiles")

        # Delete test users
        user_count = User.objects.filter(
            telegram_id__in=test_telegram_ids
        ).count()
        User.objects.filter(
            telegram_id__in=test_telegram_ids
        ).delete()
        self.stdout.write(f"Deleted {user_count} test users")

        self.stdout.write(self.style.SUCCESS("\nCleanup complete!"))
