# services.py - Core Business Logic

#import requests
#import json
import logging
from typing import Dict, List, Any, Tuple
from django.utils import timezone
import re
from datetime import datetime
from core.settings import FHIR_SERVER_BASE_URL
from .queueManager import SyncQueueManager

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


