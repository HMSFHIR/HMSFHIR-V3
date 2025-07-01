# services.py - Core Business Logic

import requests
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from django.apps import apps
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import SyncQueue, SyncRule, FHIRSyncConfig, SyncLog
from django.contrib.contenttypes.models import ContentType
import re
from datetime import datetime

from core.settings import FHIR_SERVER_BASE_URL


#  Declaring base url. Pointing from settings.py 
base_url = FHIR_SERVER_BASE_URL

logger = logging.getLogger(__name__)

class FHIRDataMapper:
    """Handles field mapping and transformation between HMS and FHIR formats"""
    
    @staticmethod
    def apply_field_mappings(source_data: Dict, field_mappings: Dict) -> Dict:
        """Apply field mappings to convert HMS data to FHIR format"""
        fhir_data = {}
        
        for hms_field, fhir_path in field_mappings.items():
            if hms_field in source_data and source_data[hms_field] is not None:
                value = source_data[hms_field]
                FHIRDataMapper._set_nested_value(fhir_data, fhir_path, value)
        
        return fhir_data
    
    @staticmethod
    def _set_nested_value(data: Dict, path: str, value: Any):
        """Set a nested value in a dictionary using dot notation"""
        keys = path.split('.')
        current = data
        
        for key in keys[:-1]:
            # Handle array notation like 'name[0]' or 'identifier[mrn]'
            if '[' in key and ']' in key:
                array_key, index_part = key.split('[', 1)
                index = index_part.rstrip(']')
                
                if array_key not in current:
                    current[array_key] = []
                
                # Handle numeric indices
                if index.isdigit():
                    idx = int(index)
                    while len(current[array_key]) <= idx:
                        current[array_key].append({})
                    current = current[array_key][idx]
                else:
                    # Handle named indices (for identifier types, etc.)
                    found = False
                    for item in current[array_key]:
                        if isinstance(item, dict) and item.get('type') == index:
                            current = item
                            found = True
                            break
                    
                    if not found:
                        new_item = {'type': index}
                        current[array_key].append(new_item)
                        current = new_item
            else:
                if key not in current:
                    current[key] = {}
                current = current[key]
        
        # Set the final value
        final_key = keys[-1]
        if '[' in final_key and ']' in final_key:
            array_key, index_part = final_key.split('[', 1)
            index = index_part.rstrip(']')
            
            if array_key not in current:
                current[array_key] = []
            
            if index.isdigit():
                idx = int(index)
                while len(current[array_key]) <= idx:
                    current[array_key].append(None)
                current[array_key][idx] = value
            else:
                current[array_key].append(value)
        else:
            current[final_key] = value
    
    @staticmethod
    def apply_transformations(data: Dict, transform_rules: Dict) -> Dict:
        """Apply transformation rules to field values"""
        transformed_data = data.copy()
        
        for field, rule in transform_rules.items():
            if field in transformed_data:
                value = transformed_data[field]
                if value is not None:
                    transformed_data[field] = FHIRDataMapper._transform_value(value, rule)
        
        return transformed_data
    
    @staticmethod
    def _transform_value(value: Any, rule: Dict) -> Any:
        """Transform a single value based on transformation rule"""
        transform_type = rule.get('type')
        
        if transform_type == 'map':
            mapping = rule.get('mapping', {})
            return mapping.get(str(value), value)
        
        elif transform_type == 'date_format':
            if isinstance(value, str):
                return value  # Assume already formatted
            elif hasattr(value, 'isoformat'):
                return value.isoformat()
            return str(value)
        
        elif transform_type == 'phone_format':
            return FHIRDataMapper._format_phone_number(str(value))
        
        return value
    
    @staticmethod
    def _format_phone_number(phone: str) -> str:
        """Format phone number for FHIR"""
        # Remove all non-digits
        digits = re.sub(r'\D', '', phone)
        
        # Add international prefix if missing
        if not digits.startswith('233') and len(digits) == 10:
            digits = '233' + digits
        elif not digits.startswith('233') and len(digits) == 9:
            digits = '233' + digits
        
        return '+' + digits

