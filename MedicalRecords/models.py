# encounter/models.py
from django.db import models
from django.utils import timezone
from Patients.models import Patient

class Encounter(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    encounter_type = models.CharField(max_length=100)
    reason = models.TextField()
    location = models.CharField(max_length=100)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=50)
    
    def to_fhir_dict(self):
        return {
            "resourceType": "Encounter",
            "status": self.status,
            "class": {"code": "AMB"},  # example
            "type": [{"text": self.encounter_type}],
            "subject": {"reference": f"Patient/{self.patient.patient_id}"},
            "period": {
                "start": self.start_time.isoformat(),
                "end": self.end_time.isoformat()
            },
            "reasonCode": [{"text": self.reason}],
            "location": [{"location": {"display": self.location}}]
        }

class Observation(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE)  # ForeignKey to Encounter
    code = models.CharField(max_length=255)
    value = models.CharField(max_length=255)
    unit = models.CharField(max_length=100)
    observation_time = models.DateTimeField()
    
    def __str__(self):
        return f"Observation for {self.patient} during {self.encounter}"
    
    def to_fhir_dict(self):
        return {
            "resourceType": "Observation",
            "status": "final",
            "code": {"text": self.code},
            "subject": {"reference": f"Patient/{self.patient.patient_id}"},
            "encounter": {"reference": f"Encounter/{self.encounter.id}"},
            "effectiveDateTime": self.observation_time.isoformat(),
            "valueQuantity": {
                "value": self.value,
                "unit": self.unit
            }
        }

class Condition(models.Model):
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name="medical_conditions")
    patient = models.ForeignKey("Patients.Patient", on_delete=models.CASCADE)
    code = models.CharField(max_length=100)  # e.g. ICD-10 or SNOMED code
    description = models.TextField()
    onset_date = models.DateField()
    status = models.CharField(max_length=50)  # active, resolved, etc.
    
    def to_fhir_dict(self):
        return {
            "resourceType": "Condition",
            "clinicalStatus": {"coding": [{"code": self.status}]},
            "code": {"text": self.description, "coding": [{"code": self.code}]},
            "subject": {"reference": f"Patient/{self.patient.patient_id}"},
            "encounter": {"reference": f"Encounter/{self.encounter.id}"},
            "onsetDate": self.onset_date.isoformat()
        }

class MedicationStatement(models.Model):
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name="medical_medications")
    patient = models.ForeignKey("Patients.Patient", on_delete=models.CASCADE)
    medication_name = models.CharField(max_length=100)
    dosage = models.CharField(max_length=100)
    route = models.CharField(max_length=50, blank=True)  # oral, IV, etc.
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    
    def to_fhir_dict(self):
        return {
            "resourceType": "MedicationStatement",
            "status": "active",
            "medicationCodeableConcept": {"text": self.medication_name},
            "subject": {"reference": f"Patient/{self.patient.patient_id}"},
            "context": {"reference": f"Encounter/{self.encounter.id}"},
            "effectivePeriod": {
                "start": self.start_date.isoformat(),
                "end": self.end_date.isoformat() if self.end_date else None
            },
            "dosage": [{
                "text": self.dosage,
                "route": {"text": self.route} if self.route else None
            }]
        }

class AllergyIntolerance(models.Model):
    patient = models.ForeignKey("Patients.Patient", on_delete=models.CASCADE, related_name="medical_allergies")
    substance = models.CharField(max_length=100)
    reaction = models.TextField()
    severity = models.CharField(max_length=50)
    recorded_date = models.DateField()
    
    def to_fhir_dict(self):
        return {
            "resourceType": "AllergyIntolerance",
            "clinicalStatus": {"coding": [{"code": "active"}]},
            "code": {"text": self.substance},
            "patient": {"reference": f"Patient/{self.patient.patient_id}"},
            "recordedDate": self.recorded_date.isoformat(),
            "reaction": [{
                "manifestation": [{"text": self.reaction}],
                "severity": self.severity
            }]
        }

class Procedure(models.Model):
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name="medical_procedures")
    patient = models.ForeignKey("Patients.Patient", on_delete=models.CASCADE)
    procedure_name = models.CharField(max_length=100)
    code = models.CharField(max_length=100)
    performed_date = models.DateField()
    outcome = models.TextField(blank=True)
    
    def to_fhir_dict(self):
        return {
            "resourceType": "Procedure",
            "status": "completed",
            "code": {"text": self.procedure_name, "coding": [{"code": self.code}]},
            "subject": {"reference": f"Patient/{self.patient.patient_id}"},
            "encounter": {"reference": f"Encounter/{self.encounter.id}"},
            "performedDate": self.performed_date.isoformat(),
            "outcome": {"text": self.outcome} if self.outcome else None
        }

class Immunization(models.Model):
    patient = models.ForeignKey("Patients.Patient", on_delete=models.CASCADE, related_name="medical_immunizations")
    vaccine_name = models.CharField(max_length=100)
    date_administered = models.DateField()
    lot_number = models.CharField(max_length=50, blank=True)
    performer = models.CharField(max_length=100, blank=True)
    
    def to_fhir_dict(self):
        return {
            "resourceType": "Immunization",
            "status": "completed",
            "vaccineCode": {"text": self.vaccine_name},
            "patient": {"reference": f"Patient/{self.patient.patient_id}"},
            "occurrenceDateTime": self.date_administered.isoformat(),
            "lotNumber": self.lot_number if self.lot_number else None,
            "performer": [{"actor": {"display": self.performer}}] if self.performer else None
        }

class DocumentReference(models.Model):
    patient = models.ForeignKey("Patients.Patient", on_delete=models.CASCADE, related_name="medical_documents")
    file = models.FileField(upload_to="documents/")
    title = models.CharField(max_length=255)
    type = models.CharField(max_length=100)  # e.g. discharge summary, lab report
    date_uploaded = models.DateTimeField(auto_now_add=True)
    
    def to_fhir_dict(self):
        return {
            "resourceType": "DocumentReference",
            "status": "current",
            "type": {"text": self.type},
            "subject": {"reference": f"Patient/{self.patient.patient_id}"},
            "date": self.date_uploaded.isoformat(),
            "description": self.title,
            "content": [{
                "attachment": {
                    "title": self.title,
                    "url": self.file.url if self.file else None
                }
            }]
        }