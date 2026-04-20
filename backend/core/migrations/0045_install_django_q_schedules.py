"""Install periodic task schedules for django-q2.

Replaces the Celery Beat schedule that used to live in backend/echo/celery.py.
Uses `django_q.models.Schedule` rows stored in the DB; the qcluster process
picks them up and runs them on cadence.
"""
from django.db import migrations


SCHEDULES = [
    # (func path, name, schedule_type, cron expression, kwargs JSON)
    # schedule_type values come from django_q.models.Schedule: CRON = 'C'
    (
        "posts.tasks.expire_old_posts",
        "expire-old-posts-hourly",
        "C",
        "0 * * * *",       # every hour at :00
        "",
    ),
    (
        "core.tasks.process_pending_outbox_events",
        "process-outbox-events-minutely",
        "C",
        "* * * * *",       # every minute
        '{"batch_size": 50}',
    ),
    (
        "core.tasks.retry_failed_outbox_events",
        "retry-failed-outbox-hourly",
        "C",
        "30 * * * *",      # every hour at :30
        "",
    ),
    (
        "core.tasks.cleanup_old_outbox_events",
        "cleanup-outbox-daily",
        "C",
        "0 3 * * *",       # daily at 03:00 UTC
        '{"days": 30}',
    ),
    (
        "core.tasks.reset_daily_credits",
        "reset-daily-credits-midnight",
        "C",
        "0 0 * * *",       # daily at 00:00 UTC
        "",
    ),
]


def install_schedules(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    for func, name, schedule_type, cron, kwargs_json in SCHEDULES:
        Schedule.objects.update_or_create(
            name=name,
            defaults={
                "func": func,
                "schedule_type": schedule_type,
                "cron": cron,
                "kwargs": kwargs_json,
                "repeats": -1,  # run forever
            },
        )


def remove_schedules(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    names = [s[1] for s in SCHEDULES]
    Schedule.objects.filter(name__in=names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0044_add_region_niche_platforms"),
        ("django_q", "0018_task_success_index"),
    ]

    operations = [
        migrations.RunPython(install_schedules, remove_schedules),
    ]
