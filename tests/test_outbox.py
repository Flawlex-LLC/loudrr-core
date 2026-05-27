"""Ch15 — transactional outbox: queue, drain, retry, and waitlist wiring.
Telegram is mocked."""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.integrations import telegram
from app.models.outbox_event import OutboxEvent, OutboxStatus
from app.repositories.outbox_event import OutboxEventRepository
from app.services import outbox
from app.services.outbox import OutboxService


class _FakeTelegram:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.sent = []

    async def send_message(self, chat_id, text, parse_mode="HTML"):
        if self.fail:
            raise RuntimeError("telegram down")
        self.sent.append((chat_id, text))
        return True


def _mock_telegram(monkeypatch, **kw):
    monkeypatch.setattr(telegram, "get_telegram_client", lambda: _FakeTelegram(**kw))
    # outbox imported get_telegram_client by name — patch there too
    monkeypatch.setattr(outbox, "get_telegram_client", telegram.get_telegram_client)


async def test_queue_creates_pending_event(db_session):
    ev = await OutboxService.queue_telegram_notification(
        db_session, telegram_id=123, message="hi"
    )
    await db_session.commit()
    assert ev.status == "pending"
    assert ev.payload["telegram_id"] == 123


async def test_drain_sends_and_marks_sent(db_session, monkeypatch):
    _mock_telegram(monkeypatch)
    await OutboxService.queue_telegram_notification(db_session, telegram_id=7, message="yo")
    await db_session.commit()

    result = await outbox.drain(db_session)
    assert result == {"processed": 1, "sent": 1, "failed": 0}

    ev = (await OutboxEventRepository(db_session).list(limit=1))[0]
    assert ev.status == "sent"
    assert ev.processed_at is not None


async def test_drain_retries_then_fails(db_session, monkeypatch):
    _mock_telegram(monkeypatch, fail=True)
    ev = await OutboxService.queue_telegram_notification(db_session, telegram_id=9, message="x")
    await db_session.commit()

    await outbox.drain(db_session)
    await db_session.refresh(ev)
    assert ev.status == "pending" and ev.retry_count == 1  # back to pending for retry

    await outbox.drain(db_session)
    await outbox.drain(db_session)
    await db_session.refresh(ev)
    assert ev.status == "failed" and ev.retry_count == 3  # exhausted max_retries


async def test_retry_failed_resets(db_session, monkeypatch):
    _mock_telegram(monkeypatch, fail=True)
    ev = await OutboxService.queue_telegram_notification(db_session, telegram_id=1, message="x")
    ev.max_retries = 5  # so it doesn't hit FAILED on a single drain
    await db_session.commit()
    await outbox.drain(db_session)
    await db_session.refresh(ev)
    # force it to failed to test the reset path
    ev.status = OutboxStatus.FAILED.value
    await db_session.commit()

    n = await outbox.retry_failed(db_session)
    assert n == 1
    await db_session.refresh(ev)
    assert ev.status == "pending"


async def test_cleanup_deletes_old_sent(db_session):
    old = OutboxEvent(
        event_type="telegram_notify", status="sent", payload={},
        created_at=datetime.utcnow() - timedelta(days=40),
    )
    db_session.add(old)
    await db_session.commit()
    n = await outbox.cleanup_old(db_session, older_than_days=30)
    assert n == 1


async def test_waitlist_register_queues_event(client, db_session):
    # registering through the API should leave a waitlist_submitted outbox row
    r = await client.post(
        "/waitlist/register/",
        params={"telegram_id": 555},
        json={"email": "a@b.com", "x_link": "https://x.com/someone"},
    )
    assert r.status_code == 200
    events = await OutboxEventRepository(db_session).list(limit=10)
    types = {e.event_type for e in events}
    assert "waitlist_submitted" in types
