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
        
        # Get observations not in sync queue (checking all statuses, not just successful)
        synced_obs_ids = SyncQueue.objects.filter(
            resource_type='Observation'
        ).values_list('object_id', flat=True).distinct()  # Add distinct() to avoid duplicates
        
        unsynced_observations = Observation.objects.exclude(
            id__in=synced_obs_ids
        )[:100]  # Limit to 100 at a time
        
        queued_count = 0
        
        for obs in unsynced_observations:
            try:
                # Double-check for existing queue items before creating
                existing_item = SyncQueue.objects.filter(
                    resource_type='Observation',
                    object_id=obs.id
                ).first()
                
                if existing_item:
                    logger.info(f"Skipping observation {obs.id} - already in queue (item {existing_item.id})")
                    continue
                
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
                
                # Create queue item with get_or_create to prevent duplicates
                queue_item, created = SyncQueue.objects.get_or_create(
                    resource_type='Observation',
                    object_id=obs.id,
                    defaults={
                        'resource_id': str(obs.id),
                        'operation': 'create',
                        'fhir_data': fhir_data,
                        'status': 'pending',
                        'priority': 50
                    }
                )
                
                if created:
                    queued_count += 1
                    logger.info(f"Queued observation {obs.id} for sync")
                else:
                    logger.info(f"Observation {obs.id} already queued (item {queue_item.id})")
                
            except Exception as e:
                logger.error(f"Failed to queue observation {obs.id}: {e}")
        
        logger.info(f"Queued {queued_count} new observations for sync")
        return {'queued': queued_count}
        
    except Exception as e:
        logger.error(f"Queue observations task failed: {e}")
        return {'error': str(e)}


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
        
        results = {'success': 0, 'failed': 0, 'skipped': 0}
        
        for queue_item in pending_observations:
            try:
                # Check for duplicates before processing
                duplicate_processing = SyncQueue.objects.filter(
                    resource_type='Observation',
                    object_id=queue_item.object_id,
                    status='processing'
                ).exclude(id=queue_item.id).exists()
                
                if duplicate_processing:
                    logger.info(f"Skipping observation {queue_item.object_id} - another item is already processing")
                    results['skipped'] += 1
                    continue
                
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
        
        logger.info(f"Observation sync completed: {results['success']} success, {results['failed']} failed, {results['skipped']} skipped")
        return results
        
    except Exception as e:
        logger.error(f"Observation sync task failed: {e}")
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
    

#=============================================================================
# APPOINTMENT SYNC TASKS 
#=============================================================================

@shared_task
def queue_new_appointments():
    """Queue any appointments that aren't in the sync queue yet"""
    try:
        from Appointments.models import Appointment
        
        # Get appointments not in sync queue
        synced_appointment_ids = SyncQueue.objects.filter(
            resource_type='Appointment'
        ).values_list('object_id', flat=True).distinct()
        
        unsynced_appointments = Appointment.objects.exclude(
            appointment_id__in=synced_appointment_ids
        )[:100]  # Limit to 100 at a time
        
        queued_count = 0
        skipped_count = 0
        
        for appointment in unsynced_appointments:
            try:
                # Double-check for existing queue items before creating
                existing_item = SyncQueue.objects.filter(
                    resource_type='Appointment',
                    object_id=appointment.appointment_id
                ).first()
                
                if existing_item:
                    logger.info(f"Skipping appointment {appointment.appointment_id} - already in queue")
                    skipped_count += 1
                    continue
                
                # Map appointment status to FHIR status
                status_mapping = {
                    'Scheduled': 'booked',
                    'Completed': 'fulfilled',
                    'Cancelled': 'cancelled'
                }
                fhir_status = status_mapping.get(appointment.status, 'proposed')
                
                # Build FHIR data for Appointment resource
                fhir_data = {
                    "resourceType": "Appointment",
                    "status": fhir_status,
                    "participant": []
                }
                
                # Add patient as participant using patient_id
                fhir_data["participant"].append({
                    "actor": {
                        "reference": f"Patient/{appointment.patient.patient_id}",
                        "display": appointment.patient.full_name
                    },
                    "status": "accepted"
                })
                
                # FIXED: Only add practitioner if they exist in FHIR
                if appointment.practitioner:
                    # Check if practitioner is synced to FHIR
                    practitioner_sync = SyncQueue.objects.filter(
                        resource_type='Practitioner',
                        object_id=appointment.practitioner.id,
                        status='success'
                    ).first()
                    
                    if practitioner_sync and practitioner_sync.fhir_id:
                        # Use the FHIR ID from successful sync
                        fhir_data["participant"].append({
                            "actor": {
                                "reference": f"Practitioner/{practitioner_sync.fhir_id}",
                                "display": appointment.practitioner.name
                            },
                            "status": "accepted"
                        })
                        logger.info(f"Added synced practitioner {practitioner_sync.fhir_id} to appointment {appointment.appointment_id}")
                    else:
                        # DON'T add practitioner reference if not synced to avoid FHIR errors
                        logger.warning(f"Skipping practitioner {appointment.practitioner.practitioner_id} for appointment {appointment.appointment_id} - not synced to FHIR")
                
                # Add appointment date/time
                if appointment.appointment_date:
                    from datetime import timedelta
                    start_time = appointment.appointment_date
                    end_time = start_time + timedelta(minutes=30)
                    
                    fhir_data["start"] = start_time.isoformat()
                    fhir_data["end"] = end_time.isoformat()
                
                # Add notes/comment if present
                if appointment.notes:
                    fhir_data["comment"] = str(appointment.notes)
                
                # Add service type
                fhir_data["serviceType"] = [{
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/service-type",
                        "code": "124",
                        "display": "General Practice"
                    }]
                }]
                
                # Add appointment type
                fhir_data["appointmentType"] = {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/v2-0276",
                        "code": "ROUTINE",
                        "display": "Routine appointment"
                    }]
                }
                
                # Use get_or_create to prevent duplicates
                queue_item, created = SyncQueue.objects.get_or_create(
                    resource_type='Appointment',
                    object_id=appointment.appointment_id,
                    defaults={
                        'resource_id': str(appointment.appointment_id),
                        'operation': 'create',
                        'fhir_data': fhir_data,
                        'status': 'pending',
                        'priority': 40
                    }
                )
                
                if created:
                    queued_count += 1
                    logger.info(f"Queued appointment {appointment.appointment_id} for sync")
                else:
                    skipped_count += 1
                    logger.info(f"Appointment {appointment.appointment_id} already queued")
                
            except Exception as e:
                logger.error(f"Failed to queue appointment {appointment.appointment_id}: {e}")
        
        logger.info(f"Queued {queued_count} new appointments, skipped {skipped_count}")
        return {'queued': queued_count, 'skipped': skipped_count}
        
    except Exception as e:
        logger.error(f"Queue appointments task failed: {e}")
        return {'error': str(e)}


# OPTIONAL: Task to sync the missing practitioner
@shared_task
def queue_missing_practitioners():
    """Queue practitioners that are referenced by appointments but not synced"""
    try:
        from Appointments.models import Appointment
        from Practitioner.models import Practitioner
        
        # Get practitioner IDs from appointments
        appointment_practitioner_ids = set(
            Appointment.objects.filter(practitioner__isnull=False)
            .values_list('practitioner_id', flat=True)
            .distinct()
        )
        
        # Get already synced practitioner IDs
        synced_practitioner_ids = set(
            SyncQueue.objects.filter(resource_type='Practitioner')
            .values_list('object_id', flat=True)
        )
        
        # Find practitioners that need to be synced
        unsynced_practitioner_ids = appointment_practitioner_ids - synced_practitioner_ids
        
        queued_count = 0
        
        for practitioner_id in unsynced_practitioner_ids:
            try:
                practitioner = Practitioner.objects.get(id=practitioner_id)
                
                # Build FHIR data for practitioner
                fhir_data = {
                    "resourceType": "Practitioner",
                    "active": True,
                    "name": [{
                        "text": practitioner.name,
                        "family": practitioner.name.split()[-1] if ' ' in practitioner.name else practitioner.name,
                        "given": practitioner.name.split()[:-1] if ' ' in practitioner.name else [practitioner.name]
                    }]
                }
                
                # Add role/qualification
                if practitioner.role:
                    fhir_data["qualification"] = [{
                        "code": {
                            "coding": [{
                                "system": "http://terminology.hl7.org/CodeSystem/practitioner-role",
                                "code": practitioner.role.lower(),
                                "display": practitioner.role.title()
                            }]
                        }
                    }]
                
                # Add contact info
                telecom = []
                if practitioner.phone:
                    telecom.append({
                        "system": "phone",
                        "value": practitioner.phone,
                        "use": "work"
                    })
                if practitioner.email:
                    telecom.append({
                        "system": "email", 
                        "value": practitioner.email,
                        "use": "work"
                    })
                if telecom:
                    fhir_data["telecom"] = telecom
                
                # Add hospital affiliation
                if practitioner.hospital_affiliation:
                    fhir_data["extension"] = [{
                        "url": "http://example.org/fhir/StructureDefinition/hospital-affiliation",
                        "valueString": practitioner.hospital_affiliation
                    }]
                
                # Create queue item
                queue_item, created = SyncQueue.objects.get_or_create(
                    resource_type='Practitioner',
                    object_id=practitioner.id,
                    defaults={
                        'resource_id': practitioner.practitioner_id,
                        'operation': 'create',
                        'fhir_data': fhir_data,
                        'status': 'pending',
                        'priority': 30  # Higher priority since needed for appointments
                    }
                )
                
                if created:
                    queued_count += 1
                    logger.info(f"Queued practitioner {practitioner.practitioner_id} for sync")
                
            except Practitioner.DoesNotExist:
                logger.error(f"Practitioner {practitioner_id} not found")
            except Exception as e:
                logger.error(f"Failed to queue practitioner {practitioner_id}: {e}")
        
        logger.info(f"Queued {queued_count} practitioners for sync")
        return {'queued': queued_count}
        
    except Exception as e:
        logger.error(f"Queue practitioners task failed: {e}")
        return {'error': str(e)}

