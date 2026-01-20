# Generated manually - Add tweet content fields for feed display

from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Add cached tweet content fields to Post model.

    These fields are populated on post submission via Twitter API.
    One API call ($0.00015) fetches content AND validates ownership.
    """

    dependencies = [
        ('posts', '0007_remove_verification_attempts'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='tweet_text',
            field=models.TextField(blank=True, help_text='Tweet text content'),
        ),
        migrations.AddField(
            model_name='post',
            name='tweet_author_name',
            field=models.CharField(blank=True, max_length=100, help_text='Author display name'),
        ),
        migrations.AddField(
            model_name='post',
            name='tweet_author_username',
            field=models.CharField(blank=True, max_length=50, help_text='Author @handle'),
        ),
        migrations.AddField(
            model_name='post',
            name='tweet_author_avatar',
            field=models.URLField(blank=True, max_length=500, help_text='Author profile image URL'),
        ),
        migrations.AddField(
            model_name='post',
            name='tweet_media',
            field=models.JSONField(blank=True, default=list, help_text='Array of media URLs'),
        ),
        migrations.AddField(
            model_name='post',
            name='tweet_created_at',
            field=models.DateTimeField(blank=True, null=True, help_text='When tweet was posted'),
        ),
    ]
