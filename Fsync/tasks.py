# tasks.py - Complete Celery Tasks with Encryption Support
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
from requests.exceptions import ConnectionError, RequestException
import traceback

logger = logging.getLogger(__name__)

def get_resource_id(record):
    """Get appropriate resource ID based on record type"""
    # For Patient model, use patient_id
    if hasattr(record, 'patient_id') and record.patient_id:
        return str(record.patient_id)
    
    # For other models, check for specific ID fields
    if hasattr(record, 'practitioner_id') and record.practitioner_id:
        return str(record.practitioner_id)
    
    # Fall back to primary key
    return str(record.id)

def clean_encrypted_value(value):
    """Clean encrypted field values - handle None and empty strings"""
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() if value.strip() else None
    return value

def validate_fhir_data(fhir_data, resource_type):
    """Validate FHIR data before sending to prevent common errors"""
    if not fhir_data:
        return False, "Empty FHIR data"
    
    if not isinstance(fhir_data, dict):
        return False, "FHIR data must be a dictionary"
    
    # Check required fields
    if fhir_data.get('resourceType') != resource_type:
        return False, f"Resource type mismatch: expected {resource_type}, got {fhir_data.get('resourceType')}"
    
    if not fhir_data.get('id'):
        return False, "Missing required 'id' field"
    
    # Validate Patient-specific fields
    if resource_type == 'Patient':
        # Clean telecom array - remove entries with None/empty values
        telecom = fhir_data.get('telecom', [])
        if telecom:
            valid_telecom = []
            for contact in telecom:
                if contact.get('value'):
                    cleaned_value = clean_encrypted_value(contact.get('value'))
                    if cleaned_value:
                        contact['value'] = cleaned_value
                        valid_telecom.append(contact)
            
            if valid_telecom:
                fhir_data['telecom'] = valid_telecom
            else:
                fhir_data.pop('telecom', None)
        
        # Clean address array - remove entries with None/empty values
        addresses = fhir_data.get('address', [])
        if addresses:
            valid_addresses = []
            for address in addresses:
                # Clean address lines
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
                
                # Clean other address fields
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
            
            if valid_addresses:
                fhir_data['address'] = valid_addresses
            else:
                fhir_data.pop('address', None)
        
        # Clean name array - handle encrypted name fields
        names = fhir_data.get('name', [])
        if names:
            valid_names = []
            for name in names:
                # Clean name components
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
                
                if 'family' in name:
                    cleaned_family = clean_encrypted_value(name['family'])
                    if cleaned_family:
                        name['family'] = cleaned_family
                    else:
                        name.pop('family', None)
                
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
        
        # Clean identifier array
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

