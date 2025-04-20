from django.shortcuts import render, redirect
from django.forms import inlineformset_factory

from .models import (
    Encounter, Observation, Condition, MedicationStatement,
    Procedure, DocumentReference, AllergyIntolerance, Immunization
)
from .forms import (
    EncounterForm, ObservationForm, ConditionForm,
    MedicationStatementForm, AllergyIntoleranceForm,
    ProcedureForm, ImmunizationForm, DocumentReferenceForm
)

# Create your views here.
def MedicalRecordsView(request):
    return render(request, 'MedicalRecords/medical_records.html')


def add_medical_record(request):
    ObservationFormSet = inlineformset_factory(Encounter, Observation, form=ObservationForm, extra=1)
    ConditionFormSet = inlineformset_factory(Encounter, Condition, form=ConditionForm, extra=1)
    MedicationFormSet = inlineformset_factory(Encounter, MedicationStatement, form=MedicationStatementForm, extra=1)
    ProcedureFormSet = inlineformset_factory(Encounter, Procedure, form=ProcedureForm, extra=1)

    if request.method == 'POST':
        encounter_form = EncounterForm(request.POST)
        obs_formset = ObservationFormSet(request.POST, prefix="obs")
        cond_formset = ConditionFormSet(request.POST, prefix="cond")
        med_formset = MedicationFormSet(request.POST, prefix="med")
        proc_formset = ProcedureFormSet(request.POST, prefix="proc")

        if all([
            encounter_form.is_valid(),
            obs_formset.is_valid(),
            cond_formset.is_valid(),
            med_formset.is_valid(),
            proc_formset.is_valid()
        ]):
            encounter = encounter_form.save()
            obs_formset.instance = encounter
            cond_formset.instance = encounter
            med_formset.instance = encounter
            proc_formset.instance = encounter

            obs_formset.save()
            cond_formset.save()
            med_formset.save()
            proc_formset.save()

            return redirect('MedicalRecords')

    else:
        encounter_form = EncounterForm()
        obs_formset = ObservationFormSet(prefix="obs")
        cond_formset = ConditionFormSet(prefix="cond")
        med_formset = MedicationFormSet(prefix="med")
        proc_formset = ProcedureFormSet(prefix="proc")

    return render(request, 'MedicalRecords/add_medical_record.html', {
        'encounter_form': encounter_form,
        'obs_formset': obs_formset,
        'cond_formset': cond_formset,
        'med_formset': med_formset,
        'proc_formset': proc_formset,
    })


def medical_records_view(request):
    records = []

    for encounter in Encounter.objects.select_related('patient').all():
        records.append({
            'record_type': 'Encounter',
            'fhir_id': f"enc-{encounter.id}",
            'patient_id': encounter.patient.id,
            'gender': encounter.patient.gender,
            'national_id': encounter.patient.national_id,
            'last_arrived': encounter.start_time,
            'record_id': encounter.id
        })

    for observation in Observation.objects.select_related('patient', 'encounter').all():
        records.append({
            'record_type': 'Observation',
            'fhir_id': f"obs-{observation.id}",
            'patient_id': observation.patient.id,
            'gender': observation.patient.gender,
            'national_id': observation.patient.national_id,
            'last_arrived': observation.observation_time,
            'record_id': observation.id
        })

    for condition in Condition.objects.select_related('patient', 'encounter').all():
        records.append({
            'record_type': 'Condition',
            'fhir_id': f"con-{condition.id}",
            'patient_id': condition.patient.id,
            'gender': condition.patient.gender,
            'national_id': condition.patient.national_id,
            'last_arrived': condition.onset_date,
            'record_id': condition.id
        })

    # Repeat this pattern for other models...

    context = {
        'medical_records': records
    }
    return render(request, 'MedicalRecords/medical_records.html', context)



def medical_records_view(request):
    records = []

    # Reusable function to extract common patient info
    def patient_info(patient):
        return {
            'patient_id': patient.id,
            'gender': patient.gender,
            'national_id': patient.national_id,
        }

    # Add Encounter records
    for encounter in Encounter.objects.select_related('patient').all():
        info = patient_info(encounter.patient)
        records.append({
            'record_type': 'Encounter',
            'fhir_id': f'enc-{encounter.id}',
            'last_arrived': encounter.start_time,
            'record_id': encounter.id,
            **info
        })

    # Observation
    for obs in Observation.objects.select_related('patient').all():
        info = patient_info(obs.patient)
        records.append({
            'record_type': 'Observation',
            'fhir_id': f'obs-{obs.id}',
            'last_arrived': obs.observation_time,
            'record_id': obs.id,
            **info
        })

    # Condition
    for con in Condition.objects.select_related('patient').all():
        info = patient_info(con.patient)
        records.append({
            'record_type': 'Condition',
            'fhir_id': f'con-{con.id}',
            'last_arrived': con.onset_date,
            'record_id': con.id,
            **info
        })

    # MedicationStatement
    for med in MedicationStatement.objects.select_related('patient').all():
        info = patient_info(med.patient)
        records.append({
            'record_type': 'Medication',
            'fhir_id': f'med-{med.id}',
            'last_arrived': med.start_date,
            'record_id': med.id,
            **info
        })

    # AllergyIntolerance
    for allergy in AllergyIntolerance.objects.select_related('patient').all():
        info = patient_info(allergy.patient)
        records.append({
            'record_type': 'Allergy',
            'fhir_id': f'allergy-{allergy.id}',
            'last_arrived': allergy.recorded_date,
            'record_id': allergy.id,
            **info
        })

    # Procedure
    for proc in Procedure.objects.select_related('patient').all():
        info = patient_info(proc.patient)
        records.append({
            'record_type': 'Procedure',
            'fhir_id': f'proc-{proc.id}',
            'last_arrived': proc.performed_date,
            'record_id': proc.id,
            **info
        })

    # Immunization
    for imm in Immunization.objects.select_related('patient').all():
        info = patient_info(imm.patient)
        records.append({
            'record_type': 'Immunization',
            'fhir_id': f'imm-{imm.id}',
            'last_arrived': imm.date_administered,
            'record_id': imm.id,
            **info
        })

    # DocumentReference
    for doc in DocumentReference.objects.select_related('patient').all():
        info = patient_info(doc.patient)
        records.append({
            'record_type': f'Document: {doc.type}',
            'fhir_id': f'doc-{doc.id}',
            'last_arrived': doc.date_uploaded,
            'record_id': doc.id,
            **info
        })

    # Sort all records by most recent first
    records = sorted(records, key=lambda r: r['last_arrived'] or '', reverse=True)

    context = {'medical_records': records}
    return render(request, 'MedicalRecords/medical_records.html', context)
