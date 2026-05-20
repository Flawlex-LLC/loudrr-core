from sqlalchemy import select
from app.models.site_setting import SiteSetting
import time

# in-process cache for site settings to avoid hitting the database every time
_cache: dict = {}
_TTL_SECONDS = 300  # cache settings for 5 minutes

async def get_setting(db, key: str):
    """read a setting by key, cached for 5 minutes so it doesnt
    hit the database on every request."""
    cached = _cache.get(key)
    if cached and time.time() - cached[1] < _TTL_SECONDS:
        return cached [0]
    
    result = await db.execute(select(SiteSetting).where(SiteSetting.key == key))
    setting = result.scalar_one_or_none()
    if setting is None:
        raise KeyError(f"Setting with key '{key}' not found - seed it first!")
    
    # interpret
    value = int(setting.value) if setting.data_type == "int" else setting.value
    _cache[key] = (value, time.time())
    return value
