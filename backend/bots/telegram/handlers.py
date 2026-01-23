"""
Telegram bot command handlers.

All user-facing commands and callback handlers.
"""
import re
from typing import Optional

from django.conf import settings
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes

from core.models import User, WaitlistEntry
from core.services.credits import CreditService
from core.services.posts import PostService, get_feed_posts, get_feed_count
from core.services.gamification import get_user_stats, get_leaderboard
from core.services.engagements import get_cooldown_remaining, record_button_engagement
from posts.models import Post


def get_or_create_user(telegram_id: int, display_name: str = "", username: str = "") -> tuple[User, bool]:
    """Get or create a user by Telegram ID."""
    try:
        user = User.objects.get(telegram_id=telegram_id)
        # Update username if changed
        if username and user.telegram_username != username:
            user.telegram_username = username
            user.save(update_fields=["telegram_username"])
        return user, False
    except User.DoesNotExist:
        user = User.objects.create(
            telegram_id=telegram_id,
            display_name=display_name,
            telegram_username=username,
        )
        return user, True


def get_user_by_username(username: str) -> Optional[User]:
    """Get a user by Telegram username."""
    # Remove @ if present
    username = username.lstrip("@")
    try:
        return User.objects.get(telegram_username__iexact=username)
    except User.DoesNotExist:
        return None


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - onboarding or waitlist deep link."""
    telegram_user = update.effective_user

    # Check for waitlist deep link: /start join_TOKEN
    if context.args and context.args[0].startswith('join_'):
        await handle_waitlist_join(update, context)
        return

    user, created = get_or_create_user(
        telegram_id=telegram_user.id,
        display_name=telegram_user.full_name or telegram_user.username or "",
        username=telegram_user.username or "",
    )

    if created:
        welcome_text = (
            f"Welcome to Loudrr, {telegram_user.first_name}!\n\n"
            "Loudrr is a credit-based engagement exchange:\n"
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


async def handle_waitlist_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle waitlist deep link - /start join_TOKEN."""
    telegram_user = update.effective_user
    token = context.args[0].replace('join_', '')

    try:
        entry = WaitlistEntry.objects.get(join_token=token)
    except WaitlistEntry.DoesNotExist:
        await update.message.reply_text(
            "Invalid or expired link.\n\n"
            "Please try again from loudrr.com"
        )
        return

    # Check if already approved
    if entry.status == WaitlistEntry.Status.APPROVED:
        miniapp_url = getattr(settings, 'MINIAPP_URL', 'http://localhost:3000')
        keyboard = [[InlineKeyboardButton(
            "Open Loudrr",
            web_app=WebAppInfo(url=miniapp_url)
        )]]
        await update.message.reply_text(
            "You're already approved!\n\n"
            "Tap below to open Loudrr.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Check if X username already submitted
    if entry.x_username and entry.status == WaitlistEntry.Status.SUBMITTED:
        await update.message.reply_text(
            f"You're on the waitlist!\n\n"
            f"Email: {entry.email}\n"
            f"X: @{entry.x_username}\n\n"
            "We'll notify you here when you get access."
        )
        return

    # Link Telegram to entry
    entry.telegram_id = telegram_user.id
    entry.telegram_username = telegram_user.username or ""
    entry.telegram_display_name = telegram_user.full_name or ""
    entry.save(update_fields=[
        'telegram_id', 'telegram_username', 'telegram_display_name', 'updated_at'
    ])

    # Show "Apply for Whitelist" button
    keyboard = [[InlineKeyboardButton(
        "Apply for Whitelist",
        callback_data=f"apply_waitlist:{entry.id}"
    )]]

    await update.message.reply_text(
        f"Welcome!\n\n"
        f"Email: {entry.email}\n\n"
        "Click below to complete your application:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    telegram_id = update.effective_user.id

    help_text = (
        "Loudrr Commands:\n\n"
        "/engage - Open Mini App to earn karma\n"
        "/balance - Check your karma balance\n"
        "/stats - Your engagement statistics\n"
        "/feed - Get posts to engage with (text mode)\n"
        "/post <link> - Submit your X post (costs 80 karma)\n"
        "/leaderboard - View top engagers\n"
        "/help - Show this message\n\n"
        "Or just send an X link to auto-post!\n\n"
        "How it works:\n"
        "1. Use /engage to open the engagement app\n"
        "2. Click posts, engage on X\n"
        "3. Earn 1 karma per engagement\n"
        "4. Spend 80 karma to post your own link\n"
        "5. Get 80 guaranteed engagements!"
    )

    # Add admin commands if user is admin
    if is_admin(telegram_id):
        help_text += (
            "\n\nAdmin Commands:\n"
            "/give <amount> - Reply to user to give credits\n"
            "/give @username <amount> - Give credits by username\n"
            "/give <telegram_id> <amount> - Give credits by ID"
        )

    await update.message.reply_text(help_text)


async def balance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /balance command - sends visual balance card."""
    from telegram import InputFile
    from .image_utils import create_balance_card

    user, _ = get_or_create_user(
        telegram_id=update.effective_user.id,
        display_name=update.effective_user.full_name or "",
        username=update.effective_user.username or "",
    )

    credit_service = CreditService(user)
    multiplier = user.tier_multiplier * user.get_streak_multiplier()

    # Generate balance card image
    image = create_balance_card(
        credits=user.credits,
        daily_earned=user.daily_credits_earned,
        daily_cap=100,
        streak=user.current_streak,
        tier=user.tier,
        multiplier=multiplier,
        telegram_username=user.telegram_username or update.effective_user.username or "",
    )

    await update.message.reply_photo(photo=image, caption="Your Loudrr Balance")


async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command."""
    user, _ = get_or_create_user(
        telegram_id=update.effective_user.id,
        display_name=update.effective_user.full_name or "",
        username=update.effective_user.username or "",
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


async def engage_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /engage command - opens the Mini App for engagement."""
    user, _ = get_or_create_user(
        telegram_id=update.effective_user.id,
        display_name=update.effective_user.full_name or "",
        username=update.effective_user.username or "",
    )

    miniapp_url = getattr(settings, 'MINIAPP_URL', 'http://localhost:3000')

    # Get feed count for display
    total_available = get_feed_count(user)

    text = (
        f"Ready to earn karma?\n\n"
        f"Posts available: {total_available}\n"
        f"Your balance: {user.credits} karma\n"
        f"Daily earned: {user.daily_credits_earned}/100\n\n"
        f"Tap 'Engage Now' to start earning!"
    )

    keyboard = [
        [InlineKeyboardButton(
            "Engage Now",
            web_app=WebAppInfo(url=miniapp_url)
        )],
        [
            InlineKeyboardButton("My Balance", callback_data="balance"),
            InlineKeyboardButton("Leaderboard", callback_data="lb:all_time"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(text, reply_markup=reply_markup)


async def post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /post command - submit a new post."""
    user, _ = get_or_create_user(
        telegram_id=update.effective_user.id,
        display_name=update.effective_user.full_name or "",
        username=update.effective_user.username or "",
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
    """Handle /feed command - get bulk posts to engage with.

    Usage: /feed [count]
    Default: 10 posts
    """
    from django.core.cache import cache
    import uuid

    user, _ = get_or_create_user(
        telegram_id=update.effective_user.id,
        display_name=update.effective_user.full_name or "",
        username=update.effective_user.username or "",
    )

    # Parse count from args (default 10, max 20)
    count = 10
    if context.args:
        try:
            count = min(int(context.args[0]), 20)  # Max 20 at a time
            count = max(count, 1)  # Min 1
        except ValueError:
            pass

    # Get feed posts
    posts = get_feed_posts(user, limit=count)
    total_available = get_feed_count(user)

    if not posts:
        await update.message.reply_text(
            "No posts available right now.\n\n"
            "Check back later or invite others to post!"
        )
        return

    # Generate batch ID and store post IDs in cache
    batch_id = str(uuid.uuid4())[:8]
    post_ids = [str(post.id) for post in posts]
    cache_key = f"feed_batch:{user.id}:{batch_id}"
    cache.set(cache_key, post_ids, timeout=3600)  # 1 hour expiry

    # Build the message with hyperlinks
    lines = [f"📋 <b>{len(posts)} posts to engage with:</b>\n"]

    for i, post in enumerate(posts, 1):
        username = post.user.x_username or post.user.telegram_username or "user"
        lines.append(f'{i}. <a href="{post.x_link}">@{username}</a>')

    lines.append(f"\n📊 {total_available} total posts available")
    lines.append("\n✅ Open links, engage on X, then tap Claim!")
    lines.append("⚠️ 3 random posts will be verified")

    text = "\n".join(lines)

    # Create keyboard with claim button
    keyboard = [
        [InlineKeyboardButton(f"✅ Claim {len(posts)} Credits", callback_data=f"claim:{batch_id}")],
        [
            InlineKeyboardButton("🔄 New Batch", callback_data="newbatch"),
            InlineKeyboardButton("📊 My Stats", callback_data="stats"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")


def is_admin(telegram_id: int) -> bool:
    """Check if user is an admin."""
    admin_ids = [int(x) for x in settings.ADMIN_TELEGRAM_IDS]
    return telegram_id in admin_ids


async def give_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /give command - admin gives credits to users.

    Usage: /give <amount> (reply to user's message)
    Or: /give @username <amount>
    Or: /give <telegram_id> <amount>
    """
    admin_id = update.effective_user.id

    # Check if user is admin
    if not is_admin(admin_id):
        await update.message.reply_text("You are not authorized to use this command.")
        return

    # Parse arguments
    args = context.args
    target_user = None
    target_telegram_id = None

    # Check if replying to someone's message
    if update.message.reply_to_message:
        # Get target user from replied message
        target_telegram_id = update.message.reply_to_message.from_user.id
        target_name = update.message.reply_to_message.from_user.full_name
        target_username = update.message.reply_to_message.from_user.username or ""

        if not args or len(args) < 1:
            await update.message.reply_text(
                "Usage: Reply to a user's message with:\n"
                "/give <amount>\n\n"
                "Example: /give 100"
            )
            return

        try:
            amount = int(args[0])
        except ValueError:
            await update.message.reply_text("Amount must be a number.")
            return

        # Get or create target user from reply
        target_user, _ = get_or_create_user(
            telegram_id=target_telegram_id,
            display_name=target_name,
            username=target_username,
        )
    else:
        # Need @username or telegram_id and amount
        if not args or len(args) < 2:
            await update.message.reply_text(
                "Usage:\n"
                "1. Reply to a user's message: /give <amount>\n"
                "2. Or use: /give @username <amount>\n"
                "3. Or use: /give <telegram_id> <amount>\n\n"
                "Examples:\n"
                "/give 100 (when replying)\n"
                "/give @johndoe 100\n"
                "/give 123456789 100"
            )
            return

        identifier = args[0]
        try:
            amount = int(args[1])
        except ValueError:
            await update.message.reply_text("Amount must be a number.")
            return

        # Check if it's a username (starts with @)
        if identifier.startswith("@"):
            target_user = get_user_by_username(identifier)
            if not target_user:
                await update.message.reply_text(
                    f"User {identifier} not found.\n\n"
                    "The user must have interacted with the bot at least once."
                )
                return
        else:
            # Try as telegram_id
            try:
                target_telegram_id = int(identifier)
                target_user, _ = get_or_create_user(
                    telegram_id=target_telegram_id,
                    display_name=f"User {target_telegram_id}",
                )
            except ValueError:
                await update.message.reply_text(
                    "Invalid format. Use @username or telegram_id.\n\n"
                    "Examples:\n"
                    "/give @johndoe 100\n"
                    "/give 123456789 100"
                )
                return

    if amount <= 0:
        await update.message.reply_text("Amount must be positive.")
        return

    # Give credits (use admin_grant to bypass daily cap)
    credit_service = CreditService(target_user)
    credit_service.admin_grant(
        amount=amount,
        admin_id=admin_id,
        description=f"Credits granted by admin {admin_id}",
    )

    await update.message.reply_text(
        f"Credits granted!\n\n"
        f"User: {target_user.display_name or target_user.telegram_id}\n"
        f"Amount: +{amount} credits\n"
        f"New balance: {target_user.credits} credits"
    )

    # Notify the user if possible (in private chat)
    try:
        if target_user.telegram_id:
            await context.bot.send_message(
                chat_id=target_user.telegram_id,
                text=f"You received {amount} credits from an admin!\n"
                     f"New balance: {target_user.credits} credits"
            )
    except Exception:
        pass  # User may have not started the bot yet


async def handle_waitlist_x_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle X username collection for waitlist application."""
    from .image_utils import create_waitlist_card

    entry_id = context.user_data.pop('collecting_x_username')
    x_username = update.message.text.strip().lstrip('@')

    # Validate format
    if not re.match(r'^[a-zA-Z0-9_]{1,15}$', x_username):
        await update.message.reply_text(
            "Invalid username format.\n\n"
            "Please send a valid X/Twitter username (letters, numbers, underscores only):"
        )
        context.user_data['collecting_x_username'] = entry_id
        return

    try:
        entry = WaitlistEntry.objects.get(id=entry_id)
    except WaitlistEntry.DoesNotExist:
        await update.message.reply_text("Application not found. Please try again from loudrr.com")
        return

    # Check if X username already used in waitlist
    if WaitlistEntry.objects.filter(x_username__iexact=x_username).exclude(id=entry_id).exists():
        await update.message.reply_text(
            "This X account is already on the waitlist.\n\n"
            "Please use a different account:"
        )
        context.user_data['collecting_x_username'] = entry_id
        return

    # Check if X username already registered as a user
    if User.objects.filter(x_username__iexact=x_username).exists():
        await update.message.reply_text(
            "This X account is already registered.\n\n"
            "Please use a different account:"
        )
        context.user_data['collecting_x_username'] = entry_id
        return

    # Save X username and update status
    entry.x_username = x_username
    entry.status = WaitlistEntry.Status.SUBMITTED
    entry.save(update_fields=['x_username', 'status', 'updated_at'])

    # Send waitlist confirmation card
    try:
        card_image = create_waitlist_card(x_username=x_username)
        await update.message.reply_photo(
            photo=card_image,
            caption=(
                f"*You're on the Loudrr waitlist!*\n\n"
                f"X: @{x_username}\n\n"
                "_We'll notify you here when you get access._"
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        # Fallback to text if card generation fails
        await update.message.reply_text(
            f"You're on the Loudrr waitlist!\n\n"
            f"X: @{x_username}\n\n"
            "We'll notify you here when you get access."
        )


async def link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages with X/Twitter links - auto-create posts."""
    if not update.message or not update.message.text:
        return

    # Check if we're collecting X username for waitlist
    if 'collecting_x_username' in context.user_data:
        await handle_waitlist_x_username(update, context)
        return

    text = update.message.text

    # Find X/Twitter links in the message
    x_pattern = r"https?://(twitter\.com|x\.com)/\w+/status/\d+"
    matches = re.findall(x_pattern, text)

    if not matches:
        return  # No X links found, ignore message

    # Extract full URL
    match = re.search(x_pattern, text)
    if not match:
        return

    x_link = match.group(0)

    user, _ = get_or_create_user(
        telegram_id=update.effective_user.id,
        display_name=update.effective_user.full_name or "",
        username=update.effective_user.username or "",
    )

    # Check credits
    post_cost = settings.ECHO_CONFIG["POST_COST"]
    if user.credits < post_cost:
        await update.message.reply_text(
            f"Insufficient credits to post!\n\n"
            f"Required: {post_cost} credits\n"
            f"You have: {user.credits} credits\n\n"
            f"Use /feed to earn credits by engaging with others' posts."
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
        f"✅ Post auto-submitted!\n\n"
        f"Link: {x_link[:50]}...\n"
        f"Credits deducted: {post_cost}\n"
        f"Remaining balance: {user.credits}\n\n"
        f"Your post is now live and will receive up to {post_cost} engagements!"
    )


async def launch_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /launch command - sends a pinnable message with Play Now button.

    This creates a promotional message with a Web App button that can be pinned in groups.
    Similar to TabiZoo's "Play Now" button style.
    """
    miniapp_url = getattr(settings, 'MINIAPP_URL', 'http://localhost:3000')

    text = (
        "Loudrr - Earn by Engaging\n\n"
        "Reply to posts, earn karma, get replies on yours.\n"
        "Join the community and start earning!"
    )

    keyboard = [
        [InlineKeyboardButton(
            "Play Now",
            web_app=WebAppInfo(url=miniapp_url)
        )],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

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
    print(f"[DEBUG] Callback received: {data}")

    try:
        user, _ = get_or_create_user(
            telegram_id=update.effective_user.id,
            display_name=update.effective_user.full_name or "",
            username=update.effective_user.username or "",
        )
        print(f"[DEBUG] User: {user.telegram_id}")
    except Exception as e:
        print(f"[ERROR] Failed to get user: {e}")
        await query.edit_message_text(f"Error: {e}")
        return

    if data == "stats":
        # Show stats
        stats = get_user_stats(user)
        text = (
            f"Karma: {stats['credits']} | "
            f"Streak: {stats['current_streak']} days | "
            f"Rank: #{stats['rank']}"
        )
        await query.edit_message_text(text)

    elif data == "balance":
        # Show balance card
        from telegram import InputFile
        from .image_utils import create_balance_card

        credit_service = CreditService(user)
        multiplier = user.tier_multiplier * user.get_streak_multiplier()

        image = create_balance_card(
            credits=user.credits,
            daily_earned=user.daily_credits_earned,
            daily_cap=100,
            streak=user.current_streak,
            tier=user.tier,
            multiplier=multiplier,
            telegram_username=user.telegram_username or "",
        )

        # Can't edit message to photo, need to send new message
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=image,
            caption="Your Loudrr Balance"
        )

    elif data == "stop":
        await query.edit_message_text(
            "Engagement session ended.\n\n"
            "Use /feed to start again anytime!"
        )

    elif data.startswith("engaged:"):
        # User clicked "Done - I Engaged!"
        post_id = data.split(":")[1]
        print(f"[DEBUG] Engaged callback for post: {post_id}")
        try:
            post = Post.objects.get(pk=post_id)
            print(f"[DEBUG] Found post: {post.id}, status: {post.status}")
        except Post.DoesNotExist:
            print(f"[ERROR] Post not found: {post_id}")
            await query.edit_message_text("Post not found.")
            return
        except Exception as e:
            print(f"[ERROR] Error getting post: {e}")
            await query.edit_message_text(f"Error: {e}")
            return

        try:
            result = record_button_engagement(user, post)
            print(f"[DEBUG] Engagement result: {result}")
        except Exception as e:
            print(f"[ERROR] Error recording engagement: {e}")
            await query.edit_message_text(f"Error recording engagement: {e}")
            return

        if result["success"]:
            # Show success and next post
            posts = get_feed_posts(user, limit=1)
            total_available = get_feed_count(user)
            print(f"[DEBUG] After engagement - posts available: {len(posts)}, total: {total_available}")

            success_text = (
                f"+{result['credits_earned']} credit earned!\n"
                f"Daily remaining: {result['daily_remaining']}/100\n"
                f"Streak: {result['streak']} days\n\n"
            )

            try:
                if posts:
                    next_post = posts[0]
                    engage_url = next_post.x_link
                    print(f"[DEBUG] Showing next post: {next_post.id}")

                    keyboard = [
                        [InlineKeyboardButton("Open Post on X", url=engage_url)],
                        [InlineKeyboardButton("Done - I Engaged!", callback_data=f"engaged:{next_post.id}")],
                        [
                            InlineKeyboardButton("Skip", callback_data=f"skip:{next_post.id}"),
                            InlineKeyboardButton("My Stats", callback_data="stats"),
                            InlineKeyboardButton("Stop", callback_data="stop"),
                        ],
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    text = (
                        success_text +
                        f"Next post ({total_available} available):\n\n"
                        f"@{next_post.user.x_username or next_post.user.display_name or 'Creator'} wants engagement"
                    )
                    await query.edit_message_text(text, reply_markup=reply_markup)
                    print("[DEBUG] Message edited successfully with next post")
                else:
                    await query.edit_message_text(
                        success_text + "No more posts available. Great job!"
                    )
                    print("[DEBUG] Message edited - no more posts")
            except Exception as e:
                print(f"[ERROR] Failed to edit message: {e}")
                await query.edit_message_text(success_text + f"\n\nError showing next post: {e}")
        else:
            await query.edit_message_text(f"Could not record engagement: {result['error']}")

    elif data.startswith("skip:"):
        # Skip this post and show next
        posts = get_feed_posts(user, limit=1)
        total_available = get_feed_count(user)

        if not posts:
            await query.edit_message_text("No more posts available!")
            return

        post = posts[0]
        engage_url = post.x_link

        keyboard = [
            [InlineKeyboardButton("Open Post on X", url=engage_url)],
            [InlineKeyboardButton("Done - I Engaged!", callback_data=f"engaged:{post.id}")],
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
            f"1. Click 'Open Post on X' to view the post\n"
            f"2. Reply/Like on X\n"
            f"3. Click 'Done - I Engaged!' to earn credit"
        )

        await query.edit_message_text(text, reply_markup=reply_markup)

    elif data.startswith("claim:"):
        # User claiming credits for a batch
        from django.core.cache import cache
        from posts.models import Engagement

        batch_id = data.split(":")[1]
        cache_key = f"feed_batch:{user.id}:{batch_id}"
        post_ids = cache.get(cache_key)

        if not post_ids:
            await query.edit_message_text(
                "This batch has expired or was already claimed.\n\n"
                "Use /feed to get a new batch!"
            )
            return

        # Record engagements for all posts in batch
        credits_earned = 0
        posts_engaged = 0
        errors = []

        for post_id in post_ids:
            try:
                post = Post.objects.get(pk=post_id)
                result = record_button_engagement(user, post)
                if result["success"]:
                    credits_earned += result["credits_earned"]
                    posts_engaged += 1
                elif "already engaged" not in result["error"].lower():
                    errors.append(result["error"])
            except Post.DoesNotExist:
                continue
            except Exception as e:
                errors.append(str(e))

        # Clear the batch from cache
        cache.delete(cache_key)

        # Build response
        if posts_engaged > 0:
            text = (
                f"✅ Claimed {credits_earned} credits!\n\n"
                f"Posts engaged: {posts_engaged}/{len(post_ids)}\n"
                f"Balance: {user.credits} credits\n"
                f"Streak: {user.current_streak} days\n\n"
                "Use /feed to get more posts!"
            )
        else:
            text = (
                "No credits earned.\n\n"
                f"Possible reasons:\n"
                f"- Already engaged with these posts\n"
                f"- Posts are no longer active\n\n"
                "Use /feed to get new posts!"
            )

        keyboard = [
            [InlineKeyboardButton("🔄 Get More Posts", callback_data="newbatch")],
            [InlineKeyboardButton("📊 My Stats", callback_data="stats")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup)

    elif data == "newbatch":
        # Get a new batch of posts
        posts = get_feed_posts(user, limit=10)
        total_available = get_feed_count(user)

        if not posts:
            await query.edit_message_text(
                "No posts available right now.\n\n"
                "Check back later or invite others to post!"
            )
            return

        # Generate new batch ID and store
        from django.core.cache import cache
        import uuid

        batch_id = str(uuid.uuid4())[:8]
        post_ids = [str(post.id) for post in posts]
        cache_key = f"feed_batch:{user.id}:{batch_id}"
        cache.set(cache_key, post_ids, timeout=3600)

        # Build the message with hyperlinks
        lines = [f"📋 <b>{len(posts)} posts to engage with:</b>\n"]

        for i, post in enumerate(posts, 1):
            username = post.user.x_username or post.user.telegram_username or "user"
            lines.append(f'{i}. <a href="{post.x_link}">@{username}</a>')

        lines.append(f"\n📊 {total_available} total posts available")
        lines.append("\n✅ Open links, engage on X, then tap Claim!")
        lines.append("⚠️ 3 random posts will be verified")

        text = "\n".join(lines)

        keyboard = [
            [InlineKeyboardButton(f"✅ Claim {len(posts)} Credits", callback_data=f"claim:{batch_id}")],
            [
                InlineKeyboardButton("🔄 New Batch", callback_data="newbatch"),
                InlineKeyboardButton("📊 My Stats", callback_data="stats"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")

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

    elif data.startswith("apply_waitlist:"):
        # User clicked "Apply for Whitelist" button
        entry_id = data.split(":")[1]

        # Store state for collecting X username
        context.user_data['collecting_x_username'] = entry_id

        await query.edit_message_text(
            "*Apply for Whitelist*\n\n"
            "Please send your X/Twitter username:\n\n"
            "Example: `@yourusername` or `yourusername`",
            parse_mode="Markdown"
        )
