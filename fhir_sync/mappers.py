# fhir_sync/mappers.py
"""
FHIR Resource Mappers - Convert HMS models to FHIR JSON format
"""
from datetime import datetime
from django.utils import timezone

def patient_to_fhir(patient):
    """Convert Patient model to FHIR Patient resource"""
    return patient.to_json()  # Already implemented in your model

def practitioner_to_fhir(practitioner):
    """Convert Practitioner model to FHIR Practitioner resource"""
    name_parts = practitioner.name.split()
    family = name_parts[-1] if len(name_parts) > 1 else practitioner.name
    given = name_parts[:-1] if len(name_parts) > 1 else []
    
    return {
        "resourceType": "Practitioner",
        "id": practitioner.practitioner_id,
        "identifier": [
            {
                "use": "official",
                "value": practitioner.practitioner_id,
                "system": "http://example.org/practitioner-id"
            }
        ],
        "name": [
            {
                "use": "official",
                "family": family,
                "given": given
            }
        ],
        "telecom": [
            {
                "system": "phone",
                "value": practitioner.phone,
                "use": "work"
            } if practitioner.phone else None,
            {
                "system": "email",
                "value": practitioner.email,
                "use": "work"
            }
        ],
        "qualification": [
            {
                "code": {
                    "text": practitioner.role.title()
                }
            }
        ],
        "extension": [
            {
                "url": "http://example.org/fhir/StructureDefinition/hospital-affiliation",
                "valueString": practitioner.hospital_affiliation
            }
        ]
    }

def appointment_to_encounter(appointment):
    """Convert Appointment model to FHIR Encounter resource"""
    status_mapping = {
        'Completed': 'finished',
        'Scheduled': 'planned',
        'Cancelled': 'cancelled'
    }
    
    return {
        "resourceType": "Encounter",
        "id": str(appointment.appointment_id),
        "status": status_mapping.get(appointment.status, 'planned'),
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": "AMB",
            "display": "ambulatory"
        },
        "subject": {
            "reference": f"Patient/{appointment.patient.patient_id}",
            "display": appointment.patient.name
        },
        "participant": [
            {
                "individual": {
                    "reference": f"Practitioner/{appointment.practitioner.practitioner_id}",
                    "display": appointment.practitioner.name
                } if appointment.practitioner else None
            }
        ] if appointment.practitioner else [],
        "period": {
            "start": appointment.appointment_date.isoformat()
        },
        "reasonCode": [
            {
                "text": appointment.notes
            }
        ] if appointment.notes else []
    }

def encounter_to_fhir(encounter):
    """Convert Encounter model to FHIR Encounter resource"""
    return {
        "resourceType": "Encounter",
        "id": str(encounter.id),
        "status": encounter.status.lower() if encounter.status else "finished",
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": "AMB",
            "display": "ambulatory"
        },
        "type": [
            {
                "text": encounter.encounter_type
            }
        ],
        "subject": {
            "reference": f"Patient/{encounter.patient.patient_id}",
            "display": encounter.patient.name
        },
        "period": {
            "start": encounter.start_time.isoformat(),
            "end": encounter.end_time.isoformat()
        },
        "reasonCode": [
            {
                "text": encounter.reason
            }
        ],
        "location": [
            {
                "location": {
                    "display": encounter.location
                }
            }
        ]
    }

def observation_to_fhir(observation):
    """Convert Observation model to FHIR Observation resource"""
    return {
        "resourceType": "Observation",
        "id": str(observation.id),
        "status": "final",
        "code": {
            "text": observation.code
        },
        "subject": {
            "reference": f"Patient/{observation.patient.patient_id}",
            "display": observation.patient.name
        },
        "encounter": {
            "reference": f"Encounter/{observation.encounter.id}"
        },
        "effectiveDateTime": observation.observation_time.isoformat(),
        "valueString": observation.value,
        "component": [
            {
                "code": {
                    "text": "unit"
                },
                "valueString": observation.unit
            }
        ] if observation.unit else []
    }

def condition_to_fhir(condition):
    """Convert Condition model to FHIR Condition resource"""
    return {
        "resourceType": "Condition",
        "id": str(condition.id),
        "clinicalStatus": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                    "code": condition.status.lower() if condition.status else "active"
                }
            ]
        },
        "code": {
            "coding": [
                {
                    "system": "http://hl7.org/fhir/sid/icd-10",
                    "code": condition.code,
                    "display": condition.description
                }
            ],
            "text": condition.description
        },
        "subject": {
            "reference": f"Patient/{condition.patient.patient_id}",
            "display": condition.patient.name
        },
        "encounter": {
            "reference": f"Encounter/{condition.encounter.id}"
        },
        "onsetDate": condition.onset_date.isoformat()
    }

