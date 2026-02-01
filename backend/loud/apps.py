from django.apps import AppConfig


class LoudConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'loud'
    verbose_name = 'Loud - UGC Rewards'

    def ready(self):
        """Import rules to register permissions."""
        from . import rules  # noqa: F401
