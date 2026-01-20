"""
Twitter API verification service using twitterapi.io.

Verifies that users have replied to tweets.
Note: Like verification is not possible (Twitter made likes private in 2024).
"""
import logging
import re
from typing import Optional

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class TwitterVerificationService:
    """
    Verify engagements via twitterapi.io API.

    Only 3 methods - all sync, no duplicates:
    - verify_reply() - Check if user replied to tweet (1 API call)
    - get_tweet_author() - Get tweet author info (1 API call)
    - extract_tweet_id() - Extract tweet ID from URL (no API call)
    """

    BASE_URL = "https://api.twitterapi.io/twitter"
    TIMEOUT = 30

    def __init__(self):
        self.api_key = getattr(settings, "TWITTER_API_KEY", "")
        if not self.api_key:
            logger.warning("TWITTER_API_KEY not configured - verification disabled")

    def _get_headers(self) -> dict:
        return {"X-API-Key": self.api_key}

    @staticmethod
    def extract_tweet_id(url: str) -> Optional[str]:
        """
        Extract tweet ID from a Twitter/X URL.

        Supports:
        - https://twitter.com/user/status/1234567890
        - https://x.com/user/status/1234567890
        - https://x.com/user/status/1234567890?s=20

        Returns:
            Tweet ID string or None if not found.
        """
        if not url:
            return None
        patterns = [
            r"(?:twitter\.com|x\.com)/\w+/status/(\d+)",
            r"status/(\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def verify_reply(self, tweet_id: str, x_username: str) -> dict:
        """
        Verify user replied to a tweet.

        Uses advanced_search with from:user conversation_id:tweet query.
        Returns only the user's reply (1 tweet max) = $0.00015 per call.

        Args:
            tweet_id: The tweet ID to check
            x_username: User's X/Twitter username (without @)

        Returns:
            {
                "passed": bool,
                "reply_verified": bool,
                "like_verified": True,  # Always true (can't verify)
                "error": str or None,
                "skipped": bool  # True if no API key
            }
        """
        # No API key - skip verification
        if not self.api_key:
            return {
                "passed": True,
                "reply_verified": True,
                "like_verified": True,
                "error": None,
                "skipped": True,
            }

        # No username - can't verify
        if not x_username:
            return {
                "passed": False,
                "reply_verified": False,
                "like_verified": True,
                "error": "User has no X username linked",
                "skipped": False,
            }

        try:
            # Clean username (remove @ if present)
            username_clean = x_username.lower().lstrip("@")

            with httpx.Client(timeout=self.TIMEOUT) as client:
                # Optimized query: returns only this user's reply to this tweet
                # Cost: $0.00015 (1 tweet) instead of all replies
                response = client.get(
                    f"{self.BASE_URL}/tweet/advanced_search",
                    headers=self._get_headers(),
                    params={"query": f"from:{username_clean} conversation_id:{tweet_id}"},
                )
                response.raise_for_status()
                data = response.json()

                # Check if any tweets returned (user replied)
                tweets = data.get("tweets", [])
                reply_found = len(tweets) > 0

                if reply_found:
                    logger.info(f"Reply verified: @{x_username} replied to {tweet_id}")
                else:
                    logger.info(f"Reply not found: @{x_username} on {tweet_id}")

                return {
                    "passed": reply_found,
                    "reply_verified": reply_found,
                    "like_verified": True,  # Can't verify, assume done
                    "error": None,
                    "skipped": False,
                }

        except httpx.HTTPStatusError as e:
            logger.error(f"API error {e.response.status_code}: {e.response.text[:100]}")
            return {
                "passed": False,
                "reply_verified": False,
                "like_verified": True,
                "error": f"API error: {e.response.status_code}",
                "skipped": False,
            }
        except Exception as e:
            logger.error(f"Verification error: {e}")
            return {
                "passed": False,
                "reply_verified": False,
                "like_verified": True,
                "error": str(e),
                "skipped": False,
            }

    def get_tweet_author(self, tweet_id: str) -> Optional[dict]:
        """
        Get tweet author info.

        Makes 1 API call to /tweets endpoint.

        Args:
            tweet_id: The tweet ID to look up

        Returns:
            {"user_id": "123", "username": "handle", "name": "Display Name"}
            or None if error.
        """
        if not self.api_key:
            logger.warning("No API key - cannot fetch tweet author")
            return None

        try:
            with httpx.Client(timeout=self.TIMEOUT) as client:
                response = client.get(
                    f"{self.BASE_URL}/tweets",
                    headers=self._get_headers(),
                    params={"tweet_ids": tweet_id},
                )
                response.raise_for_status()
                data = response.json()

                tweets = data.get("tweets", [])
                if tweets:
                    author = tweets[0].get("author", {})
                    return {
                        "user_id": str(author.get("id", "")),
                        "username": author.get("userName", ""),
                        "name": author.get("name", ""),
                    }

                logger.warning(f"No tweet data for {tweet_id}")
                return None

        except httpx.HTTPStatusError as e:
            logger.error(f"API error fetching tweet {tweet_id}: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error fetching tweet author: {e}")
            return None

    def get_tweet_content(self, tweet_id: str) -> Optional[dict]:
        """
        Get full tweet content for caching.

        Single API call ($0.00015) fetches:
        - Tweet text
        - Author info (for ownership validation)
        - Media URLs
        - Created timestamp

        Args:
            tweet_id: The tweet ID to look up

        Returns:
            {
                "tweet_id": "123",
                "text": "Tweet content...",
                "author_id": "456",
                "author_username": "handle",
                "author_name": "Display Name",
                "author_avatar": "https://...",
                "media": ["https://..."],
                "created_at": "2024-01-01T12:00:00Z",
            }
            or None if error/not found.
        """
        if not self.api_key:
            logger.warning("No API key - cannot fetch tweet content")
            return None

        try:
            with httpx.Client(timeout=self.TIMEOUT) as client:
                response = client.get(
                    f"{self.BASE_URL}/tweets",
                    headers=self._get_headers(),
                    params={"tweet_ids": tweet_id},
                )
                response.raise_for_status()
                data = response.json()

                tweets = data.get("tweets", [])
                if not tweets:
                    logger.warning(f"Tweet not found: {tweet_id}")
                    return None

                tweet = tweets[0]
                author = tweet.get("author", {})

                # Extract media URLs
                media_urls = []
                extended_entities = tweet.get("extendedEntities", {})
                media_list = extended_entities.get("media", [])
                for media in media_list:
                    media_url = media.get("media_url_https") or media.get("url")
                    if media_url:
                        media_urls.append(media_url)

                result = {
                    "tweet_id": str(tweet.get("id", tweet_id)),
                    "text": tweet.get("text", ""),
                    "author_id": str(author.get("id", "")),
                    "author_username": author.get("userName", ""),
                    "author_name": author.get("name", ""),
                    "author_avatar": author.get("profilePicture", ""),
                    "media": media_urls,
                    "created_at": tweet.get("createdAt", ""),
                }

                logger.info(f"Fetched tweet content: {tweet_id} by @{result['author_username']}")
                return result

        except httpx.HTTPStatusError as e:
            logger.error(f"API error fetching tweet {tweet_id}: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error fetching tweet content: {e}")
            return None

    # Backwards compatibility alias
    def verify_engagement_sync(self, tweet_id: str, user_x_username: str) -> dict:
        """Alias for verify_reply() - backwards compatibility."""
        return self.verify_reply(tweet_id, user_x_username)


# Singleton instance
twitter_verification = TwitterVerificationService()
