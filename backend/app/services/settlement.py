"""Phase 2 of verification — atomic settlement, NO external calls (spec §5.2).

One DB transaction. Locks the user, then all involved posts (sorted by id to
avoid deadlocks), then the engagements. For each PASSED engagement (in its own
savepoint): compute tiered karma, cap it at remaining escrow (partial payment),
deduct escrow, credit the engager (idempotent on engagement id), mark it
verified+credited, auto-complete the post if escrow hits 0. For each FAILED
engagement: delete it so the user can re-engage cleanly. Failures drop the
user's honesty score.
"""
import logging
import math
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from app.models.engagement import Engagement
from app.models.post import Post
from app.models.user import User
from app.services import tier
from app.services.credits import CreditService
from app.services.site_settings import get_setting

logger = logging.getLogger(__name__)


async def _settle_passed(db, user, post, engagement, r, base, credits):
    """Settle one PASSED engagement → (status, amount). status is one of
    'awarded' | 'partial' | 'skipped' | 'error'."""
    now = datetime.utcnow()

    if engagement is None or engagement.credit_granted or post is None:
        return ("skipped", Decimal("0"))

    if post.status != "active":
        engagement.verified = True
        engagement.reply_verified = r.reply_verified
        engagement.like_verified = r.like_verified
        engagement.credit_granted = False
        engagement.verification_data = {"verified_at": now.isoformat(), "result": "skipped_post_inactive"}
        return ("skipped", Decimal("0"))

    karma, multiplier = tier.karma_for(base, user.tweetscout_score or 0)

    # partial payment — never deduct more than the escrow holds
    if post.escrow < karma:
        if post.escrow <= 0:
            engagement.verified = True
            engagement.credit_granted = False
            engagement.verification_data = {"verified_at": now.isoformat(), "result": "skipped_no_escrow"}
            return ("skipped", Decimal("0"))
        karma = post.escrow

    # daily cap — skip the whole award (preserve escrow) if it won't fit
    if not await credits.can_earn(karma):
        engagement.verified = True
        engagement.credit_granted = False
        engagement.verification_data = {"verified_at": now.isoformat(), "result": "skipped_daily_cap"}
        return ("skipped", Decimal("0"))

    is_partial = karma < (base * multiplier)
    try:
        async with db.begin_nested():  # savepoint — one failure can't break the batch
            post.escrow = post.escrow - karma
            await credits.earn(
                karma, idempotency_key=str(engagement.id), reference_id=engagement.id,
                description=f"Engagement verified (x{multiplier})", commit=False,
            )
            engagement.verified = True
            engagement.reply_verified = r.reply_verified
            engagement.like_verified = r.like_verified
            engagement.credit_granted = True
            engagement.verification_data = {
                "verified_at": now.isoformat(), "result": "awarded",
                "amount": str(karma), "multiplier": str(multiplier),
            }
            if post.escrow <= 0:  # escrow depleted → auto-complete
                post.status = "completed"
                post.completed_at = now
            user.total_engagements += 1
            # TODO (sponsored): award sponsored XP here once the XP service exists
            await db.flush()
    except Exception:
        logger.exception("settlement failed for engagement %s", engagement.id)
        engagement.verified = True
        engagement.credit_granted = False
        return ("error", Decimal("0"))

    return ("partial" if is_partial else "awarded", karma)


async def settle(db, *, user_id, results) -> dict:
    """Phase 2. Returns {total_awarded: Decimal, new_balance: Decimal}."""
    if not results:
        return {"total_awarded": Decimal("0"), "new_balance": Decimal("0")}

    # lock order: user → posts (sorted) → engagements
    user = (
        await db.execute(
            select(User).where(User.id == user_id)
            .with_for_update().execution_options(populate_existing=True)
        )
    ).scalar_one()

    post_ids = sorted({r.post_id for r in results})
    posts = {}
    if post_ids:
        rows = (
            await db.execute(
                select(Post).where(Post.id.in_(post_ids)).order_by(Post.id)
                .with_for_update().execution_options(populate_existing=True)
            )
        ).scalars().all()
        posts = {p.id: p for p in rows}

    eng_ids = [r.engagement_id for r in results]
    engs = {}
    if eng_ids:
        rows = (
            await db.execute(
                select(Engagement)
                .where(Engagement.id.in_(eng_ids), Engagement.user_id == user_id)
                .with_for_update().execution_options(populate_existing=True)
            )
        ).scalars().all()
        engs = {e.id: e for e in rows}

    base = Decimal(str(await get_setting(db, "CREDIT_PER_ENGAGEMENT", 1)))
    credits = CreditService(db, user)
    total_awarded = Decimal("0")
    failures = 0

    for r in results:
        if r.passed:
            status, amount = await _settle_passed(
                db, user, posts.get(r.post_id), engs.get(r.engagement_id), r, base, credits
            )
            if status in ("awarded", "partial"):
                total_awarded += amount
        else:
            eng = engs.get(r.engagement_id)
            if eng is not None:
                await db.delete(eng)  # failed → delete so the user can re-engage
            failures += 1

    if failures > 0:
        drop = max(1, math.ceil(failures / 2))
        user.honesty_score = max(0, user.honesty_score - drop)

    await db.commit()
    return {"total_awarded": total_awarded, "new_balance": user.credits}
