"""
Add database constraints for accounting and business invariants.

Business rules enforced at database level:
1. Earned must be >= spent (accounting invariant - can't spend more than earned)
2. User can't be banned AND whitelisted simultaneously
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0037_create_feature_flags'),
    ]

    operations = [
        # Accounting invariant: earned >= spent
        migrations.AddConstraint(
            model_name='user',
            constraint=models.CheckConstraint(
                check=models.Q(total_credits_earned__gte=models.F('total_credits_spent')),
                name='user_earned_gte_spent',
            ),
        ),
        # Business invariant: can't be both banned and whitelisted
        migrations.AddConstraint(
            model_name='user',
            constraint=models.CheckConstraint(
                check=~(models.Q(is_banned=True) & models.Q(is_whitelisted=True)),
                name='user_not_banned_and_whitelisted',
            ),
        ),
    ]
