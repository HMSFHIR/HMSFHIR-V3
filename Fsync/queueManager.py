from typing import Dict, List, Optional, Any, Tuple
from services import SyncQueue, SyncRule
from django.utils import timezone
from syncManager import FHIRSyncService
from django.contrib.contenttypes.models import ContentType

class SyncQueueManager:
    """Manager for sync queue operations"""
    
    @staticmethod
    def queue_resource(resource_type: str, resource_id: str, fhir_data: Dict = None, 
                      operation: str = 'create', priority: int = 100,
                      source_object=None, sync_rule=None) -> SyncQueue:
        """Add resource to sync queue"""
        
        # Generate FHIR data from source object if not provided
        if not fhir_data and source_object:
            if hasattr(source_object, 'to_fhir_dict'):
                fhir_data = source_object.to_fhir_dict()
            else:
                fhir_data = {}
        
        fhir_data = fhir_data or {}
        
        # For Patient resources, ensure we use patient_id as resource_id
        if resource_type == 'Patient' and source_object and hasattr(source_object, 'patient_id'):
            resource_id = source_object.patient_id
        
        # Check for existing queue item
        existing = SyncQueue.objects.filter(
            resource_type=resource_type,
            resource_id=resource_id,
            status__in=['pending', 'processing']
        ).first()
        
        if existing:
            # Update existing item
            existing.fhir_data = fhir_data
            existing.operation = operation
            existing.priority = priority
            existing.status = 'pending'
            existing.attempts = 0
            existing.error_message = None
            if sync_rule:
                existing.sync_rule = sync_rule
            existing.save()
            return existing
        else:
            # Create new queue item
            content_type = None
            object_id = None
            
            if source_object:
                content_type = ContentType.objects.get_for_model(source_object)
                object_id = source_object.pk
            
            return SyncQueue.objects.create(
                resource_type=resource_type,
                resource_id=resource_id,
                operation=operation,
                fhir_data=fhir_data,
                priority=priority,
                sync_rule=sync_rule,
                content_type=content_type,
                object_id=object_id
            )
    
    @staticmethod
    def queue_patient(patient, operation: str = 'create', priority: int = 100) -> SyncQueue:
        """Convenience method to queue a Patient resource"""
        # Find the appropriate sync rule for Patient
        sync_rule = SyncRule.objects.filter(
            resource_type='Patient',
            is_enabled=True
        ).first()
        
        return SyncQueueManager.queue_resource(
            resource_type='Patient',
            resource_id=patient.patient_id,
            source_object=patient,
            operation=operation,
            priority=priority,
            sync_rule=sync_rule
        )
    
    @staticmethod
    def process_queue(limit: int = 50) -> Dict[str, int]:
        """Process pending queue items"""
        sync_service = FHIRSyncService()
        
        # Get pending items
        pending_items = SyncQueue.objects.filter(
            status='pending',
            scheduled_at__lte=timezone.now()
        ).order_by('priority', 'created_at')[:limit]
        
        results = {'success': 0, 'failed': 0, 'total': len(pending_items)}
        
        for item in pending_items:
            success = sync_service.sync_resource(item)
            if success:
                results['success'] += 1
            else:
                results['failed'] += 1
        
        return results
    
    @staticmethod
    def retry_failed_items(max_retries: int = 3) -> Dict[str, int]:
        """Retry failed queue items"""
        failed_items = SyncQueue.objects.filter(
            status='failed',
            attempts__lt=max_retries
        ).order_by('last_attempt_at')
        
        results = {'retried': 0, 'success': 0, 'failed': 0}
        sync_service = FHIRSyncService()
        
        for item in failed_items:
            item.status = 'pending'
            item.save()
            results['retried'] += 1
            
            success = sync_service.sync_resource(item)
            if success:
                results['success'] += 1
            else:
                results['failed'] += 1
        
        return results
    
    @staticmethod
    def get_statistics() -> Dict[str, Any]:
        """Get queue statistics"""
        stats = {}
        
        # Overall stats
        stats['total'] = SyncQueue.objects.count()
        stats['pending'] = SyncQueue.objects.filter(status='pending').count()
        stats['processing'] = SyncQueue.objects.filter(status='processing').count()
        stats['success'] = SyncQueue.objects.filter(status='success').count()
        stats['failed'] = SyncQueue.objects.filter(status='failed').count()
        
        # By resource type
        stats['by_resource_type'] = {}
        for resource_type, _ in SyncRule.RESOURCE_TYPES:
            type_stats = {
                'pending': SyncQueue.objects.filter(
                    resource_type=resource_type, status='pending'
                ).count(),
                'success': SyncQueue.objects.filter(
                    resource_type=resource_type, status='success'
                ).count(),
                'failed': SyncQueue.objects.filter(
                    resource_type=resource_type, status='failed'
                ).count(),
            }
            type_stats['total'] = sum(type_stats.values())
            stats['by_resource_type'][resource_type] = type_stats
        
        return stats