from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import (AsyncSession, 
                                    async_sessionmaker, create_async_engine)
from app.core.config import settings

# the engine, it is the db connection pool. 
engine = create_async_engine(settings.database_url, echo=settings.debug)

# the sessionmaker, it is a factory for creating new sessions.
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session