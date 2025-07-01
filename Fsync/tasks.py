# tasks.py - Complete Celery Tasks with Encryption Support
# ============================================================================
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
from requests.exceptions import ConnectionError, RequestException
import traceback

logger = logging.getLogger(__name__)

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_resource_id(record):
    """
    Extract the appropriate resource identifier from a database record.
    
    Different HMS models may use different ID fields:
    - Patient records use 'patient_id'
    - Practitioner records use 'practitioner_id'
    - Other records fall back to primary key 'id'
    
    Args:
        record: Django model instance
        
    Returns:
        str: The resource identifier as a string
    """
    # For Patient model, use patient_id (business identifier)
    if hasattr(record, 'patient_id') and record.patient_id:
        return str(record.patient_id)
    
    # For other models, check for specific ID fields
    if hasattr(record, 'practitioner_id') and record.practitioner_id:
        return str(record.practitioner_id)
    
    # Fall back to primary key for other record types
    return str(record.id)

def clean_encrypted_value(value):
    """
    Clean encrypted field values to handle decryption artifacts.
    
    When fields are encrypted, decryption may return None, empty strings,
    or strings with only whitespace. This function normalizes these cases.
    
    Args:
        value: The potentially encrypted/decrypted value
        
    Returns:
        str or None: Cleaned value or None if empty/invalid
    """
    if value is None:
        return None
    if isinstance(value, str):
        # Strip whitespace and return None if empty
        return value.strip() if value.strip() else None
    return value

def validate_fhir_data(fhir_data, resource_type):
    """
    Comprehensive validation of FHIR data structure before transmission.
    
    This function ensures that:
    1. FHIR data structure is valid
    2. Required fields are present
    3. Encrypted fields are properly cleaned
    4. Arrays don't contain empty/null entries
    5. Patient-specific validation rules are applied
    
    Args:
        fhir_data (dict): The FHIR resource data
        resource_type (str): Expected FHIR resource type (e.g., 'Patient')
        
    Returns:
        tuple: (is_valid: bool, message: str)
    """
    # Basic structure validation
    if not fhir_data:
        return False, "Empty FHIR data"
    
    if not isinstance(fhir_data, dict):
        return False, "FHIR data must be a dictionary"
    
    # Check required FHIR fields
    if fhir_data.get('resourceType') != resource_type:
        return False, f"Resource type mismatch: expected {resource_type}, got {fhir_data.get('resourceType')}"
    
    if not fhir_data.get('id'):
        return False, "Missing required 'id' field"
    
    # Patient-specific validation and cleaning
    if resource_type == 'Patient':
        # === TELECOM VALIDATION (phone, email, etc.) ===
        telecom = fhir_data.get('telecom', [])
        if telecom:
            valid_telecom = []
            for contact in telecom:
                if contact.get('value'):
                    # Clean encrypted contact values
                    cleaned_value = clean_encrypted_value(contact.get('value'))
                    if cleaned_value:
                        contact['value'] = cleaned_value
                        valid_telecom.append(contact)
            
            # Update or remove telecom array based on valid entries
            if valid_telecom:
                fhir_data['telecom'] = valid_telecom
            else:
                fhir_data.pop('telecom', None)
        
        # === ADDRESS VALIDATION ===
        addresses = fhir_data.get('address', [])
        if addresses:
            valid_addresses = []
            for address in addresses:
                # Clean address lines (street addresses)
                if 'line' in address:
                    cleaned_lines = []
                    for line in address['line']:
                        cleaned_line = clean_encrypted_value(line)
                        if cleaned_line:
                            cleaned_lines.append(cleaned_line)
                    
                    if cleaned_lines:
                        address['line'] = cleaned_lines
                    else:
                        address.pop('line', None)
                
                # Clean other address components
                for field in ['city', 'state', 'postalCode', 'country']:
                    if field in address:
                        cleaned_value = clean_encrypted_value(address[field])
                        if cleaned_value:
                            address[field] = cleaned_value
                        else:
                            address.pop(field, None)
                
                # Only keep address if it has meaningful content
                if any(address.get(field) for field in ['line', 'city', 'state', 'postalCode']):
                    valid_addresses.append(address)
            
            # Update or remove address array
            if valid_addresses:
                fhir_data['address'] = valid_addresses
            else:
                fhir_data.pop('address', None)
        
        # === NAME VALIDATION ===
        names = fhir_data.get('name', [])
        if names:
            valid_names = []
            for name in names:
                # Clean given names (first, middle names)
                if 'given' in name:
                    cleaned_given = []
                    for given_name in name['given']:
                        cleaned_name = clean_encrypted_value(given_name)
                        if cleaned_name:
                            cleaned_given.append(cleaned_name)
                    
                    if cleaned_given:
                        name['given'] = cleaned_given
                    else:
                        name.pop('given', None)
                
                # Clean family name (last name)
                if 'family' in name:
                    cleaned_family = clean_encrypted_value(name['family'])
                    if cleaned_family:
                        name['family'] = cleaned_family
                    else:
                        name.pop('family', None)
                
                # Clean name prefixes and suffixes (Dr., Jr., etc.)
                for field in ['prefix', 'suffix']:
                    if field in name:
                        cleaned_list = []
                        for item in name[field]:
                            cleaned_item = clean_encrypted_value(item)
                            if cleaned_item:
                                cleaned_list.append(cleaned_item)
                        
                        if cleaned_list:
                            name[field] = cleaned_list
                        else:
                            name.pop(field, None)
                
                # Only keep name if it has meaningful content
                if name.get('given') or name.get('family'):
                    valid_names.append(name)
            
            if valid_names:
                fhir_data['name'] = valid_names
            else:
                return False, "No valid names found"
        
        # === IDENTIFIER VALIDATION (MRN, SSN, etc.) ===
        identifiers = fhir_data.get('identifier', [])
        if identifiers:
            valid_identifiers = []
            for identifier in identifiers:
                if identifier.get('value'):
                    cleaned_value = clean_encrypted_value(identifier.get('value'))
                    if cleaned_value:
                        identifier['value'] = cleaned_value
                        valid_identifiers.append(identifier)
            
            if valid_identifiers:
                fhir_data['identifier'] = valid_identifiers
            else:
                return False, "No valid identifiers found"
    
    return True, "Valid"

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
                mapper_func = FHIR_MAPPERS.get(rule.resource_type)
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
        cutoff_date = timezone.now() - timedelta(days=30)
        
        # Clean up successful sync logs older than 30 days
        # Keep INFO and DEBUG level logs for historical reference
        deleted_logs = SyncLog.objects.filter(
            timestamp__lt=cutoff_date,
            level__in=['INFO', 'DEBUG']  # Don't delete ERROR or WARNING logs
        ).delete()
        
        # Clean up successful queue items older than 7 days
        # Successful items don't need long-term retention
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
        # Pre-flight check: ensure FHIR server is reachable
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
            return {'status': 'failed', 'message': 'FHIR server is not available'}
            
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