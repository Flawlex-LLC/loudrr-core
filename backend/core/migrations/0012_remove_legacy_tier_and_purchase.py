# Generated manually - Remove legacy tier system and purchase fields

from django.db import migrations


class Migration(migrations.Migration):
    """
    Remove legacy tier system and purchase functionality.

    - tier: Old engagement-based tier (now computed from TweetScout via property)
    - weekly_credits_purchased: Not selling credits
    - weekly_purchased_reset_at: Not selling credits

    Also cleans up related SiteSettings entries.
    """

    dependencies = [
        ('core', '0011_add_telegram_photo_url'),
    ]

    operations = [
        # Remove tier field (now a computed property from TweetScout score)
        migrations.RemoveField(
            model_name='user',
            name='tier',
        ),
        # Remove weekly purchase tracking (not selling credits)
        migrations.RemoveField(
            model_name='user',
            name='weekly_credits_purchased',
        ),
        migrations.RemoveField(
            model_name='user',
            name='weekly_purchased_reset_at',
        ),
        # Clean up old SiteSettings
        migrations.RunSQL(
            sql="""
                DELETE FROM site_settings WHERE key IN (
                    'TIER_SILVER_THRESHOLD',
                    'TIER_GOLD_THRESHOLD',
                    'TIER_PLATINUM_THRESHOLD',
                    'TIER_SILVER_MULTIPLIER',
                    'TIER_GOLD_MULTIPLIER',
                    'TIER_PLATINUM_MULTIPLIER',
                    'WEEKLY_PURCHASE_CAP'
                );
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
