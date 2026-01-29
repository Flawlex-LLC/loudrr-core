"""
Celery tasks for core app.

Handles asynchronous operations like email sending with industry-grade reliability:
- Idempotency via database tracking (prevents duplicate emails)
- Row-level locking via select_for_update (prevents race conditions)
- Smart retry logic (distinguishes permanent vs temporary failures)
- Comprehensive error logging and tracking

References:
- https://www.vintasoftware.com/blog/celery-wild-tips-and-tricks-run-async-tasks-real-world
- https://flaky.build/how-to-avoid-sending-duplicate-emails-to-customers
"""
import logging
from smtplib import SMTPRecipientsRefused, SMTPServerDisconnected, SMTPConnectError
from celery import shared_task
from django.db import transaction
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Errors that indicate permanent failure - don't retry
PERMANENT_FAILURE_INDICATORS = [
    'Invalid email address',
    'Mailbox not found',
    'User unknown',
    'No such user',
    'does not exist',
    'rejected',
    'blacklisted',
]


def is_permanent_failure(error_message: str) -> bool:
    """Check if error indicates permanent failure (don't retry)."""
    error_lower = error_message.lower()
    return any(indicator.lower() in error_lower for indicator in PERMANENT_FAILURE_INDICATORS)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(SMTPServerDisconnected, SMTPConnectError, ConnectionError),
    retry_backoff=True,
    name='core.send_waitlist_confirmation_email'
)
def send_waitlist_confirmation_email_task(self, entry_id: str):
    """
    Send waitlist confirmation email with idempotency guarantee.

    Uses database-backed idempotency:
    1. Acquires row lock (select_for_update)
    2. Checks if email already sent (email_confirmation_sent_at)
    3. Sends email only if not already sent
    4. Updates tracking fields on success/failure

    Args:
        entry_id: UUID of the WaitlistEntry

    Returns:
        dict with status: 'sent', 'already_sent', or 'permanent_failure'
    """
    from core.models import WaitlistEntry
    from core.services.email import send_waitlist_confirmation_email

    logger.info(f"[EMAIL] Processing confirmation email for entry {entry_id}")

    try:
        with transaction.atomic():
            # Row-level lock prevents race conditions
            entry = WaitlistEntry.objects.select_for_update().get(id=entry_id)

            # IDEMPOTENCY CHECK: Already sent?
            if entry.email_confirmation_sent_at:
                logger.info(f"[EMAIL] Confirmation already sent to {entry.email} at {entry.email_confirmation_sent_at}, skipping")
                return {"status": "already_sent", "email": entry.email}

            # Build Telegram URL
            bot_username = getattr(settings, 'TELEGRAM_BOT_USERNAME', 'loudrr_bot')
            telegram_url = f"https://t.me/{bot_username}?start=join_{entry.join_token}"

            # Increment attempt counter
            entry.email_send_attempts += 1

            # Send email
            try:
                success = send_waitlist_confirmation_email(entry.email, telegram_url)

                if success:
                    entry.email_confirmation_sent_at = timezone.now()
                    entry.email_last_error = ''
                    entry.save(update_fields=[
                        'email_confirmation_sent_at',
                        'email_send_attempts',
                        'email_last_error'
                    ])
                    logger.info(f"[EMAIL] Confirmation sent successfully to {entry.email}")
                    return {"status": "sent", "email": entry.email}
                else:
                    entry.email_last_error = 'SMTP send returned False'
                    entry.save(update_fields=['email_send_attempts', 'email_last_error'])
                    raise Exception(f"Email send failed for {entry.email}")

            except SMTPRecipientsRefused as e:
                # Permanent failure - invalid email address
                error_msg = f"PERMANENT: Recipient refused - {str(e)}"
                entry.email_last_error = error_msg
                entry.save(update_fields=['email_send_attempts', 'email_last_error'])
                logger.error(f"[EMAIL] Permanent failure for {entry.email}: {e}")
                return {"status": "permanent_failure", "email": entry.email, "error": error_msg}

            except Exception as e:
                error_msg = str(e)
                entry.email_last_error = f"ERROR: {error_msg}"
                entry.save(update_fields=['email_send_attempts', 'email_last_error'])

                # Check if this is a permanent failure
                if is_permanent_failure(error_msg):
                    logger.error(f"[EMAIL] Permanent failure for {entry.email}: {e}")
                    return {"status": "permanent_failure", "email": entry.email, "error": error_msg}

                # Temporary failure - retry
                logger.warning(f"[EMAIL] Temporary failure for {entry.email}, will retry: {e}")
                raise self.retry(exc=e)

    except WaitlistEntry.DoesNotExist:
        logger.error(f"[EMAIL] Entry {entry_id} not found")
        return {"status": "error", "error": "Entry not found"}


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(SMTPServerDisconnected, SMTPConnectError, ConnectionError),
    retry_backoff=True,
    name='core.send_already_registered_email'
)
def send_already_registered_email_task(self, entry_id: str):
    """
    Send 'already registered' email with idempotency.

    This email CAN be sent multiple times (when user retries with same email),
    but we throttle to max once per hour to prevent spam.

    Args:
        entry_id: UUID of the WaitlistEntry

    Returns:
        dict with status: 'sent', 'throttled', or 'permanent_failure'
    """
    from core.models import WaitlistEntry
    from core.services.email import send_already_registered_email
    from datetime import timedelta

    logger.info(f"[EMAIL] Processing already-registered email for entry {entry_id}")

    try:
        with transaction.atomic():
            entry = WaitlistEntry.objects.select_for_update().get(id=entry_id)

            # THROTTLE CHECK: Don't spam if sent recently (within 1 hour)
            if entry.email_already_registered_sent_at:
                time_since_last = timezone.now() - entry.email_already_registered_sent_at
                if time_since_last < timedelta(hours=1):
                    logger.info(f"[EMAIL] Already-registered email recently sent to {entry.email}, throttling")
                    return {"status": "throttled", "email": entry.email}

            # Build Telegram URL
            bot_username = getattr(settings, 'TELEGRAM_BOT_USERNAME', 'loudrr_bot')
            telegram_url = f"https://t.me/{bot_username}?start=join_{entry.join_token}"

            # Increment attempt counter
            entry.email_send_attempts += 1

            # Send email
            try:
                success = send_already_registered_email(entry.email, telegram_url)

                if success:
                    entry.email_already_registered_sent_at = timezone.now()
                    entry.email_last_error = ''
                    entry.save(update_fields=[
                        'email_already_registered_sent_at',
                        'email_send_attempts',
                        'email_last_error'
                    ])
                    logger.info(f"[EMAIL] Already-registered email sent to {entry.email}")
                    return {"status": "sent", "email": entry.email}
                else:
                    entry.email_last_error = 'SMTP send returned False'
                    entry.save(update_fields=['email_send_attempts', 'email_last_error'])
                    raise Exception(f"Email send failed for {entry.email}")

            except SMTPRecipientsRefused as e:
                error_msg = f"PERMANENT: Recipient refused - {str(e)}"
                entry.email_last_error = error_msg
                entry.save(update_fields=['email_send_attempts', 'email_last_error'])
                logger.error(f"[EMAIL] Permanent failure for {entry.email}: {e}")
                return {"status": "permanent_failure", "email": entry.email, "error": error_msg}

            except Exception as e:
                error_msg = str(e)
                entry.email_last_error = f"ERROR: {error_msg}"
                entry.save(update_fields=['email_send_attempts', 'email_last_error'])

                if is_permanent_failure(error_msg):
                    logger.error(f"[EMAIL] Permanent failure for {entry.email}: {e}")
                    return {"status": "permanent_failure", "email": entry.email, "error": error_msg}

                logger.warning(f"[EMAIL] Temporary failure for {entry.email}, will retry: {e}")
                raise self.retry(exc=e)

    except WaitlistEntry.DoesNotExist:
        logger.error(f"[EMAIL] Entry {entry_id} not found")
        return {"status": "error", "error": "Entry not found"}


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    name='core.fetch_tweetscout_for_user'
)
def fetch_tweetscout_for_user_task(self, user_id: str):
    """
    Fetch TweetScout data for a newly approved user.

    Called asynchronously after admin approval to avoid blocking.
    Creates XProfile and updates User with TweetScout score.

    Args:
        user_id: UUID of the User

    Returns:
        dict with status: 'success', 'no_data', or 'error'
    """
    from datetime import datetime
    from core.models import User, XProfile
    from core.services.tweetscout import get_tweetscout_service

    logger.info(f"[TWEETSCOUT] Fetching data for user {user_id}")

    try:
        user = User.objects.get(id=user_id)

        if not user.x_username:
            logger.warning(f"[TWEETSCOUT] User {user_id} has no X username")
            return {"status": "error", "error": "No X username"}

        # Check if XProfile already exists (idempotency)
        if XProfile.objects.filter(user=user).exists():
            logger.info(f"[TWEETSCOUT] XProfile already exists for user {user_id}, skipping")
            return {"status": "already_exists"}

        # Fetch TweetScout data
        tweetscout = get_tweetscout_service()
        tweetscout_data = tweetscout.get_user_data(user.x_username)

        if not tweetscout_data:
            logger.warning(f"[TWEETSCOUT] No data returned for @{user.x_username}")
            return {"status": "no_data", "username": user.x_username}

        score = tweetscout_data.get("score", 0) or 0

        # Parse X account creation date
        x_created_at = None
        if tweetscout_data.get("register_date"):
            try:
                x_created_at = datetime.strptime(
                    tweetscout_data["register_date"], "%Y-%m-%d"
                ).date()
            except (ValueError, TypeError):
                pass

        # Create XProfile with TweetScout data
        with transaction.atomic():
            XProfile.objects.update_or_create(
                user=user,
                defaults={
                    "x_user_id": str(tweetscout_data.get("id", "")),
                    "username": tweetscout_data.get("screen_name", user.x_username),
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
                    "x_created_at": x_created_at,
                    "raw_tweetscout_data": tweetscout_data,
                }
            )

            # Update user with actual TweetScout score
            user.tweetscout_score = score
            user.save(update_fields=['tweetscout_score', 'updated_at'])

        logger.info(f"[TWEETSCOUT] Successfully fetched data for user {user_id}, score: {score}")
        return {"status": "success", "score": score, "username": user.x_username}

    except User.DoesNotExist:
        logger.error(f"[TWEETSCOUT] User {user_id} not found")
        return {"status": "error", "error": "User not found"}

    except Exception as e:
        logger.exception(f"[TWEETSCOUT] Error fetching data for user {user_id}")
        raise self.retry(exc=e)
