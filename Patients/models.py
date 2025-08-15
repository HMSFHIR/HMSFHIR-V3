from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from django.conf import settings
from datetime import date
import uuid
from encrypted_model_fields.fields import EncryptedCharField, EncryptedTextField, EncryptedEmailField


def clean_encrypted_value(value):
    """
    Clean encrypted field values before FHIR validation.
    This function handles any decryption artifacts or empty values.
    """
    if value is None:
        return None
    
    # Convert to string if not already
    if not isinstance(value, str):
        value = str(value)
    
    # Strip whitespace
    value = value.strip()
    
    # Return None for empty strings
    if not value:
        return None
    
    # Handle common encryption artifacts or placeholder values
    if value.lower() in ['none', 'null', 'undefined', '']:
        return None
    
    return value


def validate_fhir_data(fhir_data, resource_type):
    """
    Enhanced validation function that specifically addresses HAPI FHIR warnings.
    """
    if not fhir_data or not isinstance(fhir_data, dict):
        return False, "Invalid FHIR data structure"
    
    if fhir_data.get('resourceType') != resource_type:
        return False, f"Resource type mismatch: expected {resource_type}"
    
    if not fhir_data.get('id'):
        return False, "Missing required 'id' field"
    
    if resource_type == 'Patient':
        # Validate name structure
        names = fhir_data.get('name', [])
        for i, name in enumerate(names):
            if not isinstance(name, dict):
                return False, f"Name[{i}] must be an object, not {type(name).__name__}"
            
            # Validate given names is array
            if 'given' in name and not isinstance(name['given'], list):
                return False, f"Name[{i}].given must be an array"
            
            # Validate prefix/suffix are arrays
            for field in ['prefix', 'suffix']:
                if field in name and not isinstance(name[field], list):
                    return False, f"Name[{i}].{field} must be an array"
        
        # Validate telecom structure
        telecom = fhir_data.get('telecom', [])
        for i, contact in enumerate(telecom):
            if not isinstance(contact, dict):
                return False, f"Telecom[{i}] must be an object"
            
            if 'system' not in contact or 'value' not in contact:
                return False, f"Telecom[{i}] missing required system or value"
        
        # Validate address structure
        addresses = fhir_data.get('address', [])
        for i, address in enumerate(addresses):
            if not isinstance(address, dict):
                return False, f"Address[{i}] must be an object"
            
            # Validate line is array
            if 'line' in address and not isinstance(address['line'], list):
                return False, f"Address[{i}].line must be an array"
        
        # Validate identifier structure
        identifiers = fhir_data.get('identifier', [])
        for i, identifier in enumerate(identifiers):
            if not isinstance(identifier, dict):
                return False, f"Identifier[{i}] must be an object"
            
            if 'value' not in identifier:
                return False, f"Identifier[{i}] missing required value"
            
            # Validate type structure if present
            if 'type' in identifier:
                type_obj = identifier['type']
                if not isinstance(type_obj, dict):
                    return False, f"Identifier[{i}].type must be an object"
    
    return True, "Valid"


