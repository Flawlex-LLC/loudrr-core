"""
Telegram keyboard layouts.

Reusable keyboard configurations for the bot.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_feed_keyboard(post, redirect_url: str) -> InlineKeyboardMarkup:
    """Get keyboard for feed post."""
    keyboard = [
        [InlineKeyboardButton("Click to Engage", url=redirect_url)],
        [
            InlineKeyboardButton("Skip", callback_data=f"skip:{post.id}"),
            InlineKeyboardButton("My Stats", callback_data="stats"),
            InlineKeyboardButton("Stop", callback_data="stop"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_leaderboard_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for leaderboard navigation."""
    keyboard = [
        [
            InlineKeyboardButton("Daily", callback_data="lb:daily"),
            InlineKeyboardButton("Weekly", callback_data="lb:weekly"),
            InlineKeyboardButton("All-Time", callback_data="lb:all_time"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_post_confirmation_keyboard(post_id: str) -> InlineKeyboardMarkup:
    """Get keyboard for post submission confirmation."""
    keyboard = [
        [
            InlineKeyboardButton("View Status", callback_data=f"post_status:{post_id}"),
            InlineKeyboardButton("Cancel Post", callback_data=f"cancel_post:{post_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_engagement_complete_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard shown after engagement."""
    keyboard = [
        [InlineKeyboardButton("Next Post", callback_data="next")],
        [
            InlineKeyboardButton("My Stats", callback_data="stats"),
            InlineKeyboardButton("Stop", callback_data="stop"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)
