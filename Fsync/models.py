# models.py

from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
import json

class FHIRSyncConfig(models.Model):
    """Configuration for FHIR server connection"""
    name = models.CharField(max_length=100, unique=True)
    base_url = models.URLField(help_text="FHIR server base URL")
    timeout = models.IntegerField(default=30, help_text="Request timeout in seconds")
    retry_attempts = models.IntegerField(default=3)
    retry_delay = models.IntegerField(default=5, help_text="Delay between retries in seconds")
    is_active = models.BooleanField(default=True)
    
    # Authentication
    auth_type = models.CharField(max_length=20, choices=[
        ('none', 'No Authentication'),
        ('basic', 'Basic Auth'),
        ('bearer', 'Bearer Token'),
        ('oauth2', 'OAuth2')
    ], default='none')
    auth_credentials = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "FHIR Sync Configuration"
        verbose_name_plural = "FHIR Sync Configurations"
    
    def __str__(self):
        return f"{self.name} - {self.base_url}"

class SyncRule(models.Model):
    """Rules for syncing specific resource types"""
    RESOURCE_TYPES = [
        ('Patient', 'Patient'),
        ('Practitioner', 'Practitioner'),
        ('Encounter', 'Encounter'),
        ('Observation', 'Observation'),
        ('Condition', 'Condition'),
        ('MedicationStatement', 'MedicationStatement'),
        ('AllergyIntolerance', 'AllergyIntolerance'),
        ('Procedure', 'Procedure'),
        ('Immunization', 'Immunization'),
    ]
    
    resource_type = models.CharField(max_length=50, choices=RESOURCE_TYPES)
    hms_model_app = models.CharField(max_length=100, help_text="Django app name")
    hms_model_name = models.CharField(max_length=100, help_text="Django model name")
    
    # Sync settings
    is_enabled = models.BooleanField(default=True)
    sync_frequency = models.CharField(max_length=20, choices=[
        ('manual', 'Manual Only'),
        ('realtime', 'Real-time'),
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly')
    ], default='manual')
    
    # Filtering
    sync_filter = models.JSONField(default=dict, blank=True, 
                                 help_text="Django ORM filter conditions")
    
    # Mapping configuration
    field_mappings = models.JSONField(default=dict, blank=True,
                                    help_text="Custom field mappings")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['resource_type', 'hms_model_app', 'hms_model_name']
        verbose_name = "Sync Rule"
        verbose_name_plural = "Sync Rules"
    
    def __str__(self):
        return f"{self.resource_type} - {self.hms_model_app}.{self.hms_model_name}"

