# Generated manually - Add composite index for (user, project) lookups
# Critical for data integrity: ensures efficient per-project submission count queries
# Prevents race conditions where wrong leaderboard could be updated under high load

from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Add composite index on (user, project) for LoudSubmission.

    This index is critical for:
    1. Fast per-project submission count checks (daily limit enforcement)
    2. Ensuring correct leaderboard updates under concurrent load
    3. Preventing PostgreSQL from doing sequential scans on large tables

    Query pattern optimized:
        LoudSubmission.objects.filter(user=user, project=project).count()
    """

    dependencies = [
        ('loud', '0003_add_points_constraints'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='loudsubmission',
            index=models.Index(
                fields=['user', 'project'],
                name='loud_sub_user_proj_idx'
            ),
        ),
    ]
