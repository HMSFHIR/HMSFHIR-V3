from django.db import models
from Patients.models import Patient
from Practitioner.models import Practitioner
from encrypted_model_fields.fields import EncryptedCharField, EncryptedTextField

class Appointment(models.Model):
    appointment_id = models.AutoField(primary_key=True)
    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name='appointments',
    )
    practitioner = models.ForeignKey(
        Practitioner,
        on_delete=models.SET_NULL,
        null=True,
        related_name='appointments',
    )
    appointment_date = models.DateTimeField()
    
    # Use EncryptedTextField directly instead of encrypt() wrapper
    notes = EncryptedTextField(blank=True, null=True)
    
    status = models.CharField(max_length=10, choices=[
        ('Completed', 'Completed'),
        ('Scheduled', 'Scheduled'),
        ('Cancelled', 'Cancelled')
    ], default='Scheduled')

    def __str__(self):
        return f"Appointment {self.appointment_id} - {self.patient.name}"