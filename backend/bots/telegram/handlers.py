"""
Telegram bot command handlers.

All user-facing commands and callback handlers.
"""
import re
from typing import Optional

from django.conf import settings
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from core.models import User
from core.services.credits import CreditService
from core.services.posts import PostService, get_feed_posts, get_feed_count
from core.services.gamification import get_user_stats, get_leaderboard
from core.services.engagements import get_cooldown_remaining


def get_or_create_user(telegram_id: int, display_name: str = "") -> tuple[User, bool]:
    """Get or create a user by Telegram ID."""
    try:
        user = User.objects.get(telegram_id=telegram_id)
        return user, False
    except User.DoesNotExist:
        user = User.objects.create(
            telegram_id=telegram_id,
            display_name=display_name,
        )
        return user, True


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - onboarding."""
    telegram_user = update.effective_user
    user, created = get_or_create_user(
        telegram_id=telegram_user.id,
        display_name=telegram_user.full_name or telegram_user.username or "",
    )

    if created:
        welcome_text = (
            f"Welcome to ECHO, {telegram_user.first_name}!\n\n"
            "ECHO is a credit-based engagement exchange:\n"
            "- Reply to others' posts to earn credits\n"
            "- Spend credits to get replies on your posts\n\n"
            "Start engaging now:\n"
            "/feed - Get posts to engage with\n"
            "/balance - Check your credits\n"
            "/post <link> - Submit your X post\n"
            "/help - All commands"
        )
    else:
        welcome_text = (
            f"Welcome back, {telegram_user.first_name}!\n\n"
            f"Credits: {user.credits}\n"
            f"Streak: {user.current_streak} days\n\n"
            "Use /feed to start engaging!"
        )

    await update.message.reply_text(welcome_text)


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = (
        "ECHO Commands:\n\n"
        "/balance - Check your credit balance\n"
        "/stats - Your engagement statistics\n"
        "/feed - Get posts to engage with\n"
        "/post <link> - Submit your X post (costs 40 credits)\n"
        "/leaderboard - View top engagers\n"
        "/help - Show this message\n\n"
        "How it works:\n"
        "1. Use /feed to get posts to engage with\n"
        "2. Click the link, reply on X\n"
        "3. Earn 1 credit per engagement\n"
        "4. Spend 40 credits to post your own link\n"
        "5. Get 40 guaranteed replies!"
    )
    await update.message.reply_text(help_text)


async def balance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /balance command."""
    user, _ = get_or_create_user(
        telegram_id=update.effective_user.id,
        display_name=update.effective_user.full_name or "",
    )

    credit_service = CreditService(user)
    daily_remaining = credit_service.get_daily_remaining()

    text = (
        f"Your Balance\n\n"
        f"Credits: {user.credits}\n"
        f"Daily earned: {user.daily_credits_earned}/100\n"
        f"Can earn today: {daily_remaining} more\n\n"
        f"Streak: {user.current_streak} days\n"
        f"Tier: {user.tier.title()}"
    )

    # Add multiplier info if applicable
    multiplier = user.get_tier_multiplier() * user.get_streak_multiplier()
    if multiplier > 1:
        text += f"\nEarning bonus: {multiplier:.1f}x"

    await update.message.reply_text(text)


async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command."""
    user, _ = get_or_create_user(
        telegram_id=update.effective_user.id,
        display_name=update.effective_user.full_name or "",
    )

    stats = get_user_stats(user)

    text = (
        f"Your Stats\n\n"
        f"Credits: {stats['credits']}\n"
        f"Total earned: {stats['total_earned']}\n"
        f"Total spent: {stats['total_spent']}\n\n"
        f"Engagements: {stats['total_engagements']}\n"
        f"Posts created: {stats['total_posts']}\n\n"
        f"Current streak: {stats['current_streak']} days\n"
        f"Longest streak: {stats['longest_streak']} days\n\n"
        f"Tier: {stats['tier'].title()}\n"
        f"Rank: #{stats['rank']}\n"
        f"Earning multiplier: {stats['combined_multiplier']:.2f}x"
    )

    await update.message.reply_text(text)


async def post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /post command - submit a new post."""
    user, _ = get_or_create_user(
        telegram_id=update.effective_user.id,
        display_name=update.effective_user.full_name or "",
    )

    # Check if link was provided
    if not context.args:
        await update.message.reply_text(
            "Please provide your X post link:\n\n"
            "/post https://x.com/username/status/123456789"
        )
        return

    x_link = context.args[0]

    # Validate it's an X/Twitter link
    if not re.match(r"https?://(twitter\.com|x\.com)/\w+/status/\d+", x_link):
        await update.message.reply_text(
            "Invalid link. Please provide a valid X post URL:\n"
            "https://x.com/username/status/123456789"
        )
        return

    # Check credits
    post_cost = settings.ECHO_CONFIG["POST_COST"]
    if user.credits < post_cost:
        await update.message.reply_text(
            f"Insufficient credits!\n\n"
            f"Required: {post_cost} credits\n"
            f"You have: {user.credits} credits\n\n"
            f"Use /feed to earn more credits by engaging with others' posts."
        )
        return

    # Create the post
    post_service = PostService(user)
    post = post_service.create_post(
        x_link=x_link,
        platform="telegram",
        channel_id=update.effective_chat.id,
        message_id=update.message.message_id,
    )

    await update.message.reply_text(
        f"Post submitted!\n\n"
        f"Credits deducted: {post_cost}\n"
        f"Remaining balance: {user.credits}\n\n"
        f"Your post is now live. You'll receive up to {post_cost} engagements.\n"
        f"We'll notify you when it's complete!"
    )


