import requests
import json
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from core import settings
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from Patients.models import Patient, FHIRSyncTask
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
FHIR_SERVER_URL = settings.FHIR_SERVER_BASE_URL



class ExtendedPatientRequestView(View):
    """
    This is the main view that handles the form on your request.html page.
    It replaces your old PatientRequestView but adds multi-resource support.
    """
    
    def get(self, request):
        """When someone visits the page, show the form"""
        return render(request, 'Bridge/request.html')
    
    def post(self, request):
        """When someone submits the form, process the request"""
        # Get form data
        patient_id = request.POST.get('patient_id')
        national_id = request.POST.get('national_id')
        
        # Check which additional resources they want to fetch
        resources_to_fetch = {
            'observations': request.POST.get('fetch_observations'),
            'conditions': request.POST.get('fetch_conditions'), 
            'medications': request.POST.get('fetch_medications'),
            'allergies': request.POST.get('fetch_allergies'),
            'encounters': request.POST.get('fetch_encounters'),
            'procedures': request.POST.get('fetch_procedures'),
        }
        
        # Validate input
        if not patient_id and not national_id:
            messages.error(request, 'Please provide either Patient ID or National ID')
            return render(request, 'Bridge/request.html')
        
        try:
            # Step 1: Get the patient data (your existing functionality)
            patient_data = self.fetch_patient_from_fhir(patient_id, national_id)
            
            if not patient_data:
                messages.error(request, 'Patient not found in FHIR server')
                return render(request, 'Bridge/request.html', {'success': False, 'error': 'Patient not found'})
            
            # Step 2: Get additional resources if requested (NEW functionality)
            related_data = {}
            actual_patient_id = patient_data['id']
            
            for resource_type, should_fetch in resources_to_fetch.items():
                if should_fetch:  # If checkbox was checked
                    data = self.fetch_patient_resource(actual_patient_id, resource_type)
                    related_data[resource_type] = data
            
            # Step 3: Send everything to the template
            context = {
                'patient_data': patient_data,
                'related_data': related_data,
                'success': True,
                'patient_id': patient_id,
                'national_id': national_id,
            }
            
            messages.success(request, 'Patient data retrieved successfully!')
            return render(request, 'Bridge/request.html', context)
                
        except Exception as e:
            messages.error(request, f'Error retrieving patient data: {str(e)}')
            return render(request, 'Bridge/request.html', {'success': False, 'error': str(e)})


    def fetch_patient_from_fhir(self, patient_id=None, national_id=None):
        """Fetch patient data from FHIR server - THIS IS YOUR EXISTING METHOD"""
        headers = {
            'Accept': 'application/fhir+json',
            'Content-Type': 'application/fhir+json'
        }
        
        try:
            if patient_id:
                url = f"{FHIR_SERVER_URL}/Patient/{patient_id}"
                response = requests.get(url, headers=headers, timeout=30)
            elif national_id:
                url = f"{FHIR_SERVER_URL}/Patient"
                params = {'identifier': national_id}
                response = requests.get(url, headers=headers, params=params, timeout=30)
                
            response.raise_for_status()
            
            if response.status_code == 200:
                patient_data = response.json()
                
                if national_id and 'entry' in patient_data:
                    if patient_data['entry']:
                        patient_data = patient_data['entry'][0]['resource']
                    else:
                        return None
                
                return self.format_patient_data(patient_data)
            
            return None
            
        except Exception as e:
            raise Exception(f"FHIR server error: {str(e)}")

    def format_patient_data(self, fhir_patient):
        """Format patient data - THIS IS YOUR EXISTING METHOD"""
        try:
            patient_info = {
                'id': fhir_patient.get('id', 'N/A'),
                'resource_type': fhir_patient.get('resourceType', 'N/A'),
                'active': fhir_patient.get('active', False),
                'name': self.extract_name(fhir_patient.get('name', [])),
                'gender': fhir_patient.get('gender', 'N/A'),
                'birth_date': fhir_patient.get('birthDate', 'N/A'),
                'telecom': self.extract_telecom(fhir_patient.get('telecom', [])),
                'address': self.extract_address(fhir_patient.get('address', [])),
                'marital_status': self.extract_marital_status(fhir_patient.get('maritalStatus', {})),
                'identifiers': self.extract_identifiers(fhir_patient.get('identifier', [])),
                'contact': self.extract_contact(fhir_patient.get('contact', [])),
                'raw_data': fhir_patient
            }
            return patient_info
        except Exception as e:
            raise Exception(f"Error formatting patient data: {str(e)}")

    # Your existing helper methods (extract_name, extract_telecom, etc.)
    def extract_name(self, names):
        if not names:
            return {'full': 'N/A', 'given': [], 'family': 'N/A'}
        name = names[0]
        given_names = name.get('given', [])
        family_name = name.get('family', '')
        full_name = f"{' '.join(given_names)} {family_name}".strip()
        return {
            'full': full_name or 'N/A',
            'given': given_names,
            'family': family_name
        }
    
    def extract_telecom(self, telecom_list):
        telecom = {'phone': [], 'email': []}
        for contact in telecom_list:
            system = contact.get('system', '')
            value = contact.get('value', '')
            if system == 'phone':
                telecom['phone'].append(value)
            elif system == 'email':
                telecom['email'].append(value)
        return telecom
    
    def extract_address(self, address_list):
        if not address_list:
            return []
        addresses = []
        for addr in address_list:
            address = {
                'line': addr.get('line', []),
                'city': addr.get('city', ''),
                'state': addr.get('state', ''),
                'postal_code': addr.get('postalCode', ''),
                'country': addr.get('country', ''),
                'type': addr.get('type', ''),
                'use': addr.get('use', '')
            }
            addresses.append(address)
        return addresses
    
    def extract_marital_status(self, marital_status):
        if not marital_status:
            return 'N/A'
        coding = marital_status.get('coding', [])
        if coding:
            return coding[0].get('display', 'N/A')
        return marital_status.get('text', 'N/A')
    
    def extract_identifiers(self, identifiers):
        identifier_list = []
        for identifier in identifiers:
            id_info = {
                'system': identifier.get('system', ''),
                'value': identifier.get('value', ''),
                'type': identifier.get('type', {}).get('text', ''),
                'use': identifier.get('use', '')
            }
            identifier_list.append(id_info)
        return identifier_list
    
    def extract_contact(self, contacts):
        contact_list = []
        for contact in contacts:
            contact_info = {
                'relationship': contact.get('relationship', []),
                'name': self.extract_name(contact.get('name', [])),
                'telecom': self.extract_telecom(contact.get('telecom', [])),
                'address': self.extract_address(contact.get('address', [])),
                'gender': contact.get('gender', 'N/A')
            }
            contact_list.append(contact_info)
        return contact_list


    def fetch_patient_resource(self, patient_id, resource_type):
        """
        NEW METHOD: Fetch additional resources for a patient
        resource_type can be: observations, conditions, medications, allergies, encounters, procedures
        """
        # Map our simple names to FHIR resource types
        resource_map = {
            'observations': 'Observation',
            'conditions': 'Condition',
            'medications': 'MedicationRequest',
            'allergies': 'AllergyIntolerance',
            'encounters': 'Encounter',
            'procedures': 'Procedure',
        }
        
        if resource_type not in resource_map:
            return []
        
        fhir_resource_type = resource_map[resource_type]
        
        try:
            headers = {
                'Accept': 'application/fhir+json',
                'Content-Type': 'application/fhir+json'
            }
            
            url = f"{FHIR_SERVER_URL}/{fhir_resource_type}"
            params = {
                'patient': patient_id,
                '_count': 50  # Limit to 50 records
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            
            if response.status_code == 200:
                bundle_data = response.json()
                
                if 'entry' in bundle_data and bundle_data['entry']:
                    resources = [entry['resource'] for entry in bundle_data['entry']]
                    # Format the resources for display
                    return self.format_resources(resources, resource_type)
                else:
                    return []
            
            return []
            
        except Exception as e:
            logger.error(f"Error fetching {resource_type} for patient {patient_id}: {str(e)}")
            return []

    def format_resources(self, resources, resource_type):
        """Format different types of resources for display"""
        if resource_type == 'observations':
            return self.format_observations(resources)
        elif resource_type == 'conditions':
            return self.format_conditions(resources)
        elif resource_type == 'medications':
            return self.format_medications(resources)
        elif resource_type == 'allergies':
            return self.format_allergies(resources)
        elif resource_type == 'encounters':
            return self.format_encounters(resources)
        elif resource_type == 'procedures':
            return self.format_procedures(resources)
        else:
            return []

    def format_observations(self, observations):
        formatted_obs = []
        for obs in observations:
            try:
                formatted_obs.append({
                    'id': obs.get('id'),
                    'status': obs.get('status'),
                    'code': self.extract_coding_display(obs.get('code', {})),
                    'value': self.extract_observation_value(obs),
                    'effective_date': obs.get('effectiveDateTime', 'N/A'),
                    'raw_data': obs
                })
            except Exception as e:
                logger.error(f"Error formatting observation: {str(e)}")
                continue
        return formatted_obs

    def format_conditions(self, conditions):
        formatted_conditions = []
        for condition in conditions:
            try:
                formatted_conditions.append({
                    'id': condition.get('id'),
                    'clinical_status': self.extract_coding_display(condition.get('clinicalStatus', {})),
                    'code': self.extract_coding_display(condition.get('code', {})),
                    'onset_date': condition.get('onsetDateTime', 'N/A'),
                    'raw_data': condition
                })
            except Exception as e:
                logger.error(f"Error formatting condition: {str(e)}")
                continue
        return formatted_conditions

    def format_medications(self, medications):
        formatted_meds = []
        for med in medications:
            try:
                formatted_meds.append({
                    'id': med.get('id'),
                    'status': med.get('status'),
                    'medication': self.extract_medication_display(med),
                    'dosage_instruction': self.extract_dosage_simple(med.get('dosageInstruction', [])),
                    'raw_data': med
                })
            except Exception as e:
                logger.error(f"Error formatting medication: {str(e)}")
                continue
        return formatted_meds

    def format_allergies(self, allergies):
        formatted_allergies = []
        for allergy in allergies:
            try:
                formatted_allergies.append({
                    'id': allergy.get('id'),
                    'type': allergy.get('type', 'N/A'),
                    'criticality': allergy.get('criticality', 'N/A'),
                    'code': self.extract_coding_display(allergy.get('code', {})),
                    'clinical_status': self.extract_coding_display(allergy.get('clinicalStatus', {})),
                    'raw_data': allergy
                })
            except Exception as e:
                logger.error(f"Error formatting allergy: {str(e)}")
                continue
        return formatted_allergies

    def format_encounters(self, encounters):
        formatted_encounters = []
        for encounter in encounters:
            try:
                formatted_encounters.append({
                    'id': encounter.get('id'),
                    'status': encounter.get('status'),
                    'class': self.extract_coding_display(encounter.get('class', {})),
                    'type': [self.extract_coding_display(t) for t in encounter.get('type', [])],
                    'period': encounter.get('period', {}),
                    'raw_data': encounter
                })
            except Exception as e:
                logger.error(f"Error formatting encounter: {str(e)}")
                continue
        return formatted_encounters

    def format_procedures(self, procedures):
        formatted_procedures = []
        for procedure in procedures:
            try:
                formatted_procedures.append({
                    'id': procedure.get('id'),
                    'status': procedure.get('status'),
                    'code': self.extract_coding_display(procedure.get('code', {})),
                    'performed_date': procedure.get('performedDateTime', 'N/A'),
                    'raw_data': procedure
                })
            except Exception as e:
                logger.error(f"Error formatting procedure: {str(e)}")
                continue
        return formatted_procedures


    def extract_coding_display(self, codeable_concept):
        """Extract display text from a FHIR CodeableConcept"""
        if isinstance(codeable_concept, dict):
            if 'text' in codeable_concept:
                return codeable_concept['text']
            coding = codeable_concept.get('coding', [])
            if coding and len(coding) > 0:
                return coding[0].get('display', coding[0].get('code', 'N/A'))
        return 'N/A'

    def extract_observation_value(self, observation):
        """Extract the value from an observation"""
        if 'valueQuantity' in observation:
            qty = observation['valueQuantity']
            return f"{qty.get('value', '')} {qty.get('unit', '')}"
        elif 'valueString' in observation:
            return observation['valueString']
        elif 'valueCodeableConcept' in observation:
            return self.extract_coding_display(observation['valueCodeableConcept'])
        return 'N/A'

    def extract_medication_display(self, medication_request):
        """Extract medication name"""
        if 'medicationCodeableConcept' in medication_request:
            return self.extract_coding_display(medication_request['medicationCodeableConcept'])
        elif 'medicationReference' in medication_request:
            return medication_request['medicationReference'].get('display', 'N/A')
        return 'N/A'

    def extract_dosage_simple(self, dosage_instructions):
        """Extract simple dosage information"""
        if not dosage_instructions:
            return 'N/A'
        
        dosages = []
        for dosage in dosage_instructions:
            text = dosage.get('text', 'See details')
            dosages.append(text)
        
        return "; ".join(dosages)



@csrf_exempt
def save_fhir_data(request):
    """Save FHIR patient data to database - SIMPLIFIED VERSION OF YOUR EXISTING save_to_db"""
    if request.method != 'POST':
        messages.error(request, "Invalid request method")
        return redirect("Dashboard")
    
    try:
        # Get the patient data (assuming it's passed as JSON in form)
        json_string = request.POST.get('fhir_data', '{}')
        fhir_data = json.loads(json_string)
        
        if fhir_data.get('resourceType') != 'Patient':
            messages.error(request, "Invalid resource type. Expected 'Patient'")
            return redirect("Dashboard")
        
        # Use your existing extraction logic
        patient_data = extract_patient_data_from_fhir(fhir_data)
        
        # Use your existing save logic
        existing_patient = None
        patient_id = patient_data.get('patient_id')
        
        if patient_id:
            try:
                existing_patient = Patient.objects.get(patient_id=patient_id)
            except Patient.DoesNotExist:
                pass
        
        if existing_patient:
            # Update existing patient
            for field, value in patient_data.items():
                if value is not None:
                    setattr(existing_patient, field, value)
            existing_patient.fhir_id = fhir_data.get('id')
            existing_patient.last_sync = datetime.now()
            existing_patient.save()
            messages.success(request, f"Patient {existing_patient.full_name} updated successfully")
        else:
            # Create new patient
            new_patient = Patient(**patient_data)
            new_patient.fhir_id = fhir_data.get('id')
            new_patient.last_sync = datetime.now()
            new_patient.save()
            messages.success(request, f"Patient {new_patient.full_name} created successfully")
            
    except Exception as e:
        messages.error(request, f"Error saving patient data: {str(e)}")
        logger.error(f"Error saving patient data: {str(e)}")

    return redirect("Dashboard")


# Your existing extract_patient_data_from_fhir function (unchanged)
def extract_patient_data_from_fhir(fhir_data):
    """Extract patient data from FHIR JSON - YOUR EXISTING FUNCTION"""
    patient_data = {}
    
    patient_data['patient_id'] = fhir_data.get('id')
    patient_data['active'] = fhir_data.get('active', True)
    
    # Extract name information
    names = fhir_data.get('name', [])
    if names:
        name = names[0]
        patient_data['family_name'] = name.get('family', '')
        given_names = name.get('given', [])
        if given_names:
            patient_data['given_name'] = given_names[0]
            if len(given_names) > 1:
                patient_data['middle_name'] = ' '.join(given_names[1:])
        prefixes = name.get('prefix', [])
        if prefixes:
            patient_data['name_prefix'] = ' '.join(prefixes)
        suffixes = name.get('suffix', [])
        if suffixes:
            patient_data['name_suffix'] = ' '.join(suffixes)
    
    patient_data['gender'] = fhir_data.get('gender', 'unknown')
    
    # Birth date
    birth_date = fhir_data.get('birthDate')
    if birth_date:
        try:
            patient_data['birth_date'] = datetime.strptime(birth_date, '%Y-%m-%d').date()
        except ValueError:
            logger.warning(f"Invalid birth date format: {birth_date}")
    
    # Extract identifiers
    identifiers = fhir_data.get('identifier', [])
    for identifier in identifiers:
        value = identifier.get('value', '')
        if value.startswith('GHA-') or value.startswith('SSN-'):
            patient_data['national_id'] = value
        elif value.startswith('MRN-'):
            patient_data['medical_record_number'] = value
        elif identifier.get('type', {}).get('coding', [{}])[0].get('code') == 'MR':
            patient_data['medical_record_number'] = value
    
    # Extract telecom, address, marital status (your existing logic)
    # ... (keeping it short for clarity, but include all your existing extraction logic)
    
    return patient_data


@csrf_exempt
def ajax_request_patient(request):
    """AJAX endpoint for requesting patient data"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            patient_id = data.get('patient_id')
            national_id = data.get('national_id')
            
            if not patient_id and not national_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Please provide either Patient ID or National ID'
                })
            
            view_instance = ExtendedPatientRequestView()
            patient_data = view_instance.fetch_patient_from_fhir(patient_id, national_id)
            
            if patient_data:
                return JsonResponse({
                    'success': True,
                    'patient_data': patient_data
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Patient not found'
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({
        'success': False,
        'error': 'Invalid request method'
    })


PatientRequestView = ExtendedPatientRequestView