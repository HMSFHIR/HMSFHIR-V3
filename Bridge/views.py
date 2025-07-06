# views.py
import requests
import json
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from core import settings
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from django.http import JsonResponse
from Patients.models import Patient, FHIRSyncTask
from django.views.decorators.http import require_http_methods
from datetime import datetime
import logging

# FHIR server configuration
FHIR_SERVER_URL = settings.FHIR_SERVER_BASE_URL


class PatientRequestView(View):
    """View to request patient data from FHIR server"""
    
    def get(self, request):
        """Display the patient request form"""
        return render(request, 'Bridge/request.html')
    
    def post(self, request):
        """Handle patient data request from FHIR server"""
        patient_id = request.POST.get('patient_id')
        national_id = request.POST.get('national_id')
        
        if not patient_id and not national_id:
            messages.error(request, 'Please provide either Patient ID or National ID')
            return render(request, 'Bridge/request.html')
        
        try:
            # Request patient data from FHIR server
            patient_data = self.fetch_patient_from_fhir(patient_id, national_id)
            
            if patient_data:
                context = {
                    'patient_data': patient_data,
                    'success': True,
                    'patient_id': patient_id,
                    'national_id': national_id
                }
                messages.success(request, 'Patient data retrieved successfully!')
            else:
                context = {
                    'success': False,
                    'error': 'Patient not found'
                }
                messages.error(request, 'Patient not found in FHIR server')
                
        except Exception as e:
            context = {
                'success': False,
                'error': str(e)
            }
            messages.error(request, f'Error retrieving patient data: {str(e)}')

        return render(request, 'Bridge/request.html', context)

    def fetch_patient_from_fhir(self, patient_id=None, national_id=None):
        """Fetch patient data from FHIR server"""
        headers = {
            'Accept': 'application/fhir+json',
            'Content-Type': 'application/fhir+json'
        }
        
        try:
            if patient_id:
                # Search by Patient ID
                url = f"{FHIR_SERVER_URL}/Patient/{patient_id}"
                response = requests.get(url, headers=headers, timeout=30)
                
            elif national_id:
                # Search by National ID (identifier)
                url = f"{FHIR_SERVER_URL}/Patient"
                params = {'identifier': national_id}
                response = requests.get(url, headers=headers, params=params, timeout=30)
                
            response.raise_for_status()
            
            if response.status_code == 200:
                patient_data = response.json()
                
                # If searching by national_id, extract first patient from bundle
                if national_id and 'entry' in patient_data:
                    if patient_data['entry']:
                        patient_data = patient_data['entry'][0]['resource']
                    else:
                        return None
                
                # Parse and format patient data
                return self.format_patient_data(patient_data)
            
            return None
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"FHIR server connection error: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response from FHIR server: {str(e)}")
        except Exception as e:
            raise Exception(f"Error processing FHIR response: {str(e)}")
    
    def format_patient_data(self, fhir_patient):
        """Format FHIR patient data for display"""
        try:
            # Extract basic information
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
                'raw_data': fhir_patient  # Include raw FHIR data for debugging
            }
            
            return patient_info
            
        except Exception as e:
            raise Exception(f"Error formatting patient data: {str(e)}")
    
    def extract_name(self, names):
        """Extract patient name from FHIR name array"""
        if not names:
            return {'full': 'N/A', 'given': [], 'family': 'N/A'}
        
        # Use first name entry
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
        """Extract telecom information (phone, email)"""
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
        """Extract address information"""
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
        """Extract marital status"""
        if not marital_status:
            return 'N/A'
        
        coding = marital_status.get('coding', [])
        if coding:
            return coding[0].get('display', 'N/A')
        
        return marital_status.get('text', 'N/A')
    
    def extract_identifiers(self, identifiers):
        """Extract patient identifiers"""
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
        """Extract emergency contact information"""
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


# Function-based view alternative
def request_patient_data(request):
    """Function-based view for patient data request"""
    if request.method == 'GET':
        return render(request, 'Bridge/request.html')
    
    elif request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        national_id = request.POST.get('national_id')
        
        if not patient_id and not national_id:
            messages.error(request, 'Please provide either Patient ID or National ID')
            return render(request, 'Bridge/request.html')
        
        try:
            # Initialize the class-based view to use its methods
            view_instance = PatientRequestView()
            patient_data = view_instance.fetch_patient_from_fhir(patient_id, national_id)
            
            if patient_data:
                context = {
                    'patient_data': patient_data,
                    'success': True,
                    'patient_id': patient_id,
                    'national_id': national_id
                }
                messages.success(request, 'Patient data retrieved successfully!')
            else:
                context = {
                    'success': False,
                    'error': 'Patient not found'
                }
                messages.error(request, 'Patient not found in FHIR server')
                
        except Exception as e:
            context = {
                'success': False,
                'error': str(e)
            }
            messages.error(request, f'Error retrieving patient data: {str(e)}')

        return render(request, 'Bridge/request.html', context)


