from django.shortcuts import render, redirect, get_object_or_404
from django.db import IntegrityError
from django.views.decorators.csrf import csrf_exempt
from datetime import date
from rest_framework import viewsets
from .models import Patient
from .serializers import PatientSerializer
from .forms import PatientForm
from django.utils.crypto import get_random_string
from django.db.models import Q
from Appointments.models import Appointment
from MedicalRecords.models import Condition, Encounter, Observation, MedicationStatement, AllergyIntolerance, Procedure, Immunization
from django.http import JsonResponse
from django.core.paginator import Paginator

#These ViewSets are for handling API endpoints 
# using Django REST Framework. Each ViewSet corresponds to a model 
#and provides built-in CRUD (Create, Read, Update, Delete) functionality.
class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer

# Views for rendering HTML templates
def Dashboard(request):
    appointments = Appointment.objects.all()  # Fetch all appointments
    appointment_count = Appointment.objects.count()
    pending_appointments = appointments.filter(status='pending').count()

    patient_count = Patient.objects.count()
    context = {'Appointments': appointments,
               'patient_count': patient_count,
               'appointment_count': appointment_count,
               'pending_appointments': pending_appointments}
    
    return render(request, "Patients/dashboard.html", context)

def PatientList(request):
    query = request.GET.get('q')
    
    if query:
        # UPDATED: Search strategy for encrypted fields
        # Strategy 1: Search only non-encrypted fields and exact matches
        patients = Patient.objects.filter(
            Q(patient_id__icontains=query) |  # patient_id is not encrypted
            Q(gender__icontains=query) |      # gender is not encrypted
            Q(country__icontains=query)       # country is not encrypted
        )
        
        # Strategy 2: For exact matches on encrypted fields
        exact_match_patients = Patient.objects.filter(
            Q(name__exact=query) |
            Q(given_name__exact=query) |
            Q(family_name__exact=query) |
            Q(national_id__exact=query) |
            Q(medical_record_number__exact=query)
        )
        
        # Combine results
        patients = patients.union(exact_match_patients)
        
        # Strategy 3: If you need partial matching on encrypted fields
        # This is slower but more user-friendly
        if not patients.exists():
            all_patients = Patient.objects.filter(active=True)
            matching_patients = []
            query_lower = query.lower()
            
            for patient in all_patients:
                # Check if query matches any name field (case-insensitive)
                if (query_lower in (patient.name or '').lower() or
                    query_lower in (patient.given_name or '').lower() or
                    query_lower in (patient.family_name or '').lower() or
                    query in (patient.national_id or '') or
                    query in (patient.medical_record_number or '')):
                    matching_patients.append(patient.id)
            
            # Get the matching patients by ID
            if matching_patients:
                patients = Patient.objects.filter(id__in=matching_patients)
        
        # Add pagination for search results
        paginator = Paginator(patients, 20)  # 20 patients per page
        page_number = request.GET.get('page')
        patients = paginator.get_page(page_number)
        
    else:
        # Default view - order by non-encrypted fields
        patients = Patient.objects.filter(active=True).order_by('-created_at')
        
        # Add pagination
        paginator = Paginator(patients, 20)
        page_number = request.GET.get('page')
        patients = paginator.get_page(page_number)
    
    context = {
        'Patients': patients,
        'query': query,
        'total_patients': Patient.objects.filter(active=True).count()
    }
    
    return render(request, 'Patients/patientList.html', context)

# NEW: Advanced search view for better encrypted field handling
def PatientAdvancedSearch(request):
    """Advanced search that handles encrypted fields better"""
    context = {}
    
    if request.method == 'POST':
        # Get search parameters
        given_name = request.POST.get('given_name', '').strip()
        family_name = request.POST.get('family_name', '').strip()
        patient_id = request.POST.get('patient_id', '').strip()
        national_id = request.POST.get('national_id', '').strip()
        phone = request.POST.get('phone', '').strip()
        
        # Start with all active patients
        patients = Patient.objects.filter(active=True)
        
        # Apply exact match filters for encrypted fields
        if given_name:
            patients = patients.filter(given_name__exact=given_name)
        if family_name:
            patients = patients.filter(family_name__exact=family_name)
        if national_id:
            patients = patients.filter(national_id__exact=national_id)
        if phone:
            patients = patients.filter(
                Q(primary_phone__exact=phone) | 
                Q(secondary_phone__exact=phone)
            )
        
        # Apply partial match for non-encrypted fields
        if patient_id:
            patients = patients.filter(patient_id__icontains=patient_id)
        
        context['patients'] = patients
        context['search_performed'] = True
    
    return render(request, 'Patients/advanced_search.html', context)

