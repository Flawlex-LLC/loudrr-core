"""
Image generation utilities for Telegram bot.
Fetches card images from the Next.js @vercel/og API routes.
"""
import io
import httpx
from urllib.parse import urlencode

from django.conf import settings

# Landing page URL (where the card API routes are hosted)
LANDING_URL = getattr(settings, 'LANDING_URL', 'https://loudrr.com')


def create_waitlist_card(
    x_username: str,
    display_name: str = None,
    followers_count: int = None,
    avatar_url: str = None,
    is_verified: bool = False,
    telegram_username: str = None,
) -> io.BytesIO:
    """
    Fetch waitlist confirmation card from vercel/og API.
    """
    params = {
        "username": x_username,
    }
    if display_name:
        params["displayName"] = display_name
    if followers_count is not None:
        params["followers"] = str(followers_count)
    if telegram_username:
        params["telegram"] = telegram_username

    url = f"{LANDING_URL}/api/cards/waitlist?{urlencode(params)}"

    with httpx.Client(timeout=30) as client:
        response = client.get(url)
        response.raise_for_status()

        output = io.BytesIO(response.content)
        output.seek(0)
        return output


def create_approval_card(
    x_username: str,
    display_name: str = None,
    avatar_url: str = None,
    tweetscout_score: float = None,
    tier: str = None,
) -> io.BytesIO:
    """
    Fetch approval notification card from vercel/og API.
    """
    params = {
        "username": x_username,
    }
    if display_name:
        params["displayName"] = display_name
    if tweetscout_score is not None:
        params["score"] = str(int(tweetscout_score))
    if tier:
        params["tier"] = tier

    url = f"{LANDING_URL}/api/cards/approval?{urlencode(params)}"

    with httpx.Client(timeout=30) as client:
        response = client.get(url)
        response.raise_for_status()

        output = io.BytesIO(response.content)
        output.seek(0)
        return output
