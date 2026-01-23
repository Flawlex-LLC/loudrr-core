"""
Seed SiteSettings for Loud feature.
"""
from django.db import migrations


def seed_settings(apps, schema_editor):
    SiteSetting = apps.get_model('core', 'SiteSetting')

    settings = [
        ('LOUD_DAILY_LIMIT', '6', 'int',
         'Max submissions per user per day across all Loud projects'),
        ('LOUD_POINTS_DIVISOR', '10', 'int',
         'Divisor for points calculation (tweetscout_score / divisor)'),
    ]

    for key, value, dtype, desc in settings:
        SiteSetting.objects.get_or_create(
            key=key,
            defaults={'value': value, 'data_type': dtype, 'description': desc}
        )


def reverse_seed(apps, schema_editor):
    SiteSetting = apps.get_model('core', 'SiteSetting')
    SiteSetting.objects.filter(key__in=['LOUD_DAILY_LIMIT', 'LOUD_POINTS_DIVISOR']).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('loud', '0001_initial'),
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_settings, reverse_seed),
    ]
