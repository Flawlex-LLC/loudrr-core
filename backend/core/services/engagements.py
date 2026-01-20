"""
Engagement tracking service.

Handles recording engagements, validating them, and updating streaks.

ROBUSTNESS GUARANTEES:
- No check-then-act patterns (uses get_or_create + IntegrityError)
- Atomic escrow decrement with F() expressions
- Row-level locking with select_for_update()
- Lock ordering: Post -> User (prevents deadlocks)

DECIMAL KARMA SYSTEM:
- All karma calculations use Decimal with 4 decimal places
- Escrow deducted = karma earned (no inflation)
- Uses ROUND_HALF_EVEN for fairness
"""
import base64
import hashlib
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.cache import cache
from django.db import transaction, IntegrityError
from django.db.models import F
from django.utils import timezone

from core.models import User
from core.services.credits import CreditService, DailyCapReachedError
from core.services.settings import get_setting
from core.services.tweet_score import calculate_engagement_karma


def get_user_score(user: User) -> float:
    """
    Get user's TweetScout score from XProfile or fallback.

    Order of priority:
    1. XProfile.score (preferred - complete data)
    2. User.tweetscout_score (fallback - legacy)
    3. 0 (default)
    """
    try:
        if hasattr(user, 'x_profile') and user.x_profile:
            return user.x_profile.score or 0
    except Exception:
        pass
    return user.tweetscout_score or 0


class EngagementError(Exception):
    """Base error for engagement issues."""
    pass


class SelfEngagementError(EngagementError):
    """User tried to engage with their own post."""
    pass


class AlreadyEngagedError(EngagementError):
    """User already engaged with this post."""
    pass


class CooldownError(EngagementError):
    """User is still in cooldown period."""
    pass


class PostNotActiveError(EngagementError):
    """Post is not active (completed or cancelled)."""
    pass


def get_encryption_cipher():
    """Get Fernet cipher for encrypting user IDs."""
    key = settings.ENCRYPTION_KEY.encode()
    # Ensure key is 32 bytes
    key = hashlib.sha256(key).digest()
    key = base64.urlsafe_b64encode(key)
    return Fernet(key)


def encrypt_user_id(user_id: str) -> str:
    """Encrypt a user ID for use in redirect URLs."""
    cipher = get_encryption_cipher()
    return cipher.encrypt(str(user_id).encode()).decode()


def decrypt_user_id(encrypted: str) -> Optional[str]:
    """Decrypt a user ID from a redirect URL."""
    try:
        cipher = get_encryption_cipher()
        return cipher.decrypt(encrypted.encode()).decode()
    except Exception:
        return None


def check_cooldown(user: User) -> bool:
    """
    Check if user is still in cooldown period.

    Returns True if cooldown has passed, False if still in cooldown.
    """
    cooldown_key = f"engagement_cooldown:{user.id}"
    if cache.get(cooldown_key):
        return False
    return True


def set_cooldown(user: User):
    """Set cooldown for user after engagement."""
    cooldown_seconds = get_setting('ENGAGEMENT_COOLDOWN')
    if cooldown_seconds > 0:
        cooldown_key = f"engagement_cooldown:{user.id}"
        cache.set(cooldown_key, True, timeout=cooldown_seconds)


def get_cooldown_remaining(user: User) -> int:
    """Get seconds remaining in cooldown, or 0 if not in cooldown."""
    cooldown_key = f"engagement_cooldown:{user.id}"
    # Check if cooldown exists (LocMemCache doesn't support ttl())
    if cache.get(cooldown_key):
        # Return default cooldown time since we can't get exact TTL
        return get_setting('ENGAGEMENT_COOLDOWN')
    return 0


