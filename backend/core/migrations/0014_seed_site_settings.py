# Generated manually - Seed SiteSettings with ECHO_CONFIG defaults

from django.db import migrations


def seed_settings(apps, schema_editor):
    """Populate SiteSettings with all ECHO_CONFIG values."""
    SiteSetting = apps.get_model('core', 'SiteSetting')

    # All settings from ECHO_CONFIG with descriptions
    settings_data = [
        # Core costs & caps
        ("POST_COST", "80", "int", "Credits required to submit a post"),
        ("CREDIT_PER_ENGAGEMENT", "1", "int", "Base credits earned per engagement"),
        ("DAILY_EARN_CAP", "160", "int", "Maximum credits earnable per day"),
        ("ENGAGEMENT_COOLDOWN", "0", "int", "Seconds between engagements (0 = no cooldown)"),
        ("AUDIT_PROBABILITY", "0.05", "float", "Random audit chance (0.05 = 5%)"),

        # Streak multipliers (currently disabled = 1.0)
        ("STREAK_7_DAY_MULTIPLIER", "1.0", "float", "Karma multiplier at 7-day streak"),
        ("STREAK_14_DAY_MULTIPLIER", "1.0", "float", "Karma multiplier at 14-day streak"),
        ("STREAK_30_DAY_MULTIPLIER", "1.0", "float", "Karma multiplier at 30-day streak"),

        # Streak bonuses
        ("STREAK_7_DAY_BONUS", "5", "int", "Bonus karma at 7-day streak milestone"),
        ("STREAK_14_DAY_BONUS", "6", "int", "Bonus karma at 14-day streak milestone"),
        ("STREAK_30_DAY_BONUS", "10", "int", "Bonus karma at 30-day streak milestone"),

        # Karma decay (v1)
        ("KARMA_DECAY_THRESHOLD_DAYS", "14", "int", "Days of inactivity before karma decay starts"),
        ("KARMA_DECAY_RATE", "0.015", "float", "Daily decay rate (0.015 = 1.5% per day)"),
    ]

    for key, value, data_type, description in settings_data:
        SiteSetting.objects.update_or_create(
            key=key,
            defaults={
                'value': value,
                'data_type': data_type,
                'description': description,
            }
        )


def reverse_seed(apps, schema_editor):
    """Remove seeded settings (optional - keeps them for safety)."""
    pass


class Migration(migrations.Migration):
    """
    Seed SiteSettings with all ECHO_CONFIG defaults.

    This makes all settings visible and editable in Django admin.
    """

    dependencies = [
        ('core', '0013_remove_pro_subscription'),
    ]

    operations = [
        migrations.RunPython(seed_settings, reverse_seed),
    ]
