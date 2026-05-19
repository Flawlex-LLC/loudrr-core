from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from sqlalchemy import text
from app.core.config import settings
from app.api import quests, users
from app.db.session import engine
from app.db.base import Base
from app.api.deps import get_current_user
from app.models.user import User


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.connect() as conn:
        # create_all is removed since alembic is used for migrations, 
        # and it can cause issues with the migration process. 
        # we can ensure that the database connection is working 
        # by executing a simple query.
        # await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("SELECT 1"))
    print("Database connection: OK")
    yield

app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(users.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/whoami")
async def whoami(user: User = Depends(get_current_user)):
    return {"UUID": user.id, "username": user.telegram_username}