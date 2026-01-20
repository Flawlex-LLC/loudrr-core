# Generated manually - Simplify verification system

from django.db import migrations, models
from django.db.models import F


def migrate_honesty_scores(apps, schema_editor):
    """Convert honesty scores from 0-10 to 0-50 scale."""
    User = apps.get_model('core', 'User')
    # Multiply existing scores by 5 (10 → 50, 9 → 45, etc.)
    User.objects.update(honesty_score=F('honesty_score') * 5)


def reverse_honesty_scores(apps, schema_editor):
    """Reverse: convert from 0-50 to 0-10 scale."""
    User = apps.get_model('core', 'User')
    # Divide by 5, rounding down
    User.objects.update(honesty_score=F('honesty_score') / 5)


def cleanup_settings(apps, schema_editor):
    """Remove unused settings, rename others."""
    SiteSetting = apps.get_model('core', 'SiteSetting')

    # Delete unused settings
    SiteSetting.objects.filter(key__in=[
        'MAX_VERIFICATION_RETRIES',
        'VERIFICATION_SAMPLE_SIZE',
    ]).delete()

    # Rename batch_size to min_to_claim
    SiteSetting.objects.filter(key='VERIFICATION_BATCH_SIZE').update(
        key='MIN_ENGAGEMENTS_TO_CLAIM',
        description='Minimum engagements required before claiming rewards (default: 10)',
    )


def reverse_settings(apps, schema_editor):
    """Reverse settings changes."""
    SiteSetting = apps.get_model('core', 'SiteSetting')

    # Rename back
    SiteSetting.objects.filter(key='MIN_ENGAGEMENTS_TO_CLAIM').update(
        key='VERIFICATION_BATCH_SIZE',
        description='Number of engagements per verification batch',
    )

    # Re-create deleted settings
    SiteSetting.objects.get_or_create(
        key='VERIFICATION_SAMPLE_SIZE',
        defaults={
            'value': '3',
            'data_type': 'int',
            'description': 'Number of posts to API-verify per batch',
        }
    )
    SiteSetting.objects.get_or_create(
        key='MAX_VERIFICATION_RETRIES',
        defaults={
            'value': '2',
            'data_type': 'int',
            'description': 'Maximum times an engagement can be re-verified',
        }
    )


class Migration(migrations.Migration):
    """
    Simplify verification system:
    - 100% verification (no sampling)
    - Honesty score 0-50 (no karma penalties)
    - Failed verifications stay pending for re-engagement
    """

    dependencies = [
        ('core', '0021_add_session_duration_setting'),
    ]

    operations = [
        # Update honesty_score field default and constraint
        migrations.AlterField(
            model_name='user',
            name='honesty_score',
            field=models.IntegerField(default=50),
        ),

        # Remove old constraint, add new one (0-50 range)
        migrations.RemoveConstraint(
            model_name='user',
            name='user_honesty_score_valid_range',
        ),
        migrations.AddConstraint(
            model_name='user',
            constraint=models.CheckConstraint(
                check=models.Q(honesty_score__gte=0) & models.Q(honesty_score__lte=50),
                name='user_honesty_score_valid_range',
            ),
        ),

        # Migrate existing scores (10 → 50)
        migrations.RunPython(migrate_honesty_scores, reverse_honesty_scores),

        # Cleanup settings
        migrations.RunPython(cleanup_settings, reverse_settings),
    ]