def medication_statement_to_fhir(medication):
    """Convert MedicationStatement model to FHIR MedicationStatement resource"""
    return {
        "resourceType": "MedicationStatement",
        "id": str(medication.id),
        "status": "active",
        "medicationCodeableConcept": {
            "text": medication.medication_name
        },
        "subject": {
            "reference": f"Patient/{medication.patient.patient_id}",
            "display": medication.patient.name
        },
        "context": {
            "reference": f"Encounter/{medication.encounter.id}"
        },
        "effectivePeriod": {
            "start": medication.start_date.isoformat(),
            "end": medication.end_date.isoformat() if medication.end_date else None
        },
        "dosage": [
            {
                "text": medication.dosage,
                "route": {
                    "text": medication.route
                } if medication.route else None
            }
        ]
    }

def allergy_intolerance_to_fhir(allergy):
    """Convert AllergyIntolerance model to FHIR AllergyIntolerance resource"""
    return {
        "resourceType": "AllergyIntolerance",
        "id": str(allergy.id),
        "clinicalStatus": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
                    "code": "active"
                }
            ]
        },
        "code": {
            "text": allergy.substance
        },
        "patient": {
            "reference": f"Patient/{allergy.patient.patient_id}",
            "display": allergy.patient.name
        },
        "recordedDate": allergy.recorded_date.isoformat(),
        "reaction": [
            {
                "manifestation": [
                    {
                        "text": allergy.reaction
                    }
                ],
                "severity": allergy.severity.lower()
            }
        ]
    }

def procedure_to_fhir(procedure):
    """Convert Procedure model to FHIR Procedure resource"""
    return {
        "resourceType": "Procedure",
        "id": str(procedure.id),
        "status": "completed",
        "code": {
            "coding": [
                {
                    "code": procedure.code,
                    "display": procedure.procedure_name
                }
            ],
            "text": procedure.procedure_name
        },
        "subject": {
            "reference": f"Patient/{procedure.patient.patient_id}",
            "display": procedure.patient.name
        },
        "encounter": {
            "reference": f"Encounter/{procedure.encounter.id}"
        },
        "performedDate": procedure.performed_date.isoformat(),
        "outcome": {
            "text": procedure.outcome
        } if procedure.outcome else None
    }

def immunization_to_fhir(immunization):
    """Convert Immunization model to FHIR Immunization resource"""
    return {
        "resourceType": "Immunization",
        "id": str(immunization.id),
        "status": "completed",
        "vaccineCode": {
            "text": immunization.vaccine_name
        },
        "patient": {
            "reference": f"Patient/{immunization.patient.patient_id}",
            "display": immunization.patient.name
        },
        "occurrenceDateTime": immunization.date_administered.isoformat(),
        "lotNumber": immunization.lot_number,
        "performer": [
            {
                "actor": {
                    "display": immunization.performer
                }
            }
        ] if immunization.performer else []
    }

def document_reference_to_fhir(document):
    """Convert DocumentReference model to FHIR DocumentReference resource"""
    return {
        "resourceType": "DocumentReference",
        "id": str(document.id),
        "status": "current",
        "type": {
            "text": document.type
        },
        "subject": {
            "reference": f"Patient/{document.patient.patient_id}",
            "display": document.patient.name
        },
        "date": document.date_uploaded.isoformat(),
        "description": document.title,
        "content": [
            {
                "attachment": {
                    "title": document.title,
                    "url": document.file.url if document.file else None
                }
            }
        ]
    }

# Mapper registry
FHIR_MAPPERS = {
    'Patient': patient_to_fhir,
    'Practitioner': practitioner_to_fhir,
    'Encounter': encounter_to_fhir,
    'Observation': observation_to_fhir,
    'Condition': condition_to_fhir,
    'MedicationStatement': medication_statement_to_fhir,
    'AllergyIntolerance': allergy_intolerance_to_fhir,
    'Procedure': procedure_to_fhir,
    'Immunization': immunization_to_fhir,
    'DocumentReference': document_reference_to_fhir,
}