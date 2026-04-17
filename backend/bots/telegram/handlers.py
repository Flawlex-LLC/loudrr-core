"""
Telegram bot command handlers.

Commands: /start, /help, /launch
/start handles referral deep links (ref_CODE) and shows "Open Loudrr" button.
"""
import logging

from django.conf import settings
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes

from core.models import User

logger = logging.getLogger(__name__)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - welcome message with Open Loudrr button."""
    telegram_user = update.effective_user
    miniapp_url = getattr(settings, 'MINIAPP_URL', 'http://localhost:3000')

    # Check for referral code in start param (e.g., /start ref_ABC123)
    ref_code = None
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        if arg.startswith('ref_'):
            ref_code = arg.replace('ref_', '')
            logger.info(f"Referral code detected: {ref_code} for telegram_id: {telegram_user.id}")

    # Check if user already has an account (approved user)
    try:
        user = User.objects.get(telegram_id=telegram_user.id)
        welcome_text = (
            f"Welcome back, {telegram_user.first_name}!\n\n"
            f"Karma: {user.credits}\n"
            f"Streak: {user.current_streak} days\n\n"
            "Tap below to start engaging!"
        )

        keyboard = [[InlineKeyboardButton(
            "Open Loudrr",
            web_app=WebAppInfo(url=miniapp_url)
        )]]

        await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))

    except User.DoesNotExist:
        # New user - show Open App button (they'll register in the mini app)
        # Pass referral code via URL if present
        app_url = miniapp_url
        if ref_code:
            app_url = f"{miniapp_url}?ref={ref_code}"

        welcome_text = (
            f"Welcome to Loudrr, {telegram_user.first_name}!\n\n"
            "Engage with posts on X, earn karma, and grow your reach.\n\n"
            "Tap below to get started:"
        )

        keyboard = [[InlineKeyboardButton(
            "Open Loudrr",
            web_app=WebAppInfo(url=app_url)
        )]]

        await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    miniapp_url = getattr(settings, 'MINIAPP_URL', 'http://localhost:3000')

    help_text = (
        "🔊 *Loudrr Commands*\n\n"
        "/start - Start the bot\n"
        "/launch - Get a pinnable 'Open App' message\n"
        "/help - Show this message\n\n"
        "*How it works:*\n"
        "1. Open the mini app using the button below\n"
        "2. Engage with posts on X\n"
        "3. Earn karma for each engagement\n"
        "4. Spend karma to promote your own posts!"
    )

    keyboard = [[InlineKeyboardButton(
        "Open Loudrr",
        web_app=WebAppInfo(url=miniapp_url)
    )]]

    await update.message.reply_text(
        help_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def launch_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /launch command - sends a pinnable message with Play Now button.

    This creates a promotional message with a Web App button that can be pinned in groups.
    """
    miniapp_url = getattr(settings, 'MINIAPP_URL', 'http://localhost:3000')

    text = (
        "🔊 *Loudrr - Earn by Engaging*\n\n"
        "Reply to posts, earn karma, get replies on yours.\n"
        "Join the community and start earning!"
    )

    keyboard = [
        [InlineKeyboardButton(
            "🚀 Play Now",
            web_app=WebAppInfo(url=miniapp_url)
        )],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")