@shared_task
def sync_pending_appointments():
    """Sync all pending appointments to FHIR server"""
    try:
        sync_service = FHIRSyncService()
        
        # Get pending appointment syncs
        pending_appointments = SyncQueue.objects.filter(
            resource_type='Appointment',
            status='pending'
        ).order_by('priority', 'created_at')[:50]  # Process 50 at a time
        
        results = {'success': 0, 'failed': 0, 'skipped': 0}
        
        for queue_item in pending_appointments:
            try:
                # Check for duplicates before processing
                duplicate_processing = SyncQueue.objects.filter(
                    resource_type='Appointment',
                    object_id=queue_item.object_id,
                    status='processing'
                ).exclude(id=queue_item.id).exists()
                
                if duplicate_processing:
                    logger.info(f"Skipping appointment {queue_item.object_id} - another item is already processing")
                    results['skipped'] += 1
                    continue
                
                # Validate appointment still exists
                try:
                    from Appointments.models import Appointment
                    appointment = Appointment.objects.get(appointment_id=queue_item.object_id)
                    
                    # Update patient reference to use current patient_id (in case it changed)
                    if 'participant' in queue_item.fhir_data:
                        for participant in queue_item.fhir_data['participant']:
                            if 'actor' in participant and 'reference' in participant['actor']:
                                if participant['actor']['reference'].startswith('Patient/'):
                                    participant['actor']['reference'] = f"Patient/{appointment.patient.patient_id}"
                                    participant['actor']['display'] = appointment.patient.full_name
                        queue_item.save()
                    
                except Appointment.DoesNotExist:
                    queue_item.mark_failed("Appointment no longer exists")
                    results['failed'] += 1
                    continue
                
                # Sync the appointment
                if sync_service.sync_resource(queue_item):
                    results['success'] += 1
                    logger.info(f"Successfully synced appointment {queue_item.resource_id}")
                else:
                    results['failed'] += 1
                    logger.error(f"Failed to sync appointment {queue_item.resource_id}: {queue_item.error_message}")
                    
            except Exception as e:
                results['failed'] += 1
                logger.error(f"Exception syncing appointment {queue_item.resource_id}: {e}")
                queue_item.mark_failed(str(e))
        
        logger.info(f"Appointment sync completed: {results['success']} success, {results['failed']} failed, {results['skipped']} skipped")
        return results
        
    except Exception as e:
        logger.error(f"Appointment sync task failed: {e}")
        return {'error': str(e)}


@shared_task
def process_appointment_sync_queue():
    """Combined task to queue and sync appointments"""
    try:
        # First queue any new appointments
        queue_result = queue_new_appointments()
        logger.info(f"Queue result: {queue_result}")
        
        # Then sync pending appointments
        sync_result = sync_pending_appointments()
        logger.info(f"Sync result: {sync_result}")
        
        return {
            'queued': queue_result.get('queued', 0),
            'synced': sync_result.get('success', 0),
            'failed': sync_result.get('failed', 0),
            'skipped': (queue_result.get('skipped', 0) + sync_result.get('skipped', 0))
        }
    except Exception as e:
        logger.error(f"Process appointment sync queue failed: {e}")
        return {'error': str(e)}


# Optional: Queue missing patients for appointments
@shared_task
def queue_appointment_patients():
    """Queue patients that have appointments but aren't synced yet"""
    try:
        from Appointments.models import Appointment
        from Patients.models import Patient
        
        # Get patient IDs from appointments
        appointment_patient_ids = set(Appointment.objects.values_list('patient_id', flat=True).distinct())
        
        # Get already synced patient IDs
        synced_patient_ids = set(SyncQueue.objects.filter(
            resource_type='Patient'
        ).values_list('object_id', flat=True))
        
        # Find patients that need to be synced
        unsynced_patient_ids = appointment_patient_ids - synced_patient_ids
        
        queued_count = 0
        
        for patient_id in unsynced_patient_ids:
            try:
                patient = Patient.objects.get(id=patient_id)
                
                # Use the patient's to_fhir_dict method
                fhir_data = patient.to_fhir_dict()
                
                # Create queue item
                queue_item, created = SyncQueue.objects.get_or_create(
                    resource_type='Patient',
                    object_id=patient.id,
                    defaults={
                        'resource_id': patient.patient_id,
                        'operation': 'create',
                        'fhir_data': fhir_data,
                        'status': 'pending',
                        'priority': 20  # Higher priority since needed for appointments
                    }
                )
                
                if created:
                    queued_count += 1
                    logger.info(f"Queued patient {patient.patient_id} (needed for appointments)")
                
            except Patient.DoesNotExist:
                logger.error(f"Patient {patient_id} not found")
            except Exception as e:
                logger.error(f"Failed to queue patient {patient_id}: {e}")
        
        logger.info(f"Queued {queued_count} patients needed for appointments")
        return {'queued': queued_count}
        
    except Exception as e:
        logger.error(f"Queue appointment patients task failed: {e}")
        return {'error': str(e)}
    """Update a specific appointment in FHIR when it's modified"""
    try:
        from Appointments.models import Appointment
        
        appointment = Appointment.objects.get(appointment_id=appointment_id)  # FIXED: use appointment_id
        
        # Check if patient is synced
        patient_sync = SyncQueue.objects.filter(
            resource_type='Patient',
            object_id=appointment.patient.id,
            status='success'
        ).first()
        
        if not patient_sync or not patient_sync.fhir_id:
            logger.error(f"Cannot update appointment {appointment_id} - patient not synced")
            return {'status': 'error', 'message': 'Patient not synced'}
        
        # Check if appointment already exists in sync queue
        existing_sync = SyncQueue.objects.filter(
            resource_type='Appointment',
            object_id=appointment_id
        ).first()
        
        # Build FHIR data (same logic as queue_new_appointments)
        status_mapping = {
            'Scheduled': 'booked',
            'Completed': 'fulfilled',
            'Cancelled': 'cancelled'
        }
        fhir_status = status_mapping.get(appointment.status, 'proposed')
        
        fhir_data = {
            "resourceType": "Appointment",
            "status": fhir_status,
            "participant": [{
                "actor": {
                    "reference": f"Patient/{patient_sync.fhir_id}",
                    "display": appointment.patient.full_name
                },
                "status": "accepted"
            }]
        }
        
        # Add practitioner if exists and is synced
        if appointment.practitioner:
            practitioner_sync = SyncQueue.objects.filter(
                resource_type='Practitioner',
                object_id=appointment.practitioner.id,
                status='success'
            ).first()
            
            if practitioner_sync and practitioner_sync.fhir_id:
                fhir_data["participant"].append({
                    "actor": {
                        "reference": f"Practitioner/{practitioner_sync.fhir_id}",
                        "display": appointment.practitioner.name
                    },
                    "status": "accepted"
                })
        
        # Add appointment timing
        if appointment.appointment_date:
            from datetime import timedelta
            start_time = appointment.appointment_date
            end_time = start_time + timedelta(minutes=30)
            
            fhir_data["start"] = start_time.isoformat()
            fhir_data["end"] = end_time.isoformat()
        
        # Add other fields
        if appointment.notes:
            fhir_data["comment"] = str(appointment.notes)
        
        fhir_data["serviceType"] = [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/service-type",
                "code": "124",
                "display": "General Practice"
            }]
        }]
        
        fhir_data["appointmentType"] = {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/v2-0276",
                "code": "ROUTINE",
                "display": "Routine appointment"
            }]
        }
        
        if existing_sync:
            # Update existing sync queue item
            existing_sync.fhir_data = fhir_data
            existing_sync.operation = 'update' if existing_sync.fhir_id else 'create'
            existing_sync.status = 'pending'
            existing_sync.error_message = None
            existing_sync.save()
            
            logger.info(f"Updated sync queue for appointment {appointment_id}")
        else:
            # Create new sync queue item
            SyncQueue.objects.create(
                resource_type='Appointment',
                resource_id=str(appointment_id),
                object_id=appointment_id,
                operation='create',
                fhir_data=fhir_data,
                status='pending',
                priority=30  # Higher priority for updates
            )
            
            logger.info(f"Created sync queue for appointment {appointment_id}")
        
        return {'status': 'queued', 'appointment_id': appointment_id}
            
    except Appointment.DoesNotExist:
        logger.error(f"Appointment {appointment_id} not found")
        return {'status': 'error', 'message': 'Appointment not found'}
    except Exception as e:
        logger.error(f"Update appointment sync failed for {appointment_id}: {e}")
        return {'status': 'error', 'message': str(e)}
    """Update a specific appointment in FHIR when it's modified"""
    try:
        from Appointments.models import Appointment
        
        appointment = Appointment.objects.get(id=appointment_id)  # Use id not appointment_id
        
        # Check if patient is synced
        patient_sync = SyncQueue.objects.filter(
            resource_type='Patient',
            object_id=appointment.patient.id,
            status='success'
        ).first()
        
        if not patient_sync or not patient_sync.fhir_id:
            logger.error(f"Cannot update appointment {appointment_id} - patient not synced")
            return {'status': 'error', 'message': 'Patient not synced'}
        
        # Check if appointment already exists in sync queue
        existing_sync = SyncQueue.objects.filter(
            resource_type='Appointment',
            object_id=appointment_id
        ).first()
        
        # Build FHIR data (same as in queue_new_appointments)
        status_mapping = {
            'Scheduled': 'booked',
            'Completed': 'fulfilled',
            'Cancelled': 'cancelled'
        }
        fhir_status = status_mapping.get(appointment.status, 'proposed')
        
        fhir_data = {
            "resourceType": "Appointment",
            "status": fhir_status,
            "participant": [{
                "actor": {
                    "reference": f"Patient/{patient_sync.fhir_id}",
                    "display": appointment.patient.full_name
                },
                "status": "accepted"
            }]
        }
        
        # Add practitioner if exists and is synced
        if appointment.practitioner:
            practitioner_sync = SyncQueue.objects.filter(
                resource_type='Practitioner',
                object_id=appointment.practitioner.id,
                status='success'
            ).first()
            
            if practitioner_sync and practitioner_sync.fhir_id:
                fhir_data["participant"].append({
                    "actor": {
                        "reference": f"Practitioner/{practitioner_sync.fhir_id}",
                        "display": appointment.practitioner.name
                    },
                    "status": "accepted"
                })
        
        # Add appointment timing
        if appointment.appointment_date:
            from datetime import timedelta
            start_time = appointment.appointment_date
            end_time = start_time + timedelta(minutes=30)
            
            fhir_data["start"] = start_time.isoformat()
            fhir_data["end"] = end_time.isoformat()
        
        # Add other fields
        if appointment.notes:
            fhir_data["comment"] = str(appointment.notes)
        
        fhir_data["serviceType"] = [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/service-type",
                "code": "124",
                "display": "General Practice"
            }]
        }]
        
        fhir_data["appointmentType"] = {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/v2-0276",
                "code": "ROUTINE",
                "display": "Routine appointment"
            }]
        }
        
        if existing_sync:
            # Update existing sync queue item
            existing_sync.fhir_data = fhir_data
            existing_sync.operation = 'update' if existing_sync.fhir_id else 'create'
            existing_sync.status = 'pending'
            existing_sync.error_message = None
            existing_sync.save()
            
            logger.info(f"Updated sync queue for appointment {appointment_id}")
        else:
            # Create new sync queue item
            SyncQueue.objects.create(
                resource_type='Appointment',
                resource_id=str(appointment_id),
                object_id=appointment_id,
                operation='create',
                fhir_data=fhir_data,
                status='pending',
                priority=30  # Higher priority for updates
            )
            
            logger.info(f"Created sync queue for appointment {appointment_id}")
        
        return {'status': 'queued', 'appointment_id': appointment_id}
            
    except Appointment.DoesNotExist:
        logger.error(f"Appointment {appointment_id} not found")
        return {'status': 'error', 'message': 'Appointment not found'}
    except Exception as e:
        logger.error(f"Update appointment sync failed for {appointment_id}: {e}")
        return {'status': 'error', 'message': str(e)}
    

