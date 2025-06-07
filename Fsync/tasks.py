# tasks.py - Complete Celery Tasks
# ============================================================================
from celery import shared_task
from .services import SyncQueueManager, FHIRSyncService
from .models import SyncRule, SyncQueue, SyncLog
from .mappers import FHIR_MAPPERS
from django.apps import apps
from datetime import timedelta
from django.utils import timezone
import logging
from celery import shared_task
from django.contrib.contenttypes.models import ContentType
from django.apps import apps
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

# Your other model imports
from Patients.models import Patient  # Replace with your actual models
logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def process_sync_queue_task(self, limit=50):
    """Process sync queue items"""
    try:
        results = SyncQueueManager.process_queue(limit=limit)
        logger.info(f"Processed {results['total']} items: {results['success']} success, {results['failed']} failed")
        return results
    except Exception as e:
        logger.error(f"Sync queue processing failed: {e}")
        raise self.retry(countdown=60, exc=e)

@shared_task(bind=True, max_retries=3)
def full_sync_task(self, resource_types=None):
    """Sync all HMS data to FHIR"""
    try:
        total_queued = 0
        
        # Get active sync rules
        sync_rules = SyncRule.objects.filter(is_enabled=True)
        if resource_types:
            sync_rules = sync_rules.filter(resource_type__in=resource_types)
        
        for rule in sync_rules:
            try:
                # Get the model class
                model_class = apps.get_model(rule.hms_model_app, rule.hms_model_name)
                
                # Get mapper function
                mapper_func = FHIR_MAPPERS.get(rule.resource_type)
                if not mapper_func:
                    logger.warning(f"No mapper found for {rule.resource_type}")
                    continue
                
                # Apply filters
                queryset = model_class.objects.all()
                if rule.sync_filter:
                    queryset = queryset.filter(**rule.sync_filter)
                
                # Queue each record
                for record in queryset:
                    try:
                        fhir_data = mapper_func(record)
                        resource_id = str(getattr(record, 'id'))
                        
                        SyncQueueManager.queue_resource(
                            resource_type=rule.resource_type,
                            resource_id=resource_id,
                            fhir_data=fhir_data,
                            source_object=record,
                            sync_rule=rule
                        )
                        total_queued += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to queue {rule.resource_type} {record.id}: {e}")
                        continue
                        
            except Exception as e:
                logger.error(f"Error processing sync rule {rule}: {e}")
                continue
        
        logger.info(f"Queued {total_queued} items for sync")
        
        # Process the queue
        results = SyncQueueManager.process_queue()
        
        return {
            'queued': total_queued,
            'processed': results['total'],
            'success': results['success'],
            'failed': results['failed']
        }
        
    except Exception as e:
        logger.error(f"Full sync failed: {e}")
        raise self.retry(countdown=300, exc=e)

@shared_task
def retry_failed_syncs_task():
    """Retry failed sync operations"""
    try:
        results = SyncQueueManager.retry_failed_items()
        logger.info(f"Retried {results['retried']} failed items")
        return results
    except Exception as e:
        logger.error(f"Retry failed syncs error: {e}")
        return {'error': str(e)}

@shared_task
def cleanup_sync_tasks():
    """Clean up old sync tasks"""
    try:
        cutoff_date = timezone.now() - timedelta(days=30)
        
        # Clean up successful sync logs older than 30 days
        deleted_logs = SyncLog.objects.filter(
            timestamp__lt=cutoff_date,
            level__in=['INFO', 'DEBUG']
        ).delete()
        
        # Clean up successful queue items older than 7 days
        success_cutoff = timezone.now() - timedelta(days=7)
        deleted_queue = SyncQueue.objects.filter(
            status='success',
            completed_at__lt=success_cutoff
        ).delete()
        
        logger.info(f"Cleanup completed: {deleted_logs[0]} logs, {deleted_queue[0]} queue items")
        return {
            'logs_deleted': deleted_logs[0],
            'queue_items_deleted': deleted_queue[0]
        }
    except Exception as e:
        logger.error(f"Cleanup task failed: {e}")
        return {'error': str(e)}

@shared_task
def sync_single_resource_task(resource_type, resource_id, operation='create'):
    """Sync a single resource"""
    try:
        queue_item = SyncQueue.objects.get(
            resource_type=resource_type,
            resource_id=resource_id,
            status__in=['pending', 'failed']
        )
        
        sync_service = FHIRSyncService()
        success = sync_service.sync_resource(queue_item)
        
        return {
            'success': success,
            'status': queue_item.status,
            'fhir_id': queue_item.fhir_id
        }
    except SyncQueue.DoesNotExist:
        return {'error': 'Queue item not found'}
    except Exception as e:
        logger.error(f"Single resource sync failed: {e}")
        return {'error': str(e)}