class Patient(models.Model):
    # Core Identity Fields
    patient_id = models.CharField(max_length=100, unique=True, help_text="Internal patient identifier")
    
    # Name Fields (FHIR supports multiple names, but simplified here) - ENCRYPTED
    given_name = EncryptedCharField(max_length=500, help_text="First name(s)")
    family_name = EncryptedCharField(max_length=500, help_text="Last name/surname")
    middle_name = EncryptedCharField(max_length=500, blank=True, null=True, help_text="Middle name(s)")
    name_prefix = EncryptedCharField(max_length=200, blank=True, null=True, help_text="Dr., Mr., Mrs., etc.")
    name_suffix = EncryptedCharField(max_length=200, blank=True, null=True, help_text="Jr., Sr., III, etc.")
    
    # Legacy name field for backward compatibility - ENCRYPTED
    name = EncryptedCharField(max_length=1000, blank=True, null=True, help_text="Full name (legacy field)")
    
    # Core Demographics
    gender = models.CharField(max_length=10, choices=[
        ("male", "Male"), 
        ("female", "Female"), 
        ("other", "Other"),
        ("unknown", "Unknown")
    ], default="unknown")
    
    # CHANGED: Removed encryption from date field to prevent database type conflicts
    birth_date = models.DateField(null=True, blank=True, help_text="Date of birth")
    
    # Identifiers (FHIR supports multiple identifiers) - ENCRYPTED
    national_id = EncryptedCharField(max_length=300, unique=True, null=True, blank=True, help_text="National ID/SSN")
    medical_record_number = EncryptedCharField(max_length=300, unique=True, null=True, blank=True, help_text="MRN")
    insurance_number = EncryptedCharField(max_length=500, blank=True, null=True, help_text="Insurance ID")
    
    # Contact Information - ENCRYPTED
    phone_validator = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    primary_phone = EncryptedCharField(validators=[phone_validator], max_length=200, blank=True, null=True)
    secondary_phone = EncryptedCharField(validators=[phone_validator], max_length=200, blank=True, null=True)
    email = EncryptedEmailField(max_length=400, blank=True, null=True)
    
    # Address Information - ENCRYPTED
    address_line1 = EncryptedCharField(max_length=1000, blank=True, null=True, help_text="Street address")
    address_line2 = EncryptedCharField(max_length=1000, blank=True, null=True, help_text="Apartment, suite, etc.")
    city = EncryptedCharField(max_length=500, blank=True, null=True)
    state_province = EncryptedCharField(max_length=500, blank=True, null=True)
    postal_code = EncryptedCharField(max_length=200, blank=True, null=True)
    country = models.CharField(max_length=100, default="Ghana")  # Country can remain unencrypted for analytics
    
    # Additional Demographics
    marital_status = models.CharField(max_length=20, choices=[
        ("single", "Single"),
        ("married", "Married"),
        ("divorced", "Divorced"),
        ("widowed", "Widowed"),
        ("separated", "Separated"),
        ("unknown", "Unknown")
    ], blank=True, null=True)
    
    # Language and Communication
    preferred_language = models.CharField(max_length=10, choices=[
        ("en", "English"),
        ("tw", "Twi"),
        ("ga", "Ga"),
        ("ee", "Ewe"),
        ("fr", "French"),
        ("ha", "Hausa")
    ], default="en")
    
    # Emergency Contact - ENCRYPTED
    emergency_contact_name = EncryptedCharField(max_length=1000, blank=True, null=True)
    emergency_contact_relationship = EncryptedCharField(max_length=300, blank=True, null=True)
    emergency_contact_phone = EncryptedCharField(validators=[phone_validator], max_length=200, blank=True, null=True)
    
    # Clinical Information - ENCRYPTED
    blood_type = EncryptedCharField(max_length=200, choices=[
        ("A+", "A+"), ("A-", "A-"),
        ("B+", "B+"), ("B-", "B-"),
        ("AB+", "AB+"), ("AB-", "AB-"),
        ("O+", "O+"), ("O-", "O-")
    ], blank=True, null=True)
    
    allergies = EncryptedTextField(blank=True, null=True, help_text="Known allergies (comma-separated)")
    
    # Status Fields
    active = models.BooleanField(default=True, help_text="Whether this patient record is active")
    deceased = models.BooleanField(default=False)
    # CHANGED: Removed encryption from date field to prevent database type conflicts
    deceased_date = models.DateField(blank=True, null=True)
    
    # Practice Management
    last_arrived = models.DateField(null=True, blank=True, help_text="Last visit date")  # Can remain unencrypted for scheduling analytics
    registration_date = models.DateTimeField(default=timezone.now)
    
    # FHIR Integration
    fhir_id = models.CharField(max_length=100, blank=True, null=True, help_text="FHIR server patient ID")
    last_sync = models.DateTimeField(blank=True, null=True, help_text="Last FHIR sync timestamp")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_patients')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_patients')

    class Meta:
        db_table = 'patients'
        ordering = ['family_name', 'given_name']
        indexes = [
            # Date fields can now be indexed since they're not encrypted
            models.Index(fields=['birth_date']),
            models.Index(fields=['last_arrived']),
            models.Index(fields=['active']),
            models.Index(fields=['patient_id']),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.patient_id})"
    
    # Helper method to safely get encrypted field values
    def get_encrypted_field(self, field_name):
        """Safely retrieve encrypted field value, handling None cases"""
        try:
            value = getattr(self, field_name)
            # Handle encrypted fields that might return None or empty strings
            if value is None or (isinstance(value, str) and value.strip() == ''):
                return None
            return value
        except (AttributeError, Exception):
            return None
    
    @property
    def full_name(self):
        """Returns the patient's full name"""
        # Use legacy name field if structured name fields aren't available
        legacy_name = self.get_encrypted_field('name')
        given_name = self.get_encrypted_field('given_name')
        family_name = self.get_encrypted_field('family_name')
        
        if not given_name and not family_name and legacy_name:
            return legacy_name
            
        name_parts = []
        name_prefix = self.get_encrypted_field('name_prefix')
        middle_name = self.get_encrypted_field('middle_name')
        name_suffix = self.get_encrypted_field('name_suffix')
        
        if name_prefix:
            name_parts.append(name_prefix)
        if given_name:
            name_parts.append(given_name)
        if middle_name:
            name_parts.append(middle_name)
        if family_name:
            name_parts.append(family_name)
        if name_suffix:
            name_parts.append(name_suffix)
        
        return " ".join(name_parts) if name_parts else "Unknown Patient"
    
    def get_full_name(self):
        return self.full_name

    @property
    def age(self):
        """Calculate patient age from birth_date"""
        if not self.birth_date:
            return None
        today = timezone.now().date()
        return today.year - self.birth_date.year - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
    
    @property
    def full_address(self):
        """Returns formatted full address"""
        address_parts = []
        
        address_line1 = self.get_encrypted_field('address_line1')
        address_line2 = self.get_encrypted_field('address_line2')
        city = self.get_encrypted_field('city')
        state_province = self.get_encrypted_field('state_province')
        postal_code = self.get_encrypted_field('postal_code')
        
        if address_line1:
            address_parts.append(address_line1)
        if address_line2:
            address_parts.append(address_line2)
        if city:
            address_parts.append(city)
        if state_province:
            address_parts.append(state_province)
        if postal_code:
            address_parts.append(postal_code)
        if self.country:
            address_parts.append(self.country)
            
        return ", ".join(address_parts)
    
    def get_primary_identifier(self):
        """Returns the primary identifier for FHIR integration"""
        mrn = self.get_encrypted_field('medical_record_number')
        national_id = self.get_encrypted_field('national_id')
        
        return mrn or national_id or self.patient_id
    
    def to_fhir_dict(self):
        """Convert patient data to FHIR-compatible dictionary structure (FIXED VERSION)"""
        fhir_data = {
            "resourceType": "Patient",
            "id": self.patient_id,
            "active": self.active,
        }
        
        # === IDENTIFIERS - Fixed structure ===
        identifiers = []
        
        # Primary identifier (MRN/Patient ID)
        primary_id = self.get_primary_identifier()
        if primary_id:
            identifiers.append({
                "use": "usual",
                "type": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/v2-0203", 
                        "code": "MR",
                        "display": "Medical Record Number"
                    }]
                },
                "value": primary_id
            })
        
        # National ID as additional identifier
        national_id = self.get_encrypted_field('national_id')
        if national_id and national_id != primary_id:
            identifiers.append({
                "use": "official",
                "type": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                        "code": "SB",
                        "display": "Social Beneficiary Identifier"
                    }]
                },
                "value": national_id
            })
        
        if identifiers:
            fhir_data["identifier"] = identifiers
        
        # === NAME - Fixed structure ===
        names = []
        given_name = self.get_encrypted_field('given_name')
        family_name = self.get_encrypted_field('family_name')
        middle_name = self.get_encrypted_field('middle_name')
        name_prefix = self.get_encrypted_field('name_prefix')
        name_suffix = self.get_encrypted_field('name_suffix')
        legacy_name = self.get_encrypted_field('name')
        
        if given_name or family_name:
            name_data = {"use": "official"}
            
            # Family name (required if we have structured names)
            if family_name:
                name_data["family"] = family_name
            
            # Given names array
            given_names = []
            if given_name:
                given_names.append(given_name)
            if middle_name:
                given_names.append(middle_name)
            if given_names:
                name_data["given"] = given_names
            
            # Prefix array
            if name_prefix:
                name_data["prefix"] = [name_prefix]
            
            # Suffix array  
            if name_suffix:
                name_data["suffix"] = [name_suffix]
            
            names.append(name_data)
            
        elif legacy_name:
            # Handle legacy name field
            name_parts = legacy_name.strip().split()
            if name_parts:
                name_data = {"use": "official"}
                
                if len(name_parts) == 1:
                    # Single name - use as both given and family
                    name_data["family"] = name_parts[0]
                    name_data["given"] = [name_parts[0]]
                else:
                    # Multiple parts - last is family, rest are given
                    name_data["family"] = name_parts[-1]
                    name_data["given"] = name_parts[:-1]
                
                names.append(name_data)
        
        if names:
            fhir_data["name"] = names
        
        # === GENDER ===
        if self.gender and self.gender != "unknown":
            fhir_data["gender"] = self.gender
        
        # === BIRTH DATE ===
        if self.birth_date:
            fhir_data["birthDate"] = self.birth_date.isoformat()
        
        # === TELECOM - Fixed structure ===
        telecom = []
        primary_phone = self.get_encrypted_field('primary_phone')
        secondary_phone = self.get_encrypted_field('secondary_phone')
        email = self.get_encrypted_field('email')
        
        if primary_phone:
            telecom.append({
                "system": "phone",
                "value": primary_phone,
                "use": "home"
            })
        
        if secondary_phone:
            telecom.append({
                "system": "phone", 
                "value": secondary_phone,
                "use": "work"
            })
        
        if email:
            telecom.append({
                "system": "email",
                "value": email,
                "use": "home"
            })
        
        if telecom:
            fhir_data["telecom"] = telecom
        
        # === ADDRESS - Fixed structure ===
        addresses = []
        address_line1 = self.get_encrypted_field('address_line1')
        address_line2 = self.get_encrypted_field('address_line2')
        city = self.get_encrypted_field('city')
        state_province = self.get_encrypted_field('state_province')
        postal_code = self.get_encrypted_field('postal_code')
        
        # Only create address if we have meaningful data
        if any([address_line1, address_line2, city, state_province, postal_code]):
            address_data = {
                "use": "home",
                "type": "physical"
            }
            
            # Address lines array
            lines = []
            if address_line1:
                lines.append(address_line1)
            if address_line2:
                lines.append(address_line2)
            if lines:
                address_data["line"] = lines
            
            # Other address components
            if city:
                address_data["city"] = city
            if state_province:
                address_data["state"] = state_province
            if postal_code:
                address_data["postalCode"] = postal_code
            if self.country:
                address_data["country"] = self.country
            
            addresses.append(address_data)
        
        if addresses:
            fhir_data["address"] = addresses
        
        # === MARITAL STATUS ===
        if self.marital_status and self.marital_status != "unknown":
            marital_status_codes = {
                "single": "S",
                "married": "M", 
                "divorced": "D",
                "widowed": "W",
                "separated": "L"
            }
            code = marital_status_codes.get(self.marital_status, self.marital_status)
            fhir_data["maritalStatus"] = {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v3-MaritalStatus",
                    "code": code,
                    "display": self.marital_status.title()
                }]
            }
        
        # === DECEASED STATUS ===
        if self.deceased:
            if self.deceased_date:
                fhir_data["deceasedDateTime"] = self.deceased_date.isoformat()
            else:
                fhir_data["deceasedBoolean"] = True
        
        # === EXTENSIONS ===
        extensions = []
        
        # Last arrived extension
        if self.last_arrived:
            extensions.append({
                "url": "http://example.org/fhir/StructureDefinition/last-arrived",
                "valueDate": self.last_arrived.isoformat()
            })
        
        # Blood type extension
        blood_type = self.get_encrypted_field('blood_type')
        if blood_type:
            extensions.append({
                "url": "http://example.org/fhir/StructureDefinition/blood-type",
                "valueString": blood_type
            })
        
        # Allergies extension
        allergies = self.get_encrypted_field('allergies')
        if allergies:
            extensions.append({
                "url": "http://example.org/fhir/StructureDefinition/allergies",
                "valueString": allergies
            })
        
        # Emergency contact extension
        emergency_contact_name = self.get_encrypted_field('emergency_contact_name')
        emergency_contact_phone = self.get_encrypted_field('emergency_contact_phone')
        emergency_contact_relationship = self.get_encrypted_field('emergency_contact_relationship')
        
        if any([emergency_contact_name, emergency_contact_phone, emergency_contact_relationship]):
            emergency_contact = {}
            if emergency_contact_name:
                emergency_contact["name"] = emergency_contact_name
            if emergency_contact_phone:
                emergency_contact["phone"] = emergency_contact_phone
            if emergency_contact_relationship:
                emergency_contact["relationship"] = emergency_contact_relationship
            
            extensions.append({
                "url": "http://example.org/fhir/StructureDefinition/emergency-contact",
                "valueString": str(emergency_contact)  # Convert to string for FHIR
            })
        
        # Preferred language extension
        if self.preferred_language and self.preferred_language != "en":
            extensions.append({
                "url": "http://example.org/fhir/StructureDefinition/preferred-language",
                "valueCode": self.preferred_language
            })
        
        if extensions:
            fhir_data["extension"] = extensions
        
        return fhir_data
    
    def to_json(self):
        """Legacy method for backward compatibility - delegates to to_fhir_dict"""
        return self.to_fhir_dict()
    
    def save(self, *args, **kwargs):
        """Override save to generate patient_id and handle legacy name field"""
        if not self.patient_id:
            # Generate a unique patient ID
            self.patient_id = f"PAT-{str(uuid.uuid4())[:8].upper()}"
        
        # If legacy name field is provided but structured fields aren't, populate them
        legacy_name = self.get_encrypted_field('name')
        given_name = self.get_encrypted_field('given_name')
        family_name = self.get_encrypted_field('family_name')
        
        if legacy_name and not given_name and not family_name:
            name_parts = legacy_name.strip().split()
            if len(name_parts) >= 2:
                self.given_name = name_parts[0]
                self.family_name = name_parts[-1]
                if len(name_parts) > 2:
                    self.middle_name = " ".join(name_parts[1:-1])
            elif len(name_parts) == 1:
                self.given_name = name_parts[0]
                self.family_name = name_parts[0]  # Use same for both if only one name
        
        # Ensure legacy name field is populated from structured fields
        if not legacy_name and (given_name or family_name):
            self.name = self.full_name
        
        super().save(*args, **kwargs)


class FHIRSyncTask(models.Model):
    resource_type = models.CharField(max_length=100, default="Patient")
    resource_id = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=[
        ("pending", "Pending"),
        ("synced", "Synced"),
        ("failed", "Failed"),
    ], default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    synced_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True, help_text="Error details if sync failed")
    retry_count = models.IntegerField(default=0)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['resource_type', 'status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.resource_type} - {self.resource_id} ({self.status})"