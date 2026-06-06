"""Ch16 — background-task logic (tested directly, no Redis) + worker config."""
from datetime import timedelta
from decimal import Decimal


from app.core.time_utils import utcnow
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
        created_at=utcnow() - timedelta(hours=50),  # > 48h default
    )
    fresh = Post(
        user_id=owner.id, x_link="https://x.com/o/status/2", escrow=Decimal("50"),
        initial_escrow=Decimal("50"), status="active", platform="web",
        created_at=utcnow(),
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
    # service-audit P1: requeue_stuck_batches recovers from worker death
    assert "requeue_stuck_batches" in names
    assert len(WorkerSettings.functions) == 8
    assert len(WorkerSettings.cron_jobs) == 6


# ---- requeue_stuck_batches (service-audit P1: stuck-batch recovery) ----
async def test_requeue_stuck_batches_recovers_old_pending(
    make_user, db_session
):
    """A batch stuck in PROCESSING past the cutoff should flip back to PENDING
    and call the schedule hook with its id."""
    from datetime import timedelta
    from app.models.verification_batch import BatchStatus, VerificationBatch
    from app.services import claims

    user = await make_user(telegram_id=10101, x_username="v")
    stuck = VerificationBatch(
        user_id=user.id, engagement_ids=[],
        status=BatchStatus.PROCESSING.value,
        created_at=utcnow() - timedelta(minutes=20),  # past the 10-min cutoff
    )
    fresh = VerificationBatch(
        user_id=user.id, engagement_ids=[],
        status=BatchStatus.PROCESSING.value,
        created_at=utcnow(),  # too young — should NOT requeue
    )
    db_session.add_all([stuck, fresh])
    await db_session.commit()

    scheduled: list = []

    async def _schedule(batch_id):
        scheduled.append(batch_id)

    n = await claims.requeue_stuck_batches(db_session, schedule=_schedule)
    assert n == 1
    await db_session.refresh(stuck)
    await db_session.refresh(fresh)
    assert stuck.status == "pending"
    assert fresh.status == "processing"  # young one untouched
    assert scheduled == [stuck.id]