# ============================================================================
# ALLERGY INTOLERANCE SYNC TASKS
# ============================================================================

@shared_task
def queue_new_allergy_intolerances():
    """Queue any allergy intolerances that aren't in the sync queue yet"""
    try:
        from MedicalRecords.models import AllergyIntolerance
        
        # Get allergy intolerances not in sync queue
        synced_allergy_ids = SyncQueue.objects.filter(
            resource_type='AllergyIntolerance'
        ).values_list('object_id', flat=True).distinct()
        
        unsynced_allergies = AllergyIntolerance.objects.exclude(
            id__in=synced_allergy_ids
        )[:100]  # Limit to 100 at a time
        
        queued_count = 0
        skipped_count = 0
        
        for allergy in unsynced_allergies:
            try:
                # Double-check for existing queue items
                existing_item = SyncQueue.objects.filter(
                    resource_type='AllergyIntolerance',
                    object_id=allergy.id
                ).first()
                
                if existing_item:
                    logger.info(f"Skipping allergy {allergy.id} - already in queue")
                    skipped_count += 1
                    continue
                
                # Use the model's to_fhir_dict method
                fhir_data = allergy.to_fhir_dict()
                
                # FIXED: Use patient_id directly (no dependency check)
                fhir_data["patient"] = {
                    "reference": f"Patient/{allergy.patient.patient_id}"
                }
                
                # Create queue item
                queue_item, created = SyncQueue.objects.get_or_create(
                    resource_type='AllergyIntolerance',
                    object_id=allergy.id,
                    defaults={
                        'resource_id': str(allergy.id),
                        'operation': 'create',
                        'fhir_data': fhir_data,
                        'status': 'pending',
                        'priority': 35  # Medium priority
                    }
                )
                
                if created:
                    queued_count += 1
                    logger.info(f"Queued allergy intolerance {allergy.id} for sync")
                else:
                    skipped_count += 1
                    logger.info(f"Allergy intolerance {allergy.id} already queued")
                
            except Exception as e:
                logger.error(f"Failed to queue allergy {allergy.id}: {e}")
        
        logger.info(f"Queued {queued_count} new allergy intolerances, skipped {skipped_count}")
        return {'queued': queued_count, 'skipped': skipped_count}
        
    except Exception as e:
        logger.error(f"Queue allergy intolerances task failed: {e}")
        return {'error': str(e)}


@shared_task
def sync_pending_allergy_intolerances():
    """Sync all pending allergy intolerances to FHIR server"""
    try:
        sync_service = FHIRSyncService()
        
        # Get pending allergy intolerance syncs
        pending_allergies = SyncQueue.objects.filter(
            resource_type='AllergyIntolerance',
            status='pending'
        ).order_by('priority', 'created_at')[:50]  # Process 50 at a time
        
        results = {'success': 0, 'failed': 0, 'skipped': 0}
        
        for queue_item in pending_allergies:
            try:
                # Check for duplicates before processing
                duplicate_processing = SyncQueue.objects.filter(
                    resource_type='AllergyIntolerance',
                    object_id=queue_item.object_id,
                    status='processing'
                ).exclude(id=queue_item.id).exists()
                
                if duplicate_processing:
                    logger.info(f"Skipping allergy {queue_item.object_id} - another item is already processing")
                    results['skipped'] += 1
                    continue
                
                # FIXED: Validate allergy still exists and update patient reference
                try:
                    from MedicalRecords.models import AllergyIntolerance
                    allergy = AllergyIntolerance.objects.get(id=queue_item.object_id)
                    
                    # Update patient reference to current patient_id (in case it changed)
                    if 'patient' in queue_item.fhir_data:
                        queue_item.fhir_data['patient']['reference'] = f"Patient/{allergy.patient.patient_id}"
                        queue_item.save()
                    
                except AllergyIntolerance.DoesNotExist:
                    queue_item.mark_failed("Allergy intolerance no longer exists")
                    results['failed'] += 1
                    continue
                
                # REMOVED: Patient sync validation - let FHIR server handle patient references
                # This allows us to use patient_id references like appointments
                
                # Sync the allergy intolerance
                if sync_service.sync_resource(queue_item):
                    results['success'] += 1
                    logger.info(f"Successfully synced allergy intolerance {queue_item.resource_id}")
                else:
                    results['failed'] += 1
                    logger.error(f"Failed to sync allergy intolerance {queue_item.resource_id}: {queue_item.error_message}")
                    
            except Exception as e:
                results['failed'] += 1
                logger.error(f"Exception syncing allergy intolerance {queue_item.resource_id}: {e}")
                queue_item.mark_failed(str(e))
        
        logger.info(f"Allergy intolerance sync completed: {results['success']} success, {results['failed']} failed, {results['skipped']} skipped")
        return results
        
    except Exception as e:
        logger.error(f"Allergy intolerance sync task failed: {e}")
        return {'error': str(e)}


@shared_task
def process_allergy_intolerance_sync_queue():
    """Combined task to queue and sync allergy intolerances"""
    try:
        # First queue any new allergy intolerances
        queue_result = queue_new_allergy_intolerances()
        logger.info(f"Queue result: {queue_result}")
        
        # Then sync pending allergy intolerances
        sync_result = sync_pending_allergy_intolerances()
        logger.info(f"Sync result: {sync_result}")
        
        return {
            'queued': queue_result.get('queued', 0),
            'synced': sync_result.get('success', 0),
            'failed': sync_result.get('failed', 0),
            'skipped': (queue_result.get('skipped', 0) + sync_result.get('skipped', 0))
        }
    except Exception as e:
        logger.error(f"Process allergy intolerance sync queue failed: {e}")
        return {'error': str(e)}

