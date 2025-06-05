# fhir_sync/enhanced_services.py - Fixed FHIR endpoints and improved error handling
import requests
from django.utils import timezone
from django.conf import settings
from django.apps import apps
from .models import PendingSyncQueue
from .mappers import FHIR_MAPPERS

# Model mappings - verify these match your actual Django models
MODEL_MAPPINGS = {
    'Patient': ('Patients', 'Patient'),
    'Practitioner': ('Practitioner', 'Practitioner'),
    'Encounter': ('MedicalRecords', 'Encounter'),
    'Observation': ('MedicalRecords', 'Observation'),
    'Condition': ('MedicalRecords', 'Condition'),
    'MedicationStatement': ('MedicalRecords', 'MedicationStatement'),
    'AllergyIntolerance': ('MedicalRecords', 'AllergyIntolerance'),
    'Procedure': ('MedicalRecords', 'Procedure'),
    'Immunization': ('MedicalRecords', 'Immunization'),
    'DocumentReference': ('MedicalRecords', 'DocumentReference'),
}

def get_model_class(resource_type):
    """Get Django model class for a resource type"""
    if resource_type not in MODEL_MAPPINGS:
        print(f"Resource type {resource_type} not in MODEL_MAPPINGS")
        return None
    
    app_name, model_name = MODEL_MAPPINGS[resource_type]
    try:
        return apps.get_model(app_name, model_name)
    except LookupError as e:
        print(f"Model {app_name}.{model_name} not found: {e}")
        return None

def get_resource_id(record, resource_type):
    """
    Get the appropriate resource ID for different resource types
    """
    if resource_type == 'Patient':
        return getattr(record, 'patient_id', str(record.id))
    elif resource_type == 'Practitioner':
        return getattr(record, 'practitioner_id', str(record.id))
    elif hasattr(record, 'patient'):
        # For medical records, use patient_id + record_id for uniqueness
        patient_id = getattr(record.patient, 'patient_id', str(record.patient.id))
        return f"{patient_id}_{record.id}"
    else:
        return str(record.id)

def sync_hms_to_fhir():
    """
    Sync all HMS data to FHIR server by queuing them for sync
    """
    print("Starting HMS to FHIR sync...")
    total_queued = 0
    
    for resource_type, (app_name, model_name) in MODEL_MAPPINGS.items():
        try:
            model_class = get_model_class(resource_type)
            if not model_class:
                print(f"Skipping {resource_type} - model not found")
                continue
                
            mapper_func = FHIR_MAPPERS.get(resource_type)
            if not mapper_func:
                print(f"Skipping {resource_type} - no mapper found")
                continue
            
            # Get all records from HMS
            records = model_class.objects.all()
            record_count = records.count()
            print(f"Found {record_count} {resource_type} records to sync")
            
            if record_count == 0:
                continue
            
            for record in records:
                try:
                    # Convert to FHIR format
                    fhir_data = mapper_func(record)
                    
                    # Get unique identifier for the record
                    resource_id = get_resource_id(record, resource_type)
                    
                    # Check if already queued
                    existing = PendingSyncQueue.objects.filter(
                        resource_type=resource_type,
                        resource_id=resource_id
                    ).first()
                    
                    if existing:
                        # Update existing queue item
                        existing.json_data = fhir_data
                        existing.status = 'pending'
                        existing.retry_count = 0
                        existing.error_message = None
                        existing.last_retry_at = None
                        existing.save()
                        print(f"Updated existing queue item for {resource_type} {resource_id}")
                    else:
                        # Create new queue item
                        PendingSyncQueue.objects.create(
                            resource_type=resource_type,
                            resource_id=resource_id,
                            json_data=fhir_data,
                            status='pending'
                        )
                        print(f"Queued new {resource_type} {resource_id}")
                    
                    total_queued += 1
                        
                except Exception as e:
                    print(f"Error processing {resource_type} {record.id}: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error syncing {resource_type}: {e}")
            continue
    
    print(f"HMS to FHIR sync queuing completed. Total items queued: {total_queued}")
    return total_queued

