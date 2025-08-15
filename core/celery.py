from celery import Celery
from celery.schedules import crontab
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('Fsync')
app.config_from_object('django.conf:settings', namespace='CELERY')

# Celery Beat Schedule
# Updated Celery Beat Schedule
# Updated Celery Beat Schedule in celery.py

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
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
    },
    
    # OBSERVATION SYNC TASKS
    'sync-observations': {
        'task': 'Fsync.tasks.process_observation_sync_queue',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'queue-new-observations': {
        'task': 'Fsync.tasks.queue_new_observations',
        'schedule': crontab(minute=0),  # Every hour at minute 0
    },
    'sync-pending-observations': {
        'task': 'Fsync.tasks.sync_pending_observations',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
    },
    
    # NEW: APPOINTMENT SYNC TASKS
    'sync-appointments': {
        'task': 'Fsync.tasks.process_appointment_sync_queue',
        'schedule': crontab(minute='1,6,11,16,21,26,31,36,41,46,51,56'),  # Every 5 minutes offset by 1
    },
    'queue-new-appointments': {
        'task': 'Fsync.tasks.queue_new_appointments',
        'schedule': crontab(minute=15),  # Every hour at minute 15
    },
    'sync-pending-appointments': {
        'task': 'Fsync.tasks.sync_pending_appointments',
        'schedule': crontab(minute='2,12,22,32,42,52'),  # Every 10 minutes offset by 2
    },
    
    # CLEANUP TASKS
    'cleanup-stuck-items': {
        'task': 'Fsync.maintenanceUtils.cleanup_stuck_processing_items',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
}

app.autodiscover_tasks()