# ============================================================================
# ENCOUNTER SYNC TASKS (Foundation for other resources)
# ============================================================================

@shared_task
def queue_new_encounters():
    """Queue any encounters that aren't in the sync queue yet"""
    try:
        from MedicalRecords.models import Encounter
        
        # Get encounters not in sync queue
        synced_encounter_ids = SyncQueue.objects.filter(
            resource_type='Encounter'
        ).values_list('object_id', flat=True).distinct()
        
        unsynced_encounters = Encounter.objects.exclude(
            id__in=synced_encounter_ids
        )[:100]  # Limit to 100 at a time
        
        queued_count = 0
        skipped_count = 0
        
        for encounter in unsynced_encounters:
            try:
                # Double-check for existing queue items
                existing_item = SyncQueue.objects.filter(
                    resource_type='Encounter',
                    object_id=encounter.id
                ).first()
                
                if existing_item:
                    skipped_count += 1
                    continue
                
                # Check if patient is synced
                patient_sync = SyncQueue.objects.filter(
                    resource_type='Patient',
                    object_id=encounter.patient.id,
                    status='success'
                ).first()
                
                if not patient_sync or not patient_sync.fhir_id:
                    logger.warning(f"Skipping encounter {encounter.id} - patient {encounter.patient.id} not synced yet")
                    skipped_count += 1
                    continue
                
                # Use the model's to_fhir_dict method
                fhir_data = encounter.to_fhir_dict()
                
                # Update patient reference to use FHIR ID
                fhir_data["subject"] = {
                    "reference": f"Patient/{patient_sync.fhir_id}"
                }
                
                # Create queue item
                queue_item, created = SyncQueue.objects.get_or_create(
                    resource_type='Encounter',
                    object_id=encounter.id,
                    defaults={
                        'resource_id': str(encounter.id),
                        'operation': 'create',
                        'fhir_data': fhir_data,
                        'status': 'pending',
                        'priority': 25  # Higher priority (foundation for others)
                    }
                )
                
                if created:
                    queued_count += 1
                    logger.info(f"Queued encounter {encounter.id} for sync")
                else:
                    skipped_count += 1
                
            except Exception as e:
                logger.error(f"Failed to queue encounter {encounter.id}: {e}")
        
        logger.info(f"Queued {queued_count} new encounters, skipped {skipped_count}")
        return {'queued': queued_count, 'skipped': skipped_count}
        
    except Exception as e:
        logger.error(f"Queue encounters task failed: {e}")
        return {'error': str(e)}


@shared_task
def sync_pending_encounters():
    """Sync all pending encounters to FHIR server"""
    try:
        sync_service = FHIRSyncService()
        
        pending_encounters = SyncQueue.objects.filter(
            resource_type='Encounter',
            status='pending'
        ).order_by('priority', 'created_at')[:50]
        
        results = {'success': 0, 'failed': 0, 'skipped': 0}
        
        for queue_item in pending_encounters:
            try:
                # Check for duplicates
                duplicate_processing = SyncQueue.objects.filter(
                    resource_type='Encounter',
                    object_id=queue_item.object_id,
                    status='processing'
                ).exclude(id=queue_item.id).exists()
                
                if duplicate_processing:
                    results['skipped'] += 1
                    continue
                
                # Validate encounter and patient
                try:
                    from MedicalRecords.models import Encounter
                    encounter = Encounter.objects.get(id=queue_item.object_id)
                    
                    patient_sync = SyncQueue.objects.filter(
                        resource_type='Patient',
                        object_id=encounter.patient.id,
                        status='success'
                    ).first()
                    
                    if not patient_sync or not patient_sync.fhir_id:
                        queue_item.mark_failed("Patient not synced - cannot sync encounter")
                        results['failed'] += 1
                        continue
                    
                    # Update patient reference
                    queue_item.fhir_data['subject']['reference'] = f"Patient/{patient_sync.fhir_id}"
                    queue_item.save()
                    
                except Encounter.DoesNotExist:
                    queue_item.mark_failed("Encounter no longer exists")
                    results['failed'] += 1
                    continue
                
                # Sync the encounter
                if sync_service.sync_resource(queue_item):
                    results['success'] += 1
                    logger.info(f"Successfully synced encounter {queue_item.resource_id}")
                else:
                    results['failed'] += 1
                    logger.error(f"Failed to sync encounter {queue_item.resource_id}: {queue_item.error_message}")
                    
            except Exception as e:
                results['failed'] += 1
                logger.error(f"Exception syncing encounter {queue_item.resource_id}: {e}")
                queue_item.mark_failed(str(e))
        
        logger.info(f"Encounter sync completed: {results}")
        return results
        
    except Exception as e:
        logger.error(f"Encounter sync task failed: {e}")
        return {'error': str(e)}


@shared_task
def process_encounter_sync_queue():
    """Combined task to queue and sync encounters"""
    try:
        queue_result = queue_new_encounters()
        sync_result = sync_pending_encounters()
        
        return {
            'queued': queue_result.get('queued', 0),
            'synced': sync_result.get('success', 0),
            'failed': sync_result.get('failed', 0),
            'skipped': (queue_result.get('skipped', 0) + sync_result.get('skipped', 0))
        }
    except Exception as e:
        logger.error(f"Process encounter sync queue failed: {e}")
        return {'error': str(e)}
    

# ============================================================================
# ENCOUNTER SYNC TASKS
# Add these to Fsync/tasks.py
# ============================================================================

@shared_task
def queue_new_encounters():
    """Queue any encounters that aren't in the sync queue yet"""
    try:
        from MedicalRecords.models import Encounter
        
        # Get encounters not in sync queue
        synced_encounter_ids = SyncQueue.objects.filter(
            resource_type='Encounter'
        ).values_list('object_id', flat=True).distinct()
        
        unsynced_encounters = Encounter.objects.exclude(
            id__in=synced_encounter_ids
        )[:100]  # Limit to 100 at a time
        
        queued_count = 0
        skipped_count = 0
        
        for encounter in unsynced_encounters:
            try:
                # Double-check for existing queue items
                existing_item = SyncQueue.objects.filter(
                    resource_type='Encounter',
                    object_id=encounter.id
                ).first()
                
                if existing_item:
                    logger.info(f"Skipping encounter {encounter.id} - already in queue")
                    skipped_count += 1
                    continue
                
                # Use the model's to_fhir_dict method
                fhir_data = encounter.to_fhir_dict()
                
                # Update patient reference to use patient_id (like appointments/allergies)
                fhir_data["subject"] = {
                    "reference": f"Patient/{encounter.patient.patient_id}"
                }
                
                # Create queue item
                queue_item, created = SyncQueue.objects.get_or_create(
                    resource_type='Encounter',
                    object_id=encounter.id,
                    defaults={
                        'resource_id': str(encounter.id),
                        'operation': 'create',
                        'fhir_data': fhir_data,
                        'status': 'pending',
                        'priority': 25  # Higher priority (foundation for other resources)
                    }
                )
                
                if created:
                    queued_count += 1
                    logger.info(f"Queued encounter {encounter.id} for sync")
                else:
                    skipped_count += 1
                    logger.info(f"Encounter {encounter.id} already queued")
                
            except Exception as e:
                logger.error(f"Failed to queue encounter {encounter.id}: {e}")
        
        logger.info(f"Queued {queued_count} new encounters, skipped {skipped_count}")
        return {'queued': queued_count, 'skipped': skipped_count}
        
    except Exception as e:
        logger.error(f"Queue encounters task failed: {e}")
        return {'error': str(e)}


@shared_task
def sync_pending_encounters():
    """Sync all pending encounters to FHIR server"""
    try:
        sync_service = FHIRSyncService()
        
        # Get pending encounter syncs
        pending_encounters = SyncQueue.objects.filter(
            resource_type='Encounter',
            status='pending'
        ).order_by('priority', 'created_at')[:50]  # Process 50 at a time
        
        results = {'success': 0, 'failed': 0, 'skipped': 0}
        
        for queue_item in pending_encounters:
            try:
                # Check for duplicates before processing
                duplicate_processing = SyncQueue.objects.filter(
                    resource_type='Encounter',
                    object_id=queue_item.object_id,
                    status='processing'
                ).exclude(id=queue_item.id).exists()
                
                if duplicate_processing:
                    logger.info(f"Skipping encounter {queue_item.object_id} - another item is already processing")
                    results['skipped'] += 1
                    continue
                
                # Validate encounter still exists and update patient reference
                try:
                    from MedicalRecords.models import Encounter
                    encounter = Encounter.objects.get(id=queue_item.object_id)
                    
                    # Update patient reference to current patient_id (in case it changed)
                    if 'subject' in queue_item.fhir_data:
                        queue_item.fhir_data['subject']['reference'] = f"Patient/{encounter.patient.patient_id}"
                        queue_item.save()
                    
                except Encounter.DoesNotExist:
                    queue_item.mark_failed("Encounter no longer exists")
                    results['failed'] += 1
                    continue
                
                # Sync the encounter (no patient validation - let FHIR server handle it)
                if sync_service.sync_resource(queue_item):
                    results['success'] += 1
                    logger.info(f"Successfully synced encounter {queue_item.resource_id}")
                else:
                    results['failed'] += 1
                    logger.error(f"Failed to sync encounter {queue_item.resource_id}: {queue_item.error_message}")
                    
            except Exception as e:
                results['failed'] += 1
                logger.error(f"Exception syncing encounter {queue_item.resource_id}: {e}")
                queue_item.mark_failed(str(e))
        
        logger.info(f"Encounter sync completed: {results['success']} success, {results['failed']} failed, {results['skipped']} skipped")
        return results
        
    except Exception as e:
        logger.error(f"Encounter sync task failed: {e}")
        return {'error': str(e)}