@shared_task(bind=True, max_retries=3)
def process_sync_queue_task(self, limit=50):
    """Process sync queue items with better error handling"""
    try:
        # Check FHIR server availability first
        sync_service = FHIRSyncService()
        if not sync_service.check_server_availability():
            logger.warning("FHIR server not available, skipping sync")
            return {'error': 'FHIR server not available', 'total': 0, 'success': 0, 'failed': 0}
        
        results = SyncQueueManager.process_queue(limit=limit)
        logger.info(f"Processed {results['total']} items: {results['success']} success, {results['failed']} failed")
        return results
        
    except ConnectionError as e:
        logger.error(f"Connection error during sync: {e}")
        # Don't retry immediately for connection errors
        raise self.retry(countdown=300, exc=e)  # Wait 5 minutes
    except Exception as e:
        logger.error(f"Sync queue processing failed: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise self.retry(countdown=60, exc=e)

@shared_task(bind=True, max_retries=3)
def full_sync_task(self, resource_types=None):
    """Sync all HMS data to FHIR with improved error handling"""
    try:
        # Check FHIR server availability first
        sync_service = FHIRSyncService()
        if not sync_service.check_server_availability():
            logger.warning("FHIR server not available, cannot perform full sync")
            return {'error': 'FHIR server not available'}
        
        total_queued = 0
        total_errors = 0
        
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
                
                # Queue each record with validation
                for record in queryset:
                    try:
                        # Generate FHIR data
                        if hasattr(record, 'to_fhir_dict'):
                            # Use model's built-in method if available
                            fhir_data = record.to_fhir_dict()
                        else:
                            # Use mapper function
                            fhir_data = mapper_func(record)
                        
                        # Validate FHIR data before queuing
                        is_valid, validation_msg = validate_fhir_data(fhir_data, rule.resource_type)
                        if not is_valid:
                            logger.warning(f"Invalid FHIR data for {rule.resource_type} {get_resource_id(record)}: {validation_msg}")
                            total_errors += 1
                            continue
                        
                        # Get appropriate resource ID
                        resource_id = get_resource_id(record)
                        
                        SyncQueueManager.queue_resource(
                            resource_type=rule.resource_type,
                            resource_id=resource_id,
                            fhir_data=fhir_data,
                            source_object=record,
                            sync_rule=rule
                        )
                        total_queued += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to queue {rule.resource_type} {get_resource_id(record)}: {e}")
                        logger.error(f"Traceback: {traceback.format_exc()}")
                        total_errors += 1
                        continue
                        
            except Exception as e:
                logger.error(f"Error processing sync rule {rule}: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                total_errors += 1
                continue
        
        logger.info(f"Queued {total_queued} items for sync, {total_errors} errors")
        
        # Process the queue
        results = SyncQueueManager.process_queue()
        
        return {
            'queued': total_queued,
            'queue_errors': total_errors,
            'processed': results['total'],
            'success': results['success'],
            'failed': results['failed']
        }
        
    except ConnectionError as e:
        logger.error(f"Connection error during full sync: {e}")
        raise self.retry(countdown=300, exc=e)  # Wait 5 minutes
    except Exception as e:
        logger.error(f"Full sync failed: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise self.retry(countdown=300, exc=e)

@shared_task
def retry_failed_syncs_task():
    """Retry failed sync operations"""
    try:
        # Check FHIR server availability first
        sync_service = FHIRSyncService()
        if not sync_service.check_server_availability():
            logger.warning("FHIR server not available, skipping retry")
            return {'error': 'FHIR server not available'}
        
        results = SyncQueueManager.retry_failed_items()
        logger.info(f"Retried {results['retried']} failed items")
        return results
    except Exception as e:
        logger.error(f"Retry failed syncs error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
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
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {'error': str(e)}

@shared_task
def sync_single_resource_task(resource_type, resource_id, operation='create'):
    """Sync a single resource"""
    try:
        # Check FHIR server availability first
        sync_service = FHIRSyncService()
        if not sync_service.check_server_availability():
            return {'error': 'FHIR server not available'}
        
        queue_item = SyncQueue.objects.get(
            resource_type=resource_type,
            resource_id=resource_id,
            status__in=['pending', 'failed']
        )
        
        # Validate FHIR data before syncing
        if queue_item.fhir_data:
            is_valid, validation_msg = validate_fhir_data(queue_item.fhir_data, resource_type)
            if not is_valid:
                queue_item.status = 'failed'
                queue_item.error_message = f"Validation failed: {validation_msg}"
                queue_item.save()
                return {'error': f'Validation failed: {validation_msg}'}
        
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

# UPDATED: Specific task for Patient sync with encryption support
@shared_task
def sync_patient_task(patient_id, operation='update'):
    """Sync a specific patient with encryption support"""
    try:
        # Check FHIR server availability first
        sync_service = FHIRSyncService()
        if not sync_service.check_server_availability():
            return {'error': 'FHIR server not available'}
        
        # Get Patient model dynamically
        Patient = apps.get_model('Patients', 'Patient')  # Adjust app name as needed
        patient = Patient.objects.get(patient_id=patient_id)
        
        # Get FHIR data using patient's built-in method
        fhir_data = patient.to_fhir_dict()
        
        # Validate FHIR data
        is_valid, validation_msg = validate_fhir_data(fhir_data, 'Patient')
        if not is_valid:
            logger.error(f"Patient {patient_id} validation failed: {validation_msg}")
            return {'error': f'Validation failed: {validation_msg}'}
        
        # Queue for sync
        queue_item = SyncQueueManager.queue_resource(
            resource_type='Patient',
            resource_id=patient_id,
            fhir_data=fhir_data,
            operation=operation,
            source_object=patient,
            priority=60  # High priority for individual syncs
        )
        
        # Process immediately
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

@shared_task
def test_fhir_connection_task():
    """Test FHIR server connection"""
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
    """Validate patient FHIR data without syncing"""
    try:
        Patient = apps.get_model('Patients', 'Patient')
        
        if patient_id:
            patients = Patient.objects.filter(patient_id=patient_id)
        else:
            patients = Patient.objects.all()[:limit]
        
        results = []
        for patient in patients:
            try:
                fhir_data = patient.to_fhir_dict()
                is_valid, validation_msg = validate_fhir_data(fhir_data, 'Patient')
                
                results.append({
                    'patient_id': patient.patient_id,
                    'valid': is_valid,
                    'message': validation_msg,
                    'has_name': bool(patient.given_name or patient.family_name),
                    'has_phone': bool(patient.primary_phone),
                    'has_email': bool(patient.email)
                })
                
            except Exception as e:
                results.append({
                    'patient_id': patient.patient_id,
                    'valid': False,
                    'message': f'Error generating FHIR data: {str(e)}'
                })
        
        return {
            'tested': len(results),
            'valid': len([r for r in results if r['valid']]),
            'invalid': len([r for r in results if not r['valid']]),
            'results': results
        }
        
    except Exception as e:
        logger.error(f"Patient data validation failed: {e}")
        return {'error': str(e)}