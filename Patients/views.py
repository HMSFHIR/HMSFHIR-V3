from django.shortcuts import render, redirect, get_object_or_404
from django.db import IntegrityError
# from .fhir_service import get_patient, get_patient_condition, get_patient_with_condition
from django.views.decorators.csrf import csrf_exempt
from datetime import date
from rest_framework import viewsets
from .models import Patient, Practitioner, Encounter, Observation, Appointment, Condition
from .serializers import PatientSerializer, PractitionerSerializer, EncounterSerializer, ObservationSerializer
from .forms import PatientForm
from django.utils.crypto import get_random_string


#These ViewSets are for handling API endpoints 
   # using Django REST Framework. Each ViewSet corresponds to a model 
    #and provides built-in CRUD (Create, Read, Update, Delete) functionality.

class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer

class PractitionerViewSet(viewsets.ModelViewSet):
    queryset = Practitioner.objects.all()
    serializer_class = PractitionerSerializer

class EncounterViewSet(viewsets.ModelViewSet):
    queryset = Encounter.objects.all()
    serializer_class = EncounterSerializer

class ObservationViewSet(viewsets.ModelViewSet):
    queryset = Observation.objects.all()
    serializer_class = ObservationSerializer




# Views for rendering HTML templates

def Dashboard(request):
    appointments = Appointment.objects.all()  # Fetch all appointments
    context = {'Appointments': appointments}
    return render(request, "Patients/dashboard.html", context)

def PatientList(request):
    Patients = Patient.objects.all()
    context = {'Patients': Patients}
    return render(request, 'Patients/patientList.html', context)

def AppointmentView(request):
    Appointments = Appointment.objects.all()
    context = {'Appointments' : Appointments }
    return render(request, "Patients/appointments.html", context)

def MedicalRecordView(request):
    context = {}
    return render(request, "Patients/medicalrecord.html", context)
#
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
    patient = get_object_or_404(Patient, patient_id=patient_id)  # Fix field name

    if request.method == "POST":
        patient_form = PatientForm(request.POST, instance=patient)
        if patient_form.is_valid():
            try:
                patient_form.save()
                return redirect("PatientList")  # Ensure this URL name exists
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

    # Fetch medical conditions related to the patient
    medical_records = Condition.objects.filter(patient=patient)

    # Fetch condition details if available
    condition_details = {}
    if medical_records.exists():
        condition = medical_records.first()  # Get the first condition record
        condition_details = {
            "id": condition.condition_id,
            "clinical_status": condition.clinical_status,
            "verification_status": condition.verification_status,
            "severity": condition.severity,
            "onset": condition.onset,
            "abatement": condition.abatement,
            "recorded_date": condition.recorded_date,
            "recorder": condition.recorder.name if condition.recorder else "N/A",
            "diagnosis": condition.diagnosis,
            "allergies": condition.allergies,
            "medications": condition.medications,
            "test_results": condition.test_results,
        }

    context = {
        "patient": patient,
        "appointments": appointments,
        "medical_records": medical_records,
        "condition_details": condition_details,
    }

    return render(request, "Patients/patientsummary.html", context)