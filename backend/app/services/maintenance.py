"""Periodic-maintenance logic (Ch16) — the bodies of the scheduled tasks.

Kept as plain async functions taking a session, so they're testable without
Redis/arq. The arq worker (app/tasks/worker.py) wraps each in its own session.
"""
import logging
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select, update

from app.core.time_utils import utcnow
from app.models.post import Post
from app.models.user import User
from app.repositories.user import UserRepository
from app.services import posts as posts_svc
from app.services.outbox import OutboxService
from app.services.site_settings import get_setting

logger = logging.getLogger(__name__)


async def reset_daily_credits(db) -> int:
    """Zero every user's daily earn counter (runs at midnight UTC)."""
    result = await db.execute(
        update(User).values(
            daily_credits_earned=Decimal("0"), daily_earned_reset_at=utcnow()
        )
    )
    await db.commit()
    return result.rowcount or 0


async def expire_old_posts(db) -> int:
    """Cancel + refund active posts older than POST_EXPIRY_HOURS (hourly)."""
    hours = await get_setting(db, "POST_EXPIRY_HOURS", 48)
    cutoff = utcnow() - timedelta(hours=int(hours))
    stale = (
        await db.execute(
            select(Post).where(Post.status == "active", Post.created_at < cutoff)
        )
    ).scalars().all()
    count = 0
    for post in stale:
        # capture the refund amount before cancel_post zeros the escrow
        refund_amount = post.escrow
        poster = await UserRepository(db).get(id=post.user_id)
        await posts_svc.cancel_post(db, post, refund=True)  # commits per post
        # queue the user-facing notification in its own follow-up txn (cancel_post
        # already committed). This is best-effort — the cancel/refund itself is
        # the source of truth; the outbox just tells the user.
        if poster is not None and poster.telegram_id is not None:
            await OutboxService.queue_post_expired(
                db, post_id=post.id, user_id=post.user_id,
                telegram_id=poster.telegram_id, refund_amount=refund_amount,
            )
            await db.commit()
        count += 1
    if count:
        logger.info("expire_old_posts: cancelled+refunded %s posts", count)
    return count
