from typing import Dict, Any
from .mappers import FHIRMapper
from .mappers import PatientMapper

class PractitionerMapper(FHIRMapper):
    """Map HMS Practitioner to FHIR Practitioner"""
    
    @staticmethod
    def to_fhir(practitioner) -> Dict[str, Any]:
        # Handle existing to_fhir_dict method if available
        if hasattr(practitioner, 'to_fhir_dict'):
            return practitioner.to_fhir_dict()
        
        # Handle existing to_json method if available
        if hasattr(practitioner, 'to_json'):
            return practitioner.to_json()
        
        # Build name from available fields
        given_name = (PractitionerMapper.safe_get_attr(practitioner, 'given_name') or 
                     PractitionerMapper.safe_get_attr(practitioner, 'first_name'))
        family_name = (PractitionerMapper.safe_get_attr(practitioner, 'family_name') or 
                      PractitionerMapper.safe_get_attr(practitioner, 'last_name'))
        
        # Fall back to legacy name field if structured fields not available
        if not given_name and not family_name and hasattr(practitioner, 'name'):
            name_parts = practitioner.name.split()
            family_name = name_parts[-1] if len(name_parts) > 1 else practitioner.name
            given_name = " ".join(name_parts[:-1]) if len(name_parts) > 1 else ""
        
        names = []
        if given_name or family_name:
            name_data = {
                "use": "official"
            }
            if family_name:
                name_data["family"] = family_name
            if given_name:
                name_data["given"] = [given_name]
            names.append(name_data)
        
        # Build identifiers
        practitioner_id = (PractitionerMapper.safe_get_attr(practitioner, 'practitioner_id') or 
                          str(practitioner.id))
        
        fhir_data = {
            "resourceType": "Practitioner",
            "id": practitioner_id,
            "identifier": [
                {
                    "use": "official",
                    "value": practitioner_id,
                    "system": "http://hospital.example.org/practitioner-id"
                }
            ],
            "active": PractitionerMapper.safe_get_attr(practitioner, 'active', True)
        }
        
        if names:
            fhir_data["name"] = names
        
        # Build telecom
        telecom = []
        
        # Phone
        phone = (PractitionerMapper.safe_get_attr(practitioner, 'primary_phone') or 
                PractitionerMapper.safe_get_attr(practitioner, 'phone'))
        if phone:
            telecom.append({
                "system": "phone",
                "value": phone,
                "use": "work"
            })
        
        # Email
        email = PractitionerMapper.safe_get_attr(practitioner, 'email')
        if email:
            telecom.append({
                "system": "email",
                "value": email,
                "use": "work"
            })
        
        if telecom:
            fhir_data["telecom"] = telecom
        
        # Qualifications
        role = (PractitionerMapper.safe_get_attr(practitioner, 'role') or 
               PractitionerMapper.safe_get_attr(practitioner, 'specialty'))
        if role:
            fhir_data["qualification"] = [
                {
                    "code": {
                        "text": role.title()
                    }
                }
            ]
        
        return fhir_data

# Registry of all mappers
FHIR_MAPPERS = {
    'Patient': PatientMapper.to_fhir,
    'Practitioner': PractitionerMapper.to_fhir,
    # Add other mappers here...
}