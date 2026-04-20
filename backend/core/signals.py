"""
Django signals for core app.

Best practices followed:
1. dispatch_uid to prevent duplicate signal connections
2. Transactional Outbox pattern for reliable notifications
3. Idempotency checks to prevent duplicate messages
4. Lightweight handlers - heavy work delegated to django-q via OutboxEvent

The Transactional Outbox Pattern:
- OutboxEvent is created INSIDE the same transaction as the model change
- If transaction rolls back, the event also rolls back (no orphan notifications)
- A separate django-q worker processes events from the outbox table
- This guarantees exactly-once delivery semantics

References:
- https://hakibenita.com/django-reliable-signals
- https://docs.djangoproject.com/en/stable/topics/signals/
- https://microservices.io/patterns/data/transactional-outbox.html
- https://www.vintasoftware.com/blog/celery-wild-tips-and-tricks-run-async-tasks-real-world
"""
import logging
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import WaitlistEntry, OutboxEvent

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

    Uses Transactional Outbox pattern:
    1. OutboxEvent created in SAME transaction as WaitlistEntry update
    2. If transaction rolls back, event also rolls back (no orphan notifications)
    3. django-q worker processes events from outbox table
    4. Guarantees exactly-once delivery

    Idempotency safeguards:
    1. Only triggers on status change (SUBMITTED -> APPROVED)
    2. Uses dispatch_uid to prevent duplicate signal connections
    3. OutboxEvent includes idempotency_key to prevent duplicates

    References:
    - https://microservices.io/patterns/data/transactional-outbox.html
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

    # Status changed to APPROVED - create OutboxEvent
    logger.info(f"Waitlist entry {instance.id} approved, creating outbox event")

    # Create OutboxEvent in the SAME transaction as the model change
    # This is the key to the transactional outbox pattern
    from core.services.outbox import OutboxService
    OutboxService.queue_waitlist_approved(
        entry_id=instance.id,
        telegram_id=instance.telegram_id,
        x_username=instance.x_username,
    )

    # Optionally trigger immediate processing after commit
    # (events will also be picked up by the periodic django-q schedule)
    def trigger_processing():
        """Trigger immediate event processing after transaction commits."""
        try:
            from django_q.tasks import async_task
            async_task("core.tasks.process_pending_outbox_events", batch_size=10)
        except Exception as e:
            logger.warning(f"Failed to trigger immediate processing: {e}")
            # Not critical - periodic task will pick it up

    transaction.on_commit(trigger_processing)


@receiver(
    post_save,
    sender=WaitlistEntry,
    dispatch_uid="waitlist_entry_send_submission_confirmation"
)
def send_submission_confirmation_on_submit(sender, instance, created, **kwargs):
    """
    Send waitlist confirmation when entry is created as SUBMITTED.

    Uses Transactional Outbox pattern:
    1. OutboxEvent created in SAME transaction as WaitlistEntry creation
    2. If transaction rolls back, event also rolls back
    3. django-q worker processes events from outbox table

    Fires on create (since entries are created directly as SUBMITTED,
    _previous_status is None which triggers the notification).
    """
    previous_status = getattr(instance, '_previous_status', None)

    # Only send if status changed TO submitted
    if instance.status != WaitlistEntry.Status.SUBMITTED:
        return

    if previous_status == WaitlistEntry.Status.SUBMITTED:
        # Already submitted, don't send duplicate
        logger.debug(f"Skipping duplicate submission confirmation for {instance.id}")
        return

    logger.info(f"Waitlist entry {instance.id} submitted, creating outbox event")

    # Create OutboxEvent in the SAME transaction as the model change
    from core.services.outbox import OutboxService
    OutboxService.queue_waitlist_submitted(
        entry_id=instance.id,
        telegram_id=instance.telegram_id,
        x_username=instance.x_username,
        email=instance.email,
    )

    # Optionally trigger immediate processing after commit
    def trigger_processing():
        """Trigger immediate event processing after transaction commits."""
        try:
            from django_q.tasks import async_task
            async_task("core.tasks.process_pending_outbox_events", batch_size=10)
        except Exception as e:
            logger.warning(f"Failed to trigger immediate processing: {e}")

    transaction.on_commit(trigger_processing)


@receiver(
    post_save,
    sender=WaitlistEntry,
    dispatch_uid="increment_referral_on_waitlist_approve"
)
def increment_referral_on_approve(sender, instance, created, **kwargs):
    """
    Increment referrer's total_referrals when referee is approved.

    Uses transaction.on_commit to ensure DB is committed first.
    This happens AFTER the approval notification signal.
    """
    previous_status = getattr(instance, '_previous_status', None)

    # Only trigger on status change TO approved
    if instance.status != WaitlistEntry.Status.APPROVED:
        return
    if previous_status == WaitlistEntry.Status.APPROVED:
        return

    # Skip if no referrer
    if not instance.referrer_id:
        return

    def increment_count():
        from core.services.referral import ReferralService
        try:
            ReferralService.increment_referral_count(instance)
            logger.info(
                f"Incremented referral count for referrer of entry {instance.id}"
            )
        except Exception as e:
            logger.error(
                "referral_increment_failed",
                extra={
                    "entry_id": str(instance.id),
                    "error": str(e)
                }
            )

    transaction.on_commit(increment_count)