from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging
import traceback
from .models import SyncLog, SyncQueue
from .syncManager import FHIRSyncService
from  .tasksUtils import validate_fhir_data
from django.db.models import Count
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
        cutoff_date = timezone.now() - timedelta(seconds=300)  # 5 minutes for logs
        
        # Clean up successful sync logs older than 30 days
        # Keep INFO and DEBUG level logs for historical reference
        deleted_logs = SyncLog.objects.filter(
            timestamp__lt=cutoff_date,
            level__in=['INFO', 'DEBUG']  # Don't delete ERROR or WARNING logs
        ).delete()
        
        # Clean up successful queue items older than 7 days
        # Successful items don't need long-term retention
        # Use 'created_at' instead of 'timestamp' for SyncQueue model
        deleted_queue = SyncQueue.objects.filter(
            created_at__lt=cutoff_date,
            status='success'  # Only delete successful items
        ).delete()
        
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


# Add to Fsync/maintenanceUtils.py

@shared_task
def cleanup_stuck_processing_items():
    """Clean up items stuck in processing status and remove duplicates"""
    try:
        # Add Appointment to the resource types to clean up
        resource_types = ['Observation', 'Patient', 'Encounter', 'Appointment', 'AllergyIntolerance', 'Practitioner', 'Condition', 'MedicationStatement', 'Procedure']
        
        total_stuck_reset = 0
        total_duplicates_removed = 0
        
        for resource_type in resource_types:
            # 1. Reset items stuck in processing for more than 30 minutes
            stuck_threshold = timezone.now() - timedelta(minutes=30)
            stuck_items = SyncQueue.objects.filter(
                resource_type=resource_type,
                status='processing',
                updated_at__lt=stuck_threshold
            )
            
            stuck_count = stuck_items.count()
            if stuck_count > 0:
                stuck_items.update(status='pending')
                total_stuck_reset += stuck_count
                logger.info(f"Reset {stuck_count} stuck {resource_type} items back to pending")
            
            # 2. Clean up duplicate queue items for the same object_id
            duplicate_object_ids = SyncQueue.objects.filter(
                resource_type=resource_type,
                status__in=['pending', 'processing']
            ).values('object_id').annotate(
                count=Count('id')
            ).filter(count__gt=1).values_list('object_id', flat=True)
            
            for obj_id in duplicate_object_ids:
                # For each duplicate group, keep only the oldest item
                items = SyncQueue.objects.filter(
                    resource_type=resource_type,
                    object_id=obj_id,
                    status__in=['pending', 'processing']
                ).order_by('created_at')
                
                if items.count() > 1:
                    # Keep the oldest, delete the rest
                    oldest = items.first()
                    duplicates = items.exclude(id=oldest.id)
                    duplicate_count = duplicates.count()
                    
                    logger.info(f"Removing {duplicate_count} duplicate {resource_type} items for object_id {obj_id}, keeping item {oldest.id}")
                    duplicates.delete()
                    total_duplicates_removed += duplicate_count
        
        # 3. Check for items that have been pending too long (over 24 hours)
        old_pending_threshold = timezone.now() - timedelta(hours=24)
        old_pending_counts = {}
        
        for resource_type in resource_types:
            old_pending = SyncQueue.objects.filter(
                resource_type=resource_type,
                status='pending',
                created_at__lt=old_pending_threshold
            ).count()
            
            if old_pending > 0:
                old_pending_counts[resource_type] = old_pending
                logger.warning(f"Found {old_pending} {resource_type} items pending for over 24 hours")
        
        results = {
            'stuck_items_reset': total_stuck_reset,
            'duplicates_removed': total_duplicates_removed,
            'old_pending_items': old_pending_counts,
            'resource_types_cleaned': resource_types
        }
        
        logger.info(f"Cleanup completed: {results}")
        return results
        
    except Exception as e:
        logger.error(f"Cleanup task failed: {e}")
        return {'error': str(e)}

@shared_task  
def cleanup_sync_tasks():
    """Enhanced cleanup that includes stuck items"""
    try:
        # Run your existing cleanup logic first
        # ... your existing cleanup code ...
        
        # Then run the new stuck items cleanup
        stuck_cleanup = cleanup_stuck_processing_items()
        
        return {
            'regular_cleanup': 'completed',
            'stuck_cleanup': stuck_cleanup
        }
        
    except Exception as e:
        logger.error(f"Enhanced cleanup failed: {e}")
        return {'error': str(e)}