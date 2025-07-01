
import requests
import logging
from Fsync.models import SyncLog
from core import settings
from services import SyncQueue, FHIRDataMapper, FHIRSyncConfig, FHIRDataValidator
from django.utils import timezone
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)


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
    