@shared_task
def process_encounter_sync_queue():
    """Combined task to queue and sync encounters"""
    try:
        # First queue any new encounters
        queue_result = queue_new_encounters()
        logger.info(f"Queue result: {queue_result}")
        
        # Then sync pending encounters
        sync_result = sync_pending_encounters()
        logger.info(f"Sync result: {sync_result}")
        
        return {
            'queued': queue_result.get('queued', 0),
            'synced': sync_result.get('success', 0),
            'failed': sync_result.get('failed', 0),
            'skipped': (queue_result.get('skipped', 0) + sync_result.get('skipped', 0))
        }
    except Exception as e:
        logger.error(f"Process encounter sync queue failed: {e}")
        return {'error': str(e)}



# ============================================================================
# CONDITION SYNC TASKS
# ============================================================================

@shared_task
def queue_new_conditions():
    """Queue any conditions that aren't in the sync queue yet"""
    try:
        from MedicalRecords.models import Condition
        
        # Get conditions not in sync queue
        synced_condition_ids = SyncQueue.objects.filter(
            resource_type='Condition'
        ).values_list('object_id', flat=True).distinct()
        
        unsynced_conditions = Condition.objects.exclude(
            id__in=synced_condition_ids
        )[:100]  # Limit to 100 at a time
        
        queued_count = 0
        skipped_count = 0
        
        for condition in unsynced_conditions:
            try:
                # Double-check for existing queue items
                existing_item = SyncQueue.objects.filter(
                    resource_type='Condition',
                    object_id=condition.id
                ).first()
                
                if existing_item:
                    logger.info(f"Skipping condition {condition.id} - already in queue")
                    skipped_count += 1
                    continue
                
                # Use the model's to_fhir_dict method
                fhir_data = condition.to_fhir_dict()
                
                # Update patient reference to use patient_id
                fhir_data["subject"] = {
                    "reference": f"Patient/{condition.patient.patient_id}"
                }
                
                # Handle encounter reference - use FHIR ID if encounter is synced
                if condition.encounter:
                    encounter_sync = SyncQueue.objects.filter(
                        resource_type='Encounter',
                        object_id=condition.encounter.id,
                        status='success'
                    ).first()
                    
                    if encounter_sync and encounter_sync.fhir_id:
                        # Use synced encounter FHIR ID
                        fhir_data["encounter"] = {
                            "reference": f"Encounter/{encounter_sync.fhir_id}"
                        }
                        logger.info(f"Condition {condition.id}: Using synced encounter {encounter_sync.fhir_id}")
                    else:
                        # Remove encounter reference if not synced
                        fhir_data.pop("encounter", None)
                        logger.info(f"Condition {condition.id}: Removed unsynced encounter reference")
                
                # Validate and fix status if needed
                valid_statuses = ['active', 'recurrence', 'relapse', 'inactive', 'remission', 'resolved']
                if fhir_data.get('clinicalStatus', {}).get('coding', [{}])[0].get('code') not in valid_statuses:
                    # Map status to valid FHIR codes
                    status_mapping = {
                        'active': 'active',
                        'resolved': 'resolved',
                        'inactive': 'inactive',
                        'completed': 'resolved'
                    }
                    current_status = condition.status.lower()
                    mapped_status = status_mapping.get(current_status, 'active')
                    
                    fhir_data["clinicalStatus"] = {
                        "coding": [{
                            "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                            "code": mapped_status,
                            "display": mapped_status.title()
                        }]
                    }
                
                # Create queue item
                queue_item, created = SyncQueue.objects.get_or_create(
                    resource_type='Condition',
                    object_id=condition.id,
                    defaults={
                        'resource_id': str(condition.id),
                        'operation': 'create',
                        'fhir_data': fhir_data,
                        'status': 'pending',
                        'priority': 30  # Medium priority
                    }
                )
                
                if created:
                    queued_count += 1
                    logger.info(f"Queued condition {condition.id} for sync")
                else:
                    skipped_count += 1
                    logger.info(f"Condition {condition.id} already queued")
                
            except Exception as e:
                logger.error(f"Failed to queue condition {condition.id}: {e}")
        
        logger.info(f"Queued {queued_count} new conditions, skipped {skipped_count}")
        return {'queued': queued_count, 'skipped': skipped_count}
        
    except Exception as e:
        logger.error(f"Queue conditions task failed: {e}")
        return {'error': str(e)}


@shared_task
def sync_pending_conditions():
    """Sync all pending conditions to FHIR server"""
    try:
        sync_service = FHIRSyncService()
        
        # Get pending condition syncs
        pending_conditions = SyncQueue.objects.filter(
            resource_type='Condition',
            status='pending'
        ).order_by('priority', 'created_at')[:50]  # Process 50 at a time
        
        results = {'success': 0, 'failed': 0, 'skipped': 0}
        
        for queue_item in pending_conditions:
            try:
                # Check for duplicates before processing
                duplicate_processing = SyncQueue.objects.filter(
                    resource_type='Condition',
                    object_id=queue_item.object_id,
                    status='processing'
                ).exclude(id=queue_item.id).exists()
                
                if duplicate_processing:
                    logger.info(f"Skipping condition {queue_item.object_id} - another item is already processing")
                    results['skipped'] += 1
                    continue
                
                # Validate condition still exists and update references
                try:
                    from MedicalRecords.models import Condition
                    condition = Condition.objects.get(id=queue_item.object_id)
                    
                    # Update patient reference to current patient_id
                    if 'subject' in queue_item.fhir_data:
                        queue_item.fhir_data['subject']['reference'] = f"Patient/{condition.patient.patient_id}"
                    
                    # Update encounter reference if encounter is now synced
                    if condition.encounter:
                        encounter_sync = SyncQueue.objects.filter(
                            resource_type='Encounter',
                            object_id=condition.encounter.id,
                            status='success'
                        ).first()
                        
                        if encounter_sync and encounter_sync.fhir_id:
                            queue_item.fhir_data["encounter"] = {
                                "reference": f"Encounter/{encounter_sync.fhir_id}"
                            }
                        else:
                            # Remove encounter reference if not synced
                            queue_item.fhir_data.pop("encounter", None)
                    
                    queue_item.save()
                    
                except Condition.DoesNotExist:
                    queue_item.mark_failed("Condition no longer exists")
                    results['failed'] += 1
                    continue
                
                # Sync the condition (no dependency validation - let FHIR server handle it)
                if sync_service.sync_resource(queue_item):
                    results['success'] += 1
                    logger.info(f"Successfully synced condition {queue_item.resource_id}")
                else:
                    results['failed'] += 1
                    logger.error(f"Failed to sync condition {queue_item.resource_id}: {queue_item.error_message}")
                    
            except Exception as e:
                results['failed'] += 1
                logger.error(f"Exception syncing condition {queue_item.resource_id}: {e}")
                queue_item.mark_failed(str(e))
        
        logger.info(f"Condition sync completed: {results['success']} success, {results['failed']} failed, {results['skipped']} skipped")
        return results
        
    except Exception as e:
        logger.error(f"Condition sync task failed: {e}")
        return {'error': str(e)}


@shared_task
def process_condition_sync_queue():
    """Combined task to queue and sync conditions"""
    try:
        # First queue any new conditions
        queue_result = queue_new_conditions()
        logger.info(f"Queue result: {queue_result}")
        
        # Then sync pending conditions
        sync_result = sync_pending_conditions()
        logger.info(f"Sync result: {sync_result}")
        
        return {
            'queued': queue_result.get('queued', 0),
            'synced': sync_result.get('success', 0),
            'failed': sync_result.get('failed', 0),
            'skipped': (queue_result.get('skipped', 0) + sync_result.get('skipped', 0))
        }
    except Exception as e:
        logger.error(f"Process condition sync queue failed: {e}")
        return {'error': str(e)}



# ============================================================================
# MEDICATION STATEMENT SYNC TASKS
# ============================================================================

