"""TweetScout API client — a user's clout score and X profile (spec §7).

Async httpx client. TweetScout is a *paid, quota-limited* service, so the
golden rule (spec §5, §7): every successful fetch is cached in the
`x_profiles` table and never re-fetched needlessly — a cached score is a call
we did not pay for. This client only makes the call; the caller owns the cache.

Failure policy: any timeout / network error / non-200 (other than 404) returns
``None`` rather than raising. The caller decides what a missing score means —
on link-X it's a user-facing "username not found", on onboarding it's "enter
with a default score and try later". We never crash a request because an
external API hiccuped.
"""
import logging
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

TWEETSCOUT_BASE_URL = "https://api.tweetscout.io/v2"
_TIMEOUT = httpx.Timeout(10.0)


class TweetScoutClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key if api_key is not None else settings.tweetscout_api_key
        self.headers = {"ApiKey": self.api_key}

    @staticmethod
    def _clean(username: str) -> str:
        return username.strip().lstrip("@")

    async def _get(self, path: str) -> Optional[dict]:
        """GET {base}{path} → parsed JSON, or None on 404 / any error."""
        if not self.api_key:
            logger.warning("TWEETSCOUT_API_KEY not configured")
            return None
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    f"{TWEETSCOUT_BASE_URL}{path}", headers=self.headers
                )
        except httpx.HTTPError as e:
            logger.error("TweetScout request failed for %s: %s", path, e)
            return None

        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 404:
            logger.warning("TweetScout 404 for %s", path)
            return None
        logger.error("TweetScout error %s for %s: %s", resp.status_code, path, resp.text)
        return None

    async def get_score(self, username: str) -> Optional[float]:
        """The numeric clout score for a username, or None."""
        data = await self._get(f"/score/{self._clean(username)}")
        if not data:
            return None
        score = data.get("score")
        return float(score) if score is not None else None

    async def get_info(self, username: str) -> Optional[dict]:
        """The profile dict (name, followers, avatar, …) for a username, or None."""
        return await self._get(f"/info/{self._clean(username)}")

    async def get_user_data(self, username: str) -> Optional[dict]:
        """Combined score + profile as one *flat* dict, or None if both fail.

        Shape: the /info fields at the top level, with ``score`` merged in —
        e.g. ``{"id", "name", "screen_name", "followers_count", ..., "score"}``.
        """
        username = self._clean(username)
        score = await self.get_score(username)
        info = await self.get_info(username)
        if score is None and info is None:
            return None
        result = dict(info or {})
        if score is not None:
            result["score"] = score
        return result


def get_tweetscout_client() -> TweetScoutClient:
    """Factory — a client bound to the configured API key."""
    return TweetScoutClient()
