"""
Mini App API views for Telegram Web App.

ARCHITECTURE:
- Phase 1: VerificationService - Twitter API calls (no DB locks)
- Phase 2: SettlementService - Atomic DB writes (no external calls)

This ensures:
- No database locks held during slow network calls
- Atomic escrow + credit transfers (savepoints per engagement)
- If credit award fails, escrow is NOT deducted
- Partial payment supported (user gets remaining escrow if < full amount)

DECIMAL KARMA SYSTEM:
- All credit values are Decimal internally
- Convert to float for JSON responses
- Frontend displays 2 decimal places
"""
import hashlib
import hmac
import json
from decimal import Decimal
from urllib.parse import parse_qsl

from django.conf import settings
from django.db import transaction, IntegrityError
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from core.models import User, WaitlistEntry, FeatureInterest
from .schema import (
    HealthResponseSerializer,
    SettingsResponseSerializer,
    WaitlistSubmitRequestSerializer,
    WaitlistSubmitResponseSerializer,
    WaitlistStatusResponseSerializer,
    WaitlistEntryResponseSerializer,
    WaitlistCompleteRequestSerializer,
    UserInfoResponseSerializer,
    UserStatsResponseSerializer,
    LinkXRequestSerializer,
    StartSessionResponseSerializer,
    RecordClickRequestSerializer,
    RecordClickResponseSerializer,
    QueueClaimRequestSerializer,
    QueueClaimResponseSerializer,
    ClaimHistoryResponseSerializer,
    SubmitPostRequestSerializer,
    SubmitPostResponseSerializer,
    ReferralInfoResponseSerializer,
    FeatureInterestRequestSerializer,
    FeatureInterestResponseSerializer,
    CompleteOnboardingResponseSerializer,
    ErrorResponseSerializer,
)
from core.services.credits import CreditService
from core.services.posts import get_feed_posts
from core.services.twitter_verification import twitter_verification
from posts.models import Post, Engagement


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

        # Validate HMAC
        if calculated_hash != received_hash:
            return None

        # Check auth_date expiry (max 24 hours - Telegram recommendation)
        import time
        auth_date = int(parsed.get("auth_date", 0))
        if auth_date and (time.time() - auth_date > 86400):
            return None  # Expired init data

        # Parse user data
        if "user" in parsed:
            return json.loads(parsed["user"])

        return None

    except Exception:
        return None


def get_user_from_telegram_data(user_data: dict) -> User:
    """
    Get user from Telegram Web App data.

    Does NOT auto-create users. Users must be created via waitlist approval.
    Returns None if user doesn't exist (will show "not whitelisted" in frontend).
    """
    telegram_id = user_data.get("id")
    if not telegram_id:
        return None

    try:
        user = User.objects.get(telegram_id=telegram_id)

        # Update user info if changed
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

    except User.DoesNotExist:
        return None


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


@extend_schema_view(
    post=extend_schema(
        tags=["Engagement"],
        summary="Start engagement session",
        description="Start engagement flow - returns posts and user's pending progress. Progress is tracked at USER level.",
        responses={
            200: StartSessionResponseSerializer,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
        },
    )
)
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


