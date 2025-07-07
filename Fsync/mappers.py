# ============================================================================
# mappers.py - FHIR Resource Mappers
# ============================================================================
from typing import Dict, Any, Optional, List
from django.db import models
from datetime import datetime
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class FHIRMapper:
    """Base class for FHIR resource mappers"""
    
    @staticmethod
    def safe_get_attr(obj, attr_path: str, default=None):
        """Safely get nested attribute from object"""
        try:
            attrs = attr_path.split('.')
            result = obj
            for attr in attrs:
                result = getattr(result, attr, default)
                if result is None:
                    return default
            return result
        except (AttributeError, TypeError):
            return default
    
    @staticmethod
    def format_datetime(dt) -> Optional[str]:
        """Format datetime for FHIR"""
        if dt is None:
            return None
        if isinstance(dt, str):
            return dt
        return dt.isoformat()
    
    @staticmethod
    def format_date(dt) -> Optional[str]:
        """Format date for FHIR"""
        if dt is None:
            return None
        if isinstance(dt, str):
            return dt
        return dt.strftime('%Y-%m-%d')

    @staticmethod
    def safe_get_encrypted_field(obj, field_name: str, default=None):
        """Safely get encrypted field value from object"""
        try:
            if hasattr(obj, 'get_encrypted_field'):
                value = obj.get_encrypted_field(field_name)
                return value if value is not None else default
            else:
                return getattr(obj, field_name, default)
        except Exception as e:
            logger.warning(f"Could not get encrypted field {field_name}: {e}")
            return default


class PatientMapper(FHIRMapper):
    """Mapper for Patient resources with encryption support"""
    
    @classmethod
    def to_fhir(cls, patient) -> Dict[str, Any]:
        """Convert Patient model to FHIR Patient resource"""
        try:
            # Use the Patient model's built-in FHIR conversion method
            if hasattr(patient, 'to_fhir_dict'):
                return patient.to_fhir_dict()
            
            # Fallback manual mapping for encrypted fields
            return cls._manual_patient_mapping(patient)
            
        except Exception as e:
            logger.error(f"Error mapping patient to FHIR: {e}")
            # Return minimal valid FHIR resource
            return {
                "resourceType": "Patient",
                "id": getattr(patient, 'patient_id', None),
                "active": getattr(patient, 'active', True)
            }
    
    @classmethod
    def _manual_patient_mapping(cls, patient) -> Dict[str, Any]:
        """Manual mapping for Patient with encrypted fields"""
        fhir_data = {
            "resourceType": "Patient",
            "id": getattr(patient, 'patient_id', None),
            "active": getattr(patient, 'active', True),
        }
        
        # Handle name with encrypted fields
        given_name = cls.safe_get_encrypted_field(patient, 'given_name')
        family_name = cls.safe_get_encrypted_field(patient, 'family_name')
        middle_name = cls.safe_get_encrypted_field(patient, 'middle_name')
        name_prefix = cls.safe_get_encrypted_field(patient, 'name_prefix')
        name_suffix = cls.safe_get_encrypted_field(patient, 'name_suffix')
        
        if given_name or family_name:
            name_data = {"use": "official"}
            if family_name:
                name_data["family"] = family_name
            if given_name:
                name_data["given"] = [given_name]
                if middle_name:
                    name_data["given"].append(middle_name)
            if name_prefix:
                name_data["prefix"] = [name_prefix]
            if name_suffix:
                name_data["suffix"] = [name_suffix]
            
            fhir_data["name"] = [name_data]
        
        # Handle gender
        if hasattr(patient, 'gender') and patient.gender and patient.gender != "unknown":
            fhir_data["gender"] = patient.gender
        
        # Handle birth date
        if hasattr(patient, 'birth_date') and patient.birth_date:
            fhir_data["birthDate"] = cls.format_date(patient.birth_date)
        
        # Handle telecom with encrypted fields
        telecom = []
        primary_phone = cls.safe_get_encrypted_field(patient, 'primary_phone')
        secondary_phone = cls.safe_get_encrypted_field(patient, 'secondary_phone')
        email = cls.safe_get_encrypted_field(patient, 'email')
        
        if primary_phone:
            telecom.append({"system": "phone", "value": primary_phone, "use": "home"})
        if secondary_phone:
            telecom.append({"system": "phone", "value": secondary_phone, "use": "work"})
        if email:
            telecom.append({"system": "email", "value": email})
        
        if telecom:
            fhir_data["telecom"] = telecom
        
        # Handle address with encrypted fields
        address_line1 = cls.safe_get_encrypted_field(patient, 'address_line1')
        address_line2 = cls.safe_get_encrypted_field(patient, 'address_line2')
        city = cls.safe_get_encrypted_field(patient, 'city')
        state_province = cls.safe_get_encrypted_field(patient, 'state_province')
        postal_code = cls.safe_get_encrypted_field(patient, 'postal_code')
        
        if any([address_line1, city, state_province, postal_code]):
            address_data = {"use": "home", "type": "physical"}
            
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
            if hasattr(patient, 'country') and patient.country:
                address_data["country"] = patient.country
            
            fhir_data["address"] = [address_data]
        
        # Handle identifiers with encrypted fields
        identifiers = []
        
        # Primary identifier
        primary_id = patient.patient_id
        if primary_id:
            identifiers.append({
                "use": "usual",
                "type": {
                    "coding": [{"system": "http://terminology.hl7.org/CodeSystem/v2-0203", "code": "MR"}]
                },
                "value": primary_id
            })
        
        # National ID
        national_id = cls.safe_get_encrypted_field(patient, 'national_id')
        if national_id:
            identifiers.append({
                "use": "official",
                "type": {"text": "National ID"},
                "value": national_id,
                "system": "http://example.org/national-id"
            })
        
        # Medical Record Number
        mrn = cls.safe_get_encrypted_field(patient, 'medical_record_number')
        if mrn:
            identifiers.append({
                "use": "usual",
                "type": {
                    "coding": [{"system": "http://terminology.hl7.org/CodeSystem/v2-0203", "code": "MR"}]
                },
                "value": mrn
            })
        
        if identifiers:
            fhir_data["identifier"] = identifiers
        
        return fhir_data


