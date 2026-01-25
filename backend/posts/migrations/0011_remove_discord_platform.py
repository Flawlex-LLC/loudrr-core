# Generated manually - Remove Discord platform choice
# Discord bot is no longer used

from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Remove Discord from Post platform choices.

    Updates:
    - Post.platform choices: removes "discord" option
    """

    dependencies = [
        ('posts', '0010_add_escrow_constraints'),
    ]

    operations = [
        migrations.AlterField(
            model_name='post',
            name='platform',
            field=models.CharField(
                choices=[('telegram', 'Telegram'), ('web', 'Web')],
                max_length=20,
            ),
        ),
    ]
