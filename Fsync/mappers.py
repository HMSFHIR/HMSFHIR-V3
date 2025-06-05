# ============================================================================
# mappers.py - FHIR Resource Mappers
# ============================================================================
from typing import Dict, Any, Optional
from django.db import models
from datetime import datetime
from django.utils import timezone

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

class PatientMapper(FHIRMapper):
    """Map HMS Patient to FHIR Patient"""
    
    @staticmethod
    def to_fhir(patient) -> Dict[str, Any]:
        """Convert Patient model to FHIR Patient resource"""
        
        # Handle existing to_json method if available
        if hasattr(patient, 'to_json'):
            return patient.to_json()
        
        # Parse name
        name_parts = patient.name.split() if hasattr(patient, 'name') else []
        family = name_parts[-1] if len(name_parts) > 1 else (patient.name if hasattr(patient, 'name') else '')
        given = name_parts[:-1] if len(name_parts) > 1 else []
        
        return {
            "resourceType": "Patient",
            "id": str(getattr(patient, 'patient_id', patient.id)),
            "identifier": [
                {
                    "use": "usual",
                    "value": str(getattr(patient, 'patient_id', patient.id)),
                    "system": "http://hospital.example.org/patient-id"
                }
            ],
            "name": [
                {
                    "use": "official",
                    "family": family,
                    "given": given
                }
            ],
            "telecom": [
                {
                    "system": "phone",
                    "value": PatientMapper.safe_get_attr(patient, 'phone'),
                    "use": "home"
                },
                {
                    "system": "email",
                    "value": PatientMapper.safe_get_attr(patient, 'email'),
                    "use": "home"
                }
            ],
            "gender": PatientMapper._map_gender(PatientMapper.safe_get_attr(patient, 'gender')),
            "birthDate": PatientMapper.format_date(PatientMapper.safe_get_attr(patient, 'date_of_birth')),
            "address": [
                {
                    "use": "home",
                    "text": PatientMapper.safe_get_attr(patient, 'address'),
                    "city": PatientMapper.safe_get_attr(patient, 'city'),
                    "state": PatientMapper.safe_get_attr(patient, 'state'),
                    "country": PatientMapper.safe_get_attr(patient, 'country')
                }
            ] if PatientMapper.safe_get_attr(patient, 'address') else []
        }
    
    @staticmethod
    def _map_gender(gender: str) -> str:
        """Map gender to FHIR values"""
        if not gender:
            return "unknown"
        
        gender_map = {
            'M': 'male',
            'F': 'female',
            'Male': 'male',
            'Female': 'female',
            'male': 'male',
            'female': 'female'
        }
        return gender_map.get(gender, 'unknown')

class PractitionerMapper(FHIRMapper):
    """Map HMS Practitioner to FHIR Practitioner"""
    
    @staticmethod
    def to_fhir(practitioner) -> Dict[str, Any]:
        name_parts = practitioner.name.split() if hasattr(practitioner, 'name') else []
        family = name_parts[-1] if len(name_parts) > 1 else (practitioner.name if hasattr(practitioner, 'name') else '')
        given = name_parts[:-1] if len(name_parts) > 1 else []
        
        return {
            "resourceType": "Practitioner",
            "id": str(getattr(practitioner, 'practitioner_id', practitioner.id)),
            "identifier": [
                {
                    "use": "official",
                    "value": str(getattr(practitioner, 'practitioner_id', practitioner.id)),
                    "system": "http://hospital.example.org/practitioner-id"
                }
            ],
            "name": [
                {
                    "use": "official",
                    "family": family,
                    "given": given
                }
            ],
            "telecom": [
                {
                    "system": "phone",
                    "value": PractitionerMapper.safe_get_attr(practitioner, 'phone'),
                    "use": "work"
                },
                {
                    "system": "email",
                    "value": PractitionerMapper.safe_get_attr(practitioner, 'email'),
                    "use": "work"
                }
            ],
            "qualification": [
                {
                    "code": {
                        "text": PractitionerMapper.safe_get_attr(practitioner, 'role', '').title()
                    }
                }
            ] if PractitionerMapper.safe_get_attr(practitioner, 'role') else []
        }

# Registry of all mappers
FHIR_MAPPERS = {
    'Patient': PatientMapper.to_fhir,
    'Practitioner': PractitionerMapper.to_fhir,
    # Add other mappers here...
}
