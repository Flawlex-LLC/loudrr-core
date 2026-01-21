"""
Mini App API views for Telegram Web App.

Handles engagement sessions with:
- Layer 1: Click tracking
- Layer 2: Twitter API verification (100% of engagements)
- Layer 3: Honesty score drops for failed verification (no karma penalty)

DECIMAL KARMA SYSTEM:
- All credit values are Decimal internally
- Convert to float for JSON responses
- Frontend displays 2 decimal places
"""
import math
import hashlib
import hmac
import json
from decimal import Decimal
from urllib.parse import parse_qsl

from django.conf import settings
from django.db import transaction, IntegrityError
from django.db.models import F
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import User
from core.services.credits import CreditService, DailyCapReachedError
from core.services.posts import get_feed_posts
from core.services.engagements import record_button_engagement
from core.services.twitter_verification import twitter_verification
from posts.models import Post, Engagement
# Note: EngagementSession and SessionClick models removed (dead code)


def decimal_to_float(value):
    """Convert Decimal to float for JSON serialization."""
    if isinstance(value, Decimal):
        return float(value)
    return value


def validate_telegram_webapp_data(init_data: str) -> dict:
    """
    Validate Telegram Web App init data.

    Returns user data if valid, None otherwise.
    """
    try:
        # Parse the init_data query string
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))

        if "hash" not in parsed:
            return None

        received_hash = parsed.pop("hash")

        # Create data check string (alphabetically sorted)
        data_check_string = "\n".join(
            f"{key}={value}" for key, value in sorted(parsed.items())
        )

        # Create secret key
        bot_token = settings.TELEGRAM_BOT_TOKEN
        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode(),
            hashlib.sha256
        ).digest()

        # Calculate hash
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        # Validate
        if calculated_hash != received_hash:
            return None

        # Parse user data
        if "user" in parsed:
            return json.loads(parsed["user"])

        return None

    except Exception:
        return None


def get_user_from_telegram_data(user_data: dict) -> User:
    """Get or create user from Telegram Web App data."""
    telegram_id = user_data.get("id")
    if not telegram_id:
        return None

    user, created = User.objects.get_or_create(
        telegram_id=telegram_id,
        defaults={
            "display_name": user_data.get("first_name", ""),
            "telegram_username": user_data.get("username", ""),
            "telegram_photo_url": user_data.get("photo_url", ""),
        }
    )

    # Update user info if changed
    if not created:
        new_name = user_data.get("first_name", "")
        new_username = user_data.get("username", "")
        new_photo = user_data.get("photo_url", "")

        update_fields = []
        if user.display_name != new_name:
            user.display_name = new_name
            update_fields.append("display_name")
        if user.telegram_username != new_username:
            user.telegram_username = new_username
            update_fields.append("telegram_username")
        if user.telegram_photo_url != new_photo:
            user.telegram_photo_url = new_photo
            update_fields.append("telegram_photo_url")

        if update_fields:
            update_fields.append("updated_at")
            user.save(update_fields=update_fields)

    return user


class MiniAppAuthMixin:
    """Mixin for authenticating Mini App requests via Telegram Web App data."""

    def get_user_from_request(self, request):
        """Extract and validate user from Telegram init data."""
        # In development, allow mock user via telegram_id query param
        if settings.DEBUG:
            telegram_id = request.query_params.get("telegram_id")
            if telegram_id:
                try:
                    return User.objects.get(telegram_id=int(telegram_id))
                except (User.DoesNotExist, ValueError):
                    pass

        init_data = request.headers.get("X-Telegram-Init-Data", "")

        if not init_data:
            # For development, allow query param
            init_data = request.query_params.get("init_data", "")

        if not init_data:
            return None

        # Validate the init data
        user_data = validate_telegram_webapp_data(init_data)
        if not user_data:
            return None

        return get_user_from_telegram_data(user_data)