@shared_task
def queue_new_medication_statements():
    """Queue any medication statements that aren't in the sync queue yet"""
    try:
        from MedicalRecords.models import MedicationStatement
        
        # Get medication statements not in sync queue
        synced_med_ids = SyncQueue.objects.filter(
            resource_type='MedicationStatement'
        ).values_list('object_id', flat=True).distinct()
        
        unsynced_medications = MedicationStatement.objects.exclude(
            id__in=synced_med_ids
        )[:100]  # Limit to 100 at a time
        
        queued_count = 0
        skipped_count = 0
        
        for medication in unsynced_medications:
            try:
                # Double-check for existing queue items
                existing_item = SyncQueue.objects.filter(
                    resource_type='MedicationStatement',
                    object_id=medication.id
                ).first()
                
                if existing_item:
                    logger.info(f"Skipping medication {medication.id} - already in queue")
                    skipped_count += 1
                    continue
                
                # Use the model's to_fhir_dict method
                fhir_data = medication.to_fhir_dict()
                
                # Update patient reference to use patient_id
                fhir_data["subject"] = {
                    "reference": f"Patient/{medication.patient.patient_id}"
                }
                
                # Handle encounter reference - use FHIR ID if encounter is synced
                if medication.encounter:
                    encounter_sync = SyncQueue.objects.filter(
                        resource_type='Encounter',
                        object_id=medication.encounter.id,
                        status='success'
                    ).first()
                    
                    if encounter_sync and encounter_sync.fhir_id:
                        # Use synced encounter FHIR ID and correct field name
                        fhir_data["context"] = {
                            "reference": f"Encounter/{encounter_sync.fhir_id}"
                        }
                        logger.info(f"Medication {medication.id}: Using synced encounter {encounter_sync.fhir_id}")
                    else:
                        # Remove encounter reference if not synced
                        fhir_data.pop("context", None)
                        logger.info(f"Medication {medication.id}: Removed unsynced encounter reference")
                
                # Validate medication status
                valid_statuses = ['active', 'completed', 'entered-in-error', 'intended', 'stopped', 'on-hold', 'unknown', 'not-taken']
                current_status = fhir_data.get('status', 'active').lower()
                
                if current_status not in valid_statuses:
                    # Map common status values
                    status_mapping = {
                        'prescribed': 'active',
                        'dispensed': 'active', 
                        'administered': 'completed',
                        'discontinued': 'stopped',
                        'finished': 'completed',
                        'cancelled': 'stopped'
                    }
                    mapped_status = status_mapping.get(current_status, 'active')
                    fhir_data['status'] = mapped_status
                    logger.info(f"Medication {medication.id}: Mapped status {current_status} -> {mapped_status}")
                
                # Create queue item
                queue_item, created = SyncQueue.objects.get_or_create(
                    resource_type='MedicationStatement',
                    object_id=medication.id,
                    defaults={
                        'resource_id': str(medication.id),
                        'operation': 'create',
                        'fhir_data': fhir_data,
                        'status': 'pending',
                        'priority': 32  # Medium priority, after conditions
                    }
                )
                
                if created:
                    queued_count += 1
                    logger.info(f"Queued medication statement {medication.id} for sync")
                else:
                    skipped_count += 1
                    logger.info(f"Medication statement {medication.id} already queued")
                
            except Exception as e:
                logger.error(f"Failed to queue medication {medication.id}: {e}")
        
        logger.info(f"Queued {queued_count} new medication statements, skipped {skipped_count}")
        return {'queued': queued_count, 'skipped': skipped_count}
        
    except Exception as e:
        logger.error(f"Queue medication statements task failed: {e}")
        return {'error': str(e)}


@shared_task
def sync_pending_medication_statements():
    """Sync all pending medication statements to FHIR server"""
    try:
        sync_service = FHIRSyncService()
        
        # Get pending medication statement syncs
        pending_medications = SyncQueue.objects.filter(
            resource_type='MedicationStatement',
            status='pending'
        ).order_by('priority', 'created_at')[:50]  # Process 50 at a time
        
        results = {'success': 0, 'failed': 0, 'skipped': 0}
        
        for queue_item in pending_medications:
            try:
                # Check for duplicates before processing
                duplicate_processing = SyncQueue.objects.filter(
                    resource_type='MedicationStatement',
                    object_id=queue_item.object_id,
                    status='processing'
                ).exclude(id=queue_item.id).exists()
                
                if duplicate_processing:
                    logger.info(f"Skipping medication {queue_item.object_id} - another item is already processing")
                    results['skipped'] += 1
                    continue
                
                # Validate medication still exists and update references
                try:
                    from MedicalRecords.models import MedicationStatement
                    medication = MedicationStatement.objects.get(id=queue_item.object_id)
                    
                    # Update patient reference to current patient_id
                    if 'subject' in queue_item.fhir_data:
                        queue_item.fhir_data['subject']['reference'] = f"Patient/{medication.patient.patient_id}"
                    
                    # Update encounter reference if encounter is now synced
                    if medication.encounter:
                        encounter_sync = SyncQueue.objects.filter(
                            resource_type='Encounter',
                            object_id=medication.encounter.id,
                            status='success'
                        ).first()
                        
                        if encounter_sync and encounter_sync.fhir_id:
                            queue_item.fhir_data["context"] = {
                                "reference": f"Encounter/{encounter_sync.fhir_id}"
                            }
                        else:
                            # Remove encounter reference if not synced
                            queue_item.fhir_data.pop("context", None)
                    
                    queue_item.save()
                    
                except MedicationStatement.DoesNotExist:
                    queue_item.mark_failed("Medication statement no longer exists")
                    results['failed'] += 1
                    continue
                
                # Sync the medication statement
                if sync_service.sync_resource(queue_item):
                    results['success'] += 1
                    logger.info(f"Successfully synced medication statement {queue_item.resource_id}")
                else:
                    results['failed'] += 1
                    logger.error(f"Failed to sync medication statement {queue_item.resource_id}: {queue_item.error_message}")
                    
            except Exception as e:
                results['failed'] += 1
                logger.error(f"Exception syncing medication statement {queue_item.resource_id}: {e}")
                queue_item.mark_failed(str(e))
        
        logger.info(f"Medication statement sync completed: {results['success']} success, {results['failed']} failed, {results['skipped']} skipped")
        return results
        
    except Exception as e:
        logger.error(f"Medication statement sync task failed: {e}")
        return {'error': str(e)}


@shared_task
def process_medication_statement_sync_queue():
    """Combined task to queue and sync medication statements"""
    try:
        # First queue any new medication statements
        queue_result = queue_new_medication_statements()
        logger.info(f"Queue result: {queue_result}")
        
        # Then sync pending medication statements
        sync_result = sync_pending_medication_statements()
        logger.info(f"Sync result: {sync_result}")
        
        return {
            'queued': queue_result.get('queued', 0),
            'synced': sync_result.get('success', 0),
            'failed': sync_result.get('failed', 0),
            'skipped': (queue_result.get('skipped', 0) + sync_result.get('skipped', 0))
        }
    except Exception as e:
        logger.error(f"Process medication statement sync queue failed: {e}")
        return {'error': str(e)}


# ============================================================================
# PROCEDURE SYNC TASKS
# Add these to Fsync/tasks.py
# ============================================================================

@shared_task
def queue_new_procedures():
    """Queue any procedures that aren't in the sync queue yet"""
    try:
        from MedicalRecords.models import Procedure
        
        # Get procedures not in sync queue
        synced_procedure_ids = SyncQueue.objects.filter(
            resource_type='Procedure'
        ).values_list('object_id', flat=True).distinct()
        
        unsynced_procedures = Procedure.objects.exclude(
            id__in=synced_procedure_ids
        )[:100]  # Limit to 100 at a time
        
        queued_count = 0
        skipped_count = 0
        
        for procedure in unsynced_procedures:
            try:
                # Double-check for existing queue items
                existing_item = SyncQueue.objects.filter(
                    resource_type='Procedure',
                    object_id=procedure.id
                ).first()
                
                if existing_item:
                    logger.info(f"Skipping procedure {procedure.id} - already in queue")
                    skipped_count += 1
                    continue
                
                # Use the model's to_fhir_dict method
                fhir_data = procedure.to_fhir_dict()
                
                # Update patient reference to use patient_id
                fhir_data["subject"] = {
                    "reference": f"Patient/{procedure.patient.patient_id}"
                }
                
                # Handle encounter reference - use FHIR ID if encounter is synced
                if procedure.encounter:
                    encounter_sync = SyncQueue.objects.filter(
                        resource_type='Encounter',
                        object_id=procedure.encounter.id,
                        status='success'
                    ).first()
                    
                    if encounter_sync and encounter_sync.fhir_id:
                        # Use synced encounter FHIR ID
                        fhir_data["encounter"] = {
                            "reference": f"Encounter/{encounter_sync.fhir_id}"
                        }
                        logger.info(f"Procedure {procedure.id}: Using synced encounter {encounter_sync.fhir_id}")
                    else:
                        # Remove encounter reference if not synced
                        fhir_data.pop("encounter", None)
                        logger.info(f"Procedure {procedure.id}: Removed unsynced encounter reference")
                
                # Validate procedure status
                valid_statuses = ['preparation', 'in-progress', 'not-done', 'on-hold', 'stopped', 'completed', 'entered-in-error', 'unknown']
                current_status = fhir_data.get('status', 'completed').lower()
                
                if current_status not in valid_statuses:
                    # Map common status values
                    status_mapping = {
                        'done': 'completed',
                        'finished': 'completed',
                        'performed': 'completed',
                        'cancelled': 'not-done',
                        'scheduled': 'preparation',
                        'active': 'in-progress'
                    }
                    mapped_status = status_mapping.get(current_status, 'completed')
                    fhir_data['status'] = mapped_status
                    logger.info(f"Procedure {procedure.id}: Mapped status {current_status} -> {mapped_status}")
                
                # Create queue item
                queue_item, created = SyncQueue.objects.get_or_create(
                    resource_type='Procedure',
                    object_id=procedure.id,
                    defaults={
                        'resource_id': str(procedure.id),
                        'operation': 'create',
                        'fhir_data': fhir_data,
                        'status': 'pending',
                        'priority': 33  # Medium priority, after medications
                    }
                )
                
                if created:
                    queued_count += 1
                    logger.info(f"Queued procedure {procedure.id} for sync")
                else:
                    skipped_count += 1
                    logger.info(f"Procedure {procedure.id} already queued")
                
            except Exception as e:
                logger.error(f"Failed to queue procedure {procedure.id}: {e}")
        
        logger.info(f"Queued {queued_count} new procedures, skipped {skipped_count}")
        return {'queued': queued_count, 'skipped': skipped_count}
        
    except Exception as e:
        logger.error(f"Queue procedures task failed: {e}")
        return {'error': str(e)}


