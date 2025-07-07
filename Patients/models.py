from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from django.conf import settings
from datetime import date
import uuid
from encrypted_model_fields.fields import EncryptedCharField, EncryptedTextField, EncryptedEmailField


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
        """Convert patient data to FHIR-compatible dictionary structure (comprehensive)"""
        fhir_data = {
            "resourceType": "Patient",
            "id": self.patient_id,
            "identifier": [
                {
                    "use": "usual",
                    "type": {
                        "coding": [{"system": "http://terminology.hl7.org/CodeSystem/v2-0203", "code": "MR"}]
                    },
                    "value": self.get_primary_identifier()
                }
            ],
            "active": self.active,
        }
        
        # Add name information - handle encrypted fields safely
        given_name = self.get_encrypted_field('given_name')
        family_name = self.get_encrypted_field('family_name')
        middle_name = self.get_encrypted_field('middle_name')
        name_prefix = self.get_encrypted_field('name_prefix')
        name_suffix = self.get_encrypted_field('name_suffix')
        legacy_name = self.get_encrypted_field('name')
        
        if given_name and family_name:
            name_data = {
                "use": "official",
                "family": family_name,
                "given": [given_name]
            }
            
            if middle_name:
                name_data["given"].append(middle_name)
            if name_prefix:
                name_data["prefix"] = [name_prefix]
            if name_suffix:
                name_data["suffix"] = [name_suffix]
                
            fhir_data["name"] = [name_data]
            
        elif legacy_name:
            # Handle legacy name field
            name_parts = legacy_name.split()
            if len(name_parts) > 1:
                family = name_parts[-1]
                given = name_parts[:-1]
            else:
                family = legacy_name
                given = [legacy_name]
                
            fhir_data["name"] = [
                {
                    "use": "official",
                    "family": family,
                    "given": given
                }
            ]
        
        # Add gender
        if self.gender and self.gender != "unknown":
            fhir_data["gender"] = self.gender
        
        # Add national ID as additional identifier
        national_id = self.get_encrypted_field('national_id')
        if national_id:
            national_id_identifier = {
                "use": "official",
                "type": {
                    "text": "National ID"
                },
                "value": national_id,
                "system": "http://example.org/national-id"
            }
            if "identifier" not in fhir_data:
                fhir_data["identifier"] = []
            fhir_data["identifier"].append(national_id_identifier)
        
        # Add birth date if available
        if self.birth_date:
            fhir_data["birthDate"] = self.birth_date.isoformat()
            
        # Add telecom information - handle encrypted fields safely
        telecom = []
        primary_phone = self.get_encrypted_field('primary_phone')
        secondary_phone = self.get_encrypted_field('secondary_phone')
        email = self.get_encrypted_field('email')
        
        if primary_phone:
            telecom.append({"system": "phone", "value": primary_phone, "use": "home"})
        if secondary_phone:
            telecom.append({"system": "phone", "value": secondary_phone, "use": "work"})
        if email:
            telecom.append({"system": "email", "value": email})
            
        if telecom:
            fhir_data["telecom"] = telecom
            
        # Add address information - handle encrypted fields safely
        address_line1 = self.get_encrypted_field('address_line1')
        address_line2 = self.get_encrypted_field('address_line2')
        city = self.get_encrypted_field('city')
        state_province = self.get_encrypted_field('state_province')
        postal_code = self.get_encrypted_field('postal_code')
        
        if any([address_line1, city, state_province, postal_code]):
            address_data = {
                "use": "home",
                "type": "physical"
            }
            
            if address_line1 or address_line2:
                lines = [line for line in [address_line1, address_line2] if line]
                if lines:
                    address_data["line"] = lines
                    
            if city:
                address_data["city"] = city
            if state_province:
                address_data["state"] = state_province
            if postal_code:
                address_data["postalCode"] = postal_code
            if self.country:
                address_data["country"] = self.country
                
            fhir_data["address"] = [address_data]
        
        # Add marital status
        if self.marital_status and self.marital_status != "unknown":
            fhir_data["maritalStatus"] = {
                "coding": [{"system": "http://terminology.hl7.org/CodeSystem/v3-MaritalStatus", "code": self.marital_status}]
            }
            
        # Add deceased information
        if self.deceased:
            if self.deceased_date:
                fhir_data["deceasedDateTime"] = self.deceased_date.isoformat()
            else:
                fhir_data["deceasedBoolean"] = True
        
        # Add last arrived as extension
        fhir_data["extension"] = [
            {
                "url": "http://example.org/fhir/StructureDefinition/last-arrived",
                "valueDate": self.last_arrived.isoformat() if self.last_arrived else date.today().isoformat()
            }
        ]
                
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