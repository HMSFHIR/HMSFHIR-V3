from django import forms 
from .models import Appointment


class AppointmentForms(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['patient', 'practitioner', 'appointment_date', 'notes', 'status']
        # Optional: You can add labels if you want more user-friendly names
        labels = {
            'patient': 'Patient',
            'practitioner': 'Doctor/Practitioner',
            'appointment_date': 'Appointment Date',
            'notes': 'Notes',
            'status': 'Status'
        }