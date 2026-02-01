"""
Celery configuration for ECHO project.

Periodic tasks (Celery Beat):
- expire_old_posts: Runs hourly to expire posts and refund escrow
- process_pending_outbox_events: Runs every minute to process notifications
- cleanup_old_outbox_events: Runs daily to clean up processed events
- reset_daily_credits: Runs at midnight UTC to reset daily caps
- retry_failed_outbox_events: Runs hourly to retry failed events
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

    # === OUTBOX EVENT PROCESSING ===

    # Process pending outbox events every minute
    # This ensures notifications are sent quickly even if immediate trigger fails
    'process-outbox-events-minutely': {
        'task': 'core.process_pending_outbox_events',
        'schedule': crontab(),  # Every minute
        'kwargs': {'batch_size': 50},
        'options': {'queue': 'default'},
    },

    # Retry failed outbox events every hour
    # Failed events with retry_count < 3 are reset to PENDING
    'retry-failed-outbox-hourly': {
        'task': 'core.retry_failed_outbox_events',
        'schedule': crontab(minute=30),  # Every hour at :30
        'options': {'queue': 'default'},
    },

    # Clean up old processed events daily at 3 AM UTC
    # Removes SENT events older than 30 days (FAILED kept for debugging)
    'cleanup-outbox-daily': {
        'task': 'core.cleanup_old_outbox_events',
        'schedule': crontab(hour=3, minute=0),
        'kwargs': {'days': 30},
        'options': {'queue': 'default'},
    },

    # === DAILY RESETS ===

    # Reset daily credits at midnight UTC
    'reset-daily-credits-midnight': {
        'task': 'core.reset_daily_credits',
        'schedule': crontab(hour=0, minute=0),  # Midnight UTC
        'options': {'queue': 'default'},
    },
}

app.conf.timezone = 'UTC'
