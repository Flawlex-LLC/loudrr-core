"""
ECHO Telegram Bot.

Provides the main bot setup and configuration.
"""
import logging
import os

from django.conf import settings
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from telegram.request import HTTPXRequest

from .handlers import (
    start_handler,
    balance_handler,
    stats_handler,
    post_handler,
    feed_handler,
    leaderboard_handler,
    help_handler,
    callback_handler,
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
    application.add_handler(CommandHandler("balance", balance_handler))
    application.add_handler(CommandHandler("stats", stats_handler))
    application.add_handler(CommandHandler("post", post_handler))
    application.add_handler(CommandHandler("feed", feed_handler))
    application.add_handler(CommandHandler("leaderboard", leaderboard_handler))

    # Callback query handler for inline buttons
    application.add_handler(CallbackQueryHandler(callback_handler))

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
