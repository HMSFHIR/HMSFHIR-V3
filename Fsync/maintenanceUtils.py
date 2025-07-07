from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging
import traceback
from .models import SyncLog, SyncQueue
from .syncManager import FHIRSyncService
from  .tasksUtils import validate_fhir_data


logger = logging.getLogger(__name__)


# ============================================================================
# MAINTENANCE AND UTILITY TASKS
# ============================================================================

@shared_task
def cleanup_sync_tasks():
    """
    Clean up old sync logs and completed queue items to prevent database bloat.
    
    This maintenance task:
    1. Removes successful sync logs older than 30 days
    2. Removes successful queue items older than 7 days
    3. Preserves error logs for troubleshooting
    
    Returns:
        dict: Cleanup statistics
    """
    try:
        # Define cleanup thresholds

        cutoff_date = timezone.now() - timedelta(seconds=300) # 5 minutes for logs
        
        # Clean up successful sync logs older than 30 days
        # Keep INFO and DEBUG level logs for historical reference
        deleted_logs = SyncLog.objects.filter(
            timestamp__lt=cutoff_date,
            level__in=['INFO', 'DEBUG']  # Don't delete ERROR or WARNING logs
        ).delete()
        
        # Clean up successful queue items older than 7 days
        # Successful items don't need long-term retention
        deleted_queue = SyncQueue.objects.delete()
        
        logger.info(f"Cleanup completed: {deleted_logs[0]} logs, {deleted_queue[0]} queue items")
        return {
            'logs_deleted': deleted_logs[0],
            'queue_items_deleted': deleted_queue[0]
        }
    except Exception as e:
        logger.error(f"Cleanup task failed: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {'error': str(e)}



@shared_task
def sync_single_resource_task(resource_type, resource_id, operation='create'):
    """
    Synchronize a single specific resource to the FHIR server.
    
    Used for:
    - Real-time sync triggered by HMS updates
    - Manual sync of specific records
    - Testing individual resource sync
    
    Args:
        resource_type (str): FHIR resource type (e.g., 'Patient')
        resource_id (str): The resource identifier
        operation (str): FHIR operation ('create', 'update', 'delete')
        
    Returns:
        dict: Sync result with status and FHIR ID
    """
    try:
        # ensure FHIR server is reachable
        sync_service = FHIRSyncService()
        if not sync_service.check_server_availability():
            return {'error': 'FHIR server not available'}
        
        # Find the queued item to sync
        queue_item = SyncQueue.objects.get(
            resource_type=resource_type,
            resource_id=resource_id,
            status__in=['pending', 'failed']  # Only sync items that need processing
        )
        
        # Validate FHIR data before attempting sync
        if queue_item.fhir_data:
            is_valid, validation_msg = validate_fhir_data(queue_item.fhir_data, resource_type)
            if not is_valid:
                # Mark as failed due to validation error
                queue_item.status = 'failed'
                queue_item.error_message = f"Validation failed: {validation_msg}"
                queue_item.save()
                return {'error': f'Validation failed: {validation_msg}'}
        
        # Perform the actual sync
        success = sync_service.sync_resource(queue_item)
        
        return {
            'success': success,
            'status': queue_item.status,
            'fhir_id': queue_item.fhir_id
        }
    except SyncQueue.DoesNotExist:
        return {'error': 'Queue item not found'}
    except ConnectionError as e:
        logger.error(f"Connection error during single resource sync: {e}")
        return {'error': f'Connection error: {str(e)}'}
    except Exception as e:
        logger.error(f"Single resource sync failed: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {'error': str(e)}
