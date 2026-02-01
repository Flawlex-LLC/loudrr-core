"""
Production safety guards for Loudrr.

These guards prevent dangerous operations during production freeze
and provide checks for maintenance mode.

Usage:
    from core.guards import require_production_unlocked, check_maintenance_mode

    @require_production_unlocked
    def dangerous_operation():
        # Only executes if PRODUCTION_LOCK is False
        ...

    # Or check manually:
    from core.guards import is_production_locked
    if not is_production_locked():
        # Safe to proceed
        ...
"""
from functools import wraps
from django.core.exceptions import PermissionDenied


class ProductionLockError(PermissionDenied):
    """Raised when a dangerous operation is attempted during production lock."""

    def __init__(self, operation: str = "this operation"):
        super().__init__(
            f"Production freeze active. Cannot perform {operation}. "
            "Disable PRODUCTION_LOCK in admin settings to proceed."
        )


class MaintenanceModeError(PermissionDenied):
    """Raised when the app is in maintenance mode."""

    def __init__(self):
        super().__init__(
            "The app is currently under maintenance. Please try again later."
        )


def get_constance_config():
    """Get constance config with fallback for testing."""
    try:
        from constance import config
        return config
    except Exception:
        # Fallback for tests or when constance isn't available
        class FakeConfig:
            PRODUCTION_LOCK = False
            MAINTENANCE_MODE = False
        return FakeConfig()


def is_production_locked() -> bool:
    """Check if production lock is enabled."""
    config = get_constance_config()
    return getattr(config, 'PRODUCTION_LOCK', False)


def is_maintenance_mode() -> bool:
    """Check if maintenance mode is enabled."""
    config = get_constance_config()
    return getattr(config, 'MAINTENANCE_MODE', False)


def require_production_unlocked(func=None, operation: str = None):
    """
    Decorator to require production lock to be disabled.

    Usage:
        @require_production_unlocked
        def create_campaign():
            ...

        @require_production_unlocked(operation="create campaign")
        def create_campaign():
            ...
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if is_production_locked():
                op_name = operation or f.__name__.replace('_', ' ')
                raise ProductionLockError(op_name)
            return f(*args, **kwargs)
        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


def require_maintenance_off(func):
    """Decorator to require maintenance mode to be disabled."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if is_maintenance_mode():
            raise MaintenanceModeError()
        return func(*args, **kwargs)
    return wrapper


def check_production_lock(operation: str = "this operation"):
    """
    Explicitly check production lock and raise if locked.

    Usage:
        from core.guards import check_production_lock

        def create_payout():
            check_production_lock("create payout")
            # ... proceed with payout
    """
    if is_production_locked():
        raise ProductionLockError(operation)


def check_maintenance_mode():
    """Explicitly check maintenance mode and raise if enabled."""
    if is_maintenance_mode():
        raise MaintenanceModeError()