@shared_task
def sync_pending_procedures():
    """Sync all pending procedures to FHIR server"""
    try:
        sync_service = FHIRSyncService()
        
        # Get pending procedure syncs
        pending_procedures = SyncQueue.objects.filter(
            resource_type='Procedure',
            status='pending'
        ).order_by('priority', 'created_at')[:50]  # Process 50 at a time
        
        results = {'success': 0, 'failed': 0, 'skipped': 0}
        
        for queue_item in pending_procedures:
            try:
                # Check for duplicates before processing
                duplicate_processing = SyncQueue.objects.filter(
                    resource_type='Procedure',
                    object_id=queue_item.object_id,
                    status='processing'
                ).exclude(id=queue_item.id).exists()
                
                if duplicate_processing:
                    logger.info(f"Skipping procedure {queue_item.object_id} - another item is already processing")
                    results['skipped'] += 1
                    continue
                
                # Validate procedure still exists and update references
                try:
                    from MedicalRecords.models import Procedure
                    procedure = Procedure.objects.get(id=queue_item.object_id)
                    
                    # Update patient reference to current patient_id
                    if 'subject' in queue_item.fhir_data:
                        queue_item.fhir_data['subject']['reference'] = f"Patient/{procedure.patient.patient_id}"
                    
                    # Update encounter reference if encounter is now synced
                    if procedure.encounter:
                        encounter_sync = SyncQueue.objects.filter(
                            resource_type='Encounter',
                            object_id=procedure.encounter.id,
                            status='success'
                        ).first()
                        
                        if encounter_sync and encounter_sync.fhir_id:
                            queue_item.fhir_data["encounter"] = {
                                "reference": f"Encounter/{encounter_sync.fhir_id}"
                            }
                        else:
                            # Remove encounter reference if not synced
                            queue_item.fhir_data.pop("encounter", None)
                    
                    queue_item.save()
                    
                except Procedure.DoesNotExist:
                    queue_item.mark_failed("Procedure no longer exists")
                    results['failed'] += 1
                    continue
                
                # Sync the procedure
                if sync_service.sync_resource(queue_item):
                    results['success'] += 1
                    logger.info(f"Successfully synced procedure {queue_item.resource_id}")
                else:
                    results['failed'] += 1
                    logger.error(f"Failed to sync procedure {queue_item.resource_id}: {queue_item.error_message}")
                    
            except Exception as e:
                results['failed'] += 1
                logger.error(f"Exception syncing procedure {queue_item.resource_id}: {e}")
                queue_item.mark_failed(str(e))
        
        logger.info(f"Procedure sync completed: {results['success']} success, {results['failed']} failed, {results['skipped']} skipped")
        return results
        
    except Exception as e:
        logger.error(f"Procedure sync task failed: {e}")
        return {'error': str(e)}


@shared_task
def process_procedure_sync_queue():
    """Combined task to queue and sync procedures"""
    try:
        # First queue any new procedures
        queue_result = queue_new_procedures()
        logger.info(f"Queue result: {queue_result}")
        
        # Then sync pending procedures
        sync_result = sync_pending_procedures()
        logger.info(f"Sync result: {sync_result}")
        
        return {
            'queued': queue_result.get('queued', 0),
            'synced': sync_result.get('success', 0),
            'failed': sync_result.get('failed', 0),
            'skipped': (queue_result.get('skipped', 0) + sync_result.get('skipped', 0))
        }
    except Exception as e:
        logger.error(f"Process procedure sync queue failed: {e}")
        return {'error': str(e)}



# ============================================================================
# IMMUNIZATION SYNC TASKS
# Add these to Fsync/tasks.py
# ============================================================================

@shared_task
def queue_new_immunizations():
    """Queue any immunizations that aren't in the sync queue yet"""
    try:
        from MedicalRecords.models import Immunization
        
        # Get immunizations not in sync queue
        synced_immunization_ids = SyncQueue.objects.filter(
            resource_type='Immunization'
        ).values_list('object_id', flat=True).distinct()
        
        unsynced_immunizations = Immunization.objects.exclude(
            id__in=synced_immunization_ids
        )[:100]  # Limit to 100 at a time
        
        queued_count = 0
        skipped_count = 0
        
        for immunization in unsynced_immunizations:
            try:
                # Double-check for existing queue items
                existing_item = SyncQueue.objects.filter(
                    resource_type='Immunization',
                    object_id=immunization.id
                ).first()
                
                if existing_item:
                    logger.info(f"Skipping immunization {immunization.id} - already in queue")
                    skipped_count += 1
                    continue
                
                # Use the model's to_fhir_dict method
                fhir_data = immunization.to_fhir_dict()
                
                # Update patient reference to use patient_id
                fhir_data["patient"] = {
                    "reference": f"Patient/{immunization.patient.patient_id}"
                }
                
                # Validate immunization status
                valid_statuses = ['completed', 'entered-in-error', 'not-done']
                current_status = fhir_data.get('status', 'completed').lower()
                
                if current_status not in valid_statuses:
                    # Map common status values
                    status_mapping = {
                        'given': 'completed',
                        'administered': 'completed',
                        'done': 'completed',
                        'finished': 'completed',
                        'cancelled': 'not-done',
                        'skipped': 'not-done',
                        'refused': 'not-done'
                    }
                    mapped_status = status_mapping.get(current_status, 'completed')
                    fhir_data['status'] = mapped_status
                    logger.info(f"Immunization {immunization.id}: Mapped status {current_status} -> {mapped_status}")
                
                # Create queue item
                queue_item, created = SyncQueue.objects.get_or_create(
                    resource_type='Immunization',
                    object_id=immunization.id,
                    defaults={
                        'resource_id': str(immunization.id),
                        'operation': 'create',
                        'fhir_data': fhir_data,
                        'status': 'pending',
                        'priority': 36  # Medium-low priority
                    }
                )
                
                if created:
                    queued_count += 1
                    logger.info(f"Queued immunization {immunization.id} for sync")
                else:
                    skipped_count += 1
                    logger.info(f"Immunization {immunization.id} already queued")
                
            except Exception as e:
                logger.error(f"Failed to queue immunization {immunization.id}: {e}")
        
        logger.info(f"Queued {queued_count} new immunizations, skipped {skipped_count}")
        return {'queued': queued_count, 'skipped': skipped_count}
        
    except Exception as e:
        logger.error(f"Queue immunizations task failed: {e}")
        return {'error': str(e)}


@shared_task
def sync_pending_immunizations():
    """Sync all pending immunizations to FHIR server"""
    try:
        sync_service = FHIRSyncService()
        
        # Get pending immunization syncs
        pending_immunizations = SyncQueue.objects.filter(
            resource_type='Immunization',
            status='pending'
        ).order_by('priority', 'created_at')[:50]  # Process 50 at a time
        
        results = {'success': 0, 'failed': 0, 'skipped': 0}
        
        for queue_item in pending_immunizations:
            try:
                # Check for duplicates before processing
                duplicate_processing = SyncQueue.objects.filter(
                    resource_type='Immunization',
                    object_id=queue_item.object_id,
                    status='processing'
                ).exclude(id=queue_item.id).exists()
                
                if duplicate_processing:
                    logger.info(f"Skipping immunization {queue_item.object_id} - another item is already processing")
                    results['skipped'] += 1
                    continue
                
                # Validate immunization still exists and update patient reference
                try:
                    from MedicalRecords.models import Immunization
                    immunization = Immunization.objects.get(id=queue_item.object_id)
                    
                    # Update patient reference to current patient_id
                    if 'patient' in queue_item.fhir_data:
                        queue_item.fhir_data['patient']['reference'] = f"Patient/{immunization.patient.patient_id}"
                        queue_item.save()
                    
                except Immunization.DoesNotExist:
                    queue_item.mark_failed("Immunization no longer exists")
                    results['failed'] += 1
                    continue
                
                # Sync the immunization (no dependency validation - patient_id approach)
                if sync_service.sync_resource(queue_item):
                    results['success'] += 1
                    logger.info(f"Successfully synced immunization {queue_item.resource_id}")
                else:
                    results['failed'] += 1
                    logger.error(f"Failed to sync immunization {queue_item.resource_id}: {queue_item.error_message}")
                    
            except Exception as e:
                results['failed'] += 1
                logger.error(f"Exception syncing immunization {queue_item.resource_id}: {e}")
                queue_item.mark_failed(str(e))
        
        logger.info(f"Immunization sync completed: {results['success']} success, {results['failed']} failed, {results['skipped']} skipped")
        return results
        
    except Exception as e:
        logger.error(f"Immunization sync task failed: {e}")
        return {'error': str(e)}


