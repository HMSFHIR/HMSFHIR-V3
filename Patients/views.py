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
        Patients = Patient.objects.filter(
            Q(name__icontains=query) |
            Q(patient_id__icontains=query) |
            Q(national_id__icontains=query) |
            Q(gender__icontains=query)
        )
    else:
        Patients = Patient.objects.all()
    context = {'Patients': Patients}
    
    return render(request, 'Patients/patientList.html', context)
    
def AppointmentView(request):
    Appointments = Appointment.objects.all()
    context = {'Appointments' : Appointments }
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
            patient.patient_id = f"P-{get_random_string(8).upper()}"
            patient.last_arrived = date.today()
            patient.save()
            return redirect("PatientList")  # Redirect to patient list
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
                patient_form.save()
                return redirect("PatientList")
            except IntegrityError as e:
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
    appointments = Appointment.objects.filter(patient=patient)
    
    # Fetch all medical records for comprehensive view
    conditions = Condition.objects.filter(patient=patient)
    medications = MedicationStatement.objects.filter(patient=patient)
    allergies = AllergyIntolerance.objects.filter(patient=patient)
    procedures = Procedure.objects.filter(patient=patient)
    immunizations = Immunization.objects.filter(patient=patient)
    encounters = Encounter.objects.filter(patient=patient)
    
    # Get the most recent condition for condition_details
    condition_details = None
    if conditions.exists():
        latest_condition = conditions.order_by('-onset_date').first()
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
    medical_records.sort(key=lambda x: x['recorded_date'], reverse=True)
    
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
        patient.delete()
    except Patient.DoesNotExist:
        # Optionally, handle the error (e.g., flash message)
        pass
    return redirect('PatientList')