# AJAX view for asynchronous requests
@csrf_exempt
def ajax_request_patient(request):
    """AJAX view for patient data request"""
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
            
            view_instance = PatientRequestView()
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




logger = logging.getLogger(__name__)

def save_to_db(request):
    """
    Save FHIR Patient data to the database
    Expects JSON data in the request body or as form data
    """
    context = {}
    
    try:
        # Get JSON data from request
        if request.method == 'POST':
            if request.content_type == 'application/json':
                # Handle JSON request body
                fhir_data = json.loads(request.body.decode('utf-8'))
            else:
                # Handle form data with JSON string
                json_string = request.POST.get('fhir_data', '{}')
                fhir_data = json.loads(json_string)
        else:
            # For GET requests, you might want to handle differently
            # or return an error
            messages.error(request, "Invalid request method")
            return redirect("PatientList")
        
        # Validate that it's a Patient resource
        if fhir_data.get('resourceType') != 'Patient':
            messages.error(request, "Invalid resource type. Expected 'Patient'")
            return redirect("PatientList")
        
        # Extract patient data from FHIR JSON
        patient_data = extract_patient_data_from_fhir(fhir_data)
        
        # Check if patient already exists (by patient_id or identifiers)
        existing_patient = None
        patient_id = patient_data.get('patient_id')
        
        if patient_id:
            try:
                existing_patient = Patient.objects.get(patient_id=patient_id)
            except Patient.DoesNotExist:
                pass
        
        # If not found by patient_id, try by national_id or medical_record_number
        if not existing_patient:
            national_id = patient_data.get('national_id')
            mrn = patient_data.get('medical_record_number')
            
            if national_id:
                try:
                    existing_patient = Patient.objects.get(national_id=national_id)
                except Patient.DoesNotExist:
                    pass
            
            if not existing_patient and mrn:
                try:
                    existing_patient = Patient.objects.get(medical_record_number=mrn)
                except Patient.DoesNotExist:
                    pass
        
        # Create or update patient
        if existing_patient:
            # Update existing patient
            for field, value in patient_data.items():
                if value is not None:  # Only update non-None values
                    setattr(existing_patient, field, value)
            
            # Update FHIR sync information
            existing_patient.fhir_id = fhir_data.get('id')
            existing_patient.last_sync = datetime.now()
            existing_patient.save()
            
            messages.success(request, f"Patient {existing_patient.full_name} updated successfully")
            logger.info(f"Updated patient: {existing_patient.patient_id}")
            
        else:
            # Create new patient
            new_patient = Patient(**patient_data)
            new_patient.fhir_id = fhir_data.get('id')
            new_patient.last_sync = datetime.now()
            new_patient.save()
            
            messages.success(request, f"Patient {new_patient.full_name} created successfully")
            logger.info(f"Created new patient: {new_patient.patient_id}")
        
        # Update or create FHIR sync task record
        sync_task, created = FHIRSyncTask.objects.get_or_create(
            resource_type='Patient',
            resource_id=patient_data.get('patient_id', fhir_data.get('id')),
            defaults={
                'status': 'synced',
                'synced_at': datetime.now()
            }
        )
        
        if not created:
            sync_task.status = 'synced'
            sync_task.synced_at = datetime.now()
            sync_task.retry_count = 0
            sync_task.error_message = None
            sync_task.save()
        
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON data: {str(e)}"
        messages.error(request, error_msg)
        logger.error(error_msg)
        
    except Exception as e:
        error_msg = f"Error saving patient data: {str(e)}"
        messages.error(request, error_msg)
        logger.error(error_msg)
        
        # Log failed sync task
        try:
            patient_id = fhir_data.get('id', 'unknown')
            FHIRSyncTask.objects.create(
                resource_type='Patient',
                resource_id=patient_id,
                status='failed',
                error_message=str(e)
            )
        except:
            pass

    return redirect("PatientList")  # Redirect to patient list after saving

