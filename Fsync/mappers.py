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
        
        # Use model's to_fhir_dict if available
        if hasattr(observation, 'to_fhir_dict'):
            fhir_data = observation.to_fhir_dict()
        else:
            # Manual mapping as fallback
            fhir_data = {
                "resourceType": "Observation",
                "id": str(observation.id),
                "status": "final",  # Default to final
            }
        
        # Ensure required fields are present
        
        # Add category (required by many FHIR servers)
        if "category" not in fhir_data:
            fhir_data["category"] = [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                    "code": "vital-signs",
                    "display": "Vital Signs"
                }]
            }]
        
        # Ensure subject reference
        if hasattr(observation, 'patient') and observation.patient:
            if "subject" not in fhir_data or not fhir_data["subject"]:
                fhir_data["subject"] = {
                    "reference": f"Patient/{observation.patient.patient_id}"
                }
        
        # Ensure encounter reference if available
        if hasattr(observation, 'encounter') and observation.encounter:
            if "encounter" not in fhir_data or not fhir_data["encounter"]:
                fhir_data["encounter"] = {
                    "reference": f"Encounter/{observation.encounter.id}"
                }
        
        # Handle observation time (map from observation_time to effectiveDateTime)
        if hasattr(observation, 'observation_time') and observation.observation_time:
            fhir_data["effectiveDateTime"] = cls.format_datetime(observation.observation_time)
        elif "effectiveDateTime" not in fhir_data:
            # Use current time as fallback
            fhir_data["effectiveDateTime"] = cls.format_datetime(timezone.now())
        
        # Handle code
        if hasattr(observation, 'code') and observation.code:
            if "code" not in fhir_data or not fhir_data["code"]:
                fhir_data["code"] = {
                    "coding": [{
                        "system": "http://loinc.org",  # Default to LOINC
                        "code": observation.code,
                        "display": observation.code
                    }],
                    "text": observation.code
                }
        
        # Handle value and unit
        if hasattr(observation, 'value') and hasattr(observation, 'unit'):
            # Try to parse as numeric for valueQuantity
            try:
                numeric_value = float(observation.value)
                fhir_data["valueQuantity"] = {
                    "value": numeric_value,
                    "unit": observation.unit or "",
                    "system": "http://unitsofmeasure.org",
                    "code": observation.unit or ""
                }
                # Remove valueString if it exists
                fhir_data.pop("valueString", None)
            except (ValueError, TypeError):
                # Fall back to string value if not numeric
                fhir_data["valueString"] = str(observation.value)
                fhir_data.pop("valueQuantity", None)
        elif hasattr(observation, 'value'):
            fhir_data["valueString"] = str(observation.value)
        
        return fhir_data
    
class ConditionMapper(FHIRMapper):
    """Mapper for Condition resources"""

    @classmethod
    def to_fhir(cls, condition) -> Dict[str, Any]:
        """Convert Condition model to FHIR Condition resource"""
        
        # Use model's to_fhir_dict if available
        if hasattr(condition, 'to_fhir_dict'):
            return condition.to_fhir_dict()
        
        # Manual mapping
        fhir_data = {
            "resourceType": "Condition",
            "id": str(condition.id),
        }
        
        # Clinical status (required)
        status = getattr(condition, 'status', 'active')
        fhir_data["clinicalStatus"] = {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                "code": status.lower() if status.lower() in ['active', 'recurrence', 'relapse', 'inactive', 'remission', 'resolved'] else 'active'
            }]
        }
        
        # Subject (required)
        if hasattr(condition, 'patient') and condition.patient:
            fhir_data["subject"] = {
                "reference": f"Patient/{condition.patient.patient_id}"
            }
        
        # Code
        if hasattr(condition, 'code') and condition.code:
            fhir_data["code"] = {
                "coding": [{
                    "system": "http://snomed.info/sct",  # Default to SNOMED
                    "code": condition.code,
                    "display": getattr(condition, 'description', condition.code)
                }],
                "text": getattr(condition, 'description', condition.code)
            }
        
        # Encounter
        if hasattr(condition, 'encounter') and condition.encounter:
            fhir_data["encounter"] = {
                "reference": f"Encounter/{condition.encounter.id}"
            }
        
        # Onset date
        if hasattr(condition, 'onset_date') and condition.onset_date:
            fhir_data["onsetDateTime"] = cls.format_date(condition.onset_date) + "T00:00:00Z"
        
        return fhir_data
    
    
# Registry of mappers
FHIR_MAPPERS = {
    'Patient': PatientMapper,
    'Encounter': EncounterMapper,
    'Observation': ObservationMapper,
    'Condition': ConditionMapper, #need to implement ConditionMapper
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