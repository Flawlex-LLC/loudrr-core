"""
Add TweetScout score fields to User model.

TweetScout is now the primary score for tier calculation.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_add_kaito_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='tweetscout_score',
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name='user',
            name='tweetscout_last_updated',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