class FHIRDataValidator:
    """Validates data before FHIR sync"""
    
    @staticmethod
    def validate_data(data: Dict, validation_rules: Dict) -> Tuple[bool, List[str]]:
        """Validate data against validation rules"""
        errors = []
        
        # Check required fields
        required_fields = validation_rules.get('required_fields', [])
        for field in required_fields:
            if field not in data or data[field] is None or data[field] == '':
                errors.append(f"Required field '{field}' is missing or empty")
        
        # Check conditional required fields
        conditional_required = validation_rules.get('conditional_required', {})
        for condition_field, required_fields in conditional_required.items():
            if data.get(condition_field):
                for req_field in required_fields:
                    if req_field not in data or data[req_field] is None:
                        errors.append(f"Field '{req_field}' is required when '{condition_field}' is set")
        
        # Check field validations
        field_validations = validation_rules.get('field_validations', {})
        for field, validation in field_validations.items():
            if field in data and data[field] is not None:
                value = data[field]
                if not FHIRDataValidator._validate_field_value(value, validation):
                    errors.append(f"Field '{field}' has invalid value: {value}")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def _validate_field_value(value: Any, validation) -> bool:
        """Validate a single field value"""
        if validation == 'email_format':
            return re.match(r'^[^@]+@[^@]+\.[^@]+$', str(value)) is not None
        
        elif validation == 'phone_format':
            digits = re.sub(r'\D', '', str(value))
            return len(digits) >= 9
        
        elif validation == 'date_not_future':
            if isinstance(value, str):
                try:
                    date_val = datetime.fromisoformat(value).date()
                    return date_val <= timezone.now().date()
                except ValueError:
                    return False
            return True
        
        elif isinstance(validation, list):
            return str(value).lower() in [str(v).lower() for v in validation]
        
        return True

