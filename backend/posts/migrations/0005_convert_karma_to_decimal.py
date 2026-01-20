# Generated manually - Convert karma fields to DecimalField
#
# DECIMAL KARMA SYSTEM:
# - 4 decimal places internally (database)
# - 2 decimal places for display (frontend)
# - ROUND_HALF_EVEN (Banker's rounding) for fairness
# - No inflation: escrow deducted = karma earned

from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("posts", "0004_campaign_eligibility"),
    ]

    operations = [
        # Step 1: Remove the old check constraint for Post.escrow
        migrations.RemoveConstraint(
            model_name="post",
            name="post_escrow_non_negative",
        ),

        # Step 2: Convert Post escrow fields to DecimalField
        migrations.AlterField(
            model_name="post",
            name="escrow",
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal(str(settings.ECHO_CONFIG["POST_COST"])),
                max_digits=12,
            ),
        ),
        migrations.AlterField(
            model_name="post",
            name="initial_escrow",
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal(str(settings.ECHO_CONFIG["POST_COST"])),
                max_digits=12,
            ),
        ),

        # Step 3: Re-add the check constraint (works with Decimal comparison)
        migrations.AddConstraint(
            model_name="post",
            constraint=models.CheckConstraint(
                condition=models.Q(("escrow__gte", 0)),
                name="post_escrow_non_negative",
            ),
        ),

        # Step 4: Remove the old check constraint for SponsoredPost.remaining_budget
        migrations.RemoveConstraint(
            model_name="sponsoredpost",
            name="sponsored_budget_non_negative",
        ),

        # Step 5: Convert SponsoredPost fields to DecimalField
        migrations.AlterField(
            model_name="sponsoredpost",
            name="credit_reward",
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal("2"),
                max_digits=10,
            ),
        ),
        migrations.AlterField(
            model_name="sponsoredpost",
            name="total_budget",
            field=models.DecimalField(
                decimal_places=4,
                max_digits=12,
            ),
        ),
        migrations.AlterField(
            model_name="sponsoredpost",
            name="remaining_budget",
            field=models.DecimalField(
                decimal_places=4,
                max_digits=12,
            ),
        ),

        # Step 6: Re-add the check constraint for SponsoredPost
        migrations.AddConstraint(
            model_name="sponsoredpost",
            constraint=models.CheckConstraint(
                condition=models.Q(("remaining_budget__gte", 0)),
                name="sponsored_budget_non_negative",
            ),
        ),
    ]
