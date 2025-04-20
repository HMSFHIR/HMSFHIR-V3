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