def format_post_for_response(post, viewer_user) -> dict:
    """
    Format a post for API response, including author's X profile data.

    Args:
        post: Post model instance
        viewer_user: User who will view/engage with the post

    Returns:
        dict with post data including X profile info
    """
    from django.utils import timezone
    from core.services.settings import get_setting

    author = post.user

    # Calculate hours remaining until expiry
    expiry_hours = get_setting('POST_EXPIRY_HOURS', 48)
    if post.created_at:
        elapsed = timezone.now() - post.created_at
        elapsed_hours = elapsed.total_seconds() / 3600
        hours_remaining = max(0, expiry_hours - elapsed_hours)
    else:
        hours_remaining = expiry_hours

    # Get X profile data if available
    x_profile = getattr(author, 'x_profile', None)

    # Prefer X profile data, fallback to User fields, then Telegram
    if x_profile:
        display_name = x_profile.display_name or author.x_username or author.display_name or "Anonymous"
        x_username = x_profile.username or author.x_username
        avatar_url = x_profile.avatar_url or None
    else:
        display_name = author.display_name or author.telegram_username or "Anonymous"
        x_username = author.x_username
        avatar_url = None

    return {
        "id": str(post.id),
        "x_link": post.x_link,
        "redirect_url": post.get_redirect_url_for_user(viewer_user),
        "creator": display_name,
        "creator_x_username": x_username,
        "creator_avatar": avatar_url,
        "escrow_remaining": decimal_to_float(post.escrow),
        "engagement_progress": post.engagement_progress,
        "is_sponsored": post.is_sponsored,
        "tweet_id": post.tweet_id or None,
        "created_at": post.created_at.isoformat() if post.created_at else None,
        # Cached tweet content for feed display
        "tweet_text": post.tweet_text or None,
        "tweet_author_name": post.tweet_author_name or None,
        "tweet_author_username": post.tweet_author_username or None,
        "tweet_author_avatar": post.tweet_author_avatar or None,
        "tweet_media": post.tweet_media or [],
        "tweet_created_at": post.tweet_created_at.isoformat() if post.tweet_created_at else None,
        "hours_remaining": round(hours_remaining, 1),
    }


