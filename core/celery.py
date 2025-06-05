from celery import Celery
from celery.schedules import crontab
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('Fsync')
app.config_from_object('django.conf:settings', namespace='CELERY')

# Celery Beat Schedule
app.conf.beat_schedule = {
    'process-sync-queue': {
        'task': 'Fsync.tasks.process_sync_queue_task',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
        'kwargs': {'limit': 100}
    },
    'retry-failed-syncs': {
        'task': 'Fsync.tasks.retry_failed_syncs_task',
        'schedule': crontab(minute=0, hour='*/2'),  # Every 2 hours
    },
    'cleanup-old-records': {
        'task': 'Fsync.tasks.cleanup_sync_tasks',
        'schedule': crontab(minute=0, hour=2),  # Daily at 2 AM
    },
}

app.autodiscover_tasks()