"""
Celery configuration for ECHO project.

Periodic tasks (Celery Beat):
- expire_old_posts: Runs hourly to expire posts and refund escrow
"""
import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "echo.settings")

app = Celery("echo")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Celery Beat schedule for periodic tasks
app.conf.beat_schedule = {
    # Expire old posts and refund escrow every hour
    'expire-old-posts-hourly': {
        'task': 'posts.tasks.expire_old_posts',
        'schedule': crontab(minute=0),  # Every hour at :00
        'options': {'queue': 'default'},
    },
}

app.conf.timezone = 'UTC'
