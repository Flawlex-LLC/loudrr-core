from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.admin_panel import mount_admin
from app.api import (
    admin as admin_api,
    claims,
    feature_interest,
    posts,
    sessions,
    site_settings,
    users,
    waitlist,
    x_verification,
)
from app.core.config import settings
from app.core.deps import get_current_user
from app.core.exception_handlers import register_exception_handlers
from app.core.limiter import limiter
from app.db.session import engine, SessionLocal, get_session
from app.models.user import User
from app.services.site_settings import get_setting
from app.services.tier import load_tiers_from_settings

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
    # rebuild the in-memory tier bands from any TIER_* SiteSetting overrides;
    # a failure here is non-fatal — fall back to the hardcoded defaults so the
    # app can still boot during a partial migration / empty-DB scenario.
    try:
        async with SessionLocal() as _tier_db:
            await load_tiers_from_settings(_tier_db)
    except Exception as e:  # pragma: no cover — defensive
        print(f"WARNING: load_tiers_from_settings failed at startup: {e!r} — using defaults")
    yield
    # close the shared arq/Redis pool (if one was opened by enqueue())
    from app.tasks.enqueue import close_pool
    await close_pool()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# CORS — the Next.js frontend proxies same-origin in prod, but allow the
# configured origins for direct/dev calls. CORS_ALLOWED_ORIGINS is comma-sep.
_cors_origins = [o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def security_headers(request, call_next):
    """Defensive response headers on every response (closes the ZAP baseline
    warnings). Values suit a JSON API plus the one standalone HTML page (the X
    OAuth callback, which uses only inline styles): CSP allows inline style but
    nothing else, and CORP is 'cross-origin' because a separate frontend calls
    this API."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
    )
    response.headers.setdefault("Cross-Origin-Resource-Policy", "cross-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'",
    )
    return response


app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]  # slowapi handler signature; runtime is correct
app.include_router(site_settings.router)
register_exception_handlers(app)


@app.get("/health")
def health_check():
    return {"status": "ok"}


# Public mini-app settings (the frontend fetches this once on load to know the
# post-cost range). Matches the Django contract path /api/miniapp/settings/.
@app.get("/settings/")
async def miniapp_settings(db=Depends(get_session)):
    return {
        "post_cost_min": await get_setting(db, "POST_COST_MIN"),
        "post_cost_max": await get_setting(db, "POST_COST_MAX"),
    }


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
# privileged admin API (RBAC-gated; service-backed). Distinct from the SQLAdmin
# UI at /admin — this one is for the Next.js admin dashboard and CLI tools.
app.include_router(admin_api.router)

# the SQLAdmin operations panel at /admin (separate admin login)
mount_admin(app)