# Generated manually - Add X profile fields to WaitlistEntry
# Fetched from twitterapi.io on waitlist submission

from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Add X profile fields to WaitlistEntry for personalized waitlist cards.

    Fields:
    - x_display_name: User's display name on X
    - x_followers_count: Follower count (indexed for sorting in admin)
    - x_avatar_url: Profile picture URL
    - x_is_verified: Blue checkmark status
    - x_fetched_at: When the data was fetched
    """

    dependencies = [
        ('core', '0030_add_email_tracking_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='waitlistentry',
            name='x_display_name',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='waitlistentry',
            name='x_followers_count',
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='waitlistentry',
            name='x_avatar_url',
            field=models.URLField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='waitlistentry',
            name='x_is_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='waitlistentry',
            name='x_fetched_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
