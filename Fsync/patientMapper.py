from typing import Dict, Any
from .mappers import FHIRMapper

class PatientMapper(FHIRMapper):
    """Map HMS Patient to FHIR Patient"""
    
    @staticmethod
    def to_fhir(patient) -> Dict[str, Any]:
        """Convert Patient model to FHIR Patient resource"""
        
        # Handle existing to_fhir_dict method if available (from new Patient model)
        if hasattr(patient, 'to_fhir_dict'):
            return patient.to_fhir_dict()
        
        # Handle existing to_json method if available (legacy)
        if hasattr(patient, 'to_json'):
            return patient.to_json()
        
        # Build FHIR resource for cases where model doesn't have built-in methods
        fhir_data = {
            "resourceType": "Patient",
            "id": str(PatientMapper.safe_get_attr(patient, 'patient_id', patient.id)),
            "active": PatientMapper.safe_get_attr(patient, 'active', True)
        }
        
        # Build identifiers array
        identifiers = []
        
        # Primary identifier (patient_id, medical_record_number, or fallback to id)
        primary_id = (PatientMapper.safe_get_attr(patient, 'medical_record_number') or 
                     PatientMapper.safe_get_attr(patient, 'patient_id') or 
                     str(patient.id))
        
        identifiers.append({
            "use": "usual",
            "type": {
                "coding": [{"system": "http://terminology.hl7.org/CodeSystem/v2-0203", "code": "MR"}]
            },
            "value": primary_id,
            "system": "http://hospital.example.org/patient-id"
        })
        
        # National ID if available
        national_id = PatientMapper.safe_get_attr(patient, 'national_id')
        if national_id:
            identifiers.append({
                "use": "official",
                "type": {
                    "text": "National ID"
                },
                "value": national_id,
                "system": "http://example.org/national-id"
            })
        
        # Insurance number if available
        insurance_number = PatientMapper.safe_get_attr(patient, 'insurance_number')
        if insurance_number:
            identifiers.append({
                "use": "secondary",
                "type": {
                    "text": "Insurance Number"
                },
                "value": insurance_number,
                "system": "http://example.org/insurance-id"
            })
        
        fhir_data["identifier"] = identifiers
        
        # Build name array - prioritize structured fields over legacy name field
        names = []
        given_name = PatientMapper.safe_get_attr(patient, 'given_name')
        family_name = PatientMapper.safe_get_attr(patient, 'family_name')
        middle_name = PatientMapper.safe_get_attr(patient, 'middle_name')
        name_prefix = PatientMapper.safe_get_attr(patient, 'name_prefix')
        name_suffix = PatientMapper.safe_get_attr(patient, 'name_suffix')
        
        if given_name or family_name:
            # Use structured name fields
            name_data = {
                "use": "official"
            }
            
            if family_name:
                name_data["family"] = family_name
            
            given_names = []
            if given_name:
                given_names.append(given_name)
            if middle_name:
                given_names.append(middle_name)
            if given_names:
                name_data["given"] = given_names
            
            if name_prefix:
                name_data["prefix"] = [name_prefix]
            
            if name_suffix:
                name_data["suffix"] = [name_suffix]
            
            names.append(name_data)
            
        elif PatientMapper.safe_get_attr(patient, 'name'):
            # Fall back to legacy name field
            name_parts = patient.name.split()
            family = name_parts[-1] if len(name_parts) > 1 else patient.name
            given = name_parts[:-1] if len(name_parts) > 1 else []
            
            names.append({
                "use": "official",
                "family": family,
                "given": given
            })
        
        if names:
            fhir_data["name"] = names
        
        # Gender mapping
        gender = PatientMapper.safe_get_attr(patient, 'gender')
        if gender and gender != "unknown":
            fhir_data["gender"] = PatientMapper._map_gender(gender)
        
        # Birth date
        birth_date = (PatientMapper.safe_get_attr(patient, 'birth_date') or 
                     PatientMapper.safe_get_attr(patient, 'date_of_birth'))
        if birth_date:
            fhir_data["birthDate"] = PatientMapper.format_date(birth_date)
        
        # Build telecom array
        telecom = []
        
        # Primary phone
        primary_phone = (PatientMapper.safe_get_attr(patient, 'primary_phone') or 
                        PatientMapper.safe_get_attr(patient, 'phone'))
        if primary_phone:
            telecom.append({
                "system": "phone",
                "value": primary_phone,
                "use": "home"
            })
        
        # Secondary phone
        secondary_phone = PatientMapper.safe_get_attr(patient, 'secondary_phone')
        if secondary_phone:
            telecom.append({
                "system": "phone",
                "value": secondary_phone,
                "use": "work"
            })
        
        # Email
        email = PatientMapper.safe_get_attr(patient, 'email')
        if email:
            telecom.append({
                "system": "email",
                "value": email,
                "use": "home"
            })
        
        if telecom:
            fhir_data["telecom"] = telecom
        
        # Build address array - prioritize structured fields
        addresses = []
        address_line1 = PatientMapper.safe_get_attr(patient, 'address_line1')
        address_line2 = PatientMapper.safe_get_attr(patient, 'address_line2')
        city = PatientMapper.safe_get_attr(patient, 'city')
        state_province = PatientMapper.safe_get_attr(patient, 'state_province')
        postal_code = PatientMapper.safe_get_attr(patient, 'postal_code')
        country = PatientMapper.safe_get_attr(patient, 'country')
        
        if any([address_line1, address_line2, city, state_province, postal_code]):
            address_data = {
                "use": "home",
                "type": "physical"
            }
            
            # Address lines
            lines = []
            if address_line1:
                lines.append(address_line1)
            if address_line2:
                lines.append(address_line2)
            if lines:
                address_data["line"] = lines
            
            if city:
                address_data["city"] = city
            if state_province:
                address_data["state"] = state_province
            if postal_code:
                address_data["postalCode"] = postal_code
            if country:
                address_data["country"] = country
            
            addresses.append(address_data)
            
        elif PatientMapper.safe_get_attr(patient, 'address'):
            # Fall back to legacy address field
            addresses.append({
                "use": "home",
                "text": patient.address,
                "city": PatientMapper.safe_get_attr(patient, 'city'),
                "state": PatientMapper.safe_get_attr(patient, 'state'),
                "country": PatientMapper.safe_get_attr(patient, 'country')
            })
        
        if addresses:
            fhir_data["address"] = addresses
        
        # Marital status
        marital_status = PatientMapper.safe_get_attr(patient, 'marital_status')
        if marital_status and marital_status != "unknown":
            fhir_data["maritalStatus"] = {
                "coding": [{"system": "http://terminology.hl7.org/CodeSystem/v3-MaritalStatus", "code": marital_status}]
            }
        
        # Communication (preferred language)
        preferred_language = PatientMapper.safe_get_attr(patient, 'preferred_language')
        if preferred_language:
            fhir_data["communication"] = [
                {
                    "language": {
                        "coding": [{"code": preferred_language}]
                    },
                    "preferred": True
                }
            ]
        
        # Deceased status
        deceased = PatientMapper.safe_get_attr(patient, 'deceased')
        deceased_date = PatientMapper.safe_get_attr(patient, 'deceased_date')
        if deceased:
            if deceased_date:
                fhir_data["deceasedDateTime"] = PatientMapper.format_date(deceased_date)
            else:
                fhir_data["deceasedBoolean"] = True
        
        # Emergency contact
        emergency_contact_name = PatientMapper.safe_get_attr(patient, 'emergency_contact_name')
        emergency_contact_relationship = PatientMapper.safe_get_attr(patient, 'emergency_contact_relationship')
        emergency_contact_phone = PatientMapper.safe_get_attr(patient, 'emergency_contact_phone')
        
        if emergency_contact_name:
            contact_data = {
                "name": {
                    "text": emergency_contact_name
                }
            }
            
            if emergency_contact_relationship:
                contact_data["relationship"] = [
                    {
                        "text": emergency_contact_relationship
                    }
                ]
            
            if emergency_contact_phone:
                contact_data["telecom"] = [
                    {
                        "system": "phone",
                        "value": emergency_contact_phone,
                        "use": "home"
                    }
                ]
            
            fhir_data["contact"] = [contact_data]
        
        # Extensions for additional data
        extensions = []
        
        # Last arrived date
        last_arrived = PatientMapper.safe_get_attr(patient, 'last_arrived')
        if last_arrived:
            extensions.append({
                "url": "http://example.org/fhir/StructureDefinition/last-arrived",
                "valueDate": PatientMapper.format_date(last_arrived)
            })
        
        # Blood type
        blood_type = PatientMapper.safe_get_attr(patient, 'blood_type')
        if blood_type:
            extensions.append({
                "url": "http://example.org/fhir/StructureDefinition/blood-type",
                "valueString": blood_type
            })
        
        # Allergies
        allergies = PatientMapper.safe_get_attr(patient, 'allergies')
        if allergies:
            extensions.append({
                "url": "http://example.org/fhir/StructureDefinition/allergies",
                "valueString": allergies
            })
        
        # Registration date
        registration_date = PatientMapper.safe_get_attr(patient, 'registration_date')
        if registration_date:
            extensions.append({
                "url": "http://example.org/fhir/StructureDefinition/registration-date",
                "valueDateTime": PatientMapper.format_datetime(registration_date)
            })
        
        if extensions:
            fhir_data["extension"] = extensions
        
        return fhir_data
    
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
            'female': 'female',
            'other': 'other',
            'unknown': 'unknown'
        }
        return gender_map.get(gender, 'unknown')