@extend_schema_view(
    post=extend_schema(
        tags=["Engagement"],
        summary="Record click on post",
        description="Record a click/engagement on a post. Creates Engagement with verified=False.",
        request=RecordClickRequestSerializer,
        responses={
            200: RecordClickResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
)
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


@extend_schema_view(
    post=extend_schema(
        tags=["Engagement"],
        summary="Verify user returned from X",
        description="Mark that user returned to app after clicking a link. Optional confirmation step.",
        request=RecordClickRequestSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
)
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


@extend_schema_view(
    post=extend_schema(
        tags=["Engagement"],
        summary="Complete session and claim rewards",
        description="Verify pending engagements and award credits. Uses two-phase architecture for reliability.",
        responses={
            200: OpenApiTypes.OBJECT,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
        },
    )
)
class CompleteSessionView(MiniAppAuthMixin, APIView):
    """
    Verify pending engagements and award credits (Claim Rewards).

    CLEAN ARCHITECTURE (two-phase):
    Phase 1: VerificationService - API calls (no DB locks held)
    Phase 2: SettlementService - Atomic DB writes (no external calls)

    This ensures:
    - No database locks held during slow network calls
    - Atomic escrow + credit transfers (savepoints per engagement)
    - If credit award fails, escrow is NOT deducted
    - Partial payment supported (user gets remaining escrow if < full amount)

    FLOW:
    1. Validate user and preconditions (no locks)
    2. Get pending engagements (no locks)
    3. Verify ALL via Twitter API (no locks - Phase 1)
    4. Settle atomically via SettlementService (Phase 2)
    5. Return results
    """
    permission_classes = [AllowAny]

    def post(self, request):
        # NOTE: No @transaction.atomic here - we handle it in phases
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

        # Get pending engagements (NO LOCK - just reading for validation)
        pending_engagements = Engagement.objects.filter(
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

        # =================================================================
        # PHASE 1: Verify via Twitter API (NO database locks held)
        # =================================================================
        from core.services.verification import (
            VerificationService, EngagementToVerify
        )

        # Prepare verification inputs
        to_verify = []
        for eng in pending_list:
            tweet_id = eng.post.tweet_id
            if not tweet_id:
                tweet_id = twitter_verification.extract_tweet_id(eng.post.x_link)
            to_verify.append(EngagementToVerify(
                engagement_id=eng.pk,
                post_id=eng.post_id,
                tweet_id=tweet_id or "",
            ))

        # Call Twitter API for ALL engagements (no locks)
        verification_service = VerificationService()
        verification_results = verification_service.verify_engagements(
            engagements=to_verify,
            x_username=user.x_username,
        )

        # =================================================================
        # PHASE 2: Settle atomically (NO external API calls)
        # =================================================================
        from core.services.settlement import SettlementService

        settlement_service = SettlementService()
        settlement_results = settlement_service.settle_engagements(
            user_id=user.pk,
            verification_results=verification_results.results,
        )

        # Get remaining pending engagements
        remaining_pending = Engagement.objects.filter(
            user=user,
            verified=False,
            credit_granted=False,
        )
        remaining_count = remaining_pending.count()
        remaining_post_ids = list(remaining_pending.values_list('post_id', flat=True))

        # Format verification results for response
        verification_response = [
            {"post_id": str(r.post_id), "passed": r.passed}
            for r in verification_results.results
        ]

        return Response({
            "success": True,
            "message": settlement_results.message,
            "credits_awarded": float(settlement_results.total_awarded),
            "passed": settlement_results.total_passed,
            "failed": settlement_results.total_failed,
            "total_verified": settlement_results.total_passed,
            "new_balance": float(settlement_results.new_balance),
            "daily_earned": decimal_to_float(
                User.objects.get(pk=user.pk).daily_credits_earned
            ),
            "honesty_score": settlement_results.new_honesty_score,
            "pending_count": remaining_count,
            "pending_post_ids": [str(pid) for pid in remaining_post_ids],
            "verification_results": verification_response,
        })


@extend_schema_view(
    get=extend_schema(
        tags=["User"],
        summary="Get current user info",
        description="Get user profile information including credits, tier, and stats.",
        responses={
            200: UserInfoResponseSerializer,
            401: ErrorResponseSerializer,
        },
    )
)
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
            "tweetscout_last_updated": user.tweetscout_last_updated.isoformat() if user.tweetscout_last_updated else None,
            "honesty_score": getattr(user, 'honesty_score', 10),
            "available_posts": available_posts,
            "engaged_today": engaged_today,
            "is_whitelisted": getattr(user, 'is_whitelisted', True),
            "loud_access": getattr(user, 'loud_access', False),
        })


@extend_schema_view(
    post=extend_schema(
        tags=["Posts"],
        summary="Submit new post for promotion",
        description="Submit a new X post for promotion. Deducts karma as escrow for engagement rewards.",
        request=SubmitPostRequestSerializer,
        responses={
            200: SubmitPostResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
        },
    )
)
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
            description="Posted X link",
        )

        user.refresh_from_db()

        return Response({
            "success": True,
            "message": f"Post submitted! {karma_amount} karma locked in escrow.",
            "post_id": str(post.id),
            "new_balance": decimal_to_float(user.credits),
            "escrow": karma_amount,
        })


@extend_schema_view(
    get=extend_schema(
        tags=["User"],
        summary="Get detailed user stats",
        description="Get detailed statistics including posts, engagements, and recent activity.",
        responses={
            200: UserStatsResponseSerializer,
            401: ErrorResponseSerializer,
        },
    )
)
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


@extend_schema_view(
    post=extend_schema(
        tags=["User"],
        summary="Link X account",
        description="Link X/Twitter username to user account. Fetches TweetScout score and profile data.",
        request=LinkXRequestSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
        },
    )
)
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


@extend_schema_view(
    get=extend_schema(
        tags=["Health"],
        summary="Health check",
        description="Health check endpoint for monitoring.",
        responses={200: HealthResponseSerializer},
    )
)
class HealthCheckView(APIView):
    """Health check endpoint for monitoring."""
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "status": "ok",
            "service": "miniapp-api"
        })


@extend_schema_view(
    get=extend_schema(
        tags=["Settings"],
        summary="Get app settings",
        description="Returns configurable values that the frontend needs.",
        responses={200: SettingsResponseSerializer},
    )
)
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


