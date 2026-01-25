"""
Loudrr Telegram Bot.

Provides the main bot setup and configuration.
"""
import logging
import os

# Django setup must happen before importing Django models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'echo.settings')
import django
django.setup()

from django.conf import settings
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.request import HTTPXRequest

from .handlers import (
    start_handler,
    help_handler,
    callback_handler,
    message_handler,
    launch_handler,
)

logger = logging.getLogger(__name__)


def create_bot() -> Application:
    """Create and configure the Telegram bot application."""
    # Check for proxy configuration
    proxy_url = os.environ.get("TELEGRAM_PROXY_URL")

    builder = Application.builder().token(settings.TELEGRAM_BOT_TOKEN)

    if proxy_url:
        logger.info(f"Using proxy: {proxy_url}")
        request = HTTPXRequest(proxy=proxy_url, connect_timeout=30.0, read_timeout=30.0)
        builder = builder.request(request)
    else:
        # Increase timeouts for slow connections
        request = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0)
        builder = builder.request(request)

    application = builder.build()

    # Command handlers
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("launch", launch_handler))

    # Callback query handler for inline buttons
    application.add_handler(CallbackQueryHandler(callback_handler))

    # Message handler for waitlist X username collection
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Error handler
    application.add_error_handler(error_handler)

    return application


async def error_handler(update, context):
    """Handle errors in the bot."""
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)

    if update and update.effective_message:
        await update.effective_message.reply_text(
            "Sorry, something went wrong. Please try again later."
        )


if __name__ == "__main__":
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    logger.info("Starting Loudrr Telegram Bot...")
    app = create_bot()
    app.run_polling(drop_pending_updates=True)
