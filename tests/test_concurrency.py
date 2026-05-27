"""Security: prove the SELECT ... FOR UPDATE row lock actually prevents a
double-spend under genuine concurrency (two parallel requests, real separate
DB connections). Without the lock, both could read the old balance and oversell.
"""
import asyncio
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.user import User
from app.services.credits import CreditService, InsufficientCreditsError

TEST_DATABASE_URL = settings.database_url.rsplit("/", 1)[0] + "/loudrr_test"


async def test_concurrent_spend_cannot_oversell(db_session, make_user):
    # db_session created the schema + this committed user on loudrr_test
    user = await make_user(credits=Decimal("100"), total_credits_earned=Decimal("100"))
    uid = user.id

    # two INDEPENDENT sessions/connections — real concurrency, not the fixture's one
    engine = create_async_engine(TEST_DATABASE_URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def attempt() -> str:
        async with Session() as s:
            u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
            try:
                await CreditService(s, u).spend(
                    Decimal("60"), idempotency_key=f"spend-{uuid.uuid4().hex}"
                )
                return "ok"
            except InsufficientCreditsError:
                return "insufficient"

    try:
        r1, r2 = await asyncio.gather(attempt(), attempt())
    finally:
        await engine.dispose()

    # exactly one of the two 60-spends on a 100 balance may succeed
    assert sorted([r1, r2]) == ["insufficient", "ok"]
    await db_session.refresh(user)
    assert user.credits == Decimal("40")   # never -20 → the lock held