class StartSessionView(MiniAppAuthMixin, APIView):
    """
    Start engagement flow - returns posts and user's pending progress.

    Progress is tracked at USER level via Engagement.verified=False,
    NOT via session expiry. User can return after days and see their progress.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        user = self.get_user_from_request(request)
        if not user:
            return Response(
                {"error": "Invalid authentication"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if user.is_banned:
            return Response(
                {"error": "Your account has been suspended"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get user's pending (unverified) engagements - this IS their progress
        # FIFO: order by clicked_at to process oldest first
        pending_engagements = Engagement.objects.filter(
            user=user,
            verified=False,
            credit_granted=False,
        ).select_related('post', 'post__user', 'post__user__x_profile').order_by('clicked_at')

        pending_count = pending_engagements.count()
        pending_post_ids = list(pending_engagements.values_list('post_id', flat=True))

        # Get posts for pending engagements (to show progress)
        pending_posts = [
            eng.post for eng in pending_engagements
            if eng.post.status == Post.Status.ACTIVE and eng.post.escrow > 0
        ]

        # Get ALL fresh posts (excluding pending ones)
        fresh_posts = get_feed_posts(
            user,
            limit=100,  # Reasonable upper limit
            exclude_post_ids=pending_post_ids,
        )

        # Combine: pending posts first (already clicked), then fresh posts (to engage)
        all_posts = pending_posts + fresh_posts

        if not all_posts and pending_count == 0:
            return Response({
                "posts": [],
                "pending_count": 0,
                "pending_post_ids": [],
                "show_verification": False,
                "message": "No posts available right now. Check back later!",
                "user": {
                    "credits": decimal_to_float(user.credits),
                    "daily_earned": decimal_to_float(user.daily_credits_earned),
                    "daily_cap": settings.ECHO_CONFIG["DAILY_EARN_CAP"],
                },
            })

        # Format posts for response
        posts_data = [format_post_for_response(post, user) for post in all_posts]

        return Response({
            "posts": posts_data,
            "pending_count": pending_count,
            "pending_post_ids": [str(pid) for pid in pending_post_ids],
            "show_verification": False,
            "user": {
                "credits": decimal_to_float(user.credits),
                "daily_earned": decimal_to_float(user.daily_credits_earned),
                "daily_cap": settings.ECHO_CONFIG["DAILY_EARN_CAP"],
            },
        })


class RecordClickView(MiniAppAuthMixin, APIView):
    """
    Record a click/engagement on a post.

    Creates Engagement with verified=False directly (no session needed).
    Progress persists indefinitely until verification.
    """
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        user = self.get_user_from_request(request)
        if not user:
            return Response(
                {"error": "Invalid authentication"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        post_id = request.data.get("post_id")

        if not post_id:
            return Response(
                {"error": "Missing post_id"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Lock post row to prevent race conditions in engagement creation
        try:
            post = Post.objects.select_for_update().get(
                id=post_id,
                status=Post.Status.ACTIVE
            )
        except Post.DoesNotExist:
            return Response(
                {"error": "Post not found or no longer active"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Can't engage with own post
        if post.user_id == user.id:
            return Response(
                {"error": "Cannot engage with your own post"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create Engagement directly (not SessionClick)
        # verified=False means it's pending verification
        # credit_granted=False means no karma awarded yet
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
        except IntegrityError:
            # Duplicate engagement race condition - get existing
            engagement = Engagement.objects.get(user=user, post=post)
            created = False

        # Count total pending engagements for this user
        pending_count = Engagement.objects.filter(
            user=user,
            verified=False,
            credit_granted=False,
        ).count()

        return Response({
            "success": True,
            "engagement_id": str(engagement.id),
            "created": created,
            "pending_count": pending_count,
            "show_verification": pending_count >= 10,
        })


class VerifyReturnView(MiniAppAuthMixin, APIView):
    """
    Mark that user returned to app after clicking a link.

    Optional - confirms user went to X and came back.
    Engagement already exists from RecordClickView.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        user = self.get_user_from_request(request)
        if not user:
            return Response(
                {"error": "Invalid authentication"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        post_id = request.data.get("post_id")

        if not post_id:
            return Response(
                {"error": "Missing post_id"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            engagement = Engagement.objects.get(
                user=user,
                post_id=post_id,
            )
        except Engagement.DoesNotExist:
            return Response(
                {"error": "Engagement not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Engagement exists = user clicked and returned
        # No additional flag needed in new flow
        return Response({
            "success": True,
            "verified": True,
            "engagement_id": str(engagement.id),
        })


class CompleteSessionView(MiniAppAuthMixin, APIView):
    """
    Verify pending engagements and award credits (Claim Rewards).

    SIMPLIFIED FLOW (100% verification):
    1. Get ALL unverified Engagements for this user
    2. Require minimum of 10 (configurable) to claim
    3. Verify ALL via Twitter API ($0.00015 per verification)
    4. Pass → mark complete, award karma
    5. Fail → keep pending (stays in feed for re-engagement)
    6. Update honesty score based on failure count (no karma penalty)

    ROBUSTNESS:
    - Locks posts in consistent order
    - Uses F() expressions for atomic escrow decrement
    - Handles idempotency via verified flag
    """
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        user = self.get_user_from_request(request)
        if not user:
            return Response(
                {"error": "Invalid authentication"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # SECURITY: Require X account linked for verification
        if not user.x_username:
            return Response({
                "success": False,
                "error": "x_account_required",
                "message": "Please link your X account before claiming rewards.",
                "credits_awarded": 0,
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get configurable settings
        from core.services.settings import get_setting
        min_to_claim = get_setting('MIN_ENGAGEMENTS_TO_CLAIM', 10)

        # Get ALL unverified engagements for this user (no batch limit)
        pending_engagements = Engagement.objects.select_for_update().filter(
            user=user,
            verified=False,
            credit_granted=False,
        ).select_related('post').order_by('clicked_at')

        pending_list = list(pending_engagements)

        if len(pending_list) < min_to_claim:
            return Response({
                "success": False,
                "message": f"Need {min_to_claim}+ engagements to claim. You have {len(pending_list)}.",
                "credits_awarded": 0,
                "pending_count": len(pending_list),
            })

        # ANTI-GAMING: Minimum session duration check
        min_duration = get_setting('MIN_SESSION_DURATION_SECONDS', 150)
        if min_duration > 0 and pending_list:
            first_click_time = pending_list[0].clicked_at
            elapsed_seconds = (timezone.now() - first_click_time).total_seconds()
            if elapsed_seconds < min_duration:
                remaining = int(min_duration - elapsed_seconds)
                return Response({
                    "success": False,
                    "error": "insufficient_engagement_time",
                    "message": f"Please wait {remaining} seconds before claiming. Ensure you engage with all posts.",
                    "credits_awarded": 0,
                    "pending_count": len(pending_list),
                    "remaining_seconds": remaining,
                })

        # Lock posts in consistent order to prevent deadlocks
        post_ids = sorted(set(eng.post_id for eng in pending_list))
        posts_locked = {
            p.pk: p for p in Post.objects.select_for_update().filter(
                pk__in=post_ids
            ).order_by('pk')
        }

        # Verify ALL engagements (100% verification)
        total_passed = 0
        total_failed = 0
        credits_awarded = Decimal('0')
        verification_results = []

        credit_service = CreditService(user)

        # Get base credit amount
        from core.services.tweet_score import calculate_engagement_karma
        base_credit = Decimal(str(get_setting('CREDIT_PER_ENGAGEMENT', 1)))

        for eng in pending_list:
            # Get tweet_id from post
            tweet_id = eng.post.tweet_id
            if not tweet_id:
                tweet_id = twitter_verification.extract_tweet_id(eng.post.x_link)

            # Verify via Twitter API
            result = {"passed": True, "reply_verified": False, "skipped": True}
            if tweet_id and user.x_username:
                result = twitter_verification.verify_reply(
                    tweet_id=tweet_id,
                    x_username=user.x_username
                )
                # If API was skipped (no key), treat as passed
                if result.get("skipped"):
                    result["passed"] = True

            passed = result.get("passed", False)

            verification_results.append({
                "post_id": str(eng.post_id),
                "passed": passed,
            })

            if passed:
                # PASS: Mark complete, award karma
                eng.verified = True
                eng.reply_verified = True
                eng.like_verified = True
                eng.verification_data = {
                    "verified_at": timezone.now().isoformat(),
                    "method": "twitter_api_advanced_search",
                    "result": "passed",
                    "tweet_id": tweet_id,
                }

                # Get locked post
                post = posts_locked.get(eng.post_id)
                if not post or post.status != Post.Status.ACTIVE or post.escrow <= 0:
                    eng.credit_granted = False
                    eng.save()
                    total_passed += 1
                    continue

                # Check daily cap
                if not credit_service.can_earn():
                    eng.credit_granted = False
                    eng.save()
                    total_passed += 1
                    continue

                try:
                    # Calculate karma with tier multiplier
                    karma_amount, multiplier = calculate_engagement_karma(
                        base_credit, user.tweetscout_score or 0
                    )

                    # Deduct escrow atomically BEFORE awarding credits
                    updated = Post.objects.filter(
                        pk=post.pk,
                        escrow__gte=karma_amount
                    ).update(escrow=F('escrow') - karma_amount)

                    if not updated:
                        # Escrow depleted - don't award
                        eng.credit_granted = False
                        eng.save()
                        total_passed += 1
                        continue

                    # Award credit to user
                    credit_service.earn(
                        amount=karma_amount,
                        reference_id=eng.id,
                        reference_type="engagement",
                        description=f"Engagement verified (x{multiplier})",
                    )
                    credits_awarded += karma_amount
                    eng.credit_granted = True

                    # Award XP for sponsored posts
                    if post.is_sponsored:
                        from core.services.xp import XPService, get_xp_for_sponsored_engagement
                        xp_amount = get_xp_for_sponsored_engagement()
                        xp_service = XPService(user)
                        xp_service.earn_from_sponsored(
                            amount=xp_amount,
                            post_id=post.pk,
                            description="Sponsored engagement reward",
                        )

                    # Check if post completed
                    post.refresh_from_db()
                    if post.escrow <= 0:
                        Post.objects.filter(pk=post.pk).update(
                            status=Post.Status.COMPLETED,
                            completed_at=timezone.now()
                        )

                    # Update engagement stats
                    User.objects.filter(pk=user.pk).update(
                        total_engagements=F('total_engagements') + 1
                    )

                except DailyCapReachedError:
                    eng.credit_granted = False
                except Exception:
                    eng.credit_granted = False

                eng.save()
                total_passed += 1

            else:
                # FAIL: Keep pending - don't mark as verified
                # User can re-engage with this post
                # Don't save - engagement stays exactly as is
                total_failed += 1

        # Update honesty score based on failure count (no karma penalty)
        if total_failed > 0:
            # Re-lock user for update
            user = User.objects.select_for_update().get(pk=user.pk)

            # Scale drop by failures: ceil(failures/2) -> 1-2 fails = -1, 3-4 = -2, etc.
            drop = max(1, math.ceil(total_failed / 2))
            user.honesty_score = max(0, user.honesty_score - drop)
            user.save(update_fields=['honesty_score'])

        # Refresh user
        user.refresh_from_db()

        # Build response message
        if total_failed == 0:
            message = f"Earned {float(credits_awarded):.2f} karma for {total_passed} engagements!"
        else:
            message = f"Earned {float(credits_awarded):.2f} karma for {total_passed} engagements. {total_failed} need re-engagement."

        # Get remaining pending engagements (failed ones + any new ones)
        remaining_pending = Engagement.objects.filter(
            user=user,
            verified=False,
            credit_granted=False,
        )
        remaining_count = remaining_pending.count()
        remaining_post_ids = list(remaining_pending.values_list('post_id', flat=True))

        return Response({
            "success": True,
            "message": message,
            "credits_awarded": float(credits_awarded),
            "passed": total_passed,
            "failed": total_failed,
            "total_verified": total_passed,
            "new_balance": decimal_to_float(user.credits),
            "daily_earned": decimal_to_float(user.daily_credits_earned),
            "honesty_score": user.honesty_score,
            "pending_count": remaining_count,
            "pending_post_ids": [str(pid) for pid in remaining_post_ids],
            "verification_results": verification_results,
        })


class UserInfoView(MiniAppAuthMixin, APIView):
    """Get user info for Mini App."""
    permission_classes = [AllowAny]

    def get(self, request):
        user = self.get_user_from_request(request)
        if not user:
            return Response(
                {"error": "Invalid authentication"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Get available posts count (lightweight query)
        from core.services.posts import get_feed_count
        from posts.models import Engagement
        from django.utils import timezone

        available_posts = get_feed_count(user)

        # Get today's engagement count
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        engaged_today = Engagement.objects.filter(
            user=user,
            clicked_at__gte=today_start
        ).count()

        return Response({
            "id": str(user.id),
            "display_name": user.display_name,
            "telegram_username": user.telegram_username,
            "x_username": user.x_username or None,
            "credits": decimal_to_float(user.credits),
            "daily_earned": decimal_to_float(user.daily_credits_earned),
            "daily_cap": settings.ECHO_CONFIG["DAILY_EARN_CAP"],
            "total_engagements": user.total_engagements,
            "tier": user.tier,
            "current_streak": user.current_streak,
            "tweetscout_score": user.tweetscout_score or 0,
            "honesty_score": getattr(user, 'honesty_score', 10),
            "available_posts": available_posts,
            "engaged_today": engaged_today,
        })


class SubmitPostView(MiniAppAuthMixin, APIView):
    """Submit a new X post from Mini App."""
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        user = self.get_user_from_request(request)
        if not user:
            return Response(
                {"error": "Invalid authentication"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if user.is_banned:
            return Response(
                {"error": "Your account has been suspended"},
                status=status.HTTP_403_FORBIDDEN
            )

        x_link = request.data.get("x_link", "").strip()

        if not x_link:
            return Response(
                {"error": "Missing X post link"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate it looks like an X/Twitter link
        if not any(domain in x_link.lower() for domain in ["twitter.com", "x.com"]):
            return Response(
                {"error": "Invalid link. Please provide a Twitter/X post URL."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Extract tweet_id from URL
        from core.services.twitter_verification import twitter_verification
        tweet_id = twitter_verification.extract_tweet_id(x_link)

        if not tweet_id:
            return Response(
                {"error": "Could not extract tweet ID from URL. Please use format: https://x.com/username/status/123456789"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # User must have X account linked
        if not user.x_username:
            return Response(
                {"error": "Please link your X account first before submitting posts."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get user's stored X user ID for ownership validation
        from core.models import XProfile
        try:
            x_profile = XProfile.objects.get(user=user)
            stored_user_id = x_profile.x_user_id
        except XProfile.DoesNotExist:
            return Response(
                {"error": "X account not properly linked. Please re-link your account."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not stored_user_id:
            return Response(
                {"error": "X account verification data missing. Please re-link your account."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Fetch tweet content (1 API call = $0.00015)
        # This validates ownership AND caches content for feed display
        tweet_content = twitter_verification.get_tweet_content(tweet_id)

        if not tweet_content:
            return Response(
                {"error": "Could not fetch tweet. Please check the URL and try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        # Validate ownership by permanent ID
        tweet_author_id = tweet_content.get("author_id", "")
        if tweet_author_id != stored_user_id:
            return Response(
                {"error": f"This post belongs to @{tweet_content.get('author_username', 'unknown')}. You can only submit your own posts."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update username if changed (handle renames)
        new_username = tweet_content.get("author_username", "")
        if new_username and new_username.lower() != user.x_username.lower():
            user.x_username = new_username
            user.save(update_fields=["x_username", "updated_at"])
            x_profile.username = new_username
            x_profile.save(update_fields=["username", "updated_at"])

        # Get post cost limits from settings
        from core.services.settings import get_setting
        post_cost_min = get_setting('POST_COST_MIN')
        post_cost_max = get_setting('POST_COST_MAX')

        # Get user's chosen karma amount (default to minimum)
        karma_amount = request.data.get("karma_amount", post_cost_min)
        try:
            karma_amount = int(karma_amount)
        except (TypeError, ValueError):
            return Response(
                {"error": "Invalid karma amount"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate karma amount is within range
        if karma_amount < post_cost_min:
            return Response(
                {"error": f"Minimum karma is {post_cost_min}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        if karma_amount > post_cost_max:
            return Response(
                {"error": f"Maximum karma is {post_cost_max}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if user has enough credits
        if user.credits < karma_amount:
            return Response(
                {"error": f"Not enough karma. You need {karma_amount} karma to post."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if this link was already submitted
        if Post.objects.filter(x_link=x_link, status=Post.Status.ACTIVE).exists():
            return Response(
                {"error": "This post is already active in the system."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create the post and deduct credits
        credit_service = CreditService(user)

        # Parse tweet created_at timestamp
        tweet_created_at = None
        created_at_str = tweet_content.get("created_at", "")
        if created_at_str:
            from django.utils.dateparse import parse_datetime
            tweet_created_at = parse_datetime(created_at_str)

        post = Post.objects.create(
            user=user,
            x_link=x_link,
            tweet_id=tweet_id,
            platform=Post.Platform.WEB,  # Submitted via Mini App
            escrow=Decimal(str(karma_amount)),
            initial_escrow=Decimal(str(karma_amount)),
            # Cached tweet content for feed display
            tweet_text=tweet_content.get("text", ""),
            tweet_author_name=tweet_content.get("author_name", ""),
            tweet_author_username=tweet_content.get("author_username", ""),
            tweet_author_avatar=tweet_content.get("author_avatar", ""),
            tweet_media=tweet_content.get("media", []),
            tweet_created_at=tweet_created_at,
        )

        credit_service.spend(
            amount=Decimal(str(karma_amount)),
            reference_id=post.id,
            reference_type="post",
            description=f"Posted X link",
        )

        user.refresh_from_db()

        return Response({
            "success": True,
            "message": f"Post submitted! {karma_amount} karma locked in escrow.",
            "post_id": str(post.id),
            "new_balance": decimal_to_float(user.credits),
            "escrow": karma_amount,
        })


class UserStatsView(MiniAppAuthMixin, APIView):
    """Get detailed user stats for Mini App."""
    permission_classes = [AllowAny]

    def get(self, request):
        user = self.get_user_from_request(request)
        if not user:
            return Response(
                {"error": "Invalid authentication"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Get user's posts stats
        user_posts = Post.objects.filter(user=user)
        total_posts = user_posts.count()
        active_posts = user_posts.filter(status=Post.Status.ACTIVE).count()
        completed_posts = user_posts.filter(status=Post.Status.COMPLETED).count()

        # Get engagement stats
        total_engagements_given = Engagement.objects.filter(user=user).count()
        total_engagements_received = Engagement.objects.filter(post__user=user).count()

        # Get recent posts (last 5)
        recent_posts = user_posts.order_by("-created_at")[:5]
        recent_posts_data = [
            {
                "id": str(post.id),
                "x_link": post.x_link,
                "status": post.status,
                "escrow_remaining": decimal_to_float(post.escrow),
                "engagement_progress": post.engagement_progress,
                "created_at": post.created_at.isoformat(),
            }
            for post in recent_posts
        ]

        return Response({
            "user": {
                "display_name": user.display_name,
                "telegram_username": user.telegram_username,
                "credits": decimal_to_float(user.credits),
                "tier": user.tier,
                "current_streak": user.current_streak,
                "total_credits_earned": decimal_to_float(user.total_credits_earned),
                "total_credits_spent": decimal_to_float(user.total_credits_spent),
            },
            "posts": {
                "total": total_posts,
                "active": active_posts,
                "completed": completed_posts,
            },
            "engagements": {
                "given": total_engagements_given,
                "received": total_engagements_received,
            },
            "recent_posts": recent_posts_data,
        })


class LinkXAccountView(MiniAppAuthMixin, APIView):
    """
    Link X/Twitter username to user account.

    This is the ONLY place where we call TweetScout API.
    All data is fetched once and stored in XProfile for future use.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        user = self.get_user_from_request(request)
        if not user:
            return Response(
                {"error": "Invalid authentication"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        x_username = request.data.get("x_username", "").strip().lstrip("@")
        if not x_username:
            return Response(
                {"error": "Username is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Basic validation - username format
        import re
        if not re.match(r'^[a-zA-Z0-9_]{1,15}$', x_username):
            return Response(
                {"error": "Invalid username format"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Fetch ALL data from TweetScout API (score + info)
        from core.services.tweetscout import get_tweetscout_service
        from core.services.tweet_score import get_tweet_score_tier
        from core.models import XProfile

        tweetscout = get_tweetscout_service()
        tweetscout_data = tweetscout.get_user_data(x_username)

        if tweetscout_data is None:
            return Response(
                {"error": "Username not found. Please check and try again."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Extract all fields from TweetScout response
        info = tweetscout_data.get("info", {}) or {}
        score = tweetscout_data.get("score", 0) or 0

        # Parse register_date if available
        x_created_at = None
        if info.get("register_date"):
            try:
                from datetime import datetime
                x_created_at = datetime.strptime(
                    info["register_date"], "%Y-%m-%d"
                ).date()
            except (ValueError, TypeError):
                pass

        # Create or update XProfile with ALL TweetScout data
        x_profile, created = XProfile.objects.update_or_create(
            user=user,
            defaults={
                # Basic info
                "x_user_id": str(info.get("id", "")),
                "username": info.get("screen_name", x_username),
                "display_name": info.get("name", ""),
                "bio": info.get("description", "") or "",

                # Metrics
                "followers_count": info.get("followers_count", 0) or 0,
                "following_count": info.get("friends_count", 0) or 0,
                "tweets_count": info.get("tweets_count", 0) or 0,

                # TweetScout score
                "score": score,

                # Profile assets
                "avatar_url": info.get("avatar", "") or "",
                "banner_url": info.get("banner", "") or "",

                # Account status
                "is_verified": bool(info.get("verified", False)),
                "can_dm": bool(info.get("can_dm", False)),

                # Account age
                "x_created_at": x_created_at,

                # Raw JSON for future-proofing
                "raw_tweetscout_data": tweetscout_data,
            }
        )

        # Also update User model for backwards compatibility
        user.x_username = x_username
        user.tweetscout_score = score
        user.tweetscout_last_updated = timezone.now()
        user.save(update_fields=[
            "x_username",
            "tweetscout_score",
            "tweetscout_last_updated",
            "updated_at",
        ])

        return Response({
            "success": True,
            "x_username": x_profile.username,
            "tweetscout_score": score,
            "tier": get_tweet_score_tier(score),
            "followers_count": x_profile.followers_count,
            "display_name": x_profile.display_name,
        })


class HealthCheckView(APIView):
    """Health check endpoint for monitoring."""
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "status": "ok",
            "service": "miniapp-api"
        })


class SettingsView(APIView):
    """
    Get app settings for frontend.

    Returns configurable values that the frontend needs.
    Cached on backend (5 min), fetched once on frontend load.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        from core.services.settings import get_setting

        return Response({
            "post_cost_min": get_setting('POST_COST_MIN'),
            "post_cost_max": get_setting('POST_COST_MAX'),
        })
