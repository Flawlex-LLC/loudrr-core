from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        """
        Register Django built-in models with auditlog.

        Import signals to ensure they are registered.
        Best practice: Import signals in ready() to avoid circular imports.
        """
        from auditlog.registry import auditlog
        from django.contrib.auth.models import Group

        # Track permission group changes
        auditlog.register(Group)

        # Import signals to register receivers (do not remove this import!)
        # The import registers the @receiver decorators
        from . import signals  # noqa: F401

        # Import rules to register permissions
        from . import rules  # noqa: F401
