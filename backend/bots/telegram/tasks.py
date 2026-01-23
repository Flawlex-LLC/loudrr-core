"""
Celery tasks for Telegram bot notifications.

Handles async notification sending in background workers.
"""
import asyncio
import logging

from celery import shared_task

from core.models import WaitlistEntry

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_approval_notification_task(self, entry_id: str):
    """
    Send approval notification to a waitlist entry via Telegram.

    Called by admin panel when approving waitlist entries.
    Runs async notification function in sync Celery context.

    Args:
        entry_id: UUID string of the WaitlistEntry
    """
    from bots.telegram.notifications import send_approval_notification

    try:
        entry = WaitlistEntry.objects.get(id=entry_id)

        if not entry.telegram_id:
            logger.warning(f"Entry {entry_id} has no telegram_id, skipping notification")
            return

        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(send_approval_notification(entry))
            if result:
                logger.info(f"Sent approval notification for entry {entry_id}")
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
    Send waitlist confirmation to a user after they submit X username.

    Args:
        entry_id: UUID string of the WaitlistEntry
    """
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
                logger.info(f"Sent waitlist confirmation for entry {entry_id}")
            else:
                logger.warning(f"Failed to send confirmation for entry {entry_id}")
        finally:
            loop.close()

    except WaitlistEntry.DoesNotExist:
        logger.error(f"WaitlistEntry {entry_id} not found")
    except Exception as e:
        logger.error(f"Error sending waitlist confirmation: {e}")
        raise self.retry(exc=e)