class EncounterMapper(FHIRMapper):
    """Mapper for Encounter resources"""
    
    @classmethod
    def to_fhir(cls, encounter) -> Dict[str, Any]:
        """Convert Encounter model to FHIR Encounter resource"""
        return {
            "resourceType": "Encounter",
            "id": str(encounter.id),
            "status": getattr(encounter, 'status', 'unknown'),
            "class": {
                "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                "code": getattr(encounter, 'encounter_class', 'AMB')
            },
            "subject": {
                "reference": f"Patient/{encounter.patient.patient_id}"
            } if hasattr(encounter, 'patient') and encounter.patient else None,
            "period": {
                "start": cls.format_datetime(getattr(encounter, 'start_time', None)),
                "end": cls.format_datetime(getattr(encounter, 'end_time', None))
            }
        }


class ObservationMapper(FHIRMapper):
    """Mapper for Observation resources"""
    
    @classmethod
    def to_fhir(cls, observation) -> Dict[str, Any]:
        """Convert Observation model to FHIR Observation resource"""
        return {
            "resourceType": "Observation",
            "id": str(observation.id),
            "status": getattr(observation, 'status', 'final'),
            "subject": {
                "reference": f"Patient/{observation.patient.patient_id}"
            } if hasattr(observation, 'patient') and observation.patient else None,
            "effectiveDateTime": cls.format_datetime(getattr(observation, 'effective_date_time', None)),
            "code": {
                "coding": [{
                    "system": getattr(observation, 'code_system', None),
                    "code": getattr(observation, 'code', None),
                    "display": getattr(observation, 'code_display', None)
                }]
            },
            "valueString": str(getattr(observation, 'value', ''))
        }


# Registry of mappers
FHIR_MAPPERS = {
    'Patient': PatientMapper,
    'Encounter': EncounterMapper,
    'Observation': ObservationMapper,
}


def get_mapper(resource_type: str) -> Optional[FHIRMapper]:
    """Get mapper for resource type"""
    return FHIR_MAPPERS.get(resource_type)


def map_to_fhir(model_instance, resource_type: str = None) -> Dict[str, Any]:
    """Map Django model instance to FHIR resource"""
    if not resource_type:
        # Try to infer from model name
        resource_type = model_instance._meta.model_name.title()
    
    mapper = get_mapper(resource_type)
    if mapper:
        return mapper.to_fhir(model_instance)
    
    # Fallback for unmapped resources
    logger.warning(f"No mapper found for resource type: {resource_type}")
    return {
        "resourceType": resource_type,
        "id": str(getattr(model_instance, 'id', None))
    }