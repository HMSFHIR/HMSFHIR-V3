from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from Fsync.mappers import ObservationMapper
from MedicalRecords.models import Observation, Encounter, Condition, MedicationStatement, AllergyIntolerance, Procedure, Immunization
from Fsync.queueManager import SyncQueueManager
from Fsync.models import SyncRule
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Observation)
def queue_observation_for_sync(sender, instance, created, **kwargs):
    """Queue observation for FHIR sync when saved"""
    try:
        # Check if there's an active sync rule for Observation
        sync_rule = SyncRule.objects.filter(
            resource_type='Observation',
            hms_model_app='MedicalRecords',  # Adjust if your app name is different
            hms_model_name='Observation',
            is_enabled=True
        ).first()

        if sync_rule:
            # Use the FHIR mapper to convert observation data
            fhir_data = ObservationMapper.to_fhir(instance)
            operation = 'create' if created else 'update'

            # Queue the resource for sync
            SyncQueueManager.queue_resource(
                resource_type='Observation',
                resource_id=str(instance.id),
                fhir_data=fhir_data,
                operation=operation,
                source_object=instance,
                sync_rule=sync_rule,
                priority=50  # Higher priority for real-time sync
            )

            logger.info(f"Queued Observation {instance.id} for {operation}")
        else:
            logger.warning("No active sync rule found for Observation model")

    except Exception as e:
        logger.error(f"Error queuing observation for sync: {e}")

@receiver(post_delete, sender=Observation)
def queue_observation_for_deletion(sender, instance, **kwargs):
    """Queue observation for deletion in FHIR when deleted"""
    try:
        # Mark any pending sync operations for this observation as delete operations
        from Fsync.models import SyncQueue
        
        SyncQueue.objects.filter(
            resource_type='Observation',
            resource_id=str(instance.id),
            status__in=['pending', 'processing']
        ).update(
            operation='delete',
            fhir_data={'resourceType': 'Observation', 'id': str(instance.id)}
        )

        logger.info(f"Marked Observation {instance.id} for deletion")

    except Exception as e:
        logger.error(f"Error marking observation for deletion: {e}")


from django.db.models.signals import post_save
from django.dispatch import receiver
from Fsync.models import SyncQueue
import json

@receiver(post_save, sender=Observation)
def queue_observation_sync(sender, instance, created, **kwargs):
    """Queue observation for FHIR sync after save"""
    
    # Check if sync is already queued
    existing = SyncQueue.objects.filter(
        resource_type='Observation',
        object_id=instance.id,
        status__in=['pending', 'processing']
    ).exists()
    
    if not existing:
        # Create sync queue entry
        SyncQueue.objects.create(
            resource_type='Observation',
            resource_id=str(instance.id),
            object_id=instance.id,
            operation='create' if created else 'update',
            fhir_data=instance.to_fhir_dict(),
            priority=50  # Higher priority than patient updates
        )
