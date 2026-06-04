"""Seed the SiteSetting rows the app expects at runtime.

Idempotent: upserts each key. Defaults match the Django reference's `ECHO_CONFIG`
(echo/settings.py) for the shared keys; the rest come from the Django runtime
fallbacks (miniapp/views.py) — `MIN_ENGAGEMENTS_TO_CLAIM=10`,
`MIN_SESSION_DURATION_SECONDS=150`, `POST_EXPIRY_HOURS=48`. POST_COST_MIN/MAX
are FastAPI-specific bounds (the Django reference uses a flat POST_COST); we
default to a small range around POST_COST so submit_post's clamp logic has
room to work.

Run from backend/ with:
    ../.venv/Scripts/python.exe -m scripts.seed_settings
"""
import asyncio

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.site_setting import SiteSetting
from app.services import site_settings as site_settings_svc

# (key, value, data_type, description)
DEFAULTS = [
    ("POST_COST", "80", "int", "Default cost to submit a post (Django ECHO_CONFIG)"),
    ("POST_COST_MIN", "10", "int", "Minimum karma a creator can stake on a post"),
    ("POST_COST_MAX", "200", "int", "Maximum karma a creator can stake on a post"),
    ("CREDIT_PER_ENGAGEMENT", "1", "int", "Karma awarded per verified engagement"),
    ("DAILY_EARN_CAP", "160", "int", "Per-user daily karma earn ceiling"),
    ("MIN_ENGAGEMENTS_TO_CLAIM", "10", "int", "Pending engagements required before /session/complete/"),
    ("MIN_SESSION_DURATION_SECONDS", "150", "int", "Anti-gaming: seconds between first click and claim"),
    ("POST_EXPIRY_HOURS", "48", "int", "Hours after which an active post expires"),
]


async def seed() -> None:
    upserted, updated, unchanged = [], [], []
    async with SessionLocal() as db:
        for key, value, data_type, desc in DEFAULTS:
            row = (
                await db.execute(select(SiteSetting).where(SiteSetting.key == key))
            ).scalar_one_or_none()
            if row is None:
                db.add(SiteSetting(
                    key=key, value=value, data_type=data_type, description=desc,
                ))
                upserted.append(key)
            elif row.value != value or row.data_type != data_type:
                row.value, row.data_type, row.description = value, data_type, desc
                updated.append(key)
            else:
                unchanged.append(key)
        await db.commit()

    # Bust the in-process 5-minute cache so a long-running app sees the new values
    site_settings_svc._cache.clear()

    if upserted:
        print(f"  created: {upserted}")
    if updated:
        print(f"  updated: {updated}")
    if unchanged:
        print(f"  unchanged: {unchanged}")
    print(f"  cache cleared — re-fetched on next request")
    print(f"  NOTE: a running uvicorn process has its own cache; restart it to pick up changes.")


if __name__ == "__main__":
    asyncio.run(seed())