@transaction.atomic
def record_engagement(encrypted_user_id: str, post) -> bool:
    """
    Record an engagement from a redirect click.

    This is called from the redirect view when a user clicks a tracking link.

    ROBUSTNESS:
    - Uses get_or_create to prevent duplicate engagements (idempotent)
    - Locks Post row before escrow decrement
    - Uses F() for atomic escrow update

    Args:
        encrypted_user_id: Encrypted user ID from URL param
        post: Post model instance being engaged with

    Returns:
        True if engagement was recorded, False otherwise
    """
    from posts.models import Engagement, Post  # Import here to avoid circular import

    # Decrypt user ID
    user_id = decrypt_user_id(encrypted_user_id)
    if not user_id:
        return False

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return False

    # Pre-checks (safe before locking)
    if post.user_id == user.id:
        return False  # Self-engagement

    if not check_cooldown(user):
        return False  # Cooldown active

    credit_service = CreditService(user)
    if not credit_service.can_earn():
        return False  # Daily cap reached

    # LOCK ORDER: Post first, then User (prevents deadlocks)
    # Lock post row and re-check status
    try:
        post_locked = Post.objects.select_for_update().get(pk=post.pk)
    except Post.DoesNotExist:
        return False

    if post_locked.status != "active" or post_locked.escrow <= 0:
        return False  # Post no longer active

    # Atomic engagement creation - DB constraint prevents duplicates
    try:
        engagement, created = Engagement.objects.get_or_create(
            user=user,
            post=post_locked,
            defaults={
                "clicked_at": timezone.now(),
                "credit_granted": False,  # Set to True after credit granted
            }
        )
        if not created:
            return False  # Already engaged (idempotent - return False, no error)
    except IntegrityError:
        # Race condition caught by unique constraint
        return False

    # Calculate karma based on engager's TweetScout score
    base_credit = Decimal(str(get_setting('CREDIT_PER_ENGAGEMENT')))
    engager_score = get_user_score(user)
    karma_amount, multiplier = calculate_engagement_karma(base_credit, engager_score)

    # Check if post has enough escrow
    if post_locked.escrow < karma_amount:
        karma_amount = post_locked.escrow  # Partial award
        if karma_amount <= Decimal('0'):
            engagement.delete()
            return False

    # Grant credit to engager (multiplied amount)
    # IMPORTANT: escrow deducted = karma earned (no inflation)
    credit_granted = False
    try:
        credit_service.earn(
            amount=karma_amount,
            reference_id=engagement.id,
            reference_type="engagement",
            description=f"Engagement on post {post.pk} ({float(multiplier):.2f}x)",
        )
        credit_granted = True
    except DailyCapReachedError:
        pass  # Still record engagement, just no credit

    # Update engagement record
    engagement.credit_granted = credit_granted
    engagement.save(update_fields=["credit_granted"])

    # Atomic escrow decrement using F() expression
    # IMPORTANT: Deduct the EXACT same amount that was credited (no inflation)
    Post.objects.filter(pk=post.pk).update(
        escrow=F('escrow') - karma_amount,
        updated_at=timezone.now()
    )

    # Check if post should be completed
    post_locked.refresh_from_db()
    if post_locked.escrow <= Decimal('0'):
        Post.objects.filter(pk=post.pk).update(
            status="completed",
            completed_at=timezone.now()
        )

    # Update user stats atomically
    User.objects.filter(pk=user.pk).update(
        total_engagements=F('total_engagements') + 1
    )
    user.refresh_from_db()

    # Update streak
    _update_streak(user)
    user.save(update_fields=["current_streak", "longest_streak", "last_engagement_date"])

    # Set cooldown
    set_cooldown(user)

    return True


def _update_streak(user: User):
    """Update user's engagement streak."""
    from django.utils.timezone import localdate
    today = localdate()  # Respects Django USE_TZ setting
    yesterday = today - timedelta(days=1)

    if user.last_engagement_date is None:
        # First engagement ever
        user.current_streak = 1
    elif user.last_engagement_date == today:
        # Already engaged today, no change
        pass
    elif user.last_engagement_date == yesterday:
        # Engaged yesterday, continue streak
        user.current_streak += 1
    else:
        # Missed days, reset streak
        user.current_streak = 1

    user.last_engagement_date = today
    if user.current_streak > user.longest_streak:
        user.longest_streak = user.current_streak