# NEW: AJAX search endpoint for real-time search
def PatientSearchAPI(request):
    """API endpoint for patient search - optimized for encrypted fields"""
    query = request.GET.get('q', '').strip()
    
    if not query or len(query) < 2:
        return JsonResponse({'patients': []})
    
    # Search strategy for encrypted fields
    patients_data = []
    
    # First, search non-encrypted fields
    patients = Patient.objects.filter(
        Q(patient_id__icontains=query) |
        Q(gender__icontains=query)
    )[:10]
    
    for patient in patients:
        patients_data.append({
            'id': patient.patient_id,
            'name': patient.full_name,
            'patient_id': patient.patient_id,
            'age': patient.age,
            'gender': patient.gender
        })
    
    # If we don't have enough results, do exact match on encrypted fields
    if len(patients_data) < 5:
        exact_patients = Patient.objects.filter(
            Q(name__exact=query) |
            Q(given_name__exact=query) |
            Q(family_name__exact=query) |
            Q(national_id__exact=query)
        ).exclude(id__in=[p.id for p in patients])[:5]
        
        for patient in exact_patients:
            patients_data.append({
                'id': patient.patient_id,
                'name': patient.full_name,
                'patient_id': patient.patient_id,
                'age': patient.age,
                'gender': patient.gender
            })
    
    return JsonResponse({'patients': patients_data})
    
def AppointmentView(request):
    appointments = Appointment.objects.all().order_by('-appointment_date')
    context = {'appointments': appointments}
    return render(request, "Appointments/appointments.html", context)

def MedicalRecordView(request):
    context = {}
    return render(request, "Patients/medicalrecord.html", context)

def FHIRSync(request):
    context = {}
    return render(request, "Patients/fhirsync.html", context)

###Views for handling form submissions and data processing
# views for CRUD operations
#view for adding patients
def add_patient(request):
    if request.method == "POST":
        form = PatientForm(request.POST)
        if form.is_valid():
            patient = form.save(commit=False)
            # UPDATED: Use the model's built-in patient_id generation
            if not patient.patient_id:
                patient.patient_id = f"P-{get_random_string(8).upper()}"
            patient.last_arrived = date.today()
            
            # Set created_by if user is authenticated
            if request.user.is_authenticated:
                patient.created_by = request.user
            
            try:
                patient.save()
                return redirect("PatientList")
            except IntegrityError as e:
                # Handle unique constraint violations for encrypted fields
                if 'national_id' in str(e):
                    form.add_error('national_id', 'A patient with this National ID already exists.')
                elif 'medical_record_number' in str(e):
                    form.add_error('medical_record_number', 'A patient with this Medical Record Number already exists.')
                else:
                    form.add_error(None, f"Database error: {e}")
    else:
        form = PatientForm()
    return render(request, "Patients/addpatient.html", {"form": form})

#view for editing patients
def EditPatient(request, patient_id):
    patient = get_object_or_404(Patient, patient_id=patient_id)
    if request.method == "POST":
        patient_form = PatientForm(request.POST, instance=patient)
        if patient_form.is_valid():
            try:
                # Set updated_by if user is authenticated
                if request.user.is_authenticated:
                    patient.updated_by = request.user
                patient_form.save()
                return redirect("PatientList")
            except IntegrityError as e:
                # Handle unique constraint violations for encrypted fields
                if 'national_id' in str(e):
                    patient_form.add_error('national_id', 'A patient with this National ID already exists.')
                elif 'medical_record_number' in str(e):
                    patient_form.add_error('medical_record_number', 'A patient with this Medical Record Number already exists.')
                else:
                    patient_form.add_error(None, f"Database error: {e}")
    else:
        patient_form = PatientForm(instance=patient)
    return render(request, "Patients/editpatient.html", {
        "patient_form": patient_form,
        "patient": patient
    })

