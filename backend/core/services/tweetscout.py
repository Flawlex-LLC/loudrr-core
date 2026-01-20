"""
TweetScout API service.

Fetches user score and info from TweetScout for tier calculation.
"""
import logging
from typing import Optional

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

TWEETSCOUT_BASE_URL = "https://api.tweetscout.io/v2"


class TweetScoutService:
    """Service for interacting with TweetScout API."""

    def __init__(self):
        self.api_key = getattr(settings, 'TWEETSCOUT_API_KEY', '')
        self.headers = {"ApiKey": self.api_key}

    def get_score(self, username: str) -> Optional[float]:
        """
        Get TweetScout score for a username.

        Args:
            username: X/Twitter username (without @)

        Returns:
            Score as float, or None if not found/error
        """
        if not self.api_key:
            logger.warning("TWEETSCOUT_API_KEY not configured")
            return None

        username = username.lstrip("@")

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(
                    f"{TWEETSCOUT_BASE_URL}/score/{username}",
                    headers=self.headers
                )

                if response.status_code == 200:
                    data = response.json()
                    score = data.get("score")
                    logger.info(f"TweetScout score for @{username}: {score}")
                    return float(score) if score is not None else None
                elif response.status_code == 404:
                    logger.warning(f"User @{username} not found in TweetScout")
                    return None
                else:
                    logger.error(f"TweetScout API error: {response.status_code} - {response.text}")
                    return None

        except Exception as e:
            logger.error(f"Error fetching TweetScout score for @{username}: {e}")
            return None

    def get_info(self, username: str) -> Optional[dict]:
        """
        Get user info from TweetScout.

        Args:
            username: X/Twitter username (without @)

        Returns:
            Dict with user info, or None if not found/error
            {
                "id": "1456366493323644928",
                "name": "Blest",
                "screen_name": "0xBlest_",
                "description": "...",
                "followers_count": 10186,
                "friends_count": 9754,
                "register_date": "2021-11-04",
                "tweets_count": 60051,
                "banner": "https://...",
                "verified": true,
                "avatar": "https://...",
                "can_dm": true
            }
        """
        if not self.api_key:
            logger.warning("TWEETSCOUT_API_KEY not configured")
            return None

        username = username.lstrip("@")

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(
                    f"{TWEETSCOUT_BASE_URL}/info/{username}",
                    headers=self.headers
                )

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"TweetScout info for @{username}: {data.get('name')}")
                    return data
                elif response.status_code == 404:
                    logger.warning(f"User @{username} not found in TweetScout")
                    return None
                else:
                    logger.error(f"TweetScout API error: {response.status_code} - {response.text}")
                    return None

        except Exception as e:
            logger.error(f"Error fetching TweetScout info for @{username}: {e}")
            return None

    def get_user_data(self, username: str) -> Optional[dict]:
        """
        Get both score and info for a user.

        Returns:
            Dict with combined data:
            {
                "score": 444.61,
                "id": "...",
                "name": "...",
                "screen_name": "...",
                "followers_count": ...,
                ...
            }
        """
        username = username.lstrip("@")

        score = self.get_score(username)
        info = self.get_info(username)

        if score is None and info is None:
            return None

        result = info or {}
        if score is not None:
            result["score"] = score

        return result


def get_tweetscout_service() -> TweetScoutService:
    """Get a TweetScout service instance."""
    return TweetScoutService()
