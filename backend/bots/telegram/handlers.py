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

    miniapp_url = getattr(settings, 'MINIAPP_URL', 'http://localhost:3000')

    if created:
        welcome_text = (
            f"Welcome to Loudrr, {telegram_user.first_name}!\n\n"
            "Loudrr is a karma-based engagement exchange:\n"
            "- Engage with posts to earn karma\n"
            "- Spend karma to promote your own posts\n\n"
            "Tap the button below to open the app!"
        )
    else:
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
    miniapp_url = getattr(settings, 'MINIAPP_URL', 'http://localhost:3000')

    help_text = (
        "Loudrr Commands:\n\n"
        "/start - Start the bot\n"
        "/balance - Check your karma balance\n"
        "/launch - Get a pinnable 'Open App' message\n"
        "/help - Show this message\n\n"
        "How it works:\n"
        "1. Open the mini app using the button below\n"
        "2. Engage with posts on X\n"
        "3. Earn karma for each engagement\n"
        "4. Spend karma to promote your own posts!"
    )

    keyboard = [[InlineKeyboardButton(
        "Open Loudrr",
        web_app=WebAppInfo(url=miniapp_url)
    )]]

    await update.message.reply_text(help_text, reply_markup=InlineKeyboardMarkup(keyboard))


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


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages - check if collecting X username for waitlist."""
    if not update.message or not update.message.text:
        return

    # Check if we're collecting X username for waitlist
    if 'collecting_x_username' in context.user_data:
        await handle_waitlist_x_username(update, context)
        return


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