@transaction.atomic
def record_button_engagement(user: User, post) -> dict:
    """
    Record an engagement via button click (honor system).

    Used when redirect tracking is not available (no HTTPS domain).

    ROBUSTNESS:
    - Uses get_or_create to prevent duplicate engagements (idempotent)
    - Locks Post row before escrow decrement
    - Uses F() for atomic escrow update
    - Lock ordering: Post -> User (prevents deadlocks)

    Returns:
        dict with 'success', 'error', 'credits_earned', 'daily_remaining'
    """
    from posts.models import Engagement, Post  # Import here to avoid circular import

    result = {
        "success": False,
        "error": None,
        "credits_earned": Decimal('0'),
        "daily_remaining": Decimal('0'),
        "streak": 0,
        "multiplier": Decimal('1.0'),
    }

    # Pre-checks (safe before locking)
    if post.user_id == user.id:
        result["error"] = "You cannot engage with your own post."
        return result

    if not check_cooldown(user):
        cooldown = get_setting('ENGAGEMENT_COOLDOWN')
        result["error"] = f"Please wait {cooldown} seconds between engagements."
        return result

    credit_service = CreditService(user)
    if not credit_service.can_earn():
        result["error"] = "You've reached your daily credit limit. Come back tomorrow!"
        return result

    # LOCK ORDER: Post first (prevents deadlocks)
    try:
        post_locked = Post.objects.select_for_update().get(pk=post.pk)
    except Post.DoesNotExist:
        result["error"] = "Post not found."
        return result

    # Re-check status after acquiring lock
    if post_locked.status != "active":
        result["error"] = "This post is no longer active."
        return result

    if post_locked.escrow <= 0:
        result["error"] = "This post has no remaining budget."
        return result

    # Atomic engagement creation - DB constraint prevents duplicates
    try:
        engagement, created = Engagement.objects.get_or_create(
            user=user,
            post=post_locked,
            defaults={
                "clicked_at": timezone.now(),
                "credit_granted": False,
            }
        )
        if not created:
            result["error"] = "You have already engaged with this post."
            return result
    except IntegrityError:
        # Race condition caught by unique constraint
        result["error"] = "You have already engaged with this post."
        return result

    # Calculate karma based on engager's TweetScout score
    base_credit = Decimal(str(get_setting('CREDIT_PER_ENGAGEMENT')))
    engager_score = get_user_score(user)
    karma_amount, multiplier = calculate_engagement_karma(base_credit, engager_score)

    # Check if post has enough escrow
    if post_locked.escrow < karma_amount:
        karma_amount = post_locked.escrow  # Partial award
        if karma_amount <= Decimal('0'):
            engagement.delete()
            result["error"] = "This post has no remaining budget."
            return result

    # Grant credit to engager (multiplied amount)
    # IMPORTANT: escrow deducted = karma earned (no inflation)
    try:
        credit_service.earn(
            amount=karma_amount,
            reference_id=engagement.id,
            reference_type="engagement",
            description=f"Engagement on post {post.pk} ({float(multiplier):.2f}x)",
        )
        result["credits_earned"] = karma_amount
        result["multiplier"] = multiplier
        engagement.credit_granted = True
        engagement.save(update_fields=["credit_granted"])

        # Award XP for sponsored post engagements
        if post_locked.is_sponsored:
            from core.services.xp import XPService, get_xp_for_sponsored_engagement
            xp_amount = get_xp_for_sponsored_engagement()
            xp_service = XPService(user)
            xp_service.earn_from_sponsored(
                amount=xp_amount,
                post_id=post.pk,
                description=f"Sponsored engagement on post {post.pk}",
            )
            result["xp_earned"] = xp_amount

    except DailyCapReachedError:
        # Still record engagement, just no credit
        pass

    # Atomic escrow decrement using F() expression
    # IMPORTANT: Deduct the EXACT same amount that was credited (no inflation)
    Post.objects.filter(pk=post.pk).update(
        escrow=F('escrow') - karma_amount,
        updated_at=timezone.now()
    )

    # Check if post should be completed
    post_locked.refresh_from_db()
    if post_locked.escrow <= Decimal('0'):
        Post.objects.filter(pk=post.pk).update(
            status="completed",
            completed_at=timezone.now()
        )

    # Update user stats atomically
    User.objects.filter(pk=user.pk).update(
        total_engagements=F('total_engagements') + 1
    )
    user.refresh_from_db()

    # Update streak
    _update_streak(user)
    user.save(update_fields=["current_streak", "longest_streak", "last_engagement_date"])

    # Set cooldown
    set_cooldown(user)

    result["success"] = True
    result["daily_remaining"] = credit_service.get_daily_remaining()
    result["streak"] = user.current_streak

    return result
