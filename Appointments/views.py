# Appointments/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.db import IntegrityError
from .models import Appointment
from .forms import AppointmentForms
#from .forms import AppointmentForm 
from . import views

def AppointmentView(request):
    appointments = Appointment.objects.all().order_by('-appointment_date')
    
    return render(request, 'Appointments/appointments.html', {
        'appointments': appointments, 
    })

def AddAppointment(request):
    if request.method == 'POST':
        form = AppointmentForms(request.POST)
        if form.is_valid():
            try:
                form.save()
                return redirect('Appointment')
            except IntegrityError as e:
                form.add_error(None, f"Database error: {str(e)}")
    else:
        form = AppointmentForms()
    
    return render(request, 'Appointments/add_appointment.html', {
        'form': form
    })

def DeleteAppointment(request, appointment_id):
    appointment = get_object_or_404(Appointment, pk=appointment_id)
    if request.method == 'POST':
        appointment.delete()
        return redirect('Appointment')
    return render(request, 'Appointments/confirm_delete.html', {
        'appointment': appointment
    })


def EditAppointment(request, appointment_id):
    appointment = get_object_or_404(Appointment, appointment_id=appointment_id)

    if request.method == 'POST':
        appointment_form = AppointmentForms(request.POST, instance=appointment)
        if appointment_form.is_valid():
            try:
                appointment_form.save()
                return redirect('Appointment')  # Redirect to appointments list
            except IntegrityError as e:
                appointment_form.add_error(None, f'Database error: {e}')
    else:
        appointment_form = AppointmentForms(instance=appointment)

    return render(request, 'Appointments/editappointment.html', {
        'appointment_form': appointment_form,
        'appointment': appointment
    })