def sync_resource_enhanced(resource: PendingSyncQueue):
    """
    Enhanced version of sync_resource with proper FHIR endpoints and better error handling
    """
    try:
        # Use proper FHIR resource naming (Patient, not patient)
        resource_type = resource.resource_type  # Keep original case
        url = f"{settings.FHIR_SERVER_BASE_URL}/{resource_type}"
        
        # Add proper FHIR headers
        headers = {
            'Content-Type': 'application/fhir+json',
            'Accept': 'application/fhir+json'
        }
        
        # Ensure the FHIR data has the correct resourceType
        if 'resourceType' not in resource.json_data:
            resource.json_data['resourceType'] = resource_type
        
        # Try to update existing resource first
        resource_id = resource.json_data.get('id')
        if resource_id:
            update_url = f"{url}/{resource_id}"
            print(f"Attempting to update {resource_type} at {update_url}")
            response = requests.put(update_url, json=resource.json_data, headers=headers, timeout=30)
            
            if response.status_code == 404:
                # Resource doesn't exist, create new one
                print(f"Resource not found, creating new {resource_type}")
                response = requests.post(url, json=resource.json_data, headers=headers, timeout=30)
        else:
            # Create new resource
            print(f"Creating new {resource_type} at {url}")
            response = requests.post(url, json=resource.json_data, headers=headers, timeout=30)
        
        # Check response
        if response.status_code in [200, 201]:
            resource.status = 'success'
            resource.completed_at = timezone.now()
            resource.error_message = None
            
            # Try to extract the ID from the response for future updates
            if response.status_code == 201:
                try:
                    response_data = response.json()
                    if 'id' in response_data:
                        resource.json_data['id'] = response_data['id']
                except:
                    pass  # If we can't parse response, that's okay
                    
            print(f"✅ Successfully synced {resource.resource_type} {resource.resource_id}")
            
        elif response.status_code == 400:
            resource.status = 'failed'
            resource.error_message = f"Bad Request (400): {response.text[:500]}"
            resource.retry_count += 1
            resource.last_retry_at = timezone.now()
            print(f"❌ Bad request for {resource.resource_type} {resource.resource_id}: {response.text[:200]}")
            
        elif response.status_code == 422:
            resource.status = 'failed'
            resource.error_message = f"Unprocessable Entity (422): {response.text[:500]}"
            resource.retry_count += 1
            resource.last_retry_at = timezone.now()
            print(f"❌ Validation error for {resource.resource_type} {resource.resource_id}: {response.text[:200]}")
            
        else:
            resource.status = 'failed'
            resource.error_message = f"HTTP {response.status_code}: {response.text[:500]}"
            resource.retry_count += 1
            resource.last_retry_at = timezone.now()
            print(f"❌ HTTP {response.status_code} for {resource.resource_type} {resource.resource_id}")
            
    except requests.exceptions.Timeout:
        resource.status = 'failed'
        resource.error_message = "Request timeout (30s)"
        resource.retry_count += 1
        resource.last_retry_at = timezone.now()
        print(f"⏰ Timeout for {resource.resource_type} {resource.resource_id}")
        
    except requests.exceptions.ConnectionError as e:
        resource.status = 'failed'
        resource.error_message = f"Connection error - FHIR server unreachable: {str(e)[:200]}"
        resource.retry_count += 1
        resource.last_retry_at = timezone.now()
        print(f"🔌 Connection error for {resource.resource_type} {resource.resource_id}: {e}")
        
    except Exception as e:
        resource.status = 'failed'
        resource.error_message = f"Unexpected error: {str(e)[:500]}"
        resource.retry_count += 1
        resource.last_retry_at = timezone.now()
        print(f"💥 Unexpected error for {resource.resource_type} {resource.resource_id}: {e}")
        
    finally:
        resource.save()

def sync_pending_resources_enhanced():
    """
    Enhanced version of sync_pending_resources with retry logic
    """
    # Get pending resources, prioritizing those with fewer retries
    pending_resources = PendingSyncQueue.objects.filter(
        status="pending"
    ).order_by('retry_count', 'created_at')
    
    # Also retry failed resources with less than 3 attempts
    failed_resources = PendingSyncQueue.objects.filter(
        status="failed",
        retry_count__lt=3
    ).order_by('retry_count', 'last_retry_at')
    
    all_resources = list(pending_resources) + list(failed_resources)
    
    print(f"Processing {len(all_resources)} resources for sync")
    
    success_count = 0
    failed_count = 0
    
    for resource in all_resources:
        if resource.status == 'failed':
            # Reset to pending for retry
            resource.status = 'pending'
            resource.save()
            
        sync_resource_enhanced(resource)
        
        if resource.status == 'success':
            success_count += 1
        else:
            failed_count += 1
    
    print(f"Sync completed: {success_count} successful, {failed_count} failed")
    return {"success": success_count, "failed": failed_count}

def get_sync_statistics():
    """
    Get comprehensive sync statistics
    """
    stats = {}
    
    for resource_type in MODEL_MAPPINGS.keys():
        resource_stats = {
            'pending': PendingSyncQueue.objects.filter(
                resource_type=resource_type, 
                status='pending'
            ).count(),
            'success': PendingSyncQueue.objects.filter(
                resource_type=resource_type, 
                status='success'
            ).count(),
            'failed': PendingSyncQueue.objects.filter(
                resource_type=resource_type, 
                status='failed'
            ).count(),
        }
        resource_stats['total'] = sum(resource_stats.values())
        stats[resource_type] = resource_stats
    
    return stats

def clear_completed_sync_tasks():
    """
    Clean up old completed sync tasks
    """
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=7)  # Keep last 7 days
    
    deleted_count = PendingSyncQueue.objects.filter(
        status='success',
        completed_at__lt=cutoff_date
    ).delete()[0]
    
    print(f"Cleaned up {deleted_count} old sync tasks")
    return deleted_count

def test_fhir_connection():
    """
    Test connection to FHIR server and return detailed info
    """
    try:
        response = requests.get(f"{settings.FHIR_SERVER_BASE_URL}/metadata", timeout=10)
        if response.status_code == 200:
            metadata = response.json()
            return {
                'connected': True,
                'server_info': metadata.get('software', {}),
                'fhir_version': metadata.get('fhirVersion', 'Unknown'),
                'status': 'Connected successfully'
            }
        else:
            return {
                'connected': False,
                'status': f'HTTP {response.status_code}: {response.text[:200]}'
            }
    except requests.exceptions.ConnectionError:
        return {
            'connected': False,
            'status': 'Connection refused - FHIR server not reachable'
        }
    except Exception as e:
        return {
            'connected': False,
            'status': f'Error: {str(e)}'
        }