"""
This module contains Celery tasks for synchronizing healthcare data from a Hospital
Management System (HMS) to a FHIR (Fast Healthcare Interoperability Resources) server.

The tasks handle:
- Patient data synchronization with encryption support
- FHIR data validation and cleaning
- Queue-based processing for reliable data transfer
- Error handling and retry mechanisms
- Connection health checks
- Data cleanup operations

Key Features:
- Handles encrypted patient data fields (PII protection)
- Validates FHIR data structure before transmission
- Provides retry mechanisms for failed operations
- Includes comprehensive logging and error tracking
"""

from celery import shared_task
from .syncManager import FHIRSyncService
from .queueManager import SyncQueueManager
from .models import SyncRule, SyncQueue, SyncLog
from .mappers import FHIRMapper
from django.apps import apps
from datetime import timedelta
from django.utils import timezone
import logging
from django.contrib.contenttypes.models import ContentType
from django.apps import apps
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from requests.exceptions import ConnectionError, RequestException
import traceback
from .tasksUtils import get_resource_id, validate_fhir_data
logger = logging.getLogger(__name__)



# ============================================================================
# MAIN SYNC TASKS
# ============================================================================

@shared_task(bind=True, max_retries=3)
def process_sync_queue_task(self, limit=50):
    """
    Process items from the sync queue in batches.
    
    This task:
    1. Checks FHIR server availability
    2. Processes up to 'limit' queued items
    3. Handles connection errors with exponential backoff
    4. Logs comprehensive results
    
    Args:
        limit (int): Maximum number of items to process
        
    Returns:
        dict: Processing results including success/failure counts
    """
    try:
        # Pre-flight check: ensure FHIR server is reachable
        sync_service = FHIRSyncService()
        if not sync_service.check_server_availability():
            logger.warning("FHIR server not available, skipping sync")
            return {'error': 'FHIR server not available', 'total': 0, 'success': 0, 'failed': 0}
        
        # Process the queue using the queue manager
        results = SyncQueueManager.process_queue(limit=limit)
        logger.info(f"Processed {results['total']} items: {results['success']} success, {results['failed']} failed")
        return results
        
    except ConnectionError as e:
        # Network connectivity issues - retry with longer delay
        logger.error(f"Connection error during sync: {e}")
        raise self.retry(countdown=300, exc=e)  # Wait 5 minutes before retry
    except Exception as e:
        # General errors - retry with shorter delay
        logger.error(f"Sync queue processing failed: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise self.retry(countdown=60, exc=e)

@shared_task(bind=True, max_retries=3)
def full_sync_task(self, resource_types=None):
    """
    Perform a complete synchronization of all HMS data to FHIR.
    
    This comprehensive task:
    1. Validates FHIR server connectivity
    2. Processes all enabled sync rules
    3. Generates FHIR data for each HMS record
    4. Validates data before queuing
    5. Processes the entire queue
    
    Args:
        resource_types (list, optional): Specific FHIR resource types to sync
        
    Returns:
        dict: Complete sync statistics
    """
    try:
        # Pre-flight check: ensure FHIR server is reachable
        sync_service = FHIRSyncService()
        if not sync_service.check_server_availability():
            logger.warning("FHIR server not available, cannot perform full sync")
            return {'error': 'FHIR server not available'}
        
        total_queued = 0
        total_errors = 0
        
        # Get active sync rules (configuration for what to sync)
        sync_rules = SyncRule.objects.filter(is_enabled=True)
        if resource_types:
            # Filter to specific resource types if requested
            sync_rules = sync_rules.filter(resource_type__in=resource_types)
        
        # Process each sync rule
        for rule in sync_rules:
            try:
                # Dynamically get the HMS model class
                model_class = apps.get_model(rule.hms_model_app, rule.hms_model_name)
                
                # Get the appropriate FHIR mapper function
                mapper_func = FHIRMapper.get(rule.resource_type)
                if not mapper_func:
                    logger.warning(f"No mapper found for {rule.resource_type}")
                    continue
                
                # Build queryset with optional filters
                queryset = model_class.objects.all()
                if rule.sync_filter:
                    # Apply rule-specific filters (e.g., only active patients)
                    queryset = queryset.filter(**rule.sync_filter)
                
                # Process each record in the queryset
                for record in queryset:
                    try:
                        # Generate FHIR data using preferred method
                        if hasattr(record, 'to_fhir_dict'):
                            # Use model's built-in FHIR conversion method
                            fhir_data = record.to_fhir_dict()
                        else:
                            # Fall back to mapper function
                            fhir_data = mapper_func(record)
                        
                        # Validate FHIR data structure before queuing
                        is_valid, validation_msg = validate_fhir_data(fhir_data, rule.resource_type)
                        if not is_valid:
                            logger.warning(f"Invalid FHIR data for {rule.resource_type} {get_resource_id(record)}: {validation_msg}")
                            total_errors += 1
                            continue
                        
                        # Extract appropriate resource identifier
                        resource_id = get_resource_id(record)
                        
                        # Queue the resource for synchronization
                        SyncQueueManager.queue_resource(
                            resource_type=rule.resource_type,
                            resource_id=resource_id,
                            fhir_data=fhir_data,
                            source_object=record,
                            sync_rule=rule
                        )
                        total_queued += 1
                        
                    except Exception as e:
                        # Log individual record errors but continue processing
                        logger.error(f"Failed to queue {rule.resource_type} {get_resource_id(record)}: {e}")
                        logger.error(f"Traceback: {traceback.format_exc()}")
                        total_errors += 1
                        continue
                        
            except Exception as e:
                # Log rule-level errors but continue with other rules
                logger.error(f"Error processing sync rule {rule}: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                total_errors += 1
                continue
        
        logger.info(f"Queued {total_queued} items for sync, {total_errors} errors")
        
        # Process the entire queue
        results = SyncQueueManager.process_queue()
        
        return {
            'queued': total_queued,
            'queue_errors': total_errors,
            'processed': results['total'],
            'success': results['success'],
            'failed': results['failed']
        }
        
    except ConnectionError as e:
        # Network issues during full sync
        logger.error(f"Connection error during full sync: {e}")
        raise self.retry(countdown=300, exc=e)  # Wait 5 minutes
    except Exception as e:
        # General errors during full sync
        logger.error(f"Full sync failed: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise self.retry(countdown=300, exc=e)

@shared_task
def retry_failed_syncs_task():
    """
    Retry previously failed synchronization operations.
    
    This task:
    1. Identifies failed sync queue items
    2. Attempts to resync them
    3. Updates their status based on results
    
    Returns:
        dict: Retry operation results
    """
    try:
        # Pre-flight check: ensure FHIR server is reachable
        sync_service = FHIRSyncService()
        if not sync_service.check_server_availability():
            logger.warning("FHIR server not available, skipping retry")
            return {'error': 'FHIR server not available'}
        
        # Use queue manager to retry failed items
        results = SyncQueueManager.retry_failed_items()
        logger.info(f"Retried {results['retried']} failed items")
        return results
    except Exception as e:
        logger.error(f"Retry failed syncs error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {'error': str(e)}

# ============================================================================
# PATIENT-SPECIFIC TASKS
# ============================================================================

@shared_task
def sync_patient_task(patient_id, operation='update'):
    """
    Synchronize a specific patient with full encryption support.
    
    This specialized task:
    1. Handles encrypted patient data fields
    2. Uses patient's built-in FHIR conversion method
    3. Provides high-priority processing
    4. Includes comprehensive validation
    
    Args:
        patient_id (str): The patient identifier
        operation (str): FHIR operation type
        
    Returns:
        dict: Sync result with patient and FHIR details
    """
    try:
        # Pre-flight check: ensure FHIR server is reachable
        sync_service = FHIRSyncService()
        if not sync_service.check_server_availability():
            return {'error': 'FHIR server not available'}
        
        # Get Patient model dynamically (adjust app name as needed)
        Patient = apps.get_model('Patients', 'Patient')
        patient = Patient.objects.get(patient_id=patient_id)
        
        # Generate FHIR data using patient's built-in method
        # This method should handle encryption/decryption automatically
        fhir_data = patient.to_fhir_dict()
        
        # Validate FHIR data structure and clean encrypted fields
        is_valid, validation_msg = validate_fhir_data(fhir_data, 'Patient')
        if not is_valid:
            logger.error(f"Patient {patient_id} validation failed: {validation_msg}")
            return {'error': f'Validation failed: {validation_msg}'}
        
        # Queue for high-priority sync
        queue_item = SyncQueueManager.queue_resource(
            resource_type='Patient',
            resource_id=patient_id,
            fhir_data=fhir_data,
            operation=operation,
            source_object=patient,
            priority=60  # High priority for individual patient syncs
        )
        
        # Process immediately rather than waiting for batch processing
        success = sync_service.sync_resource(queue_item)
        
        return {
            'success': success,
            'patient_id': patient_id,
            'fhir_id': queue_item.fhir_id,
            'status': queue_item.status
        }
        
    except Patient.DoesNotExist:
        return {'error': f'Patient {patient_id} not found'}
    except ConnectionError as e:
        logger.error(f"Connection error during patient sync: {e}")
        return {'error': f'Connection error: {str(e)}'}
    except Exception as e:
        logger.error(f"Patient sync failed: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {'error': str(e)}

# ============================================================================
# TESTING AND VALIDATION TASKS
# ============================================================================

@shared_task
def test_fhir_connection_task():
    """
    Test connectivity to the FHIR server.
    
    This diagnostic task:
    1. Attempts to connect to the FHIR server
    2. Validates server response
    3. Logs connection status
    4. Returns detailed status information
    
    Returns:
        dict: Connection test results
    """
    try:
        sync_service = FHIRSyncService()
        is_available = sync_service.check_server_availability()
        
        if is_available:
            logger.info("FHIR server connection successful")
            return {'status': 'success', 'message': 'FHIR server is available'}
        else:
            logger.warning("FHIR server connection failed")
            return {'statsus': 'failed', 'message': 'FHIR server is not available'}
            
    except Exception as e:
        logger.error(f"FHIR connection test failed: {e}")
        return {'status': 'error', 'message': str(e)}

@shared_task
def validate_patient_data_task(patient_id=None, limit=10):
    """
    Validate patient FHIR data without actually syncing to the server.
    
    This diagnostic task:
    1. Generates FHIR data for patients
    2. Validates data structure and content
    3. Checks for common data quality issues
    4. Reports on encryption field status
    
    Args:
        patient_id (str, optional): Specific patient to validate
        limit (int): Maximum number of patients to validate
        
    Returns:
        dict: Validation results with detailed statistics
    """
    try:
        # Get Patient model dynamically
        Patient = apps.get_model('Patients', 'Patient')
        
        # Build patient queryset
        if patient_id:
            patients = Patient.objects.filter(patient_id=patient_id)
        else:
            patients = Patient.objects.all()[:limit]
        
        results = []
        for patient in patients:
            try:
                # Generate FHIR data
                fhir_data = patient.to_fhir_dict()
                
                # Validate structure and content
                is_valid, validation_msg = validate_fhir_data(fhir_data, 'Patient')
                
                # Collect detailed validation results
                results.append({
                    'patient_id': patient.patient_id,
                    'valid': is_valid,
                    'message': validation_msg,
                    'has_name': bool(patient.given_name or patient.family_name),
                    'has_phone': bool(patient.primary_phone),
                    'has_email': bool(patient.email)
                })
                
            except Exception as e:
                # Handle errors in individual patient processing
                results.append({
                    'patient_id': patient.patient_id,
                    'valid': False,
                    'message': f'Error generating FHIR data: {str(e)}'
                })
        
        # Calculate summary statistics
        return {
            'tested': len(results),
            'valid': len([r for r in results if r['valid']]),
            'invalid': len([r for r in results if not r['valid']]),
            'results': results
        }
        
    except Exception as e:
        logger.error(f"Patient data validation failed: {e}")
        return {'error': str(e)}
    


# ============================================================================
# OBSERVATION SYNC TASKS
# ============================================================================

@shared_task
def sync_pending_observations():
    """Sync all pending observations to FHIR server"""
    try:
        sync_service = FHIRSyncService()
        
        # Get pending observation syncs
        pending_observations = SyncQueue.objects.filter(
            resource_type='Observation',
            status='pending'
        ).order_by('priority', 'created_at')[:50]  # Process 50 at a time
        
        results = {'success': 0, 'failed': 0}
        
        for queue_item in pending_observations:
            try:
                # Check if encounter needs to be removed from FHIR data
                if 'encounter' in queue_item.fhir_data:
                    # Verify encounter is synced
                    from MedicalRecords.models import Observation
                    obs = Observation.objects.get(id=queue_item.object_id)
                    
                    if hasattr(obs, 'encounter') and obs.encounter:
                        encounter_sync = SyncQueue.objects.filter(
                            resource_type='Encounter',
                            object_id=obs.encounter.id,
                            status='success'
                        ).first()
                        
                        if not encounter_sync:
                            # Remove encounter reference if not synced
                            queue_item.fhir_data.pop('encounter', None)
                            queue_item.save()
                            logger.info(f"Removed unsynced encounter reference from observation {queue_item.object_id}")
                
                # Sync the observation
                if sync_service.sync_resource(queue_item):
                    results['success'] += 1
                    logger.info(f"Successfully synced observation {queue_item.resource_id}")
                else:
                    results['failed'] += 1
                    logger.error(f"Failed to sync observation {queue_item.resource_id}: {queue_item.error_message}")
                    
            except Exception as e:
                results['failed'] += 1
                logger.error(f"Exception syncing observation {queue_item.resource_id}: {e}")
                queue_item.mark_failed(str(e))
        
        logger.info(f"Observation sync completed: {results['success']} success, {results['failed']} failed")
        return results
        
    except Exception as e:
        logger.error(f"Observation sync task failed: {e}")
        return {'error': str(e)}


@shared_task
def queue_new_observations():
    """Queue any observations that aren't in the sync queue yet"""
    try:
        from MedicalRecords.models import Observation
        
        # Get observations not in sync queue
        synced_obs_ids = SyncQueue.objects.filter(
            resource_type='Observation'
        ).values_list('object_id', flat=True)
        
        unsynced_observations = Observation.objects.exclude(
            id__in=synced_obs_ids
        )[:100]  # Limit to 100 at a time
        
        queued_count = 0
        
        for obs in unsynced_observations:
            try:
                # Build FHIR data
                fhir_data = {
                    "resourceType": "Observation",
                    "status": "final",
                    "code": {"text": obs.code},
                    "subject": {"reference": f"Patient/{obs.patient.patient_id}"},
                }
                
                if obs.observation_time:
                    fhir_data["effectiveDateTime"] = obs.observation_time.isoformat()
                
                # Add value
                try:
                    fhir_data["valueQuantity"] = {
                        "value": float(obs.value),
                        "unit": getattr(obs, 'unit', '')
                    }
                except:
                    fhir_data["valueString"] = str(obs.value)
                
                # Don't add encounter reference unless it's synced
                if hasattr(obs, 'encounter') and obs.encounter:
                    encounter_sync = SyncQueue.objects.filter(
                        resource_type='Encounter',
                        object_id=obs.encounter.id,
                        status='success'
                    ).first()
                    
                    if encounter_sync and encounter_sync.fhir_id:
                        fhir_data["encounter"] = {"reference": f"Encounter/{encounter_sync.fhir_id}"}
                
                # Create queue item
                SyncQueue.objects.create(
                    resource_type='Observation',
                    resource_id=str(obs.id),
                    object_id=obs.id,
                    operation='create',
                    fhir_data=fhir_data,
                    status='pending',
                    priority=50
                )
                queued_count += 1
                
            except Exception as e:
                logger.error(f"Failed to queue observation {obs.id}: {e}")
        
        logger.info(f"Queued {queued_count} new observations for sync")
        return {'queued': queued_count}
        
    except Exception as e:
        logger.error(f"Queue observations task failed: {e}")
        return {'error': str(e)}


@shared_task
def process_observation_sync_queue():
    """Combined task to queue and sync observations"""
    try:
        # First queue any new observations
        queue_result = queue_new_observations()
        logger.info(f"Queue result: {queue_result}")
        
        # Then sync pending observations
        sync_result = sync_pending_observations()
        logger.info(f"Sync result: {sync_result}")
        
        return {
            'queued': queue_result.get('queued', 0),
            'synced': sync_result.get('success', 0),
            'failed': sync_result.get('failed', 0)
        }
    except Exception as e:
        logger.error(f"Process observation sync queue failed: {e}")
        return {'error': str(e)}