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
