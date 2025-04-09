from django.db import models
from Patients.models import Patient
from Patients.models import Practitioner  # Import the Practitioner model if it's in a separate app

class Appointment(models.Model):
    appointment_id = models.AutoField(primary_key=True)
    patient = models.ForeignKey(
        Patient, 
        on_delete=models.CASCADE, 
        related_name='appointments',  # Add this to avoid conflict
    )
    practitioner = models.ForeignKey(
        Practitioner, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='appointments',  # Add this to avoid conflict
    )
    appointment_date = models.DateTimeField()
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=[
        ('Completed', 'Completed'), 
        ('Scheduled', 'Scheduled'), 
        ('Cancelled', 'Cancelled')
    ], default='Scheduled')

    def __str__(self):
        return f"Appointment {self.appointment_id} - {self.patient.name}"

