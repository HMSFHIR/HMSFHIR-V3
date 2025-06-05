# fhir_sync/enhanced_tasks.py - Fixed imports
from celery import shared_task
from .services import sync_pending_resources
from .enhanced_services import (
    sync_hms_to_fhir,
    sync_pending_resources_enhanced,
    clear_completed_sync_tasks
)

@shared_task
def sync_pending_resources_task():
    """Original task - kept for compatibility"""
    sync_pending_resources()

@shared_task
def sync_hms_to_fhir_task():
    """
    New task: Sync all HMS data to FHIR server
    This converts your HMS data to FHIR format and queues it for sync
    """
    try:
        sync_hms_to_fhir()
        return "HMS to FHIR sync queuing completed successfully"
    except Exception as e:
        return f"HMS to FHIR sync failed: {str(e)}"

@shared_task
def sync_pending_resources_enhanced_task():
    """
    Enhanced task: Process pending sync queue with better error handling
    """
    try:
        sync_pending_resources_enhanced()
        return "Enhanced sync processing completed"
    except Exception as e:
        return f"Enhanced sync processing failed: {str(e)}"

@shared_task
def full_sync_task():
    """
    Complete sync task: HMS -> Queue -> FHIR Server
    """
    try:
        # First, queue all HMS data for sync
        sync_hms_to_fhir()
        # Then process the queue
        sync_pending_resources_enhanced()
        return "Full sync completed successfully"
    except Exception as e:
        return f"Full sync failed: {str(e)}"

@shared_task
def cleanup_sync_tasks():
    """
    Cleanup old completed sync tasks
    """
    try:
        deleted_count = clear_completed_sync_tasks()
        return f"Cleanup completed: {deleted_count} old tasks removed"
    except Exception as e:
        return f"Cleanup failed: {str(e)}"

@shared_task
def retry_failed_syncs():
    """
    Retry failed syncs with less than 3 attempts
    """
    from .models import PendingSyncQueue
    try:
        # Reset failed tasks to pending for retry
        failed_tasks = PendingSyncQueue.objects.filter(
            status='failed',
            retry_count__lt=3
        )
        count = failed_tasks.count()
        failed_tasks.update(status='pending')
        
        # Process them
        sync_pending_resources_enhanced()
        return f"Retried {count} failed sync tasks"
    except Exception as e:
        return f"Retry failed syncs error: {str(e)}"