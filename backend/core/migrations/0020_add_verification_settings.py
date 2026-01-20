# Generated manually - Add verification settings

from django.db import migrations


def seed_settings(apps, schema_editor):
    """Add verification-related settings."""
    SiteSetting = apps.get_model('core', 'SiteSetting')

    settings_data = [
        # Verification settings
        (
            "VERIFICATION_SAMPLE_SIZE",
            "3",
            "int",
            "Number of posts to API-verify per 10 engagements (0-10). Higher = more accurate but costs more credits."
        ),
        (
            "VERIFICATION_BATCH_SIZE",
            "10",
            "int",
            "Number of engagements per verification batch"
        ),
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
    """Remove settings if migration is reversed."""
    SiteSetting = apps.get_model('core', 'SiteSetting')
    SiteSetting.objects.filter(
        key__in=['VERIFICATION_SAMPLE_SIZE', 'VERIFICATION_BATCH_SIZE']
    ).delete()


class Migration(migrations.Migration):
    """Add configurable verification settings."""

    dependencies = [
        ('core', '0019_post_cost_range_settings'),
    ]

    operations = [
        migrations.RunPython(seed_settings, reverse_seed),
    ]
