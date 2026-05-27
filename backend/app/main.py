from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from sqlalchemy import text
from app.core.config import settings
from app.db.session import engine, get_session
from app.db.base import Base
from app.core.deps import get_current_user
from app.models.user import User
from app.api import site_settings
from decimal import Decimal
from app.services.credits import CreditService
from app.api import waitlist
from app.api import users
from app.api import x_verification
from app.api import sessions
from app.api import claims
from app.api import posts
from app.api import feature_interest
from app.admin_panel import mount_admin
from app.core.limiter import limiter
from app.core.exception_handlers import register_exception_handlers
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

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
    if settings.debug:
        # the ?telegram_id= auth bypass is active in debug — MUST be off in prod
        print("WARNING: DEBUG=True — Telegram auth bypass is ENABLED. Never run prod like this.")
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# CORS — the Next.js frontend proxies same-origin in prod, but allow the
# configured origins for direct/dev calls. CORS_ALLOWED_ORIGINS is comma-sep.
_cors_origins = [o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()]
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(site_settings.router)
register_exception_handlers(app)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/whoami")
async def whoami(user: User = Depends(get_current_user)):
    return {"UUID": user.id, "username": user.telegram_username}


app.include_router(waitlist.router)
app.include_router(users.router)
app.include_router(x_verification.router)
app.include_router(sessions.router)
app.include_router(claims.router)
app.include_router(posts.router)
app.include_router(feature_interest.router)

# the SQLAdmin operations panel at /admin (separate admin login)
mount_admin(app)