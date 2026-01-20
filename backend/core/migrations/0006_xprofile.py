"""
Create XProfile model for storing all X/Twitter profile data.

XProfile stores ALL data from TweetScout API in one place.
Only fetched ONCE when user links their X account.
"""
import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_add_tweetscout_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='XProfile',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                # Basic info
                ('x_user_id', models.CharField(db_index=True, max_length=50)),
                ('username', models.CharField(db_index=True, max_length=50)),
                ('display_name', models.CharField(max_length=100)),
                ('bio', models.TextField(blank=True)),
                # Metrics
                ('followers_count', models.IntegerField(default=0)),
                ('following_count', models.IntegerField(default=0)),
                ('tweets_count', models.IntegerField(default=0)),
                # TweetScout score
                ('score', models.FloatField(default=0)),
                # Profile assets
                ('avatar_url', models.URLField(blank=True, max_length=500)),
                ('banner_url', models.URLField(blank=True, max_length=500)),
                # Account status
                ('is_verified', models.BooleanField(default=False)),
                ('can_dm', models.BooleanField(default=False)),
                # Account age
                ('x_created_at', models.DateField(blank=True, null=True)),
                # Kaito data
                ('kaito_yaps_lifetime', models.FloatField(default=0)),
                # Metadata
                ('fetched_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                # Raw JSON storage
                ('raw_tweetscout_data', models.JSONField(blank=True, default=dict)),
                ('raw_kaito_data', models.JSONField(blank=True, default=dict)),
                # OneToOne with User
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='x_profile',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'db_table': 'x_profiles',
            },
        ),
        migrations.AddIndex(
            model_name='xprofile',
            index=models.Index(fields=['username'], name='x_profiles_usernam_c5f5e2_idx'),
        ),
        migrations.AddIndex(
            model_name='xprofile',
            index=models.Index(fields=['x_user_id'], name='x_profiles_x_user__e5e1f3_idx'),
        ),
        migrations.AddIndex(
            model_name='xprofile',
            index=models.Index(fields=['score'], name='x_profiles_score_a1b2c3_idx'),
        ),
    ]
