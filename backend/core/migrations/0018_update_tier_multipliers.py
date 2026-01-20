# Generated manually - Update tier multipliers to 1.0-1.2 range
#
# DECIMAL KARMA SYSTEM:
# New multiplier range (1.0x to 1.2x) to work better with decimal karma:
# - Anon (0-99):      1.00x
# - Normie (100-199): 1.03x
# - Degen (200-399):  1.06x
# - Based (400-599):  1.10x
# - Legend (600-799): 1.14x
# - OG (800-999):     1.17x
# - GOAT (1000+):     1.20x

from django.db import migrations


def update_tier_multipliers(apps, schema_editor):
    """Update tier multipliers to new 1.0-1.2 range."""
    SiteSetting = apps.get_model('core', 'SiteSetting')

    # New multiplier values (1.0x to 1.2x range)
    new_multipliers = {
        "TIER_ANON_MULTIPLIER": "1.00",
        "TIER_NORMIE_MULTIPLIER": "1.03",
        "TIER_DEGEN_MULTIPLIER": "1.06",
        "TIER_BASED_MULTIPLIER": "1.10",
        "TIER_LEGEND_MULTIPLIER": "1.14",
        "TIER_OG_MULTIPLIER": "1.17",
        "TIER_GOAT_MULTIPLIER": "1.20",
    }

    for key, value in new_multipliers.items():
        SiteSetting.objects.filter(key=key).update(value=value)


def reverse_update(apps, schema_editor):
    """Revert to old multiplier values."""
    SiteSetting = apps.get_model('core', 'SiteSetting')

    # Old multiplier values (1.0x to 1.35x range)
    old_multipliers = {
        "TIER_ANON_MULTIPLIER": "1.0",
        "TIER_NORMIE_MULTIPLIER": "1.10",
        "TIER_DEGEN_MULTIPLIER": "1.15",
        "TIER_BASED_MULTIPLIER": "1.20",
        "TIER_LEGEND_MULTIPLIER": "1.25",
        "TIER_OG_MULTIPLIER": "1.30",
        "TIER_GOAT_MULTIPLIER": "1.35",
    }

    for key, value in old_multipliers.items():
        SiteSetting.objects.filter(key=key).update(value=value)


class Migration(migrations.Migration):
    """
    Update tier multipliers to new 1.0-1.2 range for decimal karma system.

    Old range: 1.0x to 1.35x (35% max bonus)
    New range: 1.0x to 1.20x (20% max bonus)

    This is a more reasonable range that works well with decimal precision.
    """

    dependencies = [
        ('core', '0017_convert_karma_to_decimal'),
    ]

    operations = [
        migrations.RunPython(update_tier_multipliers, reverse_update),
    ]
