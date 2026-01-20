# Generated manually - Seed SPONSORED_XP_PER_ENGAGEMENT setting

from django.db import migrations


def seed_setting(apps, schema_editor):
    """Add missing SPONSORED_XP_PER_ENGAGEMENT setting."""
    SiteSetting = apps.get_model('core', 'SiteSetting')

    SiteSetting.objects.update_or_create(
        key='SPONSORED_XP_PER_ENGAGEMENT',
        defaults={
            'value': '5',
            'data_type': 'int',
            'description': 'XP earned per sponsored post engagement',
        }
    )


def reverse_seed(apps, schema_editor):
    """Remove setting (optional)."""
    pass


class Migration(migrations.Migration):
    """Seed SPONSORED_XP_PER_ENGAGEMENT into SiteSettings."""

    dependencies = [
        ('core', '0015_seed_tier_settings'),
    ]

    operations = [
        migrations.RunPython(seed_setting, reverse_seed),
    ]