def ViewRecordsSummary(request, patient_id):
    # Fetch the patient
    patient = get_object_or_404(Patient, patient_id=patient_id)
    
    # Fetch appointments related to the patient
    appointments = Appointment.objects.filter(patient=patient).order_by('-appointment_date')
    
    # Fetch all medical records for comprehensive view
    conditions = Condition.objects.filter(patient=patient).order_by('-onset_date')
    medications = MedicationStatement.objects.filter(patient=patient)
    allergies = AllergyIntolerance.objects.filter(patient=patient)
    procedures = Procedure.objects.filter(patient=patient).order_by('-performed_date')
    immunizations = Immunization.objects.filter(patient=patient)
    encounters = Encounter.objects.filter(patient=patient).order_by('-start_time')
    
    # Get the most recent condition for condition_details
    condition_details = None
    if conditions.exists():
        latest_condition = conditions.first()
        condition_details = {
            "id": latest_condition.id,
            "clinical_status": latest_condition.status,
            "verification_status": "confirmed",  # Default value since not in model
            "severity": "moderate",  # Default value since not in model
            "onset": latest_condition.onset_date,
            "abatement": None,  # Not in current model
            "recorded_date": latest_condition.onset_date,
            "recorder": "System",  # Default value since not in model
            "diagnosis": latest_condition.description,
            "code": latest_condition.code,
        }
    
    # Prepare medical records summary
    medical_records = []
    for condition in conditions:
        medical_records.append({
            'recorded_date': condition.onset_date,
            'diagnosis': condition.description,
            'type': 'Condition'
        })
    
    for procedure in procedures:
        medical_records.append({
            'recorded_date': procedure.performed_date,
            'diagnosis': procedure.procedure_name,
            'type': 'Procedure'
        })
    
    # Sort medical records by date (most recent first)
    medical_records.sort(key=lambda x: x['recorded_date'] if x['recorded_date'] else date.min, reverse=True)
    
    context = {
        "patient": patient,
        "appointments": appointments,
        "medical_records": medical_records,
        "condition_details": condition_details,
        "conditions": conditions,
        "medications": medications,
        "allergies": allergies,
        "procedures": procedures,
        "immunizations": immunizations,
        "encounters": encounters,
    }
    return render(request, "Patients/patientsummary.html", context)

def DeletePatient(request, patient_id):
    try:
        patient = Patient.objects.get(patient_id=patient_id)
        # UPDATED: Soft delete instead of hard delete for better data integrity
        patient.active = False
        patient.save()
        # If you want hard delete, uncomment the line below:
        # patient.delete()
    except Patient.DoesNotExist:
        # Optionally, handle the error (e.g., flash message)
        pass
    return redirect('PatientList')

# NEW: Patient lookup by exact identifier (useful for encrypted fields)
def PatientLookup(request):
    """Lookup patient by exact identifiers - useful for encrypted fields"""
    if request.method == 'POST':
        lookup_type = request.POST.get('lookup_type')
        lookup_value = request.POST.get('lookup_value', '').strip()
        
        patient = None
        if lookup_type == 'patient_id':
            patient = Patient.objects.filter(patient_id=lookup_value).first()
        elif lookup_type == 'national_id':
            patient = Patient.objects.filter(national_id=lookup_value).first()
        elif lookup_type == 'medical_record_number':
            patient = Patient.objects.filter(medical_record_number=lookup_value).first()
        
        if patient:
            return redirect('ViewRecordsSummary', patient_id=patient.patient_id)
        else:
            context = {
                'error': f'No patient found with {lookup_type}: {lookup_value}',
                'lookup_type': lookup_type,
                'lookup_value': lookup_value
            }
            return render(request, 'Patients/patient_lookup.html', context)
    
    return render(request, 'Patients/patient_lookup.html', {})