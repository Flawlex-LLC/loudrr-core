"""
Celery tasks for Telegram bot notifications.

DEPRECATED: These tasks are now handled by OutboxService.
See core/services/outbox.py for the new implementation.

These tasks are kept for backwards compatibility in case there are
pending tasks in the queue. They will be removed in a future release.
"""
import asyncio
import logging
import warnings

from celery import shared_task

from core.models import WaitlistEntry

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_approval_notification_task(self, entry_id: str):
    """
    DEPRECATED: Use OutboxService.queue_waitlist_approved() instead.

    Send approval notification to a waitlist entry via Telegram.
    This task is kept for backwards compatibility.
    """
    warnings.warn(
        "send_approval_notification_task is deprecated. "
        "Use OutboxService.queue_waitlist_approved() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    from bots.telegram.notifications import send_approval_notification

    try:
        entry = WaitlistEntry.objects.get(id=entry_id)

        if not entry.telegram_id:
            logger.warning(f"Entry {entry_id} has no telegram_id, skipping notification")
            return

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(send_approval_notification(entry))
            if result:
                logger.info(f"[DEPRECATED] Sent approval notification for entry {entry_id}")
            else:
                logger.warning(f"Failed to send notification for entry {entry_id}")
        finally:
            loop.close()

    except WaitlistEntry.DoesNotExist:
        logger.error(f"WaitlistEntry {entry_id} not found")
    except Exception as e:
        logger.error(f"Error sending approval notification: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_waitlist_confirmation_task(self, entry_id: str):
    """
    DEPRECATED: Use OutboxService.queue_waitlist_submitted() instead.

    Send waitlist confirmation to a user after they submit X username.
    This task is kept for backwards compatibility.
    """
    warnings.warn(
        "send_waitlist_confirmation_task is deprecated. "
        "Use OutboxService.queue_waitlist_submitted() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    from bots.telegram.notifications import send_waitlist_confirmation

    try:
        entry = WaitlistEntry.objects.get(id=entry_id)

        if not entry.telegram_id:
            logger.warning(f"Entry {entry_id} has no telegram_id, skipping confirmation")
            return

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(send_waitlist_confirmation(entry))
            if result:
                logger.info(f"[DEPRECATED] Sent waitlist confirmation for entry {entry_id}")
            else:
                logger.warning(f"Failed to send confirmation for entry {entry_id}")
        finally:
            loop.close()

    except WaitlistEntry.DoesNotExist:
        logger.error(f"WaitlistEntry {entry_id} not found")
    except Exception as e:
        logger.error(f"Error sending waitlist confirmation: {e}")
        raise self.retry(exc=e)
