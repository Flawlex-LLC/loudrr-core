"""
Create SiteSetting model and seed default settings.

This migration:
1. Creates the SiteSetting table
2. Seeds it with default values from ECHO_CONFIG

After this migration, settings can be adjusted from /loudrr-admin/
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_default_settings(apps, schema_editor):
    """
    Seed default settings from ECHO_CONFIG.

    These can be edited from /loudrr-admin/ after migration.
    """
    SiteSetting = apps.get_model('core', 'SiteSetting')

    # Key operational settings to expose in admin
    defaults = [
        # Core gameplay settings
        ('DAILY_EARN_CAP', '160', 'int', 'Maximum credits a user can earn per day'),
        ('POST_COST', '80', 'int', 'Credits required to create a post'),
        ('CREDIT_PER_ENGAGEMENT', '1', 'int', 'Base credits earned per engagement'),
        ('WEEKLY_PURCHASE_CAP', '200', 'int', 'Maximum credits purchasable per week'),
        ('ENGAGEMENT_COOLDOWN', '0', 'int', 'Seconds between engagements (0 = disabled)'),

        # Audit settings
        ('AUDIT_PROBABILITY', '0.05', 'float', 'Probability (0-1) of random engagement audit'),

        # Tier thresholds
        ('TIER_SILVER_THRESHOLD', '100', 'int', 'Engagements required for Silver tier'),
        ('TIER_GOLD_THRESHOLD', '500', 'int', 'Engagements required for Gold tier'),
        ('TIER_PLATINUM_THRESHOLD', '2000', 'int', 'Engagements required for Platinum tier'),

        # Tier multipliers (disabled by default)
        ('TIER_SILVER_MULTIPLIER', '1.0', 'float', 'Credit multiplier for Silver tier'),
        ('TIER_GOLD_MULTIPLIER', '1.0', 'float', 'Credit multiplier for Gold tier'),
        ('TIER_PLATINUM_MULTIPLIER', '1.0', 'float', 'Credit multiplier for Platinum tier'),

        # Streak settings
        ('STREAK_7_DAY_MULTIPLIER', '1.0', 'float', '7-day streak credit multiplier'),
        ('STREAK_14_DAY_MULTIPLIER', '1.0', 'float', '14-day streak credit multiplier'),
        ('STREAK_30_DAY_MULTIPLIER', '1.0', 'float', '30-day streak credit multiplier'),
        ('STREAK_7_DAY_BONUS', '5', 'int', 'Bonus credits at 7-day streak milestone'),
        ('STREAK_14_DAY_BONUS', '6', 'int', 'Bonus credits at 14-day streak milestone'),
        ('STREAK_30_DAY_BONUS', '10', 'int', 'Bonus credits at 30-day streak milestone'),

        # Pro subscription settings
        ('PRO_REPLY_INTENT_DAILY_CAP', '25', 'int', 'Daily reply intent cap for Pro users'),
        ('PRO_AI_ASSIST_DAILY_CAP', '12', 'int', 'Daily AI assist cap for Pro users'),

        # Karma decay settings
        ('KARMA_DECAY_THRESHOLD_DAYS', '14', 'int', 'Days before karma decay starts'),
        ('KARMA_DECAY_RATE', '0.015', 'float', 'Daily karma decay rate (1.5% = 0.015)'),

        # Sponsored posts
        ('MAX_SPONSORED_POSTS_PER_DAY', '10', 'int', 'Maximum sponsored posts shown per day'),
    ]

    for key, value, data_type, description in defaults:
        SiteSetting.objects.get_or_create(
            key=key,
            defaults={
                'value': value,
                'data_type': data_type,
                'description': description,
            }
        )


def remove_default_settings(apps, schema_editor):
    """Remove seeded settings (for rollback)."""
    SiteSetting = apps.get_model('core', 'SiteSetting')
    SiteSetting.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_xprofile'),
    ]

    operations = [
        migrations.CreateModel(
            name='SiteSetting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(db_index=True, max_length=100, unique=True)),
                ('value', models.CharField(max_length=500)),
                ('data_type', models.CharField(
                    choices=[('int', 'Integer'), ('float', 'Float'), ('bool', 'Boolean'), ('str', 'String')],
                    default='int',
                    max_length=10
                )),
                ('description', models.TextField(blank=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='setting_updates',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'db_table': 'site_settings',
                'ordering': ['key'],
            },
        ),
        migrations.RunPython(seed_default_settings, remove_default_settings),
    ]
