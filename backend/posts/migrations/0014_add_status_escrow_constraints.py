"""
Add database constraints for status-based escrow rules.

Business rules enforced at database level:
1. Completed posts must have zero escrow (fully depleted)
2. Cancelled posts must have zero escrow (refunded)
3. Winners must be eligible (can't win if ineligible)
4. Prize can only be claimed by winners
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('posts', '0013_alter_post_status'),
    ]

    operations = [
        # Post constraints: Completed/Cancelled posts must have zero escrow
        migrations.AddConstraint(
            model_name='post',
            constraint=models.CheckConstraint(
                check=~(models.Q(status='completed') & models.Q(escrow__gt=0)),
                name='post_completed_zero_escrow',
            ),
        ),
        migrations.AddConstraint(
            model_name='post',
            constraint=models.CheckConstraint(
                check=~(models.Q(status='cancelled') & models.Q(escrow__gt=0)),
                name='post_cancelled_zero_escrow',
            ),
        ),
        # CampaignEntry constraints: Winners must be eligible, claimed must be winners
        migrations.AddConstraint(
            model_name='campaignentry',
            constraint=models.CheckConstraint(
                check=~(models.Q(is_winner=True) & models.Q(status='ineligible')),
                name='entry_winner_must_be_eligible',
            ),
        ),
        migrations.AddConstraint(
            model_name='campaignentry',
            constraint=models.CheckConstraint(
                check=~(models.Q(prize_claimed=True) & models.Q(is_winner=False)),
                name='entry_claimed_must_be_winner',
            ),
        ),
    ]
