"""
Celery configuration for ECHO project.
"""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "echo.settings")

app = Celery("echo")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
