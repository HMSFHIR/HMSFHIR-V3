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