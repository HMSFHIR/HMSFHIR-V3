from django.db import models
from django.utils import timezone
from Patients.models import Patient


class Encounter(models.Model):
    # Your existing Encounter fields here
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    encounter_type = models.CharField(max_length=100)
    reason = models.TextField()
    location = models.CharField(max_length=100)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=50)

class Observation(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE)  # ForeignKey to Encounter
    code = models.CharField(max_length=255)
    value = models.CharField(max_length=255)
    unit = models.CharField(max_length=100)
    observation_time = models.DateTimeField()

    def __str__(self):
        return f"Observation for {self.patient} during {self.encounter}"



class Condition(models.Model):
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name="medical_conditions")
    patient = models.ForeignKey("Patients.Patient", on_delete=models.CASCADE)
    code = models.CharField(max_length=100)  # e.g. ICD-10 or SNOMED code
    description = models.TextField()
    onset_date = models.DateField()
    status = models.CharField(max_length=50)  # active, resolved, etc.

class MedicationStatement(models.Model):
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name="medical_medications")
    patient = models.ForeignKey("Patients.Patient", on_delete=models.CASCADE)
    medication_name = models.CharField(max_length=100)
    dosage = models.CharField(max_length=100)
    route = models.CharField(max_length=50, blank=True)  # oral, IV, etc.
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

class AllergyIntolerance(models.Model):
    patient = models.ForeignKey("Patients.Patient", on_delete=models.CASCADE, related_name="medical_allergies")
    substance = models.CharField(max_length=100)
    reaction = models.TextField()
    severity = models.CharField(max_length=50)
    recorded_date = models.DateField()

class Procedure(models.Model):
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name="medical_procedures")
    patient = models.ForeignKey("Patients.Patient", on_delete=models.CASCADE)
    procedure_name = models.CharField(max_length=100)
    code = models.CharField(max_length=100)
    performed_date = models.DateField()
    outcome = models.TextField(blank=True)

class Immunization(models.Model):
    patient = models.ForeignKey("Patients.Patient", on_delete=models.CASCADE, related_name="medical_immunizations")
    vaccine_name = models.CharField(max_length=100)
    date_administered = models.DateField()
    lot_number = models.CharField(max_length=50, blank=True)
    performer = models.CharField(max_length=100, blank=True)


class DocumentReference(models.Model):
    patient = models.ForeignKey("Patients.Patient", on_delete=models.CASCADE, related_name="medical_documents")
    file = models.FileField(upload_to="documents/")
    title = models.CharField(max_length=255)
    type = models.CharField(max_length=100)  # e.g. discharge summary, lab report
    date_uploaded = models.DateTimeField(auto_now_add=True)