class FHIRSyncService:
    """Core service for FHIR synchronization"""
    
    def __init__(self, config_name: str = 'default'):
        try:
            self.config = FHIRSyncConfig.objects.get(name=config_name, is_active=True)
            # Use database config if available, otherwise fall back to settings
            self.base_url = self.config.base_url or settings.FHIR_SERVER_BASE_URL
        except FHIRSyncConfig.DoesNotExist:
            # If no database config, use settings
            self.base_url = settings.FHIR_SERVER_BASE_URL
            self.config = None
        
        # Validate base_url is configured
        if not self.base_url:
            raise ValueError("FHIR server URL not configured in settings or database")
            
        self.session = requests.Session()
        self._setup_authentication()

    def _setup_authentication(self):
        """Setup authentication for FHIR requests"""
        if self.config and self.config.auth_type == 'basic':
            username = self.config.auth_credentials.get('username')
            password = self.config.auth_credentials.get('password')
            if username and password:
                self.session.auth = (username, password)
        
        elif self.config and self.config.auth_type == 'bearer':
            token = self.config.auth_credentials.get('token')
            if token:
                self.session.headers.update({'Authorization': f'Bearer {token}'})
        
        # Add common headers
        self.session.headers.update({
            'Content-Type': 'application/fhir+json',
            'Accept': 'application/fhir+json'
        })
    
    def test_connection(self) -> Dict[str, Any]:
        """Test connection to FHIR server"""
        try:
            response = self.session.get(
                f"{self.base_url}/metadata",
                timeout=getattr(self.config, 'timeout', 30)
            )
            
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
        except requests.exceptions.RequestException as e:
            return {
                'connected': False,
                'status': f'Connection error: {str(e)}'
            }
    
    def sync_resource(self, queue_item: SyncQueue) -> bool:
        """Sync a single resource to FHIR server"""
        queue_item.mark_processing()
        
        try:
            # Apply field mappings and transformations if sync rule is available
            if queue_item.sync_rule:
                success = self._sync_with_rule(queue_item)
            else:
                success = self._sync_without_rule(queue_item)
            
            return success
            
        except Exception as e:
            logger.error(f"Sync failed for {queue_item}: {e}")
            queue_item.mark_failed(str(e))
            self._log_sync_event(queue_item, 'ERROR', f"Sync failed: {e}")
            return False
    
    def _sync_with_rule(self, queue_item: SyncQueue) -> bool:
        """Sync resource using sync rule for field mappings and validation"""
        sync_rule = queue_item.sync_rule
        
        # Get source object data if available
        source_data = queue_item.fhir_data.copy()
        if queue_item.source_object:
            # Extract data from source object
            source_data.update(self._extract_model_data(queue_item.source_object))
        
        # Apply field mappings
        field_mappings = sync_rule.get_effective_field_mappings()
        mapped_data = FHIRDataMapper.apply_field_mappings(source_data, field_mappings)
        
        # Apply transformations
        transform_rules = sync_rule.get_transform_rules()
        transformed_data = FHIRDataMapper.apply_transformations(source_data, transform_rules)
        
        # Merge transformed data into mapped FHIR data
        fhir_data = {**mapped_data}
        for key, value in transformed_data.items():
            if key in field_mappings:
                fhir_path = field_mappings[key]
                FHIRDataMapper._set_nested_value(fhir_data, fhir_path, value)
        
        # Validate data
        validation_rules = sync_rule.get_validation_rules()
        is_valid, validation_errors = FHIRDataValidator.validate_data(source_data, validation_rules)
        
        if not is_valid:
            error_msg = f"Validation failed: {'; '.join(validation_errors)}"
            queue_item.mark_failed(error_msg)
            queue_item.validation_results = {'valid': False, 'errors': validation_errors}
            queue_item.save()
            self._log_sync_event(queue_item, 'ERROR', error_msg)
            return False
        
        # Record what was applied
        queue_item.field_mapping_used = field_mappings
        queue_item.transform_applied = transform_rules
        queue_item.validation_results = {'valid': True, 'errors': []}
        queue_item.save()
        
        # Ensure required FHIR fields
        if 'resourceType' not in fhir_data:
            fhir_data['resourceType'] = queue_item.resource_type
        
        # Use the appropriate resource ID
        if queue_item.resource_type == 'Patient' and 'id' not in fhir_data:
            # For Patient resources, use patient_id as the identifier
            if 'patient_id' in source_data:
                fhir_data['id'] = source_data['patient_id']
            elif queue_item.resource_id:
                fhir_data['id'] = queue_item.resource_id
        
        return self._perform_sync_operation(queue_item, fhir_data)
    
    def _sync_without_rule(self, queue_item: SyncQueue) -> bool:
        """Sync resource without sync rule (legacy mode)"""
        fhir_data = queue_item.fhir_data.copy()
        if 'resourceType' not in fhir_data:
            fhir_data['resourceType'] = queue_item.resource_type
        
        return self._perform_sync_operation(queue_item, fhir_data)
    
    def _extract_model_data(self, model_instance) -> Dict:
        """Extract data from Django model instance"""
        data = {}
        
        # Get all field values
        for field in model_instance._meta.fields:
            field_name = field.name
            value = getattr(model_instance, field_name)
            
            # Convert to serializable format
            if hasattr(value, 'isoformat'):
                value = value.isoformat()
            elif hasattr(value, '__str__'):
                value = str(value)
            
            data[field_name] = value
        
        # Include properties if they exist (like full_name, age, etc.)
        for attr_name in ['full_name', 'age', 'full_address']:
            if hasattr(model_instance, attr_name):
                try:
                    value = getattr(model_instance, attr_name)
                    data[attr_name] = value
                except Exception:
                    pass  # Skip if property fails
        
        return data
    
    def _perform_sync_operation(self, queue_item: SyncQueue, fhir_data: Dict) -> bool:
        """Perform the actual sync operation"""
        # Determine operation
        if queue_item.operation == 'create':
            return self._create_resource(queue_item, fhir_data)
        elif queue_item.operation == 'update':
            return self._update_resource(queue_item, fhir_data)
        elif queue_item.operation == 'delete':
            return self._delete_resource(queue_item)
        else:
            raise ValueError(f"Unknown operation: {queue_item.operation}")
    
    def _create_resource(self, queue_item: SyncQueue, fhir_data: Dict) -> bool:
        """Create new FHIR resource"""
        url = f"{self.base_url}/{queue_item.resource_type}"
        
        response = self.session.post(
            url, 
            json=fhir_data, 
            timeout=getattr(self.config, 'timeout', 30)
        )
        
        if response.status_code in [200, 201]:
            response_data = response.json()
            fhir_id = response_data.get('id')
            queue_item.mark_success(fhir_id=fhir_id, response_data=response_data)
            
            # Update source object with FHIR ID if it's a Patient
            if queue_item.source_object and queue_item.resource_type == 'Patient':
                self._update_source_object_fhir_id(queue_item.source_object, fhir_id)
            
            self._log_sync_event(queue_item, 'INFO', f"Resource created with ID: {fhir_id}")
            return True
        else:
            error_msg = f"HTTP {response.status_code}: {response.text[:500]}"
            queue_item.mark_failed(error_msg, response_data={'status_code': response.status_code})
            self._log_sync_event(queue_item, 'ERROR', error_msg)
            return False
    
    def _update_resource(self, queue_item: SyncQueue, fhir_data: Dict) -> bool:
        """Update existing FHIR resource"""
        fhir_id = queue_item.fhir_id or fhir_data.get('id')
        if not fhir_id:
            # Try to create instead
            return self._create_resource(queue_item, fhir_data)
        
        url = f"{self.base_url}/{queue_item.resource_type}/{fhir_id}"
        
        response = self.session.put(
            url, 
            json=fhir_data, 
            timeout=getattr(self.config, 'timeout', 30)
        )
        
        if response.status_code in [200, 201]:
            response_data = response.json()
            queue_item.mark_success(fhir_id=fhir_id, response_data=response_data)
            
            # Update source object sync timestamp
            if queue_item.source_object and queue_item.resource_type == 'Patient':
                self._update_source_object_sync_time(queue_item.source_object)
            
            self._log_sync_event(queue_item, 'INFO', f"Resource updated: {fhir_id}")
            return True
        elif response.status_code == 404:
            # Resource not found, create new one
            return self._create_resource(queue_item, fhir_data)
        else:
            error_msg = f"HTTP {response.status_code}: {response.text[:500]}"
            queue_item.mark_failed(error_msg, response_data={'status_code': response.status_code})
            self._log_sync_event(queue_item, 'ERROR', error_msg)
            return False
    
    def _delete_resource(self, queue_item: SyncQueue) -> bool:
        """Delete FHIR resource"""
        fhir_id = queue_item.fhir_id
        if not fhir_id:
            queue_item.mark_failed("No FHIR ID available for deletion")
            return False
        
        url = f"{self.base_url}/{queue_item.resource_type}/{fhir_id}"
        
        response = self.session.delete(
            url, 
            timeout=getattr(self.config, 'timeout', 30)
        )
        
        if response.status_code in [200, 204]:
            queue_item.mark_success()
            self._log_sync_event(queue_item, 'INFO', f"Resource deleted: {fhir_id}")
            return True
        elif response.status_code == 404:
            # Already deleted
            queue_item.mark_success()
            self._log_sync_event(queue_item, 'INFO', f"Resource already deleted: {fhir_id}")
            return True
        else:
            error_msg = f"HTTP {response.status_code}: {response.text[:500]}"
            queue_item.mark_failed(error_msg, response_data={'status_code': response.status_code})
            self._log_sync_event(queue_item, 'ERROR', error_msg)
            return False
    
    def _update_source_object_fhir_id(self, source_object, fhir_id: str):
        """Update source object with FHIR ID"""
        try:
            if hasattr(source_object, 'fhir_id'):
                source_object.fhir_id = fhir_id
                source_object.last_sync = timezone.now()
                source_object.save(update_fields=['fhir_id', 'last_sync'])
        except Exception as e:
            logger.warning(f"Could not update source object FHIR ID: {e}")
    
    def _update_source_object_sync_time(self, source_object):
        """Update source object sync timestamp"""
        try:
            if hasattr(source_object, 'last_sync'):
                source_object.last_sync = timezone.now()
                source_object.save(update_fields=['last_sync'])
        except Exception as e:
            logger.warning(f"Could not update source object sync time: {e}")
    
    def _log_sync_event(self, queue_item: SyncQueue, level: str, message: str, details: Dict = None):
        """Log sync event"""
        SyncLog.objects.create(
            queue_item=queue_item,
            level=level,
            message=message,
            details=details or {}
        )

    def check_server_availability(self) -> bool:
        """
        Check if the FHIR server is available and responding.
        Returns True if available, False otherwise.
        """
        try:
            if not self.base_url:
                logger.error("FHIR server URL not configured")
                return False

            # Try to access the metadata endpoint (standard FHIR capability statement)
            metadata_url = f"{self.base_url.rstrip('/')}/metadata"
            response = self.session.get(
                metadata_url,
                timeout=10,
                headers={'Accept': 'application/fhir+json'}
            )

            # Check if we got a successful response
            if response.status_code == 200:
                # Optionally validate that it's actually a FHIR capability statement
                try:
                    data = response.json()
                    return data.get('resourceType') == 'CapabilityStatement'
                except Exception:
                    # If JSON parsing fails, just check status code
                    return True

            return False

        except requests.exceptions.ConnectionError:
            logger.warning("FHIR server connection failed - server may be down")
            return False
        except requests.exceptions.Timeout:
            logger.warning("FHIR server connection timeout")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"FHIR server availability check failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error checking FHIR server availability: {e}")
            return False
    

