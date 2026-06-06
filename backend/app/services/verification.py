"""Phase 1 of verification — external Twitter calls, NO database (spec §5.2).

This phase makes the slow, fail-prone HTTP calls while holding no lock, and
produces a plain list of pass/fail results. Phase 2 (settlement) then writes
the money atomically. Skipped (no tweet_id / no API key / API down) counts as
**passed** — benefit of the doubt.
"""
import logging
import random
import uuid
from dataclasses import dataclass

from app.integrations import twitter
from app.services.site_settings import get_setting

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


async def verify_engagements(
    items: list[ToVerify], x_username: str, *, db=None,
) -> list[VResult]:
    """Run Phase 1 over a batch. No DB writes, no locks — only HTTP.

    AUDIT_PROBABILITY (live, default 1.0) gates which engagements are actually
    verified against the Twitter API. A roll above the threshold short-circuits
    to a trusted pass — preserves API budget while still randomly sampling for
    fraud. Default 1.0 = verify every item (current behavior). Caller passes
    ``db`` so we can read the setting; if ``db`` is None we keep the legacy
    "verify everything" path so existing tests / unit calls don't regress."""
    client = twitter.get_twitter_client()
    audit_prob = 1.0
    if db is not None:
        # cast defensively — settings can come back as Decimal/float/str.
        audit_prob = float(await get_setting(db, "AUDIT_PROBABILITY", 1.0))

    results: list[VResult] = []
    for it in items:
        if audit_prob < 1.0 and random.random() >= audit_prob:
            # trusted skip — counts as passed, no API call. Distinct from the
            # "tweet_id missing / API skipped" path: error stays None.
            results.append(VResult(
                it.engagement_id, it.post_id, passed=True,
                reply_verified=False, skipped=True, error=None,
            ))
            continue
        results.append(await _verify_single(client, it, x_username))
    passed = sum(1 for r in results if r.passed)
    logger.info("Phase 1 done: %s passed, %s failed", passed, len(results) - passed)
    return results
