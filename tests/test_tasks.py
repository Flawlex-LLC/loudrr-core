"""Ch16 — background-task logic (tested directly, no Redis) + worker config."""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.models.post import Post
from app.services import maintenance
from app.services import users as users_svc
from app.services.users import get_tweetscout_client  # noqa: F401 (patched target)


# ---- reset_daily_credits ----
async def test_reset_daily_credits(make_user, db_session):
    await make_user(telegram_id=10001, daily_credits_earned=Decimal("80"))
    await make_user(telegram_id=10002, daily_credits_earned=Decimal("30"))
    n = await maintenance.reset_daily_credits(db_session)
    assert n == 2
    # re-query
    from app.repositories.user import UserRepository
    u = await UserRepository(db_session).get(telegram_id=10001)
    assert u.daily_credits_earned == Decimal("0")


# ---- expire_old_posts ----
async def test_expire_old_posts_cancels_and_refunds(make_user, db_session):
    owner = await make_user(telegram_id=10003, credits=Decimal("0"), total_credits_earned=Decimal("0"))
    stale = Post(
        user_id=owner.id, x_link="https://x.com/o/status/1", escrow=Decimal("50"),
        initial_escrow=Decimal("50"), status="active", platform="web",
        created_at=datetime.utcnow() - timedelta(hours=50),  # > 48h default
    )
    fresh = Post(
        user_id=owner.id, x_link="https://x.com/o/status/2", escrow=Decimal("50"),
        initial_escrow=Decimal("50"), status="active", platform="web",
        created_at=datetime.utcnow(),
    )
    db_session.add_all([stale, fresh])
    await db_session.commit()

    n = await maintenance.expire_old_posts(db_session)
    assert n == 1
    await db_session.refresh(stale)
    await db_session.refresh(fresh)
    assert stale.status == "cancelled" and stale.escrow == Decimal("0.0000")
    assert fresh.status == "active"
    await db_session.refresh(owner)
    assert owner.credits == Decimal("50.0000")  # refunded


# ---- fetch_tweetscout_for_user ----
class _FakeTweetScout:
    async def get_user_data(self, username):
        return {"id": "9", "screen_name": "v", "name": "V", "followers_count": 5, "score": 250}


async def test_fetch_tweetscout_for_user(make_user, db_session, monkeypatch):
    user = await make_user(telegram_id=10004, x_username="v")
    monkeypatch.setattr(users_svc, "get_tweetscout_client", lambda: _FakeTweetScout())
    ok = await users_svc.fetch_tweetscout_for_user(db_session, user.id)
    assert ok is True
    await db_session.refresh(user)
    assert user.tweetscout_score == 250
    from app.repositories.x_profile import XProfileRepository
    assert await XProfileRepository(db_session).get(user_id=user.id) is not None


async def test_fetch_tweetscout_no_username(make_user, db_session):
    user = await make_user(telegram_id=10005)  # no x_username
    assert await users_svc.fetch_tweetscout_for_user(db_session, user.id) is False


# ---- worker config is valid ----
def test_worker_settings_registered():
    from app.tasks.worker import WorkerSettings
    names = {f.__name__ for f in WorkerSettings.functions}
    assert "process_verification_batch" in names
    assert "process_pending_outbox_events" in names
    assert len(WorkerSettings.functions) == 7
    assert len(WorkerSettings.cron_jobs) == 5