@shared_task
def process_immunization_sync_queue():
    """Combined task to queue and sync immunizations"""
    try:
        # First queue any new immunizations
        queue_result = queue_new_immunizations()
        logger.info(f"Queue result: {queue_result}")
        
        # Then sync pending immunizations
        sync_result = sync_pending_immunizations()
        logger.info(f"Sync result: {sync_result}")
        
        return {
            'queued': queue_result.get('queued', 0),
            'synced': sync_result.get('success', 0),
            'failed': sync_result.get('failed', 0),
            'skipped': (queue_result.get('skipped', 0) + sync_result.get('skipped', 0))
        }
    except Exception as e:
        logger.error(f"Process immunization sync queue failed: {e}")
        return {'error': str(e)}



# ============================================================================
# PRACTITIONER SYNC TASKS
# Add these to Fsync/tasks.py
# ============================================================================

@shared_task
def queue_new_practitioners():
    """Queue any practitioners that aren't in the sync queue yet"""
    try:
        from Practitioner.models import Practitioner
        
        # Get practitioners not in sync queue
        synced_practitioner_ids = SyncQueue.objects.filter(
            resource_type='Practitioner'
        ).values_list('object_id', flat=True).distinct()
        
        unsynced_practitioners = Practitioner.objects.exclude(
            id__in=synced_practitioner_ids
        )[:100]  # Limit to 100 at a time
        
        queued_count = 0
        skipped_count = 0
        
        for practitioner in unsynced_practitioners:
            try:
                # Double-check for existing queue items
                existing_item = SyncQueue.objects.filter(
                    resource_type='Practitioner',
                    object_id=practitioner.id
                ).first()
                
                if existing_item:
                    logger.info(f"Skipping practitioner {practitioner.id} - already in queue")
                    skipped_count += 1
                    continue
                
                # Build FHIR data manually (no to_fhir_dict method)
                fhir_data = {
                    "resourceType": "Practitioner",
                    "active": True,
                    "identifier": [{
                        "use": "usual",
                        "system": "http://example.org/practitioner-id",
                        "value": practitioner.practitioner_id
                    }]
                }
                
                # Add name
                if practitioner.name:
                    # Parse name into family/given components
                    name_parts = practitioner.name.strip().split()
                    if len(name_parts) >= 2:
                        fhir_data["name"] = [{
                            "use": "official",
                            "family": name_parts[-1],  # Last part is family name
                            "given": name_parts[:-1],  # Everything else is given names
                            "text": practitioner.name
                        }]
                    else:
                        fhir_data["name"] = [{
                            "use": "official",
                            "text": practitioner.name
                        }]
                
                # Add telecom (contact info)
                telecom = []
                if practitioner.phone:
                    telecom.append({
                        "system": "phone",
                        "value": practitioner.phone,
                        "use": "work"
                    })
                if practitioner.email:
                    telecom.append({
                        "system": "email",
                        "value": practitioner.email,
                        "use": "work"
                    })
                if telecom:
                    fhir_data["telecom"] = telecom
                
                # Add qualification/role
                if practitioner.role:
                    # Map role to FHIR practitioner role codes
                    role_mapping = {
                        "doctor": "doctor",
                        "nurse": "nurse", 
                        "technician": "technician",
                        "admin": "admin"
                    }
                    fhir_role = role_mapping.get(practitioner.role.lower(), practitioner.role.lower())
                    
                    fhir_data["qualification"] = [{
                        "code": {
                            "coding": [{
                                "system": "http://terminology.hl7.org/CodeSystem/practitioner-role",
                                "code": fhir_role,
                                "display": practitioner.role.title()
                            }],
                            "text": practitioner.role
                        }
                    }]
                
                # Add hospital affiliation as extension
                if practitioner.hospital_affiliation:
                    fhir_data["extension"] = [{
                        "url": "http://example.org/fhir/StructureDefinition/hospital-affiliation",
                        "valueString": practitioner.hospital_affiliation
                    }]
                
                # Create queue item
                queue_item, created = SyncQueue.objects.get_or_create(
                    resource_type='Practitioner',
                    object_id=practitioner.id,
                    defaults={
                        'resource_id': practitioner.practitioner_id,
                        'operation': 'create',
                        'fhir_data': fhir_data,
                        'status': 'pending',
                        'priority': 20  # High priority (needed for appointments)
                    }
                )
                
                if created:
                    queued_count += 1
                    logger.info(f"Queued practitioner {practitioner.practitioner_id} for sync")
                else:
                    skipped_count += 1
                    logger.info(f"Practitioner {practitioner.practitioner_id} already queued")
                
            except Exception as e:
                logger.error(f"Failed to queue practitioner {practitioner.id}: {e}")
        
        logger.info(f"Queued {queued_count} new practitioners, skipped {skipped_count}")
        return {'queued': queued_count, 'skipped': skipped_count}
        
    except Exception as e:
        logger.error(f"Queue practitioners task failed: {e}")
        return {'error': str(e)}


@shared_task
def sync_pending_practitioners():
    """Sync all pending practitioners to FHIR server"""
    try:
        sync_service = FHIRSyncService()
        
        # Get pending practitioner syncs
        pending_practitioners = SyncQueue.objects.filter(
            resource_type='Practitioner',
            status='pending'
        ).order_by('priority', 'created_at')[:50]  # Process 50 at a time
        
        results = {'success': 0, 'failed': 0, 'skipped': 0}
        
        for queue_item in pending_practitioners:
            try:
                # Check for duplicates before processing
                duplicate_processing = SyncQueue.objects.filter(
                    resource_type='Practitioner',
                    object_id=queue_item.object_id,
                    status='processing'
                ).exclude(id=queue_item.id).exists()
                
                if duplicate_processing:
                    logger.info(f"Skipping practitioner {queue_item.object_id} - another item is already processing")
                    results['skipped'] += 1
                    continue
                
                # Validate practitioner still exists
                try:
                    from Practitioner.models import Practitioner
                    practitioner = Practitioner.objects.get(id=queue_item.object_id)
                    
                    # Update practitioner data in case it changed
                    if 'identifier' in queue_item.fhir_data:
                        for identifier in queue_item.fhir_data['identifier']:
                            if identifier.get('use') == 'usual':
                                identifier['value'] = practitioner.practitioner_id
                    
                    # Update name if changed
                    if practitioner.name and 'name' in queue_item.fhir_data:
                        queue_item.fhir_data['name'][0]['text'] = practitioner.name
                    
                    queue_item.save()
                    
                except Practitioner.DoesNotExist:
                    queue_item.mark_failed("Practitioner no longer exists")
                    results['failed'] += 1
                    continue
                
                # Sync the practitioner (no dependencies)
                if sync_service.sync_resource(queue_item):
                    results['success'] += 1
                    logger.info(f"Successfully synced practitioner {queue_item.resource_id}")
                else:
                    results['failed'] += 1
                    logger.error(f"Failed to sync practitioner {queue_item.resource_id}: {queue_item.error_message}")
                    
            except Exception as e:
                results['failed'] += 1
                logger.error(f"Exception syncing practitioner {queue_item.resource_id}: {e}")
                queue_item.mark_failed(str(e))
        
        logger.info(f"Practitioner sync completed: {results['success']} success, {results['failed']} failed, {results['skipped']} skipped")
        return results
        
    except Exception as e:
        logger.error(f"Practitioner sync task failed: {e}")
        return {'error': str(e)}


@shared_task
def process_practitioner_sync_queue():
    """Combined task to queue and sync practitioners"""
    try:
        # First queue any new practitioners
        queue_result = queue_new_practitioners()
        logger.info(f"Queue result: {queue_result}")
        
        # Then sync pending practitioners
        sync_result = sync_pending_practitioners()
        logger.info(f"Sync result: {sync_result}")
        
        return {
            'queued': queue_result.get('queued', 0),
            'synced': sync_result.get('success', 0),
            'failed': sync_result.get('failed', 0),
            'skipped': (queue_result.get('skipped', 0) + sync_result.get('skipped', 0))
        }
    except Exception as e:
        logger.error(f"Process practitioner sync queue failed: {e}")
        return {'error': str(e)}



# ============================================================================
# CELERY SCHEDULE UPDATE
# ============================================================================

# Add to your celery.py beat_schedule:

# Practitioners (Independent resource, high priority for appointments)
# 'sync-practitioners': {
#     'task': 'Fsync.tasks.process_practitioner_sync_queue',
#     'schedule': crontab(minute='8,13,18,23,28,33,38,43,48,53,58,3'),  # Every 5 min, +8 offset
# },
# 'queue-new-practitioners': {
#     'task': 'Fsync.tasks.queue_new_practitioners',
#     'schedule': crontab(minute=40),  # Every hour at minute 40
# },
# 'sync-pending-practitioners': {
#     'task': 'Fsync.tasks.sync_pending_practitioners',
#     'schedule': crontab(minute='8,18,28,38,48,58'),  # Every 10 minutes offset by 8
# },