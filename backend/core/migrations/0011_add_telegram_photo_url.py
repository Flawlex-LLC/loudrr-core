# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_add_xp_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='telegram_photo_url',
            field=models.URLField(blank=True, max_length=500),
        ),
    ]
