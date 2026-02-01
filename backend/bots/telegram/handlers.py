"""
Telegram bot command handlers.

All user-facing commands and callback handlers.
Waitlist flow: /start join_TOKEN → Apply → X username → Waitlist card image
"""
import logging
import re

from django.conf import settings
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes

from core.models import User, WaitlistEntry

logger = logging.getLogger(__name__)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - onboarding or referral deep link."""
    telegram_user = update.effective_user
    miniapp_url = getattr(settings, 'MINIAPP_URL', 'http://localhost:3000')

    # Check for referral code in start param (e.g., /start ref_ABC123)
    ref_code = None
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        if arg.startswith('ref_'):
            ref_code = arg.replace('ref_', '')
            logger.info(f"Referral code detected: {ref_code} for telegram_id: {telegram_user.id}")

    # First check if user already has an account (approved user)
    try:
        user = User.objects.get(telegram_id=telegram_user.id)
        # Existing user - show welcome back
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


async def handle_waitlist_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle waitlist deep link - /start join_TOKEN.

    Flow:
    1. User clicks link from loudrr.com → arrives here
    2. Validate token, link Telegram account
    3. Show "Complete Registration" button that opens mini app
    4. Mini app shows form with email pre-filled
    5. User enters X username → submits
    6. Mini app shows success card with share buttons
    """
    telegram_user = update.effective_user
    miniapp_url = getattr(settings, 'MINIAPP_URL', 'http://localhost:3000')

    # First check if user already has an approved account
    # If so, show welcome back instead of waitlist flow
    try:
        user = User.objects.get(telegram_id=telegram_user.id)
        # User is already approved - show welcome back
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
        return
    except User.DoesNotExist:
        pass  # Not an approved user, continue with waitlist flow

    token = context.args[0].replace('join_', '')

    logger.info(
        "Waitlist join attempt",
        extra={
            'telegram_id': telegram_user.id,
            'telegram_username': telegram_user.username,
            'token': token[:8] + '...',  # Partial for privacy
        }
    )

    try:
        entry = WaitlistEntry.objects.get(join_token=token)
    except WaitlistEntry.DoesNotExist:
        logger.warning("Waitlist join failed: invalid token", extra={'token': token[:8]})
        await update.message.reply_text(
            "❌ Invalid or expired link.\n\n"
            "Please try again from loudrr.com"
        )
        return

    # Check if already approved
    if entry.status == WaitlistEntry.Status.APPROVED:
        miniapp_url = getattr(settings, 'MINIAPP_URL', 'http://localhost:3000')
        keyboard = [[InlineKeyboardButton(
            "🚀 Open Loudrr",
            web_app=WebAppInfo(url=miniapp_url)
        )]]
        await update.message.reply_text(
            "✅ You're already approved!\n\n"
            "Tap below to open Loudrr.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Check if X username already submitted (already on waitlist)
    if entry.x_username and entry.status == WaitlistEntry.Status.SUBMITTED:
        # Send the waitlist card again
        from .image_utils import create_waitlist_card

        try:
            card_image = create_waitlist_card(
                x_username=entry.x_username,
                display_name=entry.x_display_name,
                followers_count=entry.x_followers_count,
                avatar_url=entry.x_avatar_url,
                is_verified=entry.x_is_verified,
                telegram_username=telegram_user.username or "",
            )

            caption = (
                f"*You're on the Loudrr waitlist!*\n\n"
                f"📧 {entry.email}\n"
                f"🐦 @{entry.x_username}\n\n"
                "_We'll notify you here when you get access._"
            )

            await update.message.reply_photo(
                photo=card_image,
                caption=caption,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send waitlist card: {e}")
            await update.message.reply_text(
                f"✅ You're on the waitlist!\n\n"
                f"📧 {entry.email}\n"
                f"🐦 @{entry.x_username}\n\n"
                "We'll notify you here when you get access."
            )
        return

    # Check if this telegram_id is already linked to a DIFFERENT entry
    existing_entry = WaitlistEntry.objects.filter(telegram_id=telegram_user.id).first()
    if existing_entry and existing_entry.id != entry.id:
        # User already registered with a different email
        logger.info(
            f"Telegram {telegram_user.id} already linked to different entry {existing_entry.id}"
        )
        await update.message.reply_text(
            f"✅ You're already on the waitlist!\n\n"
            f"📧 {existing_entry.email}\n"
            f"🐦 @{existing_entry.x_username or 'Not set'}\n\n"
            "_We'll notify you here when you get access._"
        )
        return

    # Link Telegram to entry (only if not already linked)
    if entry.telegram_id != telegram_user.id:
        entry.telegram_id = telegram_user.id
        entry.telegram_username = telegram_user.username or ""
        entry.telegram_display_name = telegram_user.full_name or ""
        entry.save(update_fields=[
            'telegram_id', 'telegram_username', 'telegram_display_name', 'updated_at'
        ])

    logger.info(
        "Waitlist Telegram linked",
        extra={
            'entry_id': str(entry.id),
            'telegram_id': telegram_user.id,
            'email': entry.email,
        }
    )

    # Show "Complete Registration" button that opens mini app
    # Pass join token via URL so mini app can complete registration
    registration_url = f"{miniapp_url}/waitlist?token={entry.join_token}"

    keyboard = [[InlineKeyboardButton(
        "✨ Complete Registration",
        web_app=WebAppInfo(url=registration_url)
    )]]

    await update.message.reply_text(
        f"👋 Welcome to Loudrr!\n\n"
        f"📧 Email: {entry.email}\n\n"
        "Tap below to complete your application:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_waitlist_x_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle X username collection for waitlist application.

    Called when user sends a message while we're collecting their X username.
    Validates, fetches profile info, saves, and sends confirmation.
    Card is sent asynchronously via OutboxEvent (triggered by signal).
    """
    from django.utils import timezone
    from core.services.twitter_verification import twitter_verification

    entry_id = context.user_data.pop('collecting_x_username')
    x_username = update.message.text.strip().lstrip('@')
    telegram_user = update.effective_user

    logger.info(
        "Waitlist X username submitted",
        extra={
            'entry_id': entry_id,
            'x_username': x_username,
            'telegram_id': telegram_user.id,
        }
    )

    # Validate format
    if not re.match(r'^[a-zA-Z0-9_]{1,15}$', x_username):
        await update.message.reply_text(
            "❌ Invalid username format.\n\n"
            "Please send a valid X/Twitter username\n"
            "(letters, numbers, underscores only):"
        )
        context.user_data['collecting_x_username'] = entry_id
        return

    try:
        entry = WaitlistEntry.objects.get(id=entry_id)
    except WaitlistEntry.DoesNotExist:
        logger.error(f"Waitlist entry not found: {entry_id}")
        await update.message.reply_text(
            "❌ Application not found.\n\n"
            "Please try again from loudrr.com"
        )
        return

    # Check if X username already used in waitlist
    if WaitlistEntry.objects.filter(x_username__iexact=x_username).exclude(id=entry_id).exists():
        await update.message.reply_text(
            "❌ This X account is already on the waitlist.\n\n"
            "Please use a different account:"
        )
        context.user_data['collecting_x_username'] = entry_id
        return

    # Check if X username already registered as a user
    if User.objects.filter(x_username__iexact=x_username).exists():
        await update.message.reply_text(
            "❌ This X account is already registered.\n\n"
            "Please use a different account:"
        )
        context.user_data['collecting_x_username'] = entry_id
        return

    # Send "fetching profile" message
    fetching_msg = await update.message.reply_text("🔄 Fetching your X profile...")

    # Fetch X profile info
    x_info = twitter_verification.get_user_info(x_username)

    # Save X username, profile data, and update status
    entry.x_username = x_username
    entry.status = WaitlistEntry.Status.SUBMITTED

    update_fields = ['x_username', 'status', 'updated_at']

    if x_info:
        entry.x_display_name = x_info.get("display_name", "")
        entry.x_followers_count = x_info.get("followers_count")
        entry.x_avatar_url = x_info.get("avatar_url", "")
        entry.x_is_verified = x_info.get("is_verified", False)
        entry.x_fetched_at = timezone.now()
        update_fields.extend([
            'x_display_name', 'x_followers_count', 'x_avatar_url',
            'x_is_verified', 'x_fetched_at'
        ])

    entry.save(update_fields=update_fields)

    logger.info(
        "Waitlist application completed",
        extra={
            'entry_id': str(entry.id),
            'email': entry.email,
            'x_username': x_username,
            'followers_count': x_info.get("followers_count") if x_info else None,
        }
    )

    # Delete the "fetching" message
    try:
        await fetching_msg.delete()
    except Exception:
        pass

    # Send simple confirmation - the card will be sent via OutboxEvent
    # (signal creates OutboxEvent when status changes to SUBMITTED)
    await update.message.reply_text(
        f"✅ *Applied successfully!*\n\n"
        f"X: @{x_username}\n\n"
        "_Your waitlist card will arrive shortly._",
        parse_mode="Markdown"
    )


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


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages - check if collecting X username for waitlist."""
    if not update.message or not update.message.text:
        return

    # Check if we're collecting X username for waitlist
    if 'collecting_x_username' in context.user_data:
        await handle_waitlist_x_username(update, context)
        return


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button callbacks."""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("apply_waitlist:"):
        # User clicked "Apply for Whitelist" button
        entry_id = data.split(":")[1]

        # Verify entry exists and is valid
        try:
            entry = WaitlistEntry.objects.get(id=entry_id)
            if entry.status == WaitlistEntry.Status.APPROVED:
                miniapp_url = getattr(settings, 'MINIAPP_URL', 'http://localhost:3000')
                keyboard = [[InlineKeyboardButton(
                    "🚀 Open Loudrr",
                    web_app=WebAppInfo(url=miniapp_url)
                )]]
                await query.edit_message_text(
                    "✅ You're already approved!\n\n"
                    "Tap below to open Loudrr.",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return

            if entry.x_username and entry.status == WaitlistEntry.Status.SUBMITTED:
                await query.edit_message_text(
                    f"✅ You're already on the waitlist!\n\n"
                    f"🐦 @{entry.x_username}\n\n"
                    "We'll notify you here when you get access."
                )
                return

        except WaitlistEntry.DoesNotExist:
            await query.edit_message_text(
                "❌ Application not found.\n\n"
                "Please try again from loudrr.com"
            )
            return

        # Store state for collecting X username
        context.user_data['collecting_x_username'] = entry_id

        await query.edit_message_text(
            "✨ *Apply for Whitelist*\n\n"
            "Please send your X/Twitter username:\n\n"
            "Example: `@yourusername` or `yourusername`",
            parse_mode="Markdown"
        )
