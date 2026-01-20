# Generated manually - Convert karma fields to DecimalField
#
# DECIMAL KARMA SYSTEM:
# - 4 decimal places internally (database)
# - 2 decimal places for display (frontend)
# - ROUND_HALF_EVEN (Banker's rounding) for fairness
# - No inflation: escrow deducted = karma earned

from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0016_seed_sponsored_xp_setting"),
    ]

    operations = [
        # Step 1: Remove the old check constraint (it will be re-added with Decimal comparison)
        migrations.RemoveConstraint(
            model_name="user",
            name="user_credits_non_negative",
        ),

        # Step 2: Convert User credit fields to DecimalField
        migrations.AlterField(
            model_name="user",
            name="credits",
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal("0"),
                max_digits=12,
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="total_credits_earned",
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal("0"),
                max_digits=12,
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="total_credits_spent",
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal("0"),
                max_digits=12,
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="daily_credits_earned",
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal("0"),
                max_digits=12,
            ),
        ),

        # Step 3: Re-add the check constraint (works with Decimal comparison)
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=models.Q(("credits__gte", 0)),
                name="user_credits_non_negative",
            ),
        ),

        # Step 4: Convert Transaction fields to DecimalField
        migrations.AlterField(
            model_name="transaction",
            name="amount",
            field=models.DecimalField(
                decimal_places=4,
                max_digits=12,
            ),
        ),
        migrations.AlterField(
            model_name="transaction",
            name="balance_after",
            field=models.DecimalField(
                decimal_places=4,
                max_digits=12,
            ),
        ),

        # Step 5: Convert XPTransaction fields to DecimalField
        migrations.AlterField(
            model_name="xptransaction",
            name="amount",
            field=models.DecimalField(
                decimal_places=4,
                max_digits=12,
            ),
        ),
        migrations.AlterField(
            model_name="xptransaction",
            name="balance_after",
            field=models.DecimalField(
                decimal_places=4,
                max_digits=12,
            ),
        ),
    ]
