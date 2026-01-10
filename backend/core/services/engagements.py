"""
Engagement tracking service.

Handles recording engagements, validating them, and updating streaks.
"""
import base64
import hashlib
from datetime import date, timedelta
from typing import Optional

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from core.models import User
from core.services.credits import CreditService, DailyCapReachedError


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
    cooldown_seconds = settings.ECHO_CONFIG["ENGAGEMENT_COOLDOWN"]
    cooldown_key = f"engagement_cooldown:{user.id}"
    cache.set(cooldown_key, True, timeout=cooldown_seconds)


def get_cooldown_remaining(user: User) -> int:
    """Get seconds remaining in cooldown, or 0 if not in cooldown."""
    cooldown_key = f"engagement_cooldown:{user.id}"
    ttl = cache.ttl(cooldown_key)
    return max(0, ttl) if ttl else 0


@transaction.atomic
def record_engagement(encrypted_user_id: str, post) -> bool:
    """
    Record an engagement from a redirect click.

    This is called from the redirect view when a user clicks a tracking link.

    Args:
        encrypted_user_id: Encrypted user ID from URL param
        post: Post model instance being engaged with

    Returns:
        True if engagement was recorded, False otherwise
    """
    from posts.models import Engagement  # Import here to avoid circular import

    # Decrypt user ID
    user_id = decrypt_user_id(encrypted_user_id)
    if not user_id:
        return False

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return False

    # Check if post is still active
    if post.status != "active":
        return False

    # Check self-engagement
    if post.user_id == user.id:
        return False

    # Check if already engaged
    if Engagement.objects.filter(user=user, post=post).exists():
        return False

    # Check cooldown
    if not check_cooldown(user):
        return False

    # Check daily cap
    credit_service = CreditService(user)
    if not credit_service.can_earn():
        return False

    # Record engagement
    engagement = Engagement.objects.create(
        user=user,
        post=post,
        clicked_at=timezone.now(),
        credit_granted=True,
    )

    # Grant credit to engager
    try:
        credit_service.earn(
            amount=settings.ECHO_CONFIG["CREDIT_PER_ENGAGEMENT"],
            reference_id=engagement.id,
            reference_type="engagement",
            description=f"Engagement on post {post.id}",
        )
    except DailyCapReachedError:
        # Mark as no credit granted but still record engagement
        engagement.credit_granted = False
        engagement.save(update_fields=["credit_granted"])

    # Update user stats
    user.total_engagements += 1
    user.update_tier()

    # Update streak
    _update_streak(user)
    user.save()

    # Decrement post escrow
    post.escrow -= 1
    if post.escrow <= 0:
        post.status = "completed"
        post.completed_at = timezone.now()
    post.save(update_fields=["escrow", "status", "completed_at", "updated_at"])

    # Set cooldown
    set_cooldown(user)

    return True


def _update_streak(user: User):
    """Update user's engagement streak."""
    today = date.today()
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
