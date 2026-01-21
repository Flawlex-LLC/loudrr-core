"""
Seed posts using the actual submission business logic.

Creates users with proper XProfile (x_user_id from TweetScout),
then submits posts using get_tweet_content() - ownership validation passes
because tweet author matches user's stored x_user_id.

Run with: python manage.py seed_posts
"""
import time
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime

from core.models import User, XProfile
from core.services.tweetscout import get_tweetscout_service
from core.services.tweet_score import get_tweet_score_tier
from core.services.twitter_verification import twitter_verification
from core.services.settings import get_setting
from posts.models import Post, Engagement, SponsoredPost


# Test users with fake telegram IDs (NOT blest - blest uses real account)
TEST_USERS = {
    "igrisonchain1": {"telegram_id": 9000001, "name": "Test - igrisonchain1"},
    "saifmr20": {"telegram_id": 9000002, "name": "Test - saifmr20"},
    "0xunclebeanz": {"telegram_id": 9000003, "name": "Test - 0xunclebeanz"},
    "FumioWeb3": {"telegram_id": 9000004, "name": "Test - FumioWeb3"},
    "speak_SACH_in": {"telegram_id": 9000005, "name": "Test - speak_SACH_in"},
    "scanx_trade": {"telegram_id": 9000006, "name": "Test - scanx_trade"},
}

