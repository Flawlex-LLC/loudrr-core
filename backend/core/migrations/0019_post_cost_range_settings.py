# Generated manually - Add POST_COST_MIN, POST_COST_MAX and remove daily earn cap

from django.db import migrations


def add_post_cost_settings(apps, schema_editor):
    """Add post cost range settings and remove daily earn cap."""
    SiteSetting = apps.get_model('core', 'SiteSetting')

    # Add POST_COST_MIN and POST_COST_MAX
    settings_data = [
        ("POST_COST_MIN", "20", "int", "Minimum karma to spend on a post"),
        ("POST_COST_MAX", "40", "int", "Maximum karma to spend on a post"),
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

    # Set daily earn cap to very high (effectively unlimited)
    SiteSetting.objects.filter(key='DAILY_EARN_CAP').update(value='999999')

    # Remove old POST_COST if exists (no longer used)
    SiteSetting.objects.filter(key='POST_COST').delete()


def reverse_settings(apps, schema_editor):
    """Revert to old settings."""
    SiteSetting = apps.get_model('core', 'SiteSetting')

    # Remove new settings
    SiteSetting.objects.filter(key__in=['POST_COST_MIN', 'POST_COST_MAX']).delete()

    # Restore daily cap
    SiteSetting.objects.filter(key='DAILY_EARN_CAP').update(value='160')

    # Restore POST_COST
    SiteSetting.objects.update_or_create(
        key='POST_COST',
        defaults={
            'value': '80',
            'data_type': 'int',
            'description': 'Cost in karma to submit a post',
        }
    )


class Migration(migrations.Migration):
    """
    Add configurable post cost range (min/max) and remove daily earn cap.

    - POST_COST_MIN: 20 (default)
    - POST_COST_MAX: 40 (default)
    - DAILY_EARN_CAP: 999999 (effectively unlimited)
    """

    dependencies = [
        ('core', '0018_update_tier_multipliers'),
    ]

    operations = [
        migrations.RunPython(add_post_cost_settings, reverse_settings),
    ]
