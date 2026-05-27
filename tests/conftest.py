import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import settings
from app.db.base import Base
import app.models  # noqa: F401 — registers every table on Base.metadata
from app.models.user import User
from app.models.site_setting import SiteSetting
from app.services import site_settings

# Same Postgres server as the app (and the Django project), but a SEPARATE
# database so tests never touch real data. Create it once:
#   CREATE DATABASE loudrr_test;
TEST_DATABASE_URL = settings.database_url.rsplit("/", 1)[0] + "/loudrr_test"


@pytest_asyncio.fixture
async def db_session():
    """One fresh, empty schema per test — total isolation."""
    engine = create_async_engine(TEST_DATABASE_URL)
    # BEFORE the test: drop anything left over, then build every table
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        # the credit service reads DAILY_EARN_CAP from site_settings,
        # so seed it — earn() needs a cap to check against
        session.add(SiteSetting(
            key="DAILY_EARN_CAP", value="100", data_type="int",
        ))
        await session.commit()
        # the settings helper caches values for 5 minutes; clear it so
        # THIS row is read fresh, not a value cached by an earlier test
        site_settings._cache.clear()
        yield session  # the test runs here, with this session
    # AFTER the test: drop everything, close the connection pool
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def make_user(db_session):
    """Factory: ``await make_user(credits=Decimal('50'))`` -> a saved User.
    Defaults give a valid zero-balance user, with unique values for the
    UNIQUE columns so two users in one test never collide."""
    async def _make(**overrides):
        values = dict(
            telegram_id=uuid.uuid4().int % 1_000_000_000,
            referral_code=uuid.uuid4().hex[:10].upper(),
            credits=Decimal("0"),
            total_credits_earned=Decimal("0"),
            total_credits_spent=Decimal("0"),
        )
        values.update(overrides)  # the test's overrides win
        user = User(**values)
        db_session.add(user)
        await db_session.commit()
        return user
    return _make


@pytest_asyncio.fixture
async def client(db_session):
    """An httpx client wired to the real app, but pointed at the test session
    and with rate-limiting off. Endpoints authenticate via ``?telegram_id=``
    (the debug bypass), since settings.debug is True in .env."""
    from app.main import app
    from app.db.session import get_session

    async def _use_test_session():
        yield db_session

    app.dependency_overrides[get_session] = _use_test_session
    app.state.limiter.enabled = False  # don't let 5/hour limits break tests
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    app.state.limiter.enabled = True