"""
Dynamic settings service.

Provides cached access to site settings stored in the database.
All settings MUST exist in the SiteSettings table (seeded via migrations).

Usage:
    from core.services.settings import get_setting
    daily_cap = get_setting('DAILY_EARN_CAP')
"""
from django.core.cache import cache


def get_setting(key: str, default=None):
    """
    Get setting from database with caching.

    Priority: Cache -> DB -> Default -> KeyError

    Cached for 5 minutes to avoid DB hits on every request.

    Args:
        key: Setting key (e.g., 'DAILY_EARN_CAP')
        default: Default value if setting not found (optional)

    Returns:
        Setting value with proper type conversion

    Raises:
        KeyError: If setting not found and no default provided
    """
    # Try cache first
    cache_key = f'setting:{key}'
    value = cache.get(cache_key)
    if value is not None:
        return value

    # Query DB
    from core.models import SiteSetting
    try:
        setting = SiteSetting.objects.get(key=key)
        value = setting.get_value()
        cache.set(cache_key, value, timeout=300)  # 5 min cache
        return value
    except SiteSetting.DoesNotExist:
        if default is not None:
            return default
        raise KeyError(f"Setting '{key}' not found in database. Run migrations.")


def set_setting(key: str, value, data_type: str = 'int', description: str = '', user=None):
    """
    Set a setting value programmatically.

    Args:
        key: Setting key
        value: Value to set
        data_type: One of 'int', 'float', 'bool', 'str'
        description: Description of the setting
        user: User making the change (for audit)
    """
    from core.models import SiteSetting

    setting, created = SiteSetting.objects.update_or_create(
        key=key,
        defaults={
            'value': str(value),
            'data_type': data_type,
            'description': description,
            'updated_by': user,
        }
    )
    # Clear cache for this key
    cache.delete(f'setting:{key}')
    return setting


def clear_settings_cache():
    """
    Clear all settings cache.

    Call this after bulk updates to ensure fresh values.
    """
    from core.models import SiteSetting
    for setting in SiteSetting.objects.all():
        cache.delete(f'setting:{setting.key}')


def get_all_settings() -> dict:
    """
    Get all settings as a dictionary.

    Useful for debugging or admin dashboard.
    """
    from core.models import SiteSetting
    return {setting.key: setting.get_value() for setting in SiteSetting.objects.all()}
