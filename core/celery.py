from celery import Celery
from celery.schedules import crontab
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('Fsync')
app.config_from_object('django.conf:settings', namespace='CELERY')

# Celery Beat Schedule
app.conf.beat_schedule = {
    # === CORE SYNC PROCESSING ===
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
    
    # === FOUNDATION RESOURCES (High Priority) ===
    # Patients (already implemented)
    'sync-patients': {
        'task': 'Fsync.tasks.process_patient_sync_queue',
        'schedule': crontab(minute='0,5,10,15,20,25,30,35,40,45,50,55'),  # Every 5 min, base time
    },
    
    # Encounters (foundation for medical records)
    'sync-encounters': {
        'task': 'Fsync.tasks.process_encounter_sync_queue',
        'schedule': crontab(minute='1,6,11,16,21,26,31,36,41,46,51,56'),  # Every 5 min, +1 offset
    },
    
    # === INDEPENDENT MEDICAL RECORDS ===
    # AllergyIntolerance (only depends on Patient)
    'sync-allergy-intolerances': {
        'task': 'Fsync.tasks.process_allergy_intolerance_sync_queue',
        'schedule': crontab(minute='2,7,12,17,22,27,32,37,42,47,52,57'),  # Every 5 min, +2 offset
    },
    
    # === EXISTING RESOURCES ===
    # Observations
    'sync-observations': {
        'task': 'Fsync.tasks.process_observation_sync_queue',
        'schedule': crontab(minute='3,8,13,18,23,28,33,38,43,48,53,58'),  # Every 5 min, +3 offset
    },
    'queue-new-observations': {
        'task': 'Fsync.tasks.queue_new_observations',
        'schedule': crontab(minute=0),  # Every hour at minute 0
    },
    'sync-pending-observations': {
        'task': 'Fsync.tasks.sync_pending_observations',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
    },
    
    # Appointments
    'sync-appointments': {
        'task': 'Fsync.tasks.process_appointment_sync_queue',
        'schedule': crontab(minute='4,9,14,19,24,29,34,39,44,49,54,59'),  # Every 5 min, +4 offset
    },
    'queue-new-appointments': {
        'task': 'Fsync.tasks.queue_new_appointments',
        'schedule': crontab(minute=15),  # Every hour at minute 15
    },
    'sync-pending-appointments': {
        'task': 'Fsync.tasks.sync_pending_appointments',
        'schedule': crontab(minute='2,12,22,32,42,52'),  # Every 10 minutes offset by 2
    },
    
    # === DISCOVERY TASKS (Lower Frequency) ===
    'queue-new-encounters': {
        'task': 'Fsync.tasks.queue_new_encounters',
        'schedule': crontab(minute=5),  # Every hour at minute 5
    },
    'queue-new-allergy-intolerances': {
        'task': 'Fsync.tasks.queue_new_allergy_intolerances', 
        'schedule': crontab(minute=10),  # Every hour at minute 10
    },
    
    # === PENDING PROCESSING (Medium Frequency) ===
    'sync-pending-encounters': {
        'task': 'Fsync.tasks.sync_pending_encounters',
        'schedule': crontab(minute='1,11,21,31,41,51'),  # Every 10 minutes offset by 1
    },
    'sync-pending-allergy-intolerances': {
        'task': 'Fsync.tasks.sync_pending_allergy_intolerances',
        'schedule': crontab(minute='3,13,23,33,43,53'),  # Every 10 minutes offset by 3
    },
    
    # === MAINTENANCE & CLEANUP ===
    'cleanup-stuck-items': {
        'task': 'Fsync.maintenanceUtils.cleanup_stuck_processing_items',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
}


app.autodiscover_tasks()