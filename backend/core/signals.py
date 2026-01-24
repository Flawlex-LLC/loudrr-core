"""
Django signals for core app.

Best practices followed:
1. dispatch_uid to prevent duplicate signal connections
2. transaction.on_commit for side effects (Telegram notifications)
3. Idempotency checks to prevent duplicate messages
4. Lightweight handlers - heavy work delegated to Celery

References:
- https://hakibenita.com/django-reliable-signals
- https://docs.djangoproject.com/en/stable/topics/signals/
- https://medium.com/codex/preventing-duplicate-signals-and-custom-signal-handling-in-django-13aea083f917
"""
import logging
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import WaitlistEntry

logger = logging.getLogger(__name__)


# === Waitlist Entry Signals ===


@receiver(
    pre_save,
    sender=WaitlistEntry,
    dispatch_uid="waitlist_entry_track_status_change"
)
def track_waitlist_status_change(sender, instance, **kwargs):
    """
    Track previous status to detect status changes.

    Stores previous status in instance._previous_status for use in post_save.
    This enables us to only send notifications when status actually changes.

    Best practice: Use pre_save to capture old state before DB write.
    """
    if instance.pk:  # Existing entry
        try:
            previous = WaitlistEntry.objects.get(pk=instance.pk)
            instance._previous_status = previous.status
        except WaitlistEntry.DoesNotExist:
            instance._previous_status = None
    else:  # New entry
        instance._previous_status = None


@receiver(
    post_save,
    sender=WaitlistEntry,
    dispatch_uid="waitlist_entry_send_approval_notification"
)
def send_approval_notification_on_approve(sender, instance, created, **kwargs):
    """
    Send Telegram notification when waitlist entry is approved.

    Idempotency safeguards:
    1. Only triggers on status change (SUBMITTED -> APPROVED)
    2. Uses dispatch_uid to prevent duplicate signal connections
    3. Uses transaction.on_commit to ensure DB is committed first
    4. Celery task is idempotent (checks if already sent)

    Why transaction.on_commit?
    - Ensures database is committed before sending notification
    - If transaction rolls back, notification won't be sent
    - Prevents sending notification for uncommitted data

    Best practices:
    - Keep signal handler lightweight (no blocking I/O)
    - Delegate heavy work to Celery background task
    - Use transaction.on_commit for side effects

    References:
    - https://docs.djangoproject.com/en/stable/topics/db/transactions/#performing-actions-after-commit
    - https://hakibenita.com/django-reliable-signals
    """
    # Skip if not a status change to APPROVED
    previous_status = getattr(instance, '_previous_status', None)

    # Only send notification if status changed TO approved
    # (not if it was already approved and admin just saved again)
    if instance.status != WaitlistEntry.Status.APPROVED:
        return

    if previous_status == WaitlistEntry.Status.APPROVED:
        # Already approved, don't send duplicate notification
        logger.debug(f"Skipping duplicate approval notification for {instance.id}")
        return

    # Status changed to APPROVED - send notification
    logger.info(f"Waitlist entry {instance.id} approved, queuing notification")

    # Use transaction.on_commit to ensure DB is committed before sending
    def send_notification():
        """Send notification after transaction commits."""
        try:
            # Try Celery task first (preferred - async with retry)
            from bots.telegram.tasks import send_approval_notification_task
            send_approval_notification_task.delay(str(instance.id))
            logger.info(f"Queued approval notification task for {instance.id}")
        except ImportError:
            # Celery not available - fallback to direct send (blocking)
            logger.warning("Celery not available, sending notification synchronously")
            import asyncio
            from bots.telegram.notifications import send_approval_notification

            # Create new event loop for async function
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(send_approval_notification(instance))
            except Exception as e:
                logger.error(f"Failed to send approval notification: {e}")
            finally:
                loop.close()

    # Schedule notification to run AFTER transaction commits
    # If transaction rolls back, this won't execute
    transaction.on_commit(send_notification)


@receiver(
    post_save,
    sender=WaitlistEntry,
    dispatch_uid="waitlist_entry_send_submission_confirmation"
)
def send_submission_confirmation_on_submit(sender, instance, created, **kwargs):
    """
    Send waitlist confirmation when user submits X username.

    Triggered when status changes to SUBMITTED.
    Same safeguards as approval notification.
    """
    previous_status = getattr(instance, '_previous_status', None)

    # Only send if status changed TO submitted
    if instance.status != WaitlistEntry.Status.SUBMITTED:
        return

    if previous_status == WaitlistEntry.Status.SUBMITTED:
        # Already submitted, don't send duplicate
        logger.debug(f"Skipping duplicate submission confirmation for {instance.id}")
        return

    logger.info(f"Waitlist entry {instance.id} submitted, queuing confirmation")

    def send_confirmation():
        """Send confirmation after transaction commits."""
        try:
            from bots.telegram.tasks import send_waitlist_confirmation_task
            send_waitlist_confirmation_task.delay(str(instance.id))
            logger.info(f"Queued waitlist confirmation task for {instance.id}")
        except ImportError:
            logger.warning("Celery not available, sending confirmation synchronously")
            import asyncio
            from bots.telegram.notifications import send_waitlist_confirmation

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(send_waitlist_confirmation(instance))
            except Exception as e:
                logger.error(f"Failed to send waitlist confirmation: {e}")
            finally:
                loop.close()

    transaction.on_commit(send_confirmation)