# All posts from user's list (deduplicated)
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
    "speak_SACH_in": [
        "https://x.com/speak_SACH_in/status/1972908326041124932",
    ],
    "0xunclebeanz": [
        "https://x.com/0xunclebeanz/status/2012920181274914997",
        "https://x.com/0xunclebeanz/status/2012615785202716705",
        "https://x.com/0xunclebeanz/status/2012309855999246652",
        "https://x.com/0xunclebeanz/status/2011440784692891719",
        "https://x.com/0xunclebeanz/status/2011803431376507354",
        "https://x.com/0xunclebeanz/status/2010708373403205985",
    ],
    "scanx_trade": [
        "https://x.com/scanx_trade/status/1953753619414888582",
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


class Command(BaseCommand):
    help = "Seed posts using actual submission business logic"

    def __init__(self):
        super().__init__()
        self.users = {}  # x_username -> User
        self.created_posts = []

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
        self.stdout.write(self.style.SUCCESS("SEED POSTS (Using Actual Business Logic)"))
        self.stdout.write(self.style.SUCCESS("=" * 60 + "\n"))

        # Step 1: Clear existing data
        self.clear_data()

        # Step 2: Create users with proper XProfile
        self.create_users()

        # Step 3: Submit posts using actual flow
        self.submit_posts()

        # Summary
        self.print_summary()

    def clear_data(self):
        """Clear all posts and engagements."""
        self.stdout.write(self.style.WARNING("Clearing existing data..."))

        eng_count = Engagement.objects.count()
        Engagement.objects.all().delete()
        self.stdout.write(f"  Deleted {eng_count} engagements")

        sponsored_count = SponsoredPost.objects.count()
        SponsoredPost.objects.all().delete()
        self.stdout.write(f"  Deleted {sponsored_count} sponsored posts")

        post_count = Post.objects.count()
        Post.objects.all().delete()
        self.stdout.write(f"  Deleted {post_count} posts")

        self.stdout.write(self.style.SUCCESS("  Done!\n"))

    def create_users(self):
        """Create users with proper XProfile (x_user_id from TweetScout)."""
        self.stdout.write(self.style.HTTP_INFO("Creating users with XProfile...\n"))

        tweetscout = get_tweetscout_service()

        for x_username, user_data in TEST_USERS.items():
            telegram_id = user_data["telegram_id"]
            name = user_data["name"]

            try:
                # Create/update user
                user, created = User.objects.get_or_create(
                    telegram_id=telegram_id,
                    defaults={
                        "display_name": name,
                        "telegram_username": f"test_{x_username.lower()}",
                        "x_username": x_username,
                        "credits": Decimal('500'),  # Enough karma to post
                    }
                )

                if not created:
                    user.display_name = name
                    user.x_username = x_username
                    user.credits = Decimal('500')
                    user.save(update_fields=["display_name", "x_username", "credits", "updated_at"])

                # Fetch TweetScout data (includes x_user_id!)
                tweetscout_data = tweetscout.get_user_data(x_username)

                if tweetscout_data:
                    score = tweetscout_data.get("score", 0) or 0
                    x_user_id = str(tweetscout_data.get("id", ""))

                    # Create/update XProfile with x_user_id
                    XProfile.objects.update_or_create(
                        user=user,
                        defaults={
                            "x_user_id": x_user_id,
                            "username": x_username,
                            "display_name": tweetscout_data.get("name", ""),
                            "score": score,
                            "followers_count": tweetscout_data.get("followers_count", 0) or 0,
                            "avatar_url": tweetscout_data.get("avatar", "") or "",
                            "raw_tweetscout_data": tweetscout_data,
                        }
                    )

                    user.tweetscout_score = score
                    user.save(update_fields=["tweetscout_score", "updated_at"])

                    tier = get_tweet_score_tier(score)
                    self.stdout.write(self.style.SUCCESS(
                        f"  @{x_username}: x_user_id={x_user_id}, Score={score:.0f}, Tier={tier}"
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f"  @{x_username}: No TweetScout data - skipping"
                    ))
                    continue

                self.users[x_username] = user

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  @{x_username}: Error - {e}"))

            time.sleep(0.5)  # Rate limit

        # Handle blest - use existing real account
        blest_user = User.objects.filter(x_username__iexact="0xBlest_").first()
        if blest_user:
            self.users["0xBlest_"] = blest_user
            self.stdout.write(self.style.SUCCESS(
                f"  @0xBlest_: Using existing account (TG: {blest_user.telegram_id})"
            ))
        else:
            self.stdout.write(self.style.WARNING("  @0xBlest_: No existing account found"))

        self.stdout.write("")

    def submit_posts(self):
        """Submit posts using actual business logic."""
        self.stdout.write(self.style.HTTP_INFO("Submitting posts...\n"))

        karma_amount = get_setting('POST_COST_MIN')

        for x_username, posts in USER_POSTS.items():
            user = self.users.get(x_username)
            if not user:
                self.stdout.write(self.style.WARNING(f"  Skipping @{x_username} - no user"))
                continue

            # Get user's XProfile for ownership validation
            try:
                x_profile = XProfile.objects.get(user=user)
                stored_user_id = x_profile.x_user_id
            except XProfile.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"  Skipping @{x_username} - no XProfile"))
                continue

            self.stdout.write(f"  @{x_username} ({len(posts)} posts):")

            for x_link in posts:
                try:
                    # Extract tweet_id
                    tweet_id = twitter_verification.extract_tweet_id(x_link)
                    if not tweet_id:
                        self.stdout.write(f"    [SKIP] Invalid URL: {x_link[:40]}...")
                        continue

                    # Fetch tweet content (same as actual submission)
                    tweet_content = twitter_verification.get_tweet_content(tweet_id)

                    if not tweet_content:
                        # API down - create post without content
                        self.stdout.write(f"    [API DOWN] {tweet_id}: Creating without content")
                        tweet_content = {}  # Empty - will create post anyway
                    else:
                        # Validate ownership (same as actual submission)
                        tweet_author_id = tweet_content.get("author_id", "")
                        if tweet_author_id != stored_user_id:
                            self.stdout.write(self.style.WARNING(
                                f"    [SKIP] {tweet_id}: Owner mismatch "
                                f"(tweet={tweet_author_id}, user={stored_user_id})"
                            ))
                            continue

                    # Parse timestamp
                    tweet_created_at = None
                    if tweet_content.get("created_at"):
                        tweet_created_at = parse_datetime(tweet_content["created_at"])

                    # Create post (same as actual submission)
                    post = Post.objects.create(
                        user=user,
                        x_link=x_link,
                        tweet_id=tweet_id,
                        platform=Post.Platform.WEB,
                        escrow=Decimal(str(karma_amount)),
                        initial_escrow=Decimal(str(karma_amount)),
                        # Cached tweet content
                        tweet_text=tweet_content.get("text", ""),
                        tweet_author_name=tweet_content.get("author_name", ""),
                        tweet_author_username=tweet_content.get("author_username", ""),
                        tweet_author_avatar=tweet_content.get("author_avatar", ""),
                        tweet_media=tweet_content.get("media", []),
                        tweet_created_at=tweet_created_at,
                    )

                    self.created_posts.append(post)

                    # Show preview (handle encoding)
                    if tweet_content.get('text'):
                        text_preview = tweet_content.get('text', '')[:40]
                        text_preview = text_preview.encode('ascii', 'replace').decode()
                        self.stdout.write(self.style.SUCCESS(
                            f"    [OK] {tweet_id}: \"{text_preview}...\""
                        ))
                    else:
                        self.stdout.write(f"    [OK] {tweet_id}: Created (no content)")

                except Exception as e:
                    self.stdout.write(self.style.ERROR(
                        f"    [ERR] {x_link[:40]}: {e}"
                    ))

                time.sleep(0.3)  # Rate limit

            self.stdout.write("")

    def print_summary(self):
        """Print summary."""
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
        self.stdout.write(self.style.SUCCESS("SUMMARY"))
        self.stdout.write(self.style.SUCCESS("=" * 60))

        self.stdout.write(f"\nUsers Created: {len(self.users)}")
        self.stdout.write(f"Posts Created: {len(self.created_posts)}")

        with_content = sum(1 for p in self.created_posts if p.tweet_text)
        self.stdout.write(f"  With tweet content: {with_content}")
        self.stdout.write(f"  Without content: {len(self.created_posts) - with_content}")

        self.stdout.write(self.style.SUCCESS("\nDone! Test the feed in the Mini App."))
