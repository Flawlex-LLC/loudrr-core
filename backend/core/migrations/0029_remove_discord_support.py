# Generated manually - Remove Discord support
# Discord bot is no longer used, removing all Discord-related fields

from django.db import migrations


class Migration(migrations.Migration):
    """
    Remove Discord support from the User model.

    Removes:
    - discord_id field
    - discord_id index
    """

    dependencies = [
        ('core', '0028_add_data_integrity_constraints'),
    ]

    operations = [
        # Remove discord_id index first
        migrations.RemoveIndex(
            model_name='user',
            name='users_discord_fa9188_idx',
        ),
        # Remove discord_id field
        migrations.RemoveField(
            model_name='user',
            name='discord_id',
        ),
    ]
