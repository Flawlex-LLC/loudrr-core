"""
Add honesty_score field to User model.

Honesty score tracks user reliability in completing engagements.
- Default: 10 (perfect)
- First offense: warning only, score drops to 9
- Further offenses: 1-2 karma penalty
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_add_check_constraints'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='honesty_score',
            field=models.IntegerField(default=10),
        ),
        migrations.AddConstraint(
            model_name='user',
            constraint=models.CheckConstraint(
                check=models.Q(honesty_score__gte=0) & models.Q(honesty_score__lte=10),
                name='user_honesty_score_valid_range'
            ),
        ),
    ]
