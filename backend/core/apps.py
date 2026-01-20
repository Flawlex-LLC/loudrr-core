from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        """Register Django built-in models with auditlog."""
        from auditlog.registry import auditlog
        from django.contrib.auth.models import Group

        # Track permission group changes
        auditlog.register(Group)