@extend_schema_view(
    post=extend_schema(
        tags=["Engagement"],
        summary="Queue claim for verification",
        description="Queue verification for async processing. Returns immediately while verification processes in background.",
        request=QueueClaimRequestSerializer,
        responses={
            200: QueueClaimResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            503: ErrorResponseSerializer,
        },
    )
)
class QueueClaimView(MiniAppAuthMixin, APIView):
    """
    Queue verification for async processing (instant response).

    Like spot trading - queues the verification and returns immediately.
    User can continue engaging while verification processes in background.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        from posts.models import VerificationBatch
        from posts.tasks import process_verification_batch
        from core.services.settings import get_setting

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
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get minimum engagements to claim
        min_to_claim = get_setting('MIN_ENGAGEMENTS_TO_CLAIM', 10)

        # Get ALL unverified engagements for this user
        pending_engagements = Engagement.objects.filter(
            user=user,
            verified=False,
            credit_granted=False,
        ).order_by('clicked_at')

        pending_list = list(pending_engagements)

        if len(pending_list) < min_to_claim:
            return Response({
                "success": False,
                "message": f"Need {min_to_claim}+ engagements to claim. You have {len(pending_list)}.",
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
                    "message": f"Please wait {remaining} seconds before claiming.",
                    "pending_count": len(pending_list),
                    "remaining_seconds": remaining,
                })

        # Create verification batch
        engagement_ids = [str(eng.id) for eng in pending_list]
        batch = VerificationBatch.objects.create(
            user=user,
            engagement_ids=engagement_ids,
            status=VerificationBatch.Status.PENDING,
        )

        # Queue the verification task
        try:
            process_verification_batch.delay(str(batch.id))
        except Exception as e:
            # Celery/Redis not available - mark batch failed and return error
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to queue verification task: {e}")
            batch.status = VerificationBatch.Status.FAILED
            batch.message = "Queue service unavailable"
            batch.save(update_fields=['status', 'message'])
            return Response({
                "success": False,
                "error": "queue_unavailable",
                "message": "Verification queue unavailable. Please try again later.",
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # Get position in queue (count of pending batches before this one)
        queue_position = VerificationBatch.objects.filter(
            status__in=['pending', 'processing'],
            created_at__lt=batch.created_at,
        ).count() + 1

        return Response({
            "success": True,
            "batch_id": str(batch.id),
            "status": "pending",
            "position": queue_position,
            "engagement_count": len(engagement_ids),
            "message": "Verification queued! You can continue engaging.",
        })


@extend_schema_view(
    get=extend_schema(
        tags=["Engagement"],
        summary="Get claim history",
        description="Returns recent verification batches with status and results.",
        responses={
            200: ClaimHistoryResponseSerializer,
            401: ErrorResponseSerializer,
        },
    )
)
class ClaimHistoryView(MiniAppAuthMixin, APIView):
    """
    Get claim/verification history for user.

    Returns recent verification batches with status and results.
    Similar to spot trading order history.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        from posts.models import VerificationBatch

        user = self.get_user_from_request(request)
        if not user:
            return Response(
                {"error": "Invalid authentication"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Get recent batches (last 20)
        batches = VerificationBatch.objects.filter(
            user=user
        ).order_by('-created_at')[:20]

        # Check for any processing batches and refresh their status
        # (in case Celery completed but client hasn't seen it yet)

        batch_list = []
        for batch in batches:
            batch_list.append({
                "id": str(batch.id),
                "status": batch.status,
                "engagement_count": len(batch.engagement_ids),
                "passed": batch.passed,
                "failed": batch.failed,
                "credits_awarded": decimal_to_float(batch.credits_awarded) if batch.credits_awarded else None,
                "message": batch.message,
                "created_at": batch.created_at.isoformat(),
                "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
            })

        # Also return current pending engagements count
        pending_count = Engagement.objects.filter(
            user=user,
            verified=False,
            credit_granted=False,
        ).count()

        # Check if any batch is still processing
        has_processing = any(b["status"] in ["pending", "processing"] for b in batch_list)

        return Response({
            "batches": batch_list,
            "pending_engagements": pending_count,
            "has_processing": has_processing,
        })


# =============================================================================
# WAITLIST SYSTEM
# =============================================================================

class WaitlistThrottle(AnonRateThrottle):
    """
    Custom throttle for waitlist submissions.

    Limits: 5 submissions per hour per IP address.

    Prevents abuse while allowing legitimate retries.
    Based on DRF best practices: https://www.django-rest-framework.org/api-guide/throttling/
    """
    rate = '5/hour'


@extend_schema_view(
    post=extend_schema(
        tags=["Waitlist"],
        summary="Submit email to join waitlist",
        description="Submit email to join waitlist. Rate limited to 5 requests/hour per IP.",
        request=WaitlistSubmitRequestSerializer,
        responses={
            200: WaitlistSubmitResponseSerializer,
            400: ErrorResponseSerializer,
            429: ErrorResponseSerializer,
        },
    )
)
class WaitlistSubmitView(APIView):
    """
    Submit email to join waitlist (landing page).

    Flow:
    1. User submits email
    2. Creates WaitlistEntry with join_token (atomic transaction)
    3. Returns Telegram deep link URL
    4. Frontend redirects to Telegram

    Rate limited to 5 requests/hour per IP to prevent abuse.

    Best practices implemented:
    - AnonRateThrottle for IP-based rate limiting
    - transaction.atomic for database consistency
    - Email validation with regex
    - Cryptographically secure token generation
    - Race condition handling with IntegrityError

    References:
    - https://www.django-rest-framework.org/api-guide/throttling/
    - https://docs.djangoproject.com/en/stable/topics/db/transactions/
    """
    permission_classes = [AllowAny]
    throttle_classes = [WaitlistThrottle]

    def post(self, request):
        import secrets
        import re

        email = request.data.get('email', '').strip().lower()

        # Validate email format
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not email or not re.match(email_regex, email):
            return Response(
                {"error": "Please enter a valid email address"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get bot username from settings
        bot_username = getattr(settings, 'TELEGRAM_BOT_USERNAME', 'loudrr_bot')

        # Check if email already on waitlist (read-only, no transaction needed)
        try:
            existing = WaitlistEntry.objects.get(email=email)
            telegram_url = f"https://t.me/{bot_username}?start=join_{existing.join_token}"

            # Queue "already registered" email via OutboxEvent
            # (idempotent - throttled to 1/hour in the email sending logic)
            try:
                from core.services.outbox import OutboxService
                OutboxService.queue_already_registered_email(
                    entry_id=existing.id,
                    email=existing.email,
                )
            except Exception as e:
                # Don't fail the request if queueing fails
                import logging
                logging.getLogger(__name__).warning(f"Failed to queue already registered email: {e}")

            return Response({
                "success": True,
                "telegram_url": telegram_url,
                "message": "This email is already registered. Check your inbox for instructions.",
            })
        except WaitlistEntry.DoesNotExist:
            pass

        # Create new entry with unique token (atomic to handle race conditions)
        # Use transaction.atomic to ensure entry creation is all-or-nothing
        # Prevents partial state if something fails mid-operation
        try:
            with transaction.atomic():
                join_token = secrets.token_urlsafe(16)
                entry = WaitlistEntry.objects.create(
                    email=email,
                    join_token=join_token,
                    status=WaitlistEntry.Status.PENDING,
                )
        except IntegrityError:
            # Race condition - email was created by concurrent request
            # This is safe - just fetch the existing entry
            entry = WaitlistEntry.objects.get(email=email)

        telegram_url = f"https://t.me/{bot_username}?start=join_{entry.join_token}"

        # Queue confirmation email via OutboxEvent
        # (idempotent - only sends once per entry)
        try:
            from core.services.outbox import OutboxService
            OutboxService.queue_waitlist_confirmation_email(
                entry_id=entry.id,
                email=entry.email,
            )
        except Exception as e:
            # Don't fail the request if queueing fails
            import logging
            logging.getLogger(__name__).warning(f"Failed to queue confirmation email: {e}")

        return Response({
            "success": True,
            "telegram_url": telegram_url,
        })


@extend_schema_view(
    post=extend_schema(
        tags=["Waitlist"],
        summary="Register for waitlist from mini app",
        description="Register for waitlist directly from mini app with email and X username. Rate limited to 5/hour.",
        responses={
            200: WaitlistSubmitResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            429: ErrorResponseSerializer,
        },
    )
)
class WaitlistRegisterView(APIView):
    """
    Register for waitlist directly from mini app.

    Security measures:
    - Rate limited (5/hour per IP via WaitlistThrottle)
    - Telegram init data HMAC validation + auth_date expiry check
    - Email validation via Django EmailValidator (RFC 5322)
    - X username format validation
    - Race condition handling via IntegrityError catch
    - Idempotent (returns success for duplicate telegram_id)

    After successful registration:
    - Sends waitlist confirmation card to user via Telegram
    - Notifies admin about new registration
    """
    permission_classes = [AllowAny]
    throttle_classes = [WaitlistThrottle]

    def post(self, request):
        import logging
        import re
        import secrets
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError as DjangoValidationError

        logger = logging.getLogger(__name__)

        # 1. VALIDATE TELEGRAM INIT DATA (HMAC + auth_date expiry)
        init_data = request.headers.get("X-Telegram-Init-Data", "")
        user_data = validate_telegram_webapp_data(init_data)
        if not user_data:
            logger.warning("[WAITLIST] Invalid or expired Telegram init data")
            return Response({"error": "Invalid Telegram data"}, status=status.HTTP_401_UNAUTHORIZED)

        telegram_id = user_data.get("id")
        if not telegram_id:
            return Response({"error": "Missing Telegram ID"}, status=status.HTTP_400_BAD_REQUEST)

        # 2. VALIDATE EMAIL (RFC 5322 compliance)
        email = request.data.get("email", "").strip().lower()
        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)
        if len(email) > 254:
            return Response({"error": "Email too long"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_email(email)
        except DjangoValidationError:
            return Response({"error": "Invalid email format"}, status=status.HTTP_400_BAD_REQUEST)

        # 3. VALIDATE X USERNAME (alphanumeric + underscore, 1-15 chars)
        x_username = request.data.get("x_username", "").strip().lstrip("@")
        x_username_regex = r'^[a-zA-Z0-9_]{1,15}$'
        if not x_username or not re.match(x_username_regex, x_username):
            return Response(
                {"error": "Invalid X username (1-15 chars, alphanumeric and underscore only)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 4. CHECK FOR EXISTING REGISTRATION (idempotent - same telegram_id = success)
        existing_by_telegram = WaitlistEntry.objects.filter(telegram_id=telegram_id).first()
        if existing_by_telegram:
            logger.info(f"[WAITLIST] Telegram {telegram_id} already registered")
            return Response({
                "status": "already_registered",
                "message": "You're already on the waitlist"
            })

        # 5. CHECK FOR EMAIL/USERNAME CONFLICTS (different users)
        if WaitlistEntry.objects.filter(email=email).exists():
            return Response({"error": "Email already registered"}, status=status.HTTP_400_BAD_REQUEST)
        if WaitlistEntry.objects.filter(x_username__iexact=x_username).exists():
            return Response({"error": "X username already registered"}, status=status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(x_username__iexact=x_username).exists():
            return Response({"error": "X username already in use"}, status=status.HTTP_400_BAD_REQUEST)

        # 6. FETCH X PROFILE DATA (outside transaction - external API call)
        x_info = None
        try:
            x_info = twitter_verification.get_user_info(x_username)
        except Exception as e:
            logger.warning(f"[WAITLIST] Failed to fetch X profile for @{x_username}: {e}")
            # Continue without X info - not blocking

        # 7. CREATE ENTRY (atomic + IntegrityError handling for race conditions)
        try:
            with transaction.atomic():
                entry = WaitlistEntry.objects.create(
                    email=email,
                    join_token=secrets.token_urlsafe(16),
                    telegram_id=telegram_id,
                    telegram_username=user_data.get("username", ""),
                    telegram_display_name=user_data.get("first_name", ""),
                    x_username=x_username,
                    status=WaitlistEntry.Status.SUBMITTED,
                    # X profile data (if available)
                    x_display_name=x_info.get("display_name", "") if x_info else "",
                    x_followers_count=x_info.get("followers_count") if x_info else None,
                    x_avatar_url=x_info.get("avatar_url", "") if x_info else "",
                    x_is_verified=x_info.get("is_verified", False) if x_info else False,
                    x_fetched_at=timezone.now() if x_info else None,
                )
                logger.info(f"[WAITLIST] Created entry for {email}, telegram_id={telegram_id}")
        except IntegrityError as e:
            # Race condition - concurrent request created entry
            logger.warning(f"[WAITLIST] IntegrityError for telegram_id={telegram_id}: {e}")
            return Response({
                "status": "already_registered",
                "message": "You're already on the waitlist"
            })

        # NOTE: Waitlist confirmation is now sent via OutboxEvent pattern
        # The post_save signal on WaitlistEntry creates an OutboxEvent
        # which is processed by Celery to send the Telegram card.
        # See core/signals.py:send_submission_confirmation_on_submit

        return Response({
            "status": "registered",
            "message": "Successfully registered for waitlist",
            # X profile data for success card display
            "x_username": x_username,
            "x_display_name": x_info.get("display_name", "") if x_info else "",
            "x_avatar_url": x_info.get("avatar_url", "") if x_info else "",
            "x_followers_count": x_info.get("followers_count") if x_info else None,
            "x_is_verified": x_info.get("is_verified", False) if x_info else False,
        })


@extend_schema_view(
    get=extend_schema(
        tags=["Waitlist"],
        summary="Check waitlist status",
        description="Check waitlist status for current telegram user. Returns 'approved', 'waitlisted', or 'not_registered'.",
        responses={
            200: WaitlistStatusResponseSerializer,
            401: ErrorResponseSerializer,
        },
    )
)
class WaitlistStatusView(APIView):
    """
    Check waitlist status for current telegram user.

    Returns:
    - "approved" if User exists with this telegram_id
    - "waitlisted" if WaitlistEntry exists (pending approval)
    - "not_registered" if neither exists
    """
    permission_classes = [AllowAny]

    def get(self, request):
        init_data = request.headers.get("X-Telegram-Init-Data", "")
        user_data = validate_telegram_webapp_data(init_data)
        if not user_data:
            return Response({"error": "Invalid Telegram data"}, status=status.HTTP_401_UNAUTHORIZED)

        telegram_id = user_data.get("id")
        if not telegram_id:
            return Response({"error": "Missing Telegram ID"}, status=status.HTTP_400_BAD_REQUEST)

        # Check if user exists (already approved)
        if User.objects.filter(telegram_id=telegram_id).exists():
            return Response({"status": "approved"})

        # Check if on waitlist
        entry = WaitlistEntry.objects.filter(telegram_id=telegram_id).first()
        if entry:
            return Response({
                "status": "waitlisted",
                "x_username": entry.x_username,
                "submitted_at": entry.created_at.isoformat()
            })

        return Response({"status": "not_registered"})


@extend_schema_view(
    get=extend_schema(
        tags=["Waitlist"],
        summary="Get waitlist entry details",
        description="Get waitlist entry data for pre-filling registration form.",
        responses={
            200: WaitlistEntryResponseSerializer,
            401: ErrorResponseSerializer,
        },
    )
)
class WaitlistEntryView(APIView):
    """
    Get waitlist entry data for pre-filling registration form.

    Used when user clicks "Complete Registration" in Telegram bot
    and opens the mini app - we pre-fill their email from the entry.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        init_data = request.headers.get("X-Telegram-Init-Data", "")
        user_data = validate_telegram_webapp_data(init_data)
        if not user_data:
            return Response({"error": "Invalid Telegram data"}, status=status.HTTP_401_UNAUTHORIZED)

        telegram_id = user_data.get("id")
        if not telegram_id:
            return Response({"error": "Missing Telegram ID"}, status=status.HTTP_400_BAD_REQUEST)

        # Find entry by telegram_id
        entry = WaitlistEntry.objects.filter(telegram_id=telegram_id).first()

        if not entry:
            return Response({"entry": None})

        return Response({
            "entry": {
                "email": entry.email,
                "x_username": entry.x_username or None,
                "status": entry.status,
            }
        })


@extend_schema_view(
    post=extend_schema(
        tags=["User"],
        summary="Complete onboarding",
        description="Complete onboarding - fetch TweetScout score and activate user.",
        responses={
            200: CompleteOnboardingResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
        },
    )
)
class CompleteOnboardingView(MiniAppAuthMixin, APIView):
    """
    Complete onboarding - fetch TweetScout and activate user.

    Called when user clicks "Let's Go Loudrr" button.
    This is when we actually call TweetScout API.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        user = self.get_user_from_request(request)
        if not user:
            return Response(
                {"error": "Invalid authentication"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # User must have X username linked (from waitlist flow)
        if not user.x_username:
            return Response(
                {"error": "X account not linked"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Already onboarded? (tweetscout_score > 0 means already fetched)
        if user.tweetscout_score > 0:
            from core.services.tweet_score import get_tweet_score_tier
            return Response({
                "success": True,
                "already_onboarded": True,
                "tweetscout_score": user.tweetscout_score,
                "tier": get_tweet_score_tier(user.tweetscout_score),
            })

        # Fetch TweetScout data NOW
        from core.services.tweetscout import get_tweetscout_service
        from core.services.tweet_score import get_tweet_score_tier
        from core.models import XProfile

        tweetscout = get_tweetscout_service()
        tweetscout_data = tweetscout.get_user_data(user.x_username)

        if not tweetscout_data:
            # TweetScout unavailable - allow entry with default score
            user.tweetscout_score = 0
            user.tweetscout_last_updated = timezone.now()
            user.save(update_fields=['tweetscout_score', 'tweetscout_last_updated'])
            return Response({
                "success": True,
                "tweetscout_score": 0,
                "tier": "anon",
                "message": "Could not fetch X data. You can try again later.",
            })

        # Extract data - TweetScout returns flat dict with score at top level
        info = tweetscout_data  # Flat dict containing all user info
        score = tweetscout_data.get("score", 0) or 0

        # Parse register_date
        x_created_at = None
        if info.get("register_date"):
            try:
                from datetime import datetime
                x_created_at = datetime.strptime(
                    info["register_date"], "%Y-%m-%d"
                ).date()
            except (ValueError, TypeError):
                pass

        # Create/update XProfile
        XProfile.objects.update_or_create(
            user=user,
            defaults={
                "x_user_id": str(info.get("id", "")),
                "username": info.get("screen_name", user.x_username),
                "display_name": info.get("name", ""),
                "bio": info.get("description", "") or "",
                "followers_count": info.get("followers_count", 0) or 0,
                "following_count": info.get("friends_count", 0) or 0,
                "tweets_count": info.get("tweets_count", 0) or 0,
                "score": score,
                "avatar_url": info.get("avatar", "") or "",
                "banner_url": info.get("banner", "") or "",
                "is_verified": bool(info.get("verified", False)),
                "can_dm": bool(info.get("can_dm", False)),
                "x_created_at": x_created_at,
                "raw_tweetscout_data": tweetscout_data,
            }
        )

        # Update User
        user.tweetscout_score = score
        user.tweetscout_last_updated = timezone.now()
        user.save(update_fields=[
            'tweetscout_score',
            'tweetscout_last_updated',
            'updated_at',
        ])

        return Response({
            "success": True,
            "tweetscout_score": score,
            "tier": get_tweet_score_tier(score),
            "followers_count": info.get("followers_count", 0),
            "display_name": info.get("name", ""),
        })


@extend_schema_view(
    get=extend_schema(
        tags=["User"],
        summary="Check feature interest",
        description="Check if user has registered interest in a feature.",
        parameters=[
            OpenApiParameter(name="feature", type=str, required=True, description="Feature name to check"),
        ],
        responses={200: FeatureInterestResponseSerializer, 401: ErrorResponseSerializer},
    ),
    post=extend_schema(
        tags=["User"],
        summary="Register feature interest",
        description="Register interest in an upcoming feature.",
        request=FeatureInterestRequestSerializer,
        responses={200: FeatureInterestResponseSerializer, 400: ErrorResponseSerializer, 401: ErrorResponseSerializer},
    ),
)
class FeatureInterestView(MiniAppAuthMixin, APIView):
    """
    Register or check interest in upcoming features.

    POST: Register interest in a feature with specific interests
    GET: Check if user has already registered interest
    """
    permission_classes = [AllowAny]

    def post(self, request):
        user = self.get_user_from_request(request)
        if not user:
            return Response(
                {"error": "Invalid authentication"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        feature = request.data.get('feature', '').strip()
        interests = request.data.get('interests', [])

        if not feature:
            return Response(
                {"error": "Feature is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate feature name (alphanumeric + underscore/hyphen, max 50 chars)
        import re
        if not re.match(r'^[a-zA-Z0-9_-]{1,50}$', feature):
            return Response(
                {"error": "Invalid feature name"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Ensure interests is a list of strings
        if not isinstance(interests, list):
            interests = []
        interests = [str(i)[:100] for i in interests[:10]]  # Max 10 interests, 100 chars each

        # Create or update interest registration
        FeatureInterest.objects.update_or_create(
            user=user,
            feature=feature,
            defaults={'interests': interests}
        )

        return Response({"success": True})

    def get(self, request):
        user = self.get_user_from_request(request)
        if not user:
            return Response(
                {"error": "Invalid authentication"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        feature = request.query_params.get('feature', '').strip()

        if not feature:
            return Response(
                {"error": "Feature parameter is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        registered = FeatureInterest.objects.filter(
            user=user,
            feature=feature
        ).exists()

        return Response({"registered": registered})


@extend_schema_view(
    get=extend_schema(
        tags=["Waitlist"],
        summary="Get waitlist entry by token",
        description="Get waitlist entry info by join token. Used to pre-fill the form with email.",
        parameters=[
            OpenApiParameter(name="token", type=str, required=True, description="Join token from deep link"),
        ],
        responses={200: WaitlistEntryResponseSerializer, 401: ErrorResponseSerializer, 404: ErrorResponseSerializer},
    ),
    post=extend_schema(
        tags=["Waitlist"],
        summary="Complete waitlist registration",
        description="Complete waitlist registration with X username. Final step in the waitlist flow.",
        request=WaitlistCompleteRequestSerializer,
        responses={200: WaitlistSubmitResponseSerializer, 400: ErrorResponseSerializer, 401: ErrorResponseSerializer, 409: ErrorResponseSerializer},
    ),
)
class WaitlistCompleteView(APIView):
    """
    Complete waitlist registration from mini app.

    This is the new flow where user:
    1. Enters email on loudrr.com → gets WaitlistEntry (PENDING)
    2. Opens Telegram deep link → bot links telegram_id to entry
    3. Bot shows "Complete Registration" button → opens mini app
    4. Mini app shows form with email pre-filled
    5. User enters X username → calls this endpoint
    6. Returns success with card data for sharing

    Security measures:
    - Telegram init data HMAC validation + auth_date expiry
    - Join token validation (proves user came from valid deep link)
    - X username format validation
    - Idempotent (returns success for already-submitted entries)
    - Uses transaction.atomic for consistency
    - Notifications via OutboxEvent pattern (signal-triggered)
    """
    permission_classes = [AllowAny]

    def get(self, request):
        """
        Get waitlist entry info by join token.

        Used to pre-fill the form with email.
        """
        import logging
        logger = logging.getLogger(__name__)

        # Validate Telegram auth
        init_data = request.headers.get("X-Telegram-Init-Data", "")
        user_data = validate_telegram_webapp_data(init_data)
        if not user_data:
            return Response({"error": "Invalid Telegram data"}, status=status.HTTP_401_UNAUTHORIZED)

        telegram_id = user_data.get("id")
        if not telegram_id:
            return Response({"error": "Missing Telegram ID"}, status=status.HTTP_400_BAD_REQUEST)

        # Get join token from query params
        join_token = request.query_params.get("token", "").strip()
        if not join_token:
            return Response({"error": "Missing token"}, status=status.HTTP_400_BAD_REQUEST)

        # Find entry by token
        try:
            entry = WaitlistEntry.objects.get(join_token=join_token)
        except WaitlistEntry.DoesNotExist:
            logger.warning(f"[WAITLIST] Invalid token: {join_token[:8]}...")
            return Response({"error": "Invalid or expired link"}, status=status.HTTP_404_NOT_FOUND)

        # Check if already approved (User exists)
        if User.objects.filter(telegram_id=telegram_id).exists():
            return Response({
                "status": "approved",
                "message": "You're already approved!"
            })

        # Check if already submitted
        if entry.status == WaitlistEntry.Status.SUBMITTED:
            return Response({
                "status": "submitted",
                "email": entry.email,
                "x_username": entry.x_username,
                "x_display_name": entry.x_display_name,
                "x_avatar_url": entry.x_avatar_url,
                "x_followers_count": entry.x_followers_count,
            })

        return Response({
            "status": "pending",
            "email": entry.email,
        })

    def post(self, request):
        """
        Complete waitlist registration with X username.
        """
        import logging
        import re
        from django.utils import timezone
        from core.services.twitter_verification import twitter_verification

        logger = logging.getLogger(__name__)

        # 1. VALIDATE TELEGRAM AUTH
        init_data = request.headers.get("X-Telegram-Init-Data", "")
        user_data = validate_telegram_webapp_data(init_data)
        if not user_data:
            return Response({"error": "Invalid Telegram data"}, status=status.HTTP_401_UNAUTHORIZED)

        telegram_id = user_data.get("id")
        telegram_username = user_data.get("username", "")
        telegram_first_name = user_data.get("first_name", "")
        telegram_last_name = user_data.get("last_name", "")

        if not telegram_id:
            return Response({"error": "Missing Telegram ID"}, status=status.HTTP_400_BAD_REQUEST)

        # 2. VALIDATE REQUEST DATA
        join_token = request.data.get("token", "").strip()
        x_username = request.data.get("x_username", "").strip().lstrip("@")

        if not join_token:
            return Response({"error": "Missing token"}, status=status.HTTP_400_BAD_REQUEST)

        if not x_username:
            return Response({"error": "X username is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate X username format
        if not re.match(r'^[a-zA-Z0-9_]{1,15}$', x_username):
            return Response(
                {"error": "Invalid X username format"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 3. FIND ENTRY BY TOKEN
        try:
            entry = WaitlistEntry.objects.get(join_token=join_token)
        except WaitlistEntry.DoesNotExist:
            logger.warning(f"[WAITLIST] Invalid token in complete: {join_token[:8]}...")
            return Response({"error": "Invalid or expired link"}, status=status.HTTP_404_NOT_FOUND)

        # 4. IDEMPOTENCY CHECK - Already submitted
        if entry.status == WaitlistEntry.Status.SUBMITTED:
            logger.info(f"[WAITLIST] Entry {entry.id} already submitted, returning success")
            return Response({
                "status": "success",
                "message": "Already on waitlist",
                "email": entry.email,
                "x_username": entry.x_username,
                "x_display_name": entry.x_display_name,
                "x_avatar_url": entry.x_avatar_url,
                "x_followers_count": entry.x_followers_count,
                "x_is_verified": entry.x_is_verified,
            })

        # 5. CHECK IF X USERNAME ALREADY USED
        if WaitlistEntry.objects.filter(x_username__iexact=x_username).exclude(id=entry.id).exists():
            return Response(
                {"error": "This X account is already on the waitlist"},
                status=status.HTTP_409_CONFLICT
            )

        if User.objects.filter(x_username__iexact=x_username).exists():
            return Response(
                {"error": "This X account is already registered"},
                status=status.HTTP_409_CONFLICT
            )

        # 6. CHECK IF TELEGRAM ID ALREADY LINKED TO DIFFERENT ENTRY
        existing = WaitlistEntry.objects.filter(telegram_id=telegram_id).exclude(id=entry.id).first()
        if existing:
            return Response({
                "status": "already_registered",
                "message": "You're already on the waitlist with a different email",
                "email": existing.email,
                "x_username": existing.x_username,
            }, status=status.HTTP_409_CONFLICT)

        # 7. FETCH X PROFILE INFO
        x_info = twitter_verification.get_user_info(x_username)

        # 8. UPDATE ENTRY (ATOMIC)
        try:
            with transaction.atomic():
                # Select for update to prevent race conditions
                entry = WaitlistEntry.objects.select_for_update().get(id=entry.id)

                # Double-check status inside transaction
                if entry.status == WaitlistEntry.Status.SUBMITTED:
                    return Response({
                        "status": "success",
                        "message": "Already on waitlist",
                        "email": entry.email,
                        "x_username": entry.x_username,
                    })

                # Update entry
                entry.telegram_id = telegram_id
                entry.telegram_username = telegram_username
                entry.telegram_display_name = f"{telegram_first_name} {telegram_last_name}".strip()
                entry.x_username = x_username
                entry.status = WaitlistEntry.Status.SUBMITTED

                if x_info:
                    entry.x_display_name = x_info.get("display_name", "")
                    entry.x_followers_count = x_info.get("followers_count")
                    entry.x_avatar_url = x_info.get("avatar_url", "")
                    entry.x_is_verified = x_info.get("is_verified", False)
                    entry.x_fetched_at = timezone.now()

                entry.save()

                logger.info(
                    f"[WAITLIST] Entry {entry.id} completed via mini app",
                    extra={
                        "entry_id": str(entry.id),
                        "email": entry.email,
                        "x_username": x_username,
                        "telegram_id": telegram_id,
                    }
                )

        except IntegrityError as e:
            logger.error(f"[WAITLIST] IntegrityError completing entry: {e}")
            return Response(
                {"error": "Registration failed, please try again"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # NOTE: Telegram notification is sent via OutboxEvent pattern
        # The post_save signal on WaitlistEntry creates an OutboxEvent
        # when status changes to SUBMITTED.
        # See core/signals.py:send_submission_confirmation_on_submit

        # Build referral link preview for waitlist users
        # They don't have a User yet, so generate preview code from username
        referral_preview = (x_username[:4] + "XXXX").upper() if x_username else "XXXXXXXX"
        landing_url = getattr(settings, 'LANDING_URL', 'https://loudrr.com')

        return Response({
            "status": "success",
            "message": "Successfully joined waitlist",
            "email": entry.email,
            "x_username": entry.x_username,
            "x_display_name": entry.x_display_name or x_username,
            "x_avatar_url": entry.x_avatar_url,
            "x_followers_count": entry.x_followers_count,
            "x_is_verified": entry.x_is_verified,
            # Referral preview (actual code assigned when approved)
            "referral_code": referral_preview,
            "referral_link": f"{landing_url}?ref={referral_preview}",
        })


@extend_schema_view(
    get=extend_schema(
        tags=["Referral"],
        summary="Get referral info",
        description="Returns user's referral code, stats, and shareable links. Only available to whitelisted users.",
        responses={
            200: ReferralInfoResponseSerializer,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
        },
    )
)
class ReferralInfoView(MiniAppAuthMixin, APIView):
    """
    GET /api/miniapp/referral/

    Returns user's referral code, stats, and shareable links.
    Only available to whitelisted users.
    """

    def get(self, request):
        user = self.get_user_from_request(request)
        if not user:
            return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

        import rules
        if not rules.test_rule('core.can_share_referral', user):
            return Response(
                {"error": "Not eligible to share referrals"},
                status=status.HTTP_403_FORBIDDEN
            )

        from core.services.referral import ReferralService
        stats = ReferralService.get_referral_stats(user)

        return Response({
            "referral_code": stats['referral_code'],
            "total_referrals": stats['total_referrals'],
            "links": stats['links'],
        })
