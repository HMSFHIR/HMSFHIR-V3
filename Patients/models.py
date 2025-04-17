from django.db import models
from Practitioner.models import Practitioner
from datetime import date
from django.utils import timezone

#  Patient Model (FHIR-Compatible)
class Patient(models.Model):
    patient_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    gender = models.CharField(max_length=10, choices=[
        ("male", "Male"), ("female", "Female"), ("other", "Other")
    ])
    birth_date = models.DateField(null=True, blank=True)
    national_id = models.CharField(max_length=50, unique=True)
    last_arrived = models.DateField(null=True, blank=True)  # Last visit date



    def to_json(self):
        name_parts = self.name.split()
        family = name_parts[-1] if len(name_parts) > 1 else self.name
        given = name_parts[:-1] if len(name_parts) > 1 else []

        return {
        "resourceType": "Patient",
        "id": self.patient_id,
        "identifier": [
            {
                "use": "official",
                "type": {
                    "text": "National ID"
                },
                "value": self.national_id,
                "system": "http://example.org/national-id"
            }
        ],
        "name": [
            {
                "use": "official",
                "family": family,
                "given": given
            }
        ],
        "gender": self.gender,
        "birthDate": self.birth_date.isoformat() if self.birth_date else None,
        "extension": [
            {
                "url": "http://example.org/fhir/StructureDefinition/last-arrived",
                "valueDate": self.last_arrived.isoformat() if self.last_arrived else date.today().isoformat()
            }
        ]
    }

    def __str__(self):
        return f"{self.name} ({self.patient_id})"


#  Encounter Model (Merged)
class Encounter(models.Model):
    encounter_id = models.CharField(max_length=100, unique=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    practitioner = models.ForeignKey(Practitioner, on_delete=models.SET_NULL, null=True)
    encounter_type = models.CharField(max_length=50, choices=[
        ("inpatient", "Inpatient"), ("outpatient", "Outpatient"),
        ("emergency", "Emergency"), ("telehealth", "Telehealth")
    ])
    status = models.CharField(max_length=20, choices=[
        ("planned", "Planned"), ("in-progress", "In Progress"),
        ("completed", "Completed"), ("cancelled", "Cancelled")
    ])
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Encounter {self.encounter_id} - {self.patient.name} ({self.encounter_type})"

#  Observation Model
#  Condition Model
class Condition(models.Model):
    condition_id = models.AutoField(primary_key=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='conditions')  # specify related_name
    encounter = models.ForeignKey(Encounter, on_delete=models.SET_NULL, blank=True, null=True)
    recorded_date = models.DateTimeField(blank=True, null=True)
    recorder = models.ForeignKey(Practitioner, on_delete=models.SET_NULL, blank=True, null=True)
    
    diagnosis = models.TextField()
    severity = models.CharField(max_length=100, blank=True, null=True)
    clinical_status = models.CharField(max_length=100, blank=True, null=True)
    verification_status = models.CharField(max_length=100, blank=True, null=True)
    
    onset = models.CharField(max_length=255, blank=True, null=True)
    abatement = models.CharField(max_length=255, blank=True, null=True)

    allergies = models.TextField(blank=True, null=True)
    medications = models.TextField(blank=True, null=True)
    test_results = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Condition {self.condition_id} - {self.patient.name}"


#  Observation Model
class Observation(models.Model):
    observation_id = models.CharField(max_length=100, unique=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='observations')  # specify related_name
    encounter = models.ForeignKey(Encounter, on_delete=models.SET_NULL, null=True, blank=True)
    category = models.CharField(max_length=50, choices=[
        ("vital-signs", "Vital Signs"), ("laboratory", "Laboratory"),
        ("imaging", "Imaging"), ("social-history", "Social History"),
        ("diagnostic", "Diagnostic")
    ])
    observation_type = models.CharField(max_length=255)  # e.g., "Blood Pressure"
    value = models.CharField(max_length=100)  # e.g., "120/80 mmHg"
    unit = models.CharField(max_length=50, blank=True, null=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.patient.name} - {self.observation_type}: {self.value} {self.unit}"




class FHIRSyncTask(models.Model):
    resource_type = models.CharField(max_length=100, default="Patient")
    resource_id = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=[
        ("pending", "Pending"),
        ("synced", "Synced"),
        ("failed", "Failed"),
    ], default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    synced_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.resource_type} - {self.resource_id} ({self.status})"

