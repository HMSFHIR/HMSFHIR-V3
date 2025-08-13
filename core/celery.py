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
        'kwargs': {'limit': 2000}
    },
    'retry-failed-syncs': {
        'task': 'Fsync.tasks.retry_failed_syncs_task',
        'schedule': crontab(minute=0, hour='*/2'),  # Every 2 hours
    },
    'cleanup-old-records': {
        'task': 'Fsync.maintenanceUtils.cleanup_sync_tasks',
        'schedule': crontab(minute='*/3'),  # Every 3 minutes
    },
     'sync-observations': {
        'task': 'Fsync.tasks.process_observation_sync_queue',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    
    # Queue new observations every hour
    'queue-new-observations': {
        'task': 'Fsync.tasks.queue_new_observations',
        'schedule': crontab(minute=0),  # Every hour at minute 0
    },
    
    # Sync pending observations every 10 minutes
    'sync-pending-observations': {
        'task': 'Fsync.tasks.sync_pending_observations',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
    },
}

app.autodiscover_tasks()