# Fsync/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from .models import SyncRule, SyncQueue
from .services import SyncQueueManager
from .mappers import FHIR_MAPPERS
import logging

logger = logging.getLogger(__name__)

# Store registered models to avoid duplicate signal connections
_registered_models = set()

def setup_sync_signals():
    """Setup signals for auto-sync based on sync rules"""
    logger.info("Setting up FHIR sync signals...")
    
    # Get all active real-time sync rules
    sync_rules = SyncRule.objects.filter(is_enabled=True, sync_frequency='realtime')
    
    for rule in sync_rules:
        try:
            model_class = apps.get_model(rule.hms_model_app, rule.hms_model_name)
            model_key = f"{rule.hms_model_app}.{rule.hms_model_name}"
            
            # Avoid duplicate registrations
            if model_key in _registered_models:
                continue
                
            _registered_models.add(model_key)
            
            # Connect signals for this model
            @receiver(post_save, sender=model_class, weak=False)
            def handle_model_save(sender, instance, created, **kwargs):
                handle_instance_save(sender, instance, created)
            
            @receiver(post_delete, sender=model_class, weak=False)
            def handle_model_delete(sender, instance, **kwargs):
                handle_instance_delete(sender, instance)
            
            logger.info(f"Connected signals for {model_key} -> {rule.resource_type}")
            
        except Exception as e:
            logger.error(f"Error setting up signals for {rule}: {e}")

def handle_instance_save(sender, instance, created):
    """Handle model save events"""
    try:
        app_label = sender._meta.app_label
        model_name = sender._meta.model_name
        
        # Find matching sync rules
        sync_rules = SyncRule.objects.filter(
            hms_model_app=app_label,
            hms_model_name=model_name,
            is_enabled=True,
            sync_frequency='realtime'
        )
        
        for rule in sync_rules:
            try:
                # Get the mapper function
                mapper_func = FHIR_MAPPERS.get(rule.resource_type)
                if not mapper_func:
                    logger.warning(f"No mapper found for {rule.resource_type}")
                    continue
                
                # Generate FHIR data
                fhir_data = mapper_func(instance)
                operation = 'create' if created else 'update'
                
                # Queue for sync
                queue_item = SyncQueueManager.queue_resource(
                    resource_type=rule.resource_type,
                    resource_id=str(instance.id),
                    fhir_data=fhir_data,
                    operation=operation,
                    source_object=instance,
                    sync_rule=rule,
                    priority=50  # Higher priority for real-time
                )
                
                logger.info(f"Queued {rule.resource_type} {instance.id} for {operation} (Queue ID: {queue_item.id})")
                
            except Exception as e:
                logger.error(f"Error queuing {rule.resource_type} {instance.id}: {e}")
    
    except Exception as e:
        logger.error(f"Error in save signal handler: {e}")

def handle_instance_delete(sender, instance):
    """Handle model delete events"""
    try:
        app_label = sender._meta.app_label
        model_name = sender._meta.model_name
        
        # Find matching sync rules
        sync_rules = SyncRule.objects.filter(
            hms_model_app=app_label,
            hms_model_name=model_name,
            is_enabled=True
        )
        
        for rule in sync_rules:
            try:
                # Mark existing queue items for deletion
                SyncQueue.objects.filter(
                    resource_type=rule.resource_type,
                    resource_id=str(instance.id),
                    status__in=['pending', 'processing']
                ).update(
                    operation='delete',
                    fhir_data={'resourceType': rule.resource_type, 'id': str(instance.id)},
                    priority=50
                )
                
                logger.info(f"Marked {rule.resource_type} {instance.id} for deletion")
                
            except Exception as e:
                logger.error(f"Error marking {rule.resource_type} {instance.id} for deletion: {e}")
    
    except Exception as e:
        logger.error(f"Error in delete signal handler: {e}")

# Manual signal connection function for testing
def connect_patient_signals():
    """Manually connect Patient signals for testing"""
    try:
        from Patients.models import Patient  # Replace with your actual import
        
        @receiver(post_save, sender=Patient)
        def patient_saved(sender, instance, created, **kwargs):
            logger.info(f"Patient signal triggered: {instance.id} ({'created' if created else 'updated'})")
            handle_instance_save(sender, instance, created)
        
        @receiver(post_delete, sender=Patient)
        def patient_deleted(sender, instance, **kwargs):
            logger.info(f"Patient delete signal triggered: {instance.id}")
            handle_instance_delete(sender, instance)
            
        logger.info("Manually connected Patient signals")
        
    except ImportError as e:
        logger.error(f"Could not import Patient model: {e}")