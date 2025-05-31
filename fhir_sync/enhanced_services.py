# fhir_sync/enhanced_services.py
import requests
from django.utils import timezone
from django.conf import settings
from django.apps import apps
from .models import PendingSyncQueue
from .mappers import FHIR_MAPPERS

# Model mappings
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
        return None
    
    app_name, model_name = MODEL_MAPPINGS[resource_type]
    try:
        return apps.get_model(app_name, model_name)
    except LookupError:
        print(f"Model {app_name}.{model_name} not found")
        return None

def sync_hms_to_fhir():
    """
    Sync all HMS data to FHIR server by queuing them for sync
    """
    print("Starting HMS to FHIR sync...")
    
    for resource_type, (app_name, model_name) in MODEL_MAPPINGS.items():
        try:
            model_class = get_model_class(resource_type)
            if not model_class:
                continue
                
            mapper_func = FHIR_MAPPERS.get(resource_type)
            if not mapper_func:
                print(f"No mapper found for {resource_type}")
                continue
            
            # Get all records from HMS
            records = model_class.objects.all()
            print(f"Found {records.count()} {resource_type} records to sync")
            
            for record in records:
                try:
                    # Convert to FHIR format
                    fhir_data = mapper_func(record)
                    
                    # Get unique identifier for the record
                    if hasattr(record, 'patient_id'):
                        resource_id = record.patient_id
                    elif hasattr(record, 'practitioner_id'):
                        resource_id = record.practitioner_id
                    else:
                        resource_id = str(record.id)
                    
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
                        existing.save()
                    else:
                        # Create new queue item
                        PendingSyncQueue.objects.create(
                            resource_type=resource_type,
                            resource_id=resource_id,
                            json_data=fhir_data,
                            status='pending'
                        )
                        
                except Exception as e:
                    print(f"Error processing {resource_type} {record.id}: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error syncing {resource_type}: {e}")
            continue
    
    print("HMS to FHIR sync queuing completed")

def sync_resource_enhanced(resource: PendingSyncQueue):
    """
    Enhanced version of sync_resource with better error handling
    """
    try:
        # Construct FHIR server URL
        resource_type_lower = resource.resource_type.lower()
        url = f"{settings.FHIR_SERVER_BASE_URL}/{resource_type_lower}"
        
        # Add headers for FHIR
        headers = {
            'Content-Type': 'application/fhir+json',
            'Accept': 'application/fhir+json'
        }
        
        # Try to update existing resource first
        resource_id = resource.json_data.get('id')
        if resource_id:
            update_url = f"{url}/{resource_id}"
            response = requests.put(update_url, json=resource.json_data, headers=headers, timeout=10)
            
            if response.status_code == 404:
                # Resource doesn't exist, create new one
                response = requests.post(url, json=resource.json_data, headers=headers, timeout=10)
        else:
            # Create new resource
            response = requests.post(url, json=resource.json_data, headers=headers, timeout=10)
        
        # Check response
        if response.status_code in [200, 201]:
            resource.status = 'success'
            resource.completed_at = timezone.now()
            resource.error_message = None
            print(f"Successfully synced {resource.resource_type} {resource.resource_id}")
        else:
            resource.status = 'failed'
            resource.error_message = f"HTTP {response.status_code}: {response.text[:500]}"
            resource.retry_count += 1
            resource.last_retry_at = timezone.now()
            print(f"Failed to sync {resource.resource_type} {resource.resource_id}: {resource.error_message}")
            
    except requests.exceptions.Timeout:
        resource.status = 'failed'
        resource.error_message = "Request timeout"
        resource.retry_count += 1
        resource.last_retry_at = timezone.now()
        
    except requests.exceptions.ConnectionError:
        resource.status = 'failed'
        resource.error_message = "Connection error - FHIR server unreachable"
        resource.retry_count += 1
        resource.last_retry_at = timezone.now()
        
    except Exception as e:
        resource.status = 'failed'
        resource.error_message = f"Unexpected error: {str(e)[:500]}"
        resource.retry_count += 1
        resource.last_retry_at = timezone.now()
        
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
    
    for resource in all_resources:
        if resource.status == 'failed':
            # Reset to pending for retry
            resource.status = 'pending'
            resource.save()
            
        sync_resource_enhanced(resource)

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