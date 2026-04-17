"""
Outbox Service for reliable notification delivery.

The Outbox Pattern ensures notifications are never lost:
1. Business logic + OutboxEvent are saved in same transaction
2. Celery worker polls for PENDING events
3. Events are processed and marked SENT or retried

Usage:
    from core.services.outbox import OutboxService

    with transaction.atomic():
        # Your business logic
        user.credits += 10
        user.save()

        # Queue notification (inside same transaction!)
        OutboxService.queue_telegram_notification(
            telegram_id=user.telegram_id,
            message="You earned 10 karma!",
            reference_type="credits_earned",
            reference_id=str(user.id),
        )
    # Both committed atomically - notification guaranteed
"""
import logging
from typing import Optional
from uuid import UUID

from django.db import transaction

from core.models import OutboxEvent

logger = logging.getLogger(__name__)


class OutboxService:
    """Service for creating OutboxEvents within transactions."""

    @staticmethod
    def queue_telegram_notification(
        telegram_id: int,
        message: str,
        message_type: str = "text",
        reference_type: str = "",
        reference_id: str = "",
        extra_data: Optional[dict] = None,
    ) -> OutboxEvent:
        """
        Queue a Telegram notification for delivery.

        Args:
            telegram_id: Telegram user ID to send to
            message: Message content
            message_type: "text", "photo", "card" etc.
            reference_type: What triggered this (e.g., "waitlist_approval")
            reference_id: ID of the related object
            extra_data: Additional data for the notification

        Returns:
            Created OutboxEvent

        Note: MUST be called inside transaction.atomic() block!
        """
        payload = {
            "telegram_id": telegram_id,
            "message": message,
            "message_type": message_type,
            "reference_type": reference_type,
            "reference_id": reference_id,
            **(extra_data or {}),
        }

        event = OutboxEvent.objects.create(
            event_type=OutboxEvent.EventType.TELEGRAM_NOTIFY,
            payload=payload,
        )

        logger.info(
            "Outbox event created",
            extra={
                "event_id": str(event.id),
                "event_type": event.event_type,
                "telegram_id": telegram_id,
                "reference_type": reference_type,
            }
        )

        return event

    @staticmethod
    def queue_waitlist_approved(
        entry_id: UUID,
        telegram_id: int,
        x_username: str,
    ) -> OutboxEvent:
        """
        Queue waitlist approval notification.

        Args:
            entry_id: WaitlistEntry ID
            telegram_id: User's Telegram ID
            x_username: User's X username

        Returns:
            Created OutboxEvent
        """
        payload = {
            "entry_id": str(entry_id),
            "telegram_id": telegram_id,
            "x_username": x_username,
        }

        event = OutboxEvent.objects.create(
            event_type=OutboxEvent.EventType.WAITLIST_APPROVED,
            payload=payload,
        )

        logger.info(
            "Waitlist approval event created",
            extra={
                "event_id": str(event.id),
                "entry_id": str(entry_id),
                "telegram_id": telegram_id,
            }
        )

        return event

    @staticmethod
    def queue_waitlist_submitted(
        entry_id: UUID,
        telegram_id: int,
        x_username: str,
        email: str,
    ) -> OutboxEvent:
        """
        Queue waitlist submission confirmation notification.

        Args:
            entry_id: WaitlistEntry ID
            telegram_id: User's Telegram ID
            x_username: User's X username
            email: User's email

        Returns:
            Created OutboxEvent
        """
        payload = {
            "entry_id": str(entry_id),
            "telegram_id": telegram_id,
            "x_username": x_username,
            "email": email,
        }

        event = OutboxEvent.objects.create(
            event_type=OutboxEvent.EventType.WAITLIST_SUBMITTED,
            payload=payload,
        )

        logger.info(
            "Waitlist submission event created",
            extra={
                "event_id": str(event.id),
                "entry_id": str(entry_id),
                "telegram_id": telegram_id,
            }
        )

        return event

    @staticmethod
    def queue_tweetscout_fetch(
        user_id: UUID,
    ) -> OutboxEvent:
        """
        Queue TweetScout data fetch.

        Args:
            user_id: User ID to fetch data for

        Returns:
            Created OutboxEvent
        """
        payload = {
            "user_id": str(user_id),
        }

        event = OutboxEvent.objects.create(
            event_type=OutboxEvent.EventType.TWEETSCOUT_FETCH,
            payload=payload,
        )

        logger.info(
            "TweetScout fetch event created",
            extra={
                "event_id": str(event.id),
                "user_id": str(user_id),
            }
        )

        return event

    @staticmethod
    def queue_credits_earned(
        user_id: UUID,
        telegram_id: int,
        amount: str,
        reason: str,
    ) -> OutboxEvent:
        """
        Queue credits earned notification.

        Args:
            user_id: User ID
            telegram_id: User's Telegram ID
            amount: Amount earned (as string for JSON)
            reason: Why credits were earned

        Returns:
            Created OutboxEvent
        """
        payload = {
            "user_id": str(user_id),
            "telegram_id": telegram_id,
            "amount": amount,
            "reason": reason,
        }

        event = OutboxEvent.objects.create(
            event_type=OutboxEvent.EventType.CREDITS_EARNED,
            payload=payload,
        )

        logger.info(
            "Credits earned event created",
            extra={
                "event_id": str(event.id),
                "user_id": str(user_id),
                "amount": amount,
            }
        )

        return event

    @staticmethod
    def queue_post_completed(
        post_id: UUID,
        user_id: UUID,
        telegram_id: int,
    ) -> OutboxEvent:
        """
        Queue post completed notification.

        Args:
            post_id: Post ID
            user_id: Creator's User ID
            telegram_id: Creator's Telegram ID

        Returns:
            Created OutboxEvent
        """
        payload = {
            "post_id": str(post_id),
            "user_id": str(user_id),
            "telegram_id": telegram_id,
        }

        event = OutboxEvent.objects.create(
            event_type=OutboxEvent.EventType.POST_COMPLETED,
            payload=payload,
        )

        logger.info(
            "Post completed event created",
            extra={
                "event_id": str(event.id),
                "post_id": str(post_id),
            }
        )

        return event

    @staticmethod
    def queue_campaign_winner(
        campaign_id: UUID,
        user_id: UUID,
        telegram_id: int,
        prize_description: str,
    ) -> OutboxEvent:
        """
        Queue campaign winner notification.

        Args:
            campaign_id: Campaign ID
            user_id: Winner's User ID
            telegram_id: Winner's Telegram ID
            prize_description: Description of the prize

        Returns:
            Created OutboxEvent
        """
        payload = {
            "campaign_id": str(campaign_id),
            "user_id": str(user_id),
            "telegram_id": telegram_id,
            "prize_description": prize_description,
        }

        event = OutboxEvent.objects.create(
            event_type=OutboxEvent.EventType.CAMPAIGN_WINNER,
            payload=payload,
        )

        logger.info(
            "Campaign winner event created",
            extra={
                "event_id": str(event.id),
                "campaign_id": str(campaign_id),
                "user_id": str(user_id),
            }
        )

        return event

    @staticmethod
    @transaction.atomic
    def process_event(event: OutboxEvent) -> bool:
        """
        Process a single OutboxEvent.

        Args:
            event: The event to process

        Returns:
            True if successful, False otherwise
        """
        import asyncio

        # Lock the event row to prevent concurrent processing
        event = OutboxEvent.objects.select_for_update().get(pk=event.pk)

        if event.status != OutboxEvent.Status.PENDING:
            logger.debug(f"Event {event.id} already processed, skipping")
            return True

        event.mark_processing()

        try:
            if event.event_type == OutboxEvent.EventType.WAITLIST_APPROVED:
                success = OutboxService._process_waitlist_approved(event)
            elif event.event_type == OutboxEvent.EventType.WAITLIST_SUBMITTED:
                success = OutboxService._process_waitlist_submitted(event)
            elif event.event_type == OutboxEvent.EventType.TWEETSCOUT_FETCH:
                success = OutboxService._process_tweetscout_fetch(event)
            elif event.event_type == OutboxEvent.EventType.TELEGRAM_NOTIFY:
                success = OutboxService._process_telegram_notify(event)
            elif event.event_type == OutboxEvent.EventType.CREDITS_EARNED:
                success = OutboxService._process_credits_earned(event)
            elif event.event_type == OutboxEvent.EventType.POST_COMPLETED:
                success = OutboxService._process_post_completed(event)
            elif event.event_type == OutboxEvent.EventType.CAMPAIGN_WINNER:
                success = OutboxService._process_campaign_winner(event)
            else:
                logger.warning(f"Unknown event type: {event.event_type}")
                event.mark_failed(f"Unknown event type: {event.event_type}")
                return False

            if success:
                event.mark_sent()
                return True
            else:
                event.mark_failed("Processing returned False")
                return False

        except Exception as e:
            logger.error(
                f"Failed to process event {event.id}: {e}",
                exc_info=True
            )
            event.mark_failed(str(e))
            return False

    @staticmethod
    def _process_waitlist_approved(event: OutboxEvent) -> bool:
        """Process waitlist approval notification."""
        import asyncio
        from bots.telegram.notifications import send_approval_notification
        from core.models import WaitlistEntry

        entry_id = event.payload.get("entry_id")
        if not entry_id:
            logger.error("No entry_id in waitlist_approved event payload")
            return False

        try:
            entry = WaitlistEntry.objects.get(id=entry_id)
        except WaitlistEntry.DoesNotExist:
            logger.error(f"WaitlistEntry {entry_id} not found")
            return False

        # Run async notification
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(send_approval_notification(entry))
            return result
        finally:
            loop.close()

    @staticmethod
    def _process_waitlist_submitted(event: OutboxEvent) -> bool:
        """Process waitlist submission confirmation notification."""
        import asyncio
        from bots.telegram.notifications import send_waitlist_confirmation
        from core.models import WaitlistEntry

        entry_id = event.payload.get("entry_id")
        if not entry_id:
            logger.error("No entry_id in waitlist_submitted event payload")
            return False

        try:
            entry = WaitlistEntry.objects.get(id=entry_id)
        except WaitlistEntry.DoesNotExist:
            logger.error(f"WaitlistEntry {entry_id} not found")
            return False

        # Run async notification
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(send_waitlist_confirmation(entry))
            return result
        finally:
            loop.close()

    @staticmethod
    def _process_tweetscout_fetch(event: OutboxEvent) -> bool:
        """Process TweetScout data fetch."""
        from core.models import User

        user_id = event.payload.get("user_id")
        if not user_id:
            logger.error("No user_id in tweetscout_fetch event payload")
            return False

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger.error(f"User {user_id} not found")
            return False

        try:
            # Call the existing TweetScout fetch logic
            from core.tasks import _fetch_tweetscout_for_user
            _fetch_tweetscout_for_user(user)
            return True
        except Exception as e:
            logger.error(f"Failed to fetch TweetScout data: {e}")
            return False

    @staticmethod
    def _process_telegram_notify(event: OutboxEvent) -> bool:
        """Process generic Telegram notification."""
        import asyncio
        from telegram import Bot
        from django.conf import settings

        telegram_id = event.payload.get("telegram_id")
        message = event.payload.get("message")

        if not telegram_id or not message:
            logger.error("Missing telegram_id or message in payload")
            return False

        async def send_message():
            bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            await bot.send_message(chat_id=telegram_id, text=message)
            return True

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(send_message())
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
        finally:
            loop.close()

    @staticmethod
    def _process_credits_earned(event: OutboxEvent) -> bool:
        """Process credits earned notification."""
        # For now, just log - can add Telegram notification later
        logger.info(
            "Credits earned notification",
            extra={
                "user_id": event.payload.get("user_id"),
                "amount": event.payload.get("amount"),
            }
        )
        return True

    @staticmethod
    def _process_post_completed(event: OutboxEvent) -> bool:
        """Process post completed notification."""
        # For now, just log - can add Telegram notification later
        logger.info(
            "Post completed notification",
            extra={
                "post_id": event.payload.get("post_id"),
                "user_id": event.payload.get("user_id"),
            }
        )
        return True

    @staticmethod
    def _process_campaign_winner(event: OutboxEvent) -> bool:
        """Process campaign winner notification."""
        # For now, just log - can add Telegram notification later
        logger.info(
            "Campaign winner notification",
            extra={
                "campaign_id": event.payload.get("campaign_id"),
                "user_id": event.payload.get("user_id"),
            }
        )
        return True
