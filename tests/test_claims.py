"""Tests for Ch13 — two-phase verification + the claim queue (endpoints 12, 13).

The Twitter API is mocked. The settlement money paths are tested hardest:
award, tier multiplier, partial payment, failed-deletes-engagement,
benefit-of-the-doubt, daily-cap skip, and idempotent re-run.
"""
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.integrations import twitter
from app.models.engagement import Engagement
from app.models.post import Post
from app.models.site_setting import SiteSetting
from app.models.verification_batch import VerificationBatch
from app.services import claims
from app.services import site_settings


class _FakeTwitter:
    def __init__(self, *, passed=True, skipped=False):
        self.passed, self.skipped = passed, skipped

    async def verify_reply(self, tweet_id, x_username):
        if self.skipped:
            return {"passed": True, "reply_verified": True, "like_verified": True,
                    "error": None, "skipped": True}
        return {"passed": self.passed, "reply_verified": self.passed,
                "like_verified": True, "error": None if self.passed else "no reply",
                "skipped": False}


def _mock_twitter(monkeypatch, **kw):
    monkeypatch.setattr(twitter, "get_twitter_client", lambda: _FakeTwitter(**kw))


async def _make_post(db, *, owner_id, escrow="50", tweet_id="123", x_link="https://x.com/o/status/123", status="active"):
    p = Post(
        user_id=owner_id, x_link=x_link, tweet_id=tweet_id,
        escrow=Decimal(escrow), initial_escrow=Decimal("50"), status=status, platform="web",
    )
    db.add(p)
    await db.commit()
    return p


async def _make_engagement(db, *, user_id, post_id, clicked_at=None):
    e = Engagement(
        user_id=user_id, post_id=post_id, verified=False, credit_granted=False,
        clicked_at=clicked_at or datetime.utcnow(),
    )
    db.add(e)
    await db.commit()
    return e


async def _make_batch(db, *, user_id, engagement_ids):
    b = VerificationBatch(
        user_id=user_id, engagement_ids=[str(i) for i in engagement_ids], status="pending"
    )
    db.add(b)
    await db.commit()
    return b


# ============ settlement engine (run_batch) ============
async def test_award_happy_path(client, make_user, db_session, monkeypatch):
    owner = await make_user(telegram_id=8001)
    viewer = await make_user(telegram_id=8002, x_username="viewer")  # Anon, x1.00
    post = await _make_post(db_session, owner_id=owner.id, escrow="50")
    eng = await _make_engagement(db_session, user_id=viewer.id, post_id=post.id)
    batch = await _make_batch(db_session, user_id=viewer.id, engagement_ids=[eng.id])
    _mock_twitter(monkeypatch, passed=True)

    await claims.run_batch(db_session, batch.id)

    assert batch.status == "completed"
    assert (batch.passed, batch.failed) == (1, 0)
    assert batch.credits_awarded == Decimal("1.0000")
    assert post.escrow == Decimal("49.0000")
    assert viewer.credits == Decimal("1.0000")
    assert eng.verified is True and eng.credit_granted is True
    assert viewer.total_engagements == 1


async def test_award_uses_tier_multiplier(client, make_user, db_session, monkeypatch):
    owner = await make_user(telegram_id=8003)
    viewer = await make_user(telegram_id=8004, x_username="v", tweetscout_score=450)  # Based x1.20
    post = await _make_post(db_session, owner_id=owner.id, escrow="50")
    eng = await _make_engagement(db_session, user_id=viewer.id, post_id=post.id)
    batch = await _make_batch(db_session, user_id=viewer.id, engagement_ids=[eng.id])
    _mock_twitter(monkeypatch, passed=True)

    await claims.run_batch(db_session, batch.id)
    assert viewer.credits == Decimal("1.2000")
    assert post.escrow == Decimal("48.8000")


async def test_partial_payment_and_autocomplete(client, make_user, db_session, monkeypatch):
    owner = await make_user(telegram_id=8005)
    viewer = await make_user(telegram_id=8006, x_username="v", tweetscout_score=450)  # wants 1.20
    post = await _make_post(db_session, owner_id=owner.id, escrow="0.5")  # only 0.5 left
    eng = await _make_engagement(db_session, user_id=viewer.id, post_id=post.id)
    batch = await _make_batch(db_session, user_id=viewer.id, engagement_ids=[eng.id])
    _mock_twitter(monkeypatch, passed=True)

    await claims.run_batch(db_session, batch.id)
    assert viewer.credits == Decimal("0.5000")     # capped at escrow
    assert post.escrow == Decimal("0.0000")
    assert post.status == "completed"               # auto-completed at escrow 0
    assert batch.credits_awarded == Decimal("0.5000")


async def test_failed_verification_deletes_engagement(client, make_user, db_session, monkeypatch):
    from app.repositories.engagement import EngagementRepository

    owner = await make_user(telegram_id=8007)
    viewer = await make_user(telegram_id=8008, x_username="v")
    post = await _make_post(db_session, owner_id=owner.id, escrow="50")
    eng = await _make_engagement(db_session, user_id=viewer.id, post_id=post.id)
    eng_id = eng.id
    batch = await _make_batch(db_session, user_id=viewer.id, engagement_ids=[eng_id])
    _mock_twitter(monkeypatch, passed=False)

    await claims.run_batch(db_session, batch.id)
    assert (batch.passed, batch.failed) == (0, 1)
    assert batch.credits_awarded == Decimal("0")
    assert viewer.credits == Decimal("0")
    assert viewer.honesty_score == 49               # dropped by ceil(1/2)=1
    assert await EngagementRepository(db_session).get(id=eng_id) is None  # deleted


