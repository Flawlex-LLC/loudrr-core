# Generated manually - Remove Pro subscription fields

from django.db import migrations


class Migration(migrations.Migration):
    """
    Remove Pro subscription system from User model.

    User fields removed:
    - is_pro: Pro subscription flag
    - pro_expires_at: Pro expiration date
    - intent_reply_count_today: Daily Quick Reply usage
    - ai_assist_count_today: Daily AI Assist usage
    - intent_usage_reset_at: Counter reset timestamp

    Also cleans up related SiteSettings entries.
    """

    dependencies = [
        ('core', '0012_remove_legacy_tier_and_purchase'),
    ]

    operations = [
        # Remove Pro subscription fields from User
        migrations.RemoveField(
            model_name='user',
            name='is_pro',
        ),
        migrations.RemoveField(
            model_name='user',
            name='pro_expires_at',
        ),
        # Remove intent usage tracking fields from User
        migrations.RemoveField(
            model_name='user',
            name='intent_reply_count_today',
        ),
        migrations.RemoveField(
            model_name='user',
            name='ai_assist_count_today',
        ),
        migrations.RemoveField(
            model_name='user',
            name='intent_usage_reset_at',
        ),
        # Clean up old SiteSettings
        migrations.RunSQL(
            sql="""
                DELETE FROM site_settings WHERE key IN (
                    'PRO_REPLY_INTENT_DAILY_CAP',
                    'PRO_AI_ASSIST_DAILY_CAP',
                    'MAX_SPONSORED_POSTS_PER_DAY'
                );
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
