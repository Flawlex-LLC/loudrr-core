"""The transactional outbox (Ch15, spec §5.5).

`queue()` inserts a pending event in the CALLER's transaction (no commit here)
— so the side-effect commits atomically with the business write, or not at all.
`drain()` is the worker body: claim pending events, dispatch them, mark sent or
(after max_retries) failed. Ch16 schedules drain/retry/cleanup; the logic lives
here and can be run by hand.
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import delete, select

from app.integrations.telegram import get_telegram_client
from app.models.outbox_event import OutboxEvent, OutboxEventType, OutboxStatus
from app.repositories.outbox_event import OutboxEventRepository

logger = logging.getLogger(__name__)


class OutboxService:
    """Create outbox events inside a business transaction. NO commit here."""

    @staticmethod
    async def queue(db, event_type: str, payload: dict) -> OutboxEvent:
        return await OutboxEventRepository(db).create(
            event_type=event_type, payload=payload, status=OutboxStatus.PENDING.value,
        )

    @staticmethod
    async def queue_telegram_notification(db, *, telegram_id, message, **extra) -> OutboxEvent:
        return await OutboxService.queue(
            db, OutboxEventType.TELEGRAM_NOTIFY.value,
            {"telegram_id": telegram_id, "message": message, **extra},
        )

    @staticmethod
    async def queue_waitlist_submitted(db, *, entry_id, telegram_id, x_username, email="") -> OutboxEvent:
        return await OutboxService.queue(
            db, OutboxEventType.WAITLIST_SUBMITTED.value,
            {"entry_id": str(entry_id), "telegram_id": telegram_id,
             "x_username": x_username, "email": email},
        )

    @staticmethod
    async def queue_waitlist_approved(db, *, entry_id, telegram_id, x_username) -> OutboxEvent:
        return await OutboxService.queue(
            db, OutboxEventType.WAITLIST_APPROVED.value,
            {"entry_id": str(entry_id), "telegram_id": telegram_id, "x_username": x_username},
        )


# ---- dispatch ----
def _waitlist_submitted_text(p: dict) -> str:
    return (
        "🎉 You're on the Loudrr waitlist"
        + (f", @{p['x_username']}" if p.get("x_username") else "")
        + "! We'll message you the moment you're approved."
    )


def _waitlist_approved_text(p: dict) -> str:
    return (
        "✅ You're in! Your Loudrr access is approved"
        + (f", @{p['x_username']}" if p.get("x_username") else "")
        + ". Open the app to start earning karma."
    )


async def _dispatch(ev: OutboxEvent) -> None:
    """Deliver one event by type. Raises on failure (→ retry)."""
    p = ev.payload or {}
    telegram = get_telegram_client()

    if ev.event_type == OutboxEventType.TELEGRAM_NOTIFY.value:
        await telegram.send_message(p["telegram_id"], p.get("message", ""))
    elif ev.event_type == OutboxEventType.WAITLIST_SUBMITTED.value:
        if p.get("telegram_id"):
            await telegram.send_message(p["telegram_id"], _waitlist_submitted_text(p))
    elif ev.event_type == OutboxEventType.WAITLIST_APPROVED.value:
        if p.get("telegram_id"):
            await telegram.send_message(p["telegram_id"], _waitlist_approved_text(p))
    else:
        # credits_earned / post_completed / tweetscout_fetch / external_api etc.
        # currently just logged (tweetscout_fetch is handled by its own task, Ch16)
        logger.info("Outbox event %s (%s) — logged, no handler", ev.id, ev.event_type)


async def drain(db, *, limit: int = 50) -> dict:
    """Claim up to `limit` pending events and deliver them."""
    rows = (
        await db.execute(
            select(OutboxEvent)
            .where(OutboxEvent.status == OutboxStatus.PENDING.value)
            .order_by(OutboxEvent.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()

    for ev in rows:
        ev.status = OutboxStatus.PROCESSING.value
    await db.flush()

    sent = failed = 0
    for ev in rows:
        try:
            await _dispatch(ev)
            ev.status = OutboxStatus.SENT.value
            ev.processed_at = datetime.utcnow()
            ev.error_message = ""
            sent += 1
        except Exception as e:  # noqa: BLE001 — any delivery failure → retry/fail
            ev.retry_count += 1
            ev.error_message = str(e)[:500]
            ev.status = (
                OutboxStatus.FAILED.value
                if ev.retry_count >= ev.max_retries
                else OutboxStatus.PENDING.value
            )
            failed += 1
        ev.updated_at = datetime.utcnow()

    await db.commit()
    return {"processed": len(rows), "sent": sent, "failed": failed}


async def retry_failed(db) -> int:
    """Reset failed events (still under max_retries) back to pending."""
    rows = (
        await db.execute(
            select(OutboxEvent).where(
                OutboxEvent.status == OutboxStatus.FAILED.value,
                OutboxEvent.retry_count < OutboxEvent.max_retries,
            )
        )
    ).scalars().all()
    for ev in rows:
        ev.status = OutboxStatus.PENDING.value
    await db.commit()
    return len(rows)


async def cleanup_old(db, *, older_than_days: int = 30) -> int:
    """Delete sent events older than N days."""
    cutoff = datetime.utcnow() - timedelta(days=older_than_days)
    result = await db.execute(
        delete(OutboxEvent).where(
            OutboxEvent.status == OutboxStatus.SENT.value,
            OutboxEvent.created_at < cutoff,
        )
    )
    await db.commit()
    return result.rowcount or 0
