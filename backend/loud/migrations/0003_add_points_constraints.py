# Generated manually - Add points constraints (Layer 1)
# Part of data integrity implementation for LOUD tab

from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Add Layer 1 data integrity constraints:

    LoudSubmission model:
    - points_awarded non-negative
    - tweetscout_score_at_submission non-negative

    LoudLeaderboardEntry model:
    - total_points non-negative
    - submission_count non-negative
    """

    dependencies = [
        ('loud', '0002_seed_loud_settings'),
    ]

    operations = [
        # LoudSubmission constraints
        migrations.AddConstraint(
            model_name='loudsubmission',
            constraint=models.CheckConstraint(
                check=models.Q(points_awarded__gte=0),
                name='loud_submission_points_non_negative',
            ),
        ),
        migrations.AddConstraint(
            model_name='loudsubmission',
            constraint=models.CheckConstraint(
                check=models.Q(tweetscout_score_at_submission__gte=0),
                name='loud_submission_score_non_negative',
            ),
        ),

        # LoudLeaderboardEntry constraints
        migrations.AddConstraint(
            model_name='loudleaderboardentry',
            constraint=models.CheckConstraint(
                check=models.Q(total_points__gte=0),
                name='loud_leaderboard_points_non_negative',
            ),
        ),
        migrations.AddConstraint(
            model_name='loudleaderboardentry',
            constraint=models.CheckConstraint(
                check=models.Q(submission_count__gte=0),
                name='loud_leaderboard_count_non_negative',
            ),
        ),
    ]
