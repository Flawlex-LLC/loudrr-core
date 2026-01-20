# Generated manually - Remove dead session models

from django.db import migrations


class Migration(migrations.Migration):
    """
    Remove EngagementSession and SessionClick models.

    These models were designed but never used. The engagement flow uses
    Engagement model from posts app directly with user-level progress tracking
    (verified=False) instead of session-based tracking.

    This approach is more robust for Telegram Mini Apps where frontend
    state can be lost on app close/reopen.
    """

    dependencies = [
        ('miniapp', '0003_remove_pro_intent_fields'),
    ]

    operations = [
        # Delete SessionClick first (has FK to EngagementSession)
        migrations.DeleteModel(name='SessionClick'),
        # Then delete EngagementSession
        migrations.DeleteModel(name='EngagementSession'),
    ]
