# Generated manually - Remove Pro intent tracking fields from SessionClick

from django.db import migrations


class Migration(migrations.Migration):
    """
    Remove Pro-only intent tracking fields from SessionClick.

    - used_quick_reply: Pro Quick Reply tracking
    - used_ai_assist: Pro AI Assist tracking

    Note: used_quick_like is kept as it's a free feature.
    """

    dependencies = [
        ('miniapp', '0002_v1_intent_tracking'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='sessionclick',
            name='used_quick_reply',
        ),
        migrations.RemoveField(
            model_name='sessionclick',
            name='used_ai_assist',
        ),
    ]
