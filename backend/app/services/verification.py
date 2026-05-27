"""Phase 1 of verification — external Twitter calls, NO database (spec §5.2).

This phase makes the slow, fail-prone HTTP calls while holding no lock, and
produces a plain list of pass/fail results. Phase 2 (settlement) then writes
the money atomically. Skipped (no tweet_id / no API key / API down) counts as
**passed** — benefit of the doubt.
"""
import logging
import uuid
from dataclasses import dataclass

from app.integrations import twitter

logger = logging.getLogger(__name__)


@dataclass
class ToVerify:
    engagement_id: uuid.UUID
    post_id: uuid.UUID
    tweet_id: str


@dataclass
class VResult:
    engagement_id: uuid.UUID
    post_id: uuid.UUID
    passed: bool
    reply_verified: bool = False
    like_verified: bool = True  # always true — X made likes private
    skipped: bool = False
    error: str | None = None


async def _verify_single(client, item: ToVerify, x_username: str) -> VResult:
    if not item.tweet_id:
        return VResult(item.engagement_id, item.post_id, passed=True, skipped=True,
                       error="No tweet_id available")  # benefit of the doubt
    if not x_username:
        return VResult(item.engagement_id, item.post_id, passed=False,
                       error="User has no X account linked")

    api = await client.verify_reply(tweet_id=item.tweet_id, x_username=x_username)
    if api.get("skipped"):
        return VResult(item.engagement_id, item.post_id, passed=True,
                       reply_verified=False, skipped=True, error=api.get("error"))
    passed = api.get("passed", False)
    return VResult(
        item.engagement_id, item.post_id, passed=passed,
        reply_verified=api.get("reply_verified", False), like_verified=True,
        error=None if passed else api.get("error"),
    )


async def verify_engagements(items: list[ToVerify], x_username: str) -> list[VResult]:
    """Run Phase 1 over a batch. No DB writes, no locks — only HTTP."""
    client = twitter.get_twitter_client()
    results = [await _verify_single(client, it, x_username) for it in items]
    passed = sum(1 for r in results if r.passed)
    logger.info("Phase 1 done: %s passed, %s failed", passed, len(results) - passed)
    return results
