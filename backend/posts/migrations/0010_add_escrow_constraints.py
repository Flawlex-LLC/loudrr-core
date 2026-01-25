# Generated manually - Add escrow constraints (Layer 1)
# Part of data integrity implementation for Engage tab

from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Add Layer 1 data integrity constraints:

    Post model:
    - initial_escrow non-negative
    - escrow cannot exceed initial_escrow (prevents inflation)

    SponsoredPost model:
    - total_budget non-negative
    - remaining_budget cannot exceed total_budget
    """

    dependencies = [
        ('posts', '0009_verificationbatch'),
    ]

    operations = [
        # Post constraints
        migrations.AddConstraint(
            model_name='post',
            constraint=models.CheckConstraint(
                check=models.Q(initial_escrow__gte=0),
                name='post_initial_escrow_non_negative',
            ),
        ),
        migrations.AddConstraint(
            model_name='post',
            constraint=models.CheckConstraint(
                check=models.Q(escrow__lte=models.F('initial_escrow')),
                name='post_escrow_cannot_exceed_initial',
            ),
        ),

        # SponsoredPost constraints
        migrations.AddConstraint(
            model_name='sponsoredpost',
            constraint=models.CheckConstraint(
                check=models.Q(total_budget__gte=0),
                name='sponsored_total_budget_non_negative',
            ),
        ),
        migrations.AddConstraint(
            model_name='sponsoredpost',
            constraint=models.CheckConstraint(
                check=models.Q(remaining_budget__lte=models.F('total_budget')),
                name='sponsored_remaining_cannot_exceed_total',
            ),
        ),
    ]
