from django.shortcuts import render, redirect
from .models import Appointment
from .forms import AppointmentForms
from django.db import IntegrityError
from Patients.models import Patient

# Create your views here.
def AppointmentView(request):
    Appointments = Appointment.objects.all()
    context = {'Appointments' : Appointments }
    return render(request, "Appointments/appointments.html", context)

def AddAppointment(request):
    if request.method == 'POST':
        form = AppointmentForms(request.POST)
        if form.is_valid():
            try:
                form.save()
                return redirect('Appointment')  
            except IntegrityError as e:
                form.add_error(None, "This appointment conflicts with an existing one")
        # If form is invalid or save fails, render form with errors
    else:
        form = AppointmentForms()
    
    return render(request, 'Appointments/add_appointment.html', {'form': form})

def DeleteAppointment(request, appointment_id):
    appointment = get_object_or_404(Appointment, AppointmentID=appointment_id)
    patient_id = appointment.Patient.PatientID
    appointment.delete()
    return redirect('view_summary', patient_id=patient_id)
