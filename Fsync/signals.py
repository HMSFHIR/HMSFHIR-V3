from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.apps import apps
from .models import SyncRule, SyncQueue
from .services import SyncQueueManager
from .mappers import FHIR_MAPPERS
import logging


logger = logging.getLogger(__name__)

def setup_sync_signals():
    """Setup signals for auto-sync based on sync rules"""
    
    # Get all active sync rules
    sync_rules = SyncRule.objects.filter(is_enabled=True, sync_frequency='realtime')
    
    for rule in sync_rules:
        try:
            model_class = apps.get_model(rule.hms_model_app, rule.hms_model_name)
            
            # Create signal handlers for this model
            @receiver(post_save, sender=model_class, weak=False)
            def handle_model_save(sender, instance, created, **kwargs):
                try:
                    # Find the sync rule for this model
                    rule = SyncRule.objects.filter(
                        hms_model_app=sender._meta.app_label,
                        hms_model_name=sender._meta.model_name,
                        is_enabled=True,
                        sync_frequency='realtime'
                    ).first()
                    
                    if rule:
                        mapper_func = FHIR_MAPPERS.get(rule.resource_type)
                        if mapper_func:
                            fhir_data = mapper_func(instance)
                            operation = 'create' if created else 'update'
                            
                            SyncQueueManager.queue_resource(
                                resource_type=rule.resource_type,
                                resource_id=str(instance.id),
                                fhir_data=fhir_data,
                                operation=operation,
                                source_object=instance,
                                sync_rule=rule,
                                priority=50  # Higher priority for real-time
                            )
                            
                            logger.info(f"Queued {rule.resource_type} {instance.id} for {operation}")
                        
                except Exception as e:
                    logger.error(f"Error in sync signal handler: {e}")
            
            @receiver(post_delete, sender=model_class, weak=False)
            def handle_model_delete(sender, instance, **kwargs):
                try:
                    # Find existing queue items for this instance
                    SyncQueue.objects.filter(
                        resource_type__in=[rule.resource_type for rule in SyncRule.objects.filter(
                            hms_model_app=sender._meta.app_label,
                            hms_model_name=sender._meta.model_name
                        )],
                        resource_id=str(instance.id),
                        status__in=['pending', 'processing']
                    ).update(
                        operation='delete',
                        fhir_data={'resourceType': rule.resource_type, 'id': str(instance.id)}
                    )
                    
                    logger.info(f"Marked {rule.resource_type} {instance.id} for deletion")
                    
                except Exception as e:
                    logger.error(f"Error in delete signal handler: {e}")
                    
        except Exception as e:
            logger.error(f"Error setting up signals for {rule}: {e}")