class SyncQueue(models.Model):
    """Queue for tracking sync operations"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    OPERATION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
    ]
    
    # Queue metadata
    id = models.AutoField(primary_key=True)
    resource_type = models.CharField(max_length=50)
    resource_id = models.CharField(max_length=100)
    operation = models.CharField(max_length=10, choices=OPERATION_CHOICES, default='create')
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.IntegerField(default=100, help_text="Lower numbers = higher priority")
    
    # Sync data
    sync_rule = models.ForeignKey(SyncRule, on_delete=models.CASCADE, null=True, blank=True)
    fhir_data = models.JSONField(help_text="FHIR resource JSON")
    
    # Generic FK to HMS model instance
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    source_object = GenericForeignKey('content_type', 'object_id')
    
    # Execution tracking
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=3)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    scheduled_at = models.DateTimeField(default=timezone.now)
    
    # Results
    fhir_id = models.CharField(max_length=100, blank=True, null=True,
                              help_text="ID returned by FHIR server")
    error_message = models.TextField(blank=True, null=True)
    response_data = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['priority', 'created_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['resource_type', 'status']),
            models.Index(fields=['scheduled_at']),
        ]
        verbose_name = "Sync Queue Item"
        verbose_name_plural = "Sync Queue Items"
    
    def __str__(self):
        return f"{self.resource_type} {self.resource_id} - {self.status}"
    
    def can_retry(self):
        return self.attempts < self.max_attempts and self.status == 'failed'
    
    def mark_processing(self):
        self.status = 'processing'
        self.attempts += 1
        self.last_attempt_at = timezone.now()
        self.save()
    
    def mark_success(self, fhir_id=None, response_data=None):
        self.status = 'success'
        self.completed_at = timezone.now()
        self.error_message = None
        if fhir_id:
            self.fhir_id = fhir_id
        if response_data:
            self.response_data = response_data
        self.save()
    
    def mark_failed(self, error_message, response_data=None):
        self.status = 'failed'
        self.error_message = error_message
        if response_data:
            self.response_data = response_data
        self.save()

class SyncLog(models.Model):
    """Detailed logging for sync operations"""
    queue_item = models.ForeignKey(SyncQueue, on_delete=models.CASCADE, related_name='logs')
    level = models.CharField(max_length=10, choices=[
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
    ], default='INFO')
    message = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Sync Log"
        verbose_name_plural = "Sync Logs"# models.py

from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
import json

class FHIRSyncConfig(models.Model):
    """Configuration for FHIR server connection"""
    name = models.CharField(max_length=100, unique=True)
    base_url = models.URLField(help_text="FHIR server base URL")
    timeout = models.IntegerField(default=30, help_text="Request timeout in seconds")
    retry_attempts = models.IntegerField(default=3)
    retry_delay = models.IntegerField(default=5, help_text="Delay between retries in seconds")
    is_active = models.BooleanField(default=True)
    
    # Authentication
    auth_type = models.CharField(max_length=20, choices=[
        ('none', 'No Authentication'),
        ('basic', 'Basic Auth'),
        ('bearer', 'Bearer Token'),
        ('oauth2', 'OAuth2')
    ], default='none')
    auth_credentials = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "FHIR Sync Configuration"
        verbose_name_plural = "FHIR Sync Configurations"
    
    def __str__(self):
        return f"{self.name} - {self.base_url}"

class SyncRule(models.Model):
    """Rules for syncing specific resource types"""
    RESOURCE_TYPES = [
        ('Patient', 'Patient'),
        ('Practitioner', 'Practitioner'),
        ('Encounter', 'Encounter'),
        ('Observation', 'Observation'),
        ('Condition', 'Condition'),
        ('MedicationStatement', 'MedicationStatement'),
        ('AllergyIntolerance', 'AllergyIntolerance'),
        ('Procedure', 'Procedure'),
        ('Immunization', 'Immunization'),
    ]
    
    resource_type = models.CharField(max_length=50, choices=RESOURCE_TYPES)
    hms_model_app = models.CharField(max_length=100, help_text="Django app name")
    hms_model_name = models.CharField(max_length=100, help_text="Django model name")
    
    # Sync settings
    is_enabled = models.BooleanField(default=True)
    sync_frequency = models.CharField(max_length=20, choices=[
        ('manual', 'Manual Only'),
        ('realtime', 'Real-time'),
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly')
    ], default='manual')
    
    # Filtering
    sync_filter = models.JSONField(default=dict, blank=True, 
                                 help_text="Django ORM filter conditions")
    
    # Enhanced field mapping configuration
    field_mappings = models.JSONField(default=dict, blank=True,
                                    help_text="Custom field mappings from HMS to FHIR")
    
    # Default field mappings for Patient resource type
    default_patient_mappings = models.JSONField(default=dict, blank=True,
                                              help_text="Default Patient field mappings")
    
    # Advanced mapping options
    transform_rules = models.JSONField(default=dict, blank=True,
                                     help_text="Field transformation rules")
    
    # Validation rules
    validation_rules = models.JSONField(default=dict, blank=True,
                                      help_text="Data validation rules before sync")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['resource_type', 'hms_model_app', 'hms_model_name']
        verbose_name = "Sync Rule"
        verbose_name_plural = "Sync Rules"
    
    def __str__(self):
        return f"{self.resource_type} - {self.hms_model_app}.{self.hms_model_name}"
    
    def get_default_patient_field_mappings(self):
        """Return default field mappings for Patient resource"""
        return {
            # Core identity fields
            'patient_id': 'id',
            'fhir_id': 'id',
            
            # Name fields - map to FHIR name array
            'given_name': 'name[0].given[0]',
            'family_name': 'name[0].family',
            'middle_name': 'name[0].given[1]',
            'name_prefix': 'name[0].prefix[0]',
            'name_suffix': 'name[0].suffix[0]',
            'name': 'name[0].text',  # Legacy field
            
            # Core demographics
            'gender': 'gender',
            'birth_date': 'birthDate',
            
            # Identifiers
            'national_id': 'identifier[national_id].value',
            'medical_record_number': 'identifier[mrn].value',
            'insurance_number': 'identifier[insurance].value',
            
            # Contact information - map to telecom array
            'primary_phone': 'telecom[phone_home].value',
            'secondary_phone': 'telecom[phone_work].value',
            'email': 'telecom[email].value',
            
            # Address fields - map to address array
            'address_line1': 'address[0].line[0]',
            'address_line2': 'address[0].line[1]',
            'city': 'address[0].city',
            'state_province': 'address[0].state',
            'postal_code': 'address[0].postalCode',
            'country': 'address[0].country',
            
            # Additional demographics
            'marital_status': 'maritalStatus.coding[0].code',
            'preferred_language': 'communication[0].language.coding[0].code',
            
            # Emergency contact - map to contact array
            'emergency_contact_name': 'contact[0].name.text',
            'emergency_contact_relationship': 'contact[0].relationship[0].coding[0].code',
            'emergency_contact_phone': 'contact[0].telecom[0].value',
            
            # Clinical information - map to extensions
            'blood_type': 'extension[blood_type].valueString',
            'allergies': 'extension[allergies].valueString',
            
            # Status fields
            'active': 'active',
            'deceased': 'deceasedBoolean',
            'deceased_date': 'deceasedDateTime',
            
            # Practice management - map to extensions
            'last_arrived': 'extension[last_arrived].valueDate',
            'registration_date': 'extension[registration_date].valueDateTime',
            
            # Metadata - map to meta
            'created_at': 'meta.lastUpdated',
            'updated_at': 'meta.lastUpdated',
        }
    
    def get_effective_field_mappings(self):
        """Get the effective field mappings, combining defaults with custom mappings"""
        if self.resource_type == 'Patient':
            default_mappings = self.get_default_patient_field_mappings()
            # Merge with custom mappings, custom takes precedence
            effective_mappings = {**default_mappings, **self.field_mappings}
            return effective_mappings
        return self.field_mappings
    
    def get_transform_rules(self):
        """Get transformation rules for field values"""
        default_transforms = {}
        if self.resource_type == 'Patient':
            default_transforms = {
                'gender': {
                    'type': 'map',
                    'mapping': {
                        'male': 'male',
                        'female': 'female',
                        'other': 'other',
                        'unknown': 'unknown'
                    }
                },
                'marital_status': {
                    'type': 'map',
                    'mapping': {
                        'single': 'S',
                        'married': 'M',
                        'divorced': 'D',
                        'widowed': 'W',
                        'separated': 'L',
                        'unknown': 'UNK'
                    }
                },
                'birth_date': {
                    'type': 'date_format',
                    'format': 'YYYY-MM-DD'
                },
                'phone_numbers': {
                    'type': 'phone_format',
                    'format': 'international'
                }
            }
        
        # Merge with custom transform rules
        return {**default_transforms, **self.transform_rules}
    
    def get_validation_rules(self):
        """Get validation rules for the resource type"""
        default_validations = {}
        if self.resource_type == 'Patient':
            default_validations = {
                'required_fields': ['given_name', 'family_name'],
                'conditional_required': {
                    'deceased': ['deceased_date']  # If deceased=True, deceased_date is required
                },
                'field_validations': {
                    'email': 'email_format',
                    'primary_phone': 'phone_format',
                    'secondary_phone': 'phone_format',
                    'birth_date': 'date_not_future',
                    'gender': ['male', 'female', 'other', 'unknown']
                }
            }
        
        # Merge with custom validation rules
        return {**default_validations, **self.validation_rules}
    
    def save(self, *args, **kwargs):
        """Override save to populate default mappings for Patient resources"""
        if self.resource_type == 'Patient' and not self.default_patient_mappings:
            self.default_patient_mappings = self.get_default_patient_field_mappings()
        
        super().save(*args, **kwargs)

class SyncQueue(models.Model):
    """Queue for tracking sync operations"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    OPERATION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
    ]
    
    # Queue metadata
    id = models.AutoField(primary_key=True)
    resource_type = models.CharField(max_length=50)
    resource_id = models.CharField(max_length=100)
    operation = models.CharField(max_length=10, choices=OPERATION_CHOICES, default='create')
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.IntegerField(default=100, help_text="Lower numbers = higher priority")
    
    # Sync data
    sync_rule = models.ForeignKey(SyncRule, on_delete=models.CASCADE, null=True, blank=True)
    fhir_data = models.JSONField(help_text="FHIR resource JSON")
    
    # Generic FK to HMS model instance
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    source_object = GenericForeignKey('content_type', 'object_id')
    
    # Execution tracking
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=3)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    scheduled_at = models.DateTimeField(default=timezone.now)
    
    # Results
    fhir_id = models.CharField(max_length=100, blank=True, null=True,
                              help_text="ID returned by FHIR server")
    error_message = models.TextField(blank=True, null=True)
    response_data = models.JSONField(default=dict, blank=True)
    
    # Enhanced tracking for new Patient fields
    field_mapping_used = models.JSONField(default=dict, blank=True,
                                        help_text="Field mappings used for this sync")
    transform_applied = models.JSONField(default=dict, blank=True,
                                       help_text="Transformations applied")
    validation_results = models.JSONField(default=dict, blank=True,
                                        help_text="Validation results")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['priority', 'created_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['resource_type', 'status']),
            models.Index(fields=['scheduled_at']),
        ]
        verbose_name = "Sync Queue Item"
        verbose_name_plural = "Sync Queue Items"
    
    def __str__(self):
        return f"{self.resource_type} {self.resource_id} - {self.status}"
    
    def can_retry(self):
        return self.attempts < self.max_attempts and self.status == 'failed'
    
    def mark_processing(self):
        self.status = 'processing'
        self.attempts += 1
        self.last_attempt_at = timezone.now()
        self.save()
    
    def mark_success(self, fhir_id=None, response_data=None):
        self.status = 'success'
        self.completed_at = timezone.now()
        self.error_message = None
        if fhir_id:
            self.fhir_id = fhir_id
        if response_data:
            self.response_data = response_data
        self.save()
    
    def mark_failed(self, error_message, response_data=None):
        self.status = 'failed'
        self.error_message = error_message
        if response_data:
            self.response_data = response_data
        self.save()

class SyncLog(models.Model):
    """Detailed logging for sync operations"""
    queue_item = models.ForeignKey(SyncQueue, on_delete=models.CASCADE, related_name='logs')
    level = models.CharField(max_length=10, choices=[
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
    ], default='INFO')
    message = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Sync Log"
        verbose_name_plural = "Sync Logs"