"""
Telegram bot notification utilities.

Send notifications to users for various events (waitlist approval, etc).
"""
import logging
from django.conf import settings
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application

from core.models import WaitlistEntry

logger = logging.getLogger(__name__)


async def send_approval_notification(entry: WaitlistEntry) -> bool:
    """
    Send approval notification to a waitlist entry.

    Called when admin approves a waitlist entry.
    Sends a card image with "Open Loudrr" button.

    Args:
        entry: Approved WaitlistEntry instance

    Returns:
        True if notification sent successfully, False otherwise
    """
    from .image_utils import create_approval_card
    from telegram import WebAppInfo

    if not entry.telegram_id:
        logger.warning(f"Cannot send notification: entry {entry.id} has no telegram_id")
        return False

    try:
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        miniapp_url = getattr(settings, 'MINIAPP_URL', 'http://localhost:3000')

        # Generate approval card
        card_image = create_approval_card(x_username=entry.x_username)

        # Keyboard with Open Loudrr button
        keyboard = [[InlineKeyboardButton(
            "Open Loudrr",
            web_app=WebAppInfo(url=miniapp_url)
        )]]

        await bot.send_photo(
            chat_id=entry.telegram_id,
            photo=card_image,
            caption=(
                "*Welcome to Loudrr!*\n\n"
                "You've been approved! Tap below to start.\n\n"
                "_Earn karma by engaging. Spend karma to grow._"
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        logger.info(f"Sent approval notification to {entry.telegram_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to send approval notification to {entry.telegram_id}: {e}")
        return False


async def send_waitlist_confirmation(entry: WaitlistEntry) -> bool:
    """
    Send waitlist confirmation to a user.

    Called after user submits X username in bot.

    Args:
        entry: WaitlistEntry instance with x_username set

    Returns:
        True if notification sent successfully, False otherwise
    """
    from .image_utils import create_waitlist_card

    if not entry.telegram_id:
        logger.warning(f"Cannot send confirmation: entry {entry.id} has no telegram_id")
        return False

    try:
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

        # Generate waitlist card
        card_image = create_waitlist_card(x_username=entry.x_username)

        await bot.send_photo(
            chat_id=entry.telegram_id,
            photo=card_image,
            caption=(
                "*You're on the Loudrr waitlist!*\n\n"
                f"X: @{entry.x_username}\n\n"
                "_We'll notify you here when you get access._"
            ),
            parse_mode="Markdown"
        )

        logger.info(f"Sent waitlist confirmation to {entry.telegram_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to send waitlist confirmation to {entry.telegram_id}: {e}")
        return False