class SyncQueueManager:
    """Manager for sync queue operations"""
    
    @staticmethod
    def queue_resource(resource_type: str, resource_id: str, fhir_data: Dict = None, 
                      operation: str = 'create', priority: int = 100,
                      source_object=None, sync_rule=None) -> SyncQueue:
        """Add resource to sync queue"""
        
        # Generate FHIR data from source object if not provided
        if not fhir_data and source_object:
            if hasattr(source_object, 'to_fhir_dict'):
                fhir_data = source_object.to_fhir_dict()
            else:
                fhir_data = {}
        
        fhir_data = fhir_data or {}
        
        # For Patient resources, ensure we use patient_id as resource_id
        if resource_type == 'Patient' and source_object and hasattr(source_object, 'patient_id'):
            resource_id = source_object.patient_id
        
        # Check for existing queue item
        existing = SyncQueue.objects.filter(
            resource_type=resource_type,
            resource_id=resource_id,
            status__in=['pending', 'processing']
        ).first()
        
        if existing:
            # Update existing item
            existing.fhir_data = fhir_data
            existing.operation = operation
            existing.priority = priority
            existing.status = 'pending'
            existing.attempts = 0
            existing.error_message = None
            if sync_rule:
                existing.sync_rule = sync_rule
            existing.save()
            return existing
        else:
            # Create new queue item
            content_type = None
            object_id = None
            
            if source_object:
                content_type = ContentType.objects.get_for_model(source_object)
                object_id = source_object.pk
            
            return SyncQueue.objects.create(
                resource_type=resource_type,
                resource_id=resource_id,
                operation=operation,
                fhir_data=fhir_data,
                priority=priority,
                sync_rule=sync_rule,
                content_type=content_type,
                object_id=object_id
            )
    
    @staticmethod
    def queue_patient(patient, operation: str = 'create', priority: int = 100) -> SyncQueue:
        """Convenience method to queue a Patient resource"""
        # Find the appropriate sync rule for Patient
        sync_rule = SyncRule.objects.filter(
            resource_type='Patient',
            is_enabled=True
        ).first()
        
        return SyncQueueManager.queue_resource(
            resource_type='Patient',
            resource_id=patient.patient_id,
            source_object=patient,
            operation=operation,
            priority=priority,
            sync_rule=sync_rule
        )
    
    @staticmethod
    def process_queue(limit: int = 50) -> Dict[str, int]:
        """Process pending queue items"""
        sync_service = FHIRSyncService()
        
        # Get pending items
        pending_items = SyncQueue.objects.filter(
            status='pending',
            scheduled_at__lte=timezone.now()
        ).order_by('priority', 'created_at')[:limit]
        
        results = {'success': 0, 'failed': 0, 'total': len(pending_items)}
        
        for item in pending_items:
            success = sync_service.sync_resource(item)
            if success:
                results['success'] += 1
            else:
                results['failed'] += 1
        
        return results
    
    @staticmethod
    def retry_failed_items(max_retries: int = 3) -> Dict[str, int]:
        """Retry failed queue items"""
        failed_items = SyncQueue.objects.filter(
            status='failed',
            attempts__lt=max_retries
        ).order_by('last_attempt_at')
        
        results = {'retried': 0, 'success': 0, 'failed': 0}
        sync_service = FHIRSyncService()
        
        for item in failed_items:
            item.status = 'pending'
            item.save()
            results['retried'] += 1
            
            success = sync_service.sync_resource(item)
            if success:
                results['success'] += 1
            else:
                results['failed'] += 1
        
        return results
    
    @staticmethod
    def get_statistics() -> Dict[str, Any]:
        """Get queue statistics"""
        stats = {}
        
        # Overall stats
        stats['total'] = SyncQueue.objects.count()
        stats['pending'] = SyncQueue.objects.filter(status='pending').count()
        stats['processing'] = SyncQueue.objects.filter(status='processing').count()
        stats['success'] = SyncQueue.objects.filter(status='success').count()
        stats['failed'] = SyncQueue.objects.filter(status='failed').count()
        
        # By resource type
        stats['by_resource_type'] = {}
        for resource_type, _ in SyncRule.RESOURCE_TYPES:
            type_stats = {
                'pending': SyncQueue.objects.filter(
                    resource_type=resource_type, status='pending'
                ).count(),
                'success': SyncQueue.objects.filter(
                    resource_type=resource_type, status='success'
                ).count(),
                'failed': SyncQueue.objects.filter(
                    resource_type=resource_type, status='failed'
                ).count(),
            }
            type_stats['total'] = sum(type_stats.values())
            stats['by_resource_type'][resource_type] = type_stats
        
        return stats