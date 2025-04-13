from Patients.models import Patient, FHIRSyncTask
from django.conf import settings
import requests
from django.utils import timezone

def run_sync():
    FHIR_SERVER_URL = settings.FHIR_SERVER_BASE_URL
    patients = Patient.objects.all()

    for patient in patients:
        if not patient.patient_id:
            print(f"⚠️ Skipping: {patient.name} (no patient_id)")
            continue

        # Compose FHIR resource
        name_parts = patient.name.split()
        given_name = name_parts[0]
        family_name = name_parts[1] if len(name_parts) > 1 else ""

        patient_data = {
            "resourceType": "Patient",
            "id": patient.patient_id,
            "name": [{"use": "official", "family": family_name, "given": [given_name]}],
            "gender": patient.gender,
            "birthDate": patient.birth_date.isoformat() if patient.birth_date else None,
            "identifier": [{
                "system": "urn:ietf:rfc:3986",
                "value": patient.national_id
            }],
        }

        try:
            response = requests.put(
                f"{FHIR_SERVER_URL}/Patient/{patient.patient_id}",
                json=patient_data,
                headers={"Content-Type": "application/fhir+json"}
            )

            if response.status_code in [200, 201]:
                print(f"✅ Synced: {patient.name}")
                patient.last_arrived = patient.birth_date
                patient.save()

                FHIRSyncTask.objects.update_or_create(
                    resource_type="Patient",
                    resource_id=patient.patient_id,
                    defaults={
                        "status": "synced",
                        "synced_at": timezone.now()
                    }
                )
            else:
                print(f"❌ Failed to sync {patient.name}: {response.status_code}")
                FHIRSyncTask.objects.update_or_create(
                    resource_type="Patient",
                    resource_id=patient.patient_id,
                    defaults={"status": "failed"}
                )
        except Exception as e:
            print(f"⚠️ Error syncing {patient.name}: {e}")
            FHIRSyncTask.objects.update_or_create(
                resource_type="Patient",
                resource_id=patient.patient_id,
                defaults={"status": "failed"}
            )

    print("✅ Sync complete.")