async def feed_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /feed command - get posts to engage with."""
    user, _ = get_or_create_user(
        telegram_id=update.effective_user.id,
        display_name=update.effective_user.full_name or "",
    )

    # Check cooldown
    cooldown = get_cooldown_remaining(user)
    if cooldown > 0:
        await update.message.reply_text(
            f"Cooldown active: {cooldown} seconds remaining.\n"
            f"Please wait before engaging again."
        )
        return

    # Get feed posts
    posts = get_feed_posts(user, limit=1)
    total_available = get_feed_count(user)

    if not posts:
        await update.message.reply_text(
            "No posts available right now.\n\n"
            "Check back later or invite others to post!"
        )
        return

    post = posts[0]
    redirect_url = post.get_redirect_url_for_user(user)

    # Create keyboard with engage button
    keyboard = [
        [InlineKeyboardButton("Click to Engage", url=redirect_url)],
        [
            InlineKeyboardButton("Skip", callback_data=f"skip:{post.id}"),
            InlineKeyboardButton("My Stats", callback_data="stats"),
            InlineKeyboardButton("Stop", callback_data="stop"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        f"Post 1 of {total_available} available\n\n"
        f"@{post.user.x_username or post.user.display_name or 'Creator'} wants engagement:\n\n"
        f"Click the button below, engage on X, then come back for the next post!"
    )

    await update.message.reply_text(text, reply_markup=reply_markup)


async def leaderboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /leaderboard command."""
    # Get period from args
    period = "all_time"
    if context.args:
        if context.args[0] in ["daily", "weekly", "all_time"]:
            period = context.args[0]

    leaders = get_leaderboard(period=period, limit=10)

    if not leaders:
        await update.message.reply_text("No leaderboard data yet!")
        return

    period_display = {
        "daily": "Today's",
        "weekly": "This Week's",
        "all_time": "All-Time",
    }

    text = f"{period_display[period]} Top Engagers\n\n"

    for entry in leaders:
        medal = ""
        if entry["rank"] == 1:
            medal = " [1st]"
        elif entry["rank"] == 2:
            medal = " [2nd]"
        elif entry["rank"] == 3:
            medal = " [3rd]"

        text += f"{entry['rank']}. {entry['display_name']}{medal}\n"
        text += f"   {entry['engagements']} engagements | {entry['streak']} day streak\n"

    keyboard = [
        [
            InlineKeyboardButton("Daily", callback_data="lb:daily"),
            InlineKeyboardButton("Weekly", callback_data="lb:weekly"),
            InlineKeyboardButton("All-Time", callback_data="lb:all_time"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(text, reply_markup=reply_markup)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button callbacks."""
    query = update.callback_query
    await query.answer()

    data = query.data
    user, _ = get_or_create_user(
        telegram_id=update.effective_user.id,
        display_name=update.effective_user.full_name or "",
    )

    if data == "stats":
        # Show stats
        stats = get_user_stats(user)
        text = (
            f"Credits: {stats['credits']} | "
            f"Streak: {stats['current_streak']} days | "
            f"Rank: #{stats['rank']}"
        )
        await query.edit_message_text(text)

    elif data == "stop":
        await query.edit_message_text(
            "Engagement session ended.\n\n"
            "Use /feed to start again anytime!"
        )

    elif data.startswith("skip:"):
        # Skip this post and show next
        posts = get_feed_posts(user, limit=1)
        total_available = get_feed_count(user)

        if not posts:
            await query.edit_message_text("No more posts available!")
            return

        post = posts[0]
        redirect_url = post.get_redirect_url_for_user(user)

        keyboard = [
            [InlineKeyboardButton("Click to Engage", url=redirect_url)],
            [
                InlineKeyboardButton("Skip", callback_data=f"skip:{post.id}"),
                InlineKeyboardButton("My Stats", callback_data="stats"),
                InlineKeyboardButton("Stop", callback_data="stop"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            f"Post 1 of {total_available} available\n\n"
            f"@{post.user.x_username or post.user.display_name or 'Creator'} wants engagement:"
        )

        await query.edit_message_text(text, reply_markup=reply_markup)

    elif data.startswith("lb:"):
        # Leaderboard period switch
        period = data.split(":")[1]
        leaders = get_leaderboard(period=period, limit=10)

        period_display = {
            "daily": "Today's",
            "weekly": "This Week's",
            "all_time": "All-Time",
        }

        text = f"{period_display[period]} Top Engagers\n\n"

        for entry in leaders:
            text += f"{entry['rank']}. {entry['display_name']}\n"
            text += f"   {entry['engagements']} engagements\n"

        keyboard = [
            [
                InlineKeyboardButton("Daily", callback_data="lb:daily"),
                InlineKeyboardButton("Weekly", callback_data="lb:weekly"),
                InlineKeyboardButton("All-Time", callback_data="lb:all_time"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup)
