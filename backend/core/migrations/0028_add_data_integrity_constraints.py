# Generated manually - Add data integrity constraints (Layer 1)
# Part of data integrity implementation for Engage and LOUD tabs

from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Add Layer 1 data integrity constraints:

    User model:
    - daily_credits_earned valid range (0-500 hard cap)
    - total_credits_earned non-negative
    - total_credits_spent non-negative

    Transaction model:
    - idempotency_key field for deduplication
    - unique constraint on (user, type, idempotency_key)
    - amount cannot be zero
    """

    dependencies = [
        ('core', '0027_remove_x_username_unique'),
    ]

    operations = [
        # Add idempotency_key field to Transaction
        migrations.AddField(
            model_name='transaction',
            name='idempotency_key',
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),

        # Add User constraints
        migrations.AddConstraint(
            model_name='user',
            constraint=models.CheckConstraint(
                check=models.Q(daily_credits_earned__gte=0) & models.Q(daily_credits_earned__lte=500),
                name='user_daily_credits_earned_valid_range',
            ),
        ),
        migrations.AddConstraint(
            model_name='user',
            constraint=models.CheckConstraint(
                check=models.Q(total_credits_earned__gte=0),
                name='user_total_credits_earned_non_negative',
            ),
        ),
        migrations.AddConstraint(
            model_name='user',
            constraint=models.CheckConstraint(
                check=models.Q(total_credits_spent__gte=0),
                name='user_total_credits_spent_non_negative',
            ),
        ),

        # Add Transaction constraints
        migrations.AddConstraint(
            model_name='transaction',
            constraint=models.UniqueConstraint(
                condition=~models.Q(idempotency_key=''),
                fields=['user', 'type', 'idempotency_key'],
                name='transaction_idempotency_unique',
            ),
        ),
        migrations.AddConstraint(
            model_name='transaction',
            constraint=models.CheckConstraint(
                check=~models.Q(amount=0),
                name='transaction_amount_non_zero',
            ),
        ),

        # Add index for idempotency_key lookups
        migrations.AddIndex(
            model_name='transaction',
            index=models.Index(fields=['idempotency_key'], name='transaction_idempotency_idx'),
        ),
    ]
