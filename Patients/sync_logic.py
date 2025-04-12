def run_sync():
    from django.conf import settings
    import requests
    from Patients.models import Patient

    FHIR_SERVER_URL = settings.FHIR_SERVER_BASE_URL
    patients = Patient.objects.all()

    for patient in patients:
        if not patient.patient_id:
            print(f"⚠️ Skipping patient {patient.name} — no ID assigned.")
            continue  # Skip this patient if there's no ID

        name_parts = patient.name.split()
        family_name = name_parts[1] if len(name_parts) > 1 else ""
        given_name = name_parts[0]

        patient_data = {
            "resourceType": "Patient",
            "id": patient.patient_id,
            "name": [{"use": "official", "family": family_name, "given": [given_name]}],
            "gender": patient.gender,
            "birthDate": patient.birth_date.isoformat() if patient.birth_date else None,
            "identifier": [{"system": "urn:ietf:rfc:3986", "value": patient.national_id}],
        }

        try:
            put_url = f"{FHIR_SERVER_URL}/Patient/{patient.patient_id}"
            response = requests.put(
                put_url,
                json=patient_data,
                headers={"Content-Type": "application/fhir+json"}
            )

            if response.status_code in [200, 201]:
                print(f"✅ Successfully synced patient: {patient.name}")
                patient.last_arrived = patient.birth_date
                patient.save()
            else:
                print(f"❌ Failed to sync patient {patient.name}: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Error syncing patient {patient.name}: {e}")

    print("✅ Sync process completed.")
