# Generated manually - Seed tier thresholds and multipliers into SiteSettings

from django.db import migrations


def seed_tier_settings(apps, schema_editor):
    """Populate SiteSettings with tier thresholds and multipliers."""
    SiteSetting = apps.get_model('core', 'SiteSetting')

    # Tier thresholds and multipliers
    settings_data = [
        # Tier thresholds (TweetScout score)
        ("TIER_NORMIE_THRESHOLD", "100", "int", "TweetScout score required for Normie tier"),
        ("TIER_DEGEN_THRESHOLD", "200", "int", "TweetScout score required for Degen tier"),
        ("TIER_BASED_THRESHOLD", "400", "int", "TweetScout score required for Based tier"),
        ("TIER_LEGEND_THRESHOLD", "600", "int", "TweetScout score required for Legend tier"),
        ("TIER_OG_THRESHOLD", "800", "int", "TweetScout score required for OG tier"),
        ("TIER_GOAT_THRESHOLD", "1000", "int", "TweetScout score required for GOAT tier"),

        # Tier multipliers (karma earned)
        ("TIER_ANON_MULTIPLIER", "1.0", "float", "Karma multiplier for Anon tier (score 0-99)"),
        ("TIER_NORMIE_MULTIPLIER", "1.10", "float", "Karma multiplier for Normie tier"),
        ("TIER_DEGEN_MULTIPLIER", "1.15", "float", "Karma multiplier for Degen tier"),
        ("TIER_BASED_MULTIPLIER", "1.20", "float", "Karma multiplier for Based tier"),
        ("TIER_LEGEND_MULTIPLIER", "1.25", "float", "Karma multiplier for Legend tier"),
        ("TIER_OG_MULTIPLIER", "1.30", "float", "Karma multiplier for OG tier"),
        ("TIER_GOAT_MULTIPLIER", "1.35", "float", "Karma multiplier for GOAT tier"),
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
    """Remove seeded tier settings (optional)."""
    pass


class Migration(migrations.Migration):
    """
    Seed tier thresholds and multipliers into SiteSettings.

    This allows adjusting tier requirements and karma multipliers from admin.
    """

    dependencies = [
        ('core', '0014_seed_site_settings'),
    ]

    operations = [
        migrations.RunPython(seed_tier_settings, reverse_seed),
    ]