async def test_benefit_of_doubt_no_tweet_id(client, make_user, db_session, monkeypatch):
    owner = await make_user(telegram_id=8009)
    viewer = await make_user(telegram_id=8010, x_username="v")
    # x_link has no /status/ id and tweet_id empty → can't verify → passed (skipped)
    post = await _make_post(db_session, owner_id=owner.id, escrow="50", tweet_id="", x_link="https://x.com/owner")
    eng = await _make_engagement(db_session, user_id=viewer.id, post_id=post.id)
    batch = await _make_batch(db_session, user_id=viewer.id, engagement_ids=[eng.id])
    _mock_twitter(monkeypatch, passed=False)  # must NOT be consulted

    await claims.run_batch(db_session, batch.id)
    assert (batch.passed, batch.failed) == (1, 0)
    assert viewer.credits == Decimal("1.0000")


async def test_daily_cap_skips_award_preserving_escrow(client, make_user, db_session, monkeypatch):
    owner = await make_user(telegram_id=8011)
    # already at the daily cap (100) → no headroom
    viewer = await make_user(
        telegram_id=8012, x_username="v",
        daily_credits_earned=Decimal("100"), daily_earned_reset_at=datetime.utcnow(),
    )
    post = await _make_post(db_session, owner_id=owner.id, escrow="50")
    eng = await _make_engagement(db_session, user_id=viewer.id, post_id=post.id)
    batch = await _make_batch(db_session, user_id=viewer.id, engagement_ids=[eng.id])
    _mock_twitter(monkeypatch, passed=True)

    await claims.run_batch(db_session, batch.id)
    assert batch.passed == 1                  # passed verification
    assert batch.credits_awarded == Decimal("0")
    assert post.escrow == Decimal("50.0000")  # escrow preserved (skipped, not partial)
    assert eng.verified is True and eng.credit_granted is False


async def test_rerun_is_idempotent(client, make_user, db_session, monkeypatch):
    owner = await make_user(telegram_id=8013)
    viewer = await make_user(telegram_id=8014, x_username="v")
    post = await _make_post(db_session, owner_id=owner.id, escrow="50")
    eng = await _make_engagement(db_session, user_id=viewer.id, post_id=post.id)
    batch = await _make_batch(db_session, user_id=viewer.id, engagement_ids=[eng.id])
    _mock_twitter(monkeypatch, passed=True)

    await claims.run_batch(db_session, batch.id)
    second = await claims.run_batch(db_session, batch.id)
    assert second.get("already_processed") is True
    assert viewer.credits == Decimal("1.0000")  # not double-credited


# ============ queue-claim gates (endpoint) ============
def _no_background(monkeypatch):
    async def _noop(batch_id):
        return None
    monkeypatch.setattr(claims, "process_batch_in_new_session", _noop)


def _seed(db, **kv):
    for k, v in kv.items():
        db.add(SiteSetting(key=k, value=str(v), data_type="int"))


async def test_queue_requires_x_username(client, make_user):
    await make_user(telegram_id=8015)  # no x_username
    r = await client.post("/session/queue-claim/", params={"telegram_id": 8015})
    assert r.status_code == 400
    assert r.json()["error"] == "x_account_required"


async def test_queue_not_enough_engagements(client, make_user, db_session):
    _seed(db_session, MIN_ENGAGEMENTS_TO_CLAIM=2)
    await db_session.commit()
    site_settings._cache.clear()
    await make_user(telegram_id=8016, x_username="v")
    r = await client.post("/session/queue-claim/", params={"telegram_id": 8016})
    assert r.status_code == 200
    assert r.json()["success"] is False
    assert r.json()["pending_count"] == 0


async def test_queue_duration_gate(client, make_user, db_session, monkeypatch):
    _seed(db_session, MIN_ENGAGEMENTS_TO_CLAIM=1, MIN_SESSION_DURATION_SECONDS=3600)
    owner = await make_user(telegram_id=8017)
    viewer = await make_user(telegram_id=8018, x_username="v")
    post = await _make_post(db_session, owner_id=owner.id)
    await _make_engagement(db_session, user_id=viewer.id, post_id=post.id)
    site_settings._cache.clear()
    r = await client.post("/session/queue-claim/", params={"telegram_id": 8018})
    body = r.json()
    assert body["success"] is False
    assert body["error"] == "insufficient_engagement_time"
    assert body["remaining_seconds"] > 0


async def test_queue_success_creates_batch(client, make_user, db_session, monkeypatch):
    _seed(db_session, MIN_ENGAGEMENTS_TO_CLAIM=1, MIN_SESSION_DURATION_SECONDS=0)
    owner = await make_user(telegram_id=8019)
    viewer = await make_user(telegram_id=8020, x_username="v")
    post = await _make_post(db_session, owner_id=owner.id)
    await _make_engagement(db_session, user_id=viewer.id, post_id=post.id)
    site_settings._cache.clear()
    _no_background(monkeypatch)  # don't actually process in this endpoint test

    r = await client.post("/session/queue-claim/", params={"telegram_id": 8020})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["status"] == "pending"
    assert body["engagement_count"] == 1
    assert body["position"] == 1


# ============ claim history (endpoint) ============
async def test_claim_history_lists_batches(client, make_user, db_session):
    viewer = await make_user(telegram_id=8021, x_username="v")
    await _make_batch(db_session, user_id=viewer.id, engagement_ids=[uuid.uuid4()])

    r = await client.get("/claims/history/", params={"telegram_id": 8021})
    assert r.status_code == 200
    body = r.json()
    assert len(body["batches"]) == 1
    assert body["batches"][0]["status"] == "pending"
    assert body["has_processing"] is True
