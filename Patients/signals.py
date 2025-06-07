from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from Patients.models import Patient
from Fsync.services import SyncQueueManager
from Fsync.mappers import PatientMapper
from Fsync.models import SyncRule
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Patient)
def queue_patient_for_sync(sender, instance, created, **kwargs):
    """Queue patient for FHIR sync when saved"""
    try:
        # Check if there's an active sync rule for Patient
        sync_rule = SyncRule.objects.filter(
            resource_type='Patient',
            hms_model_app='Patients',  # Adjust if your app name is different
            hms_model_name='Patient',
            is_enabled=True
        ).first()
        
        if sync_rule:
            # Use the FHIR mapper to convert patient data
            fhir_data = PatientMapper.to_fhir(instance)
            operation = 'create' if created else 'update'
            
            # Queue the resource for sync
            SyncQueueManager.queue_resource(
                resource_type='Patient',
                resource_id=str(instance.patient_id),  # or instance.id
                fhir_data=fhir_data,
                operation=operation,
                source_object=instance,
                sync_rule=sync_rule,
                priority=50  # Higher priority for real-time sync
            )
            
            logger.info(f"Queued Patient {instance.patient_id} for {operation}")
        else:
            logger.warning("No active sync rule found for Patient model")
            
    except Exception as e:
        logger.error(f"Error queuing patient for sync: {e}")

@receiver(post_delete, sender=Patient)
def queue_patient_for_deletion(sender, instance, **kwargs):
    """Queue patient for deletion in FHIR when deleted"""
    try:
        # Mark any pending sync operations for this patient as delete operations
        from Fsync.models import SyncQueue
        
        SyncQueue.objects.filter(
            resource_type='Patient',
            resource_id=str(instance.patient_id),
            status__in=['pending', 'processing']
        ).update(
            operation='delete',
            fhir_data={'resourceType': 'Patient', 'id': str(instance.patient_id)}
        )
        
        logger.info(f"Marked Patient {instance.patient_id} for deletion")
        
    except Exception as e:
        logger.error(f"Error marking patient for deletion: {e}")