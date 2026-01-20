# Generated manually - Add minimum session duration setting

from django.db import migrations


def seed_settings(apps, schema_editor):
    """Add session duration anti-gaming setting."""
    SiteSetting = apps.get_model('core', 'SiteSetting')

    SiteSetting.objects.update_or_create(
        key='MIN_SESSION_DURATION_SECONDS',
        defaults={
            'value': '150',
            'data_type': 'int',
            'description': 'Minimum seconds between first click and verification. Prevents instant clicking without real engagement. 0 to disable.',
        }
    )


def reverse_seed(apps, schema_editor):
    """Remove setting if migration is reversed."""
    SiteSetting = apps.get_model('core', 'SiteSetting')
    SiteSetting.objects.filter(key='MIN_SESSION_DURATION_SECONDS').delete()


class Migration(migrations.Migration):
    """Add configurable minimum session duration for anti-gaming."""

    dependencies = [
        ('core', '0020_add_verification_settings'),
    ]

    operations = [
        migrations.RunPython(seed_settings, reverse_seed),
    ]
