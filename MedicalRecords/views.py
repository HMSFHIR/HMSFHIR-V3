from django.forms import inlineformset_factory
from django.utils.timezone import make_aware, is_naive
from datetime import datetime
from Patients.views import Patient
from .models import (
    Encounter, Observation, Condition, MedicationStatement,
    Procedure, AllergyIntolerance, Immunization
)
from .forms import (
    EncounterForm, ObservationForm, ConditionForm,
    MedicationStatementForm, AllergyIntoleranceForm,
    ProcedureForm, ImmunizationForm,
)
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

def MedicalRecordsView(request):
    patient_count = Patient.objects.count()
    context = {
        'patient_count': patient_count,
    }
    return render(request, 'MedicalRecords/medical_records.html', context)


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
            
            # Set the instance for all formsets
            obs_formset.instance = encounter
            cond_formset.instance = encounter
            med_formset.instance = encounter
            proc_formset.instance = encounter

            # Save formsets and set patient for each instance
            for formset in [obs_formset, cond_formset, med_formset, proc_formset]:
                instances = formset.save(commit=False)
                for instance in instances:
                    # Set the patient from the encounter
                    instance.patient = encounter.patient
                    instance.save()
                # Save any remaining instances
                formset.save_m2m()

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


def normalize_datetime(dt):
    if dt is None:
        return make_aware(datetime.min)
    if isinstance(dt, datetime):
        return make_aware(dt) if is_naive(dt) else dt
    # It's a date object, convert to datetime
    return make_aware(datetime.combine(dt, datetime.min.time()))


def medical_records_view(request):
    records = []

    def patient_info(patient):
        return {
            'patient_id': patient.patient_id,
            'gender': patient.gender,
            'national_id': patient.national_id,
        }

    # Encounter
    for encounter in Encounter.objects.select_related('patient').all():
        info = patient_info(encounter.patient)
        records.append({
            'record_type': 'Encounter',
            'fhir_id': f'enc-{encounter.id}',
            'last_arrived': normalize_datetime(encounter.start_time),
            'record_id': encounter.id,
            **info
        })

    # Observation
    for obs in Observation.objects.select_related('patient').all():
        info = patient_info(obs.patient)
        records.append({
            'record_type': 'Observation',
            'fhir_id': f'obs-{obs.id}',
            'last_arrived': normalize_datetime(obs.observation_time),
            'record_id': obs.id,
            **info
        })

    # Condition
    for con in Condition.objects.select_related('patient').all():
        info = patient_info(con.patient)
        records.append({
            'record_type': 'Condition',
            'fhir_id': f'con-{con.id}',
            'last_arrived': normalize_datetime(con.onset_date),
            'record_id': con.id,
            **info
        })

    # MedicationStatement
    for med in MedicationStatement.objects.select_related('patient').all():
        info = patient_info(med.patient)
        records.append({
            'record_type': 'Medication',
            'fhir_id': f'med-{med.id}',
            'last_arrived': normalize_datetime(med.start_date),
            'record_id': med.id,
            **info
        })

    # AllergyIntolerance
    for allergy in AllergyIntolerance.objects.select_related('patient').all():
        info = patient_info(allergy.patient)
        records.append({
            'record_type': 'Allergy',
            'fhir_id': f'allergy-{allergy.id}',
            'last_arrived': normalize_datetime(allergy.recorded_date),
            'record_id': allergy.id,
            **info
        })

    # Procedure
    for proc in Procedure.objects.select_related('patient').all():
        info = patient_info(proc.patient)
        records.append({
            'record_type': 'Procedure',
            'fhir_id': f'proc-{proc.id}',
            'last_arrived': normalize_datetime(proc.performed_date),
            'record_id': proc.id,
            **info
        })

    # Immunization
    for imm in Immunization.objects.select_related('patient').all():
        info = patient_info(imm.patient)
        records.append({
            'record_type': 'Immunization',
            'fhir_id': f'imm-{imm.id}',
            'last_arrived': normalize_datetime(imm.date_administered),
            'record_id': imm.id,
            **info
        })

    # Sort all records by most recent first
    records = sorted(records, key=lambda r: r['last_arrived'], reverse=True)

    context = {'medical_records': records}
    return render(request, 'MedicalRecords/medical_records.html', context)




def view_medical_record_detail(request, record_type, record_id):
    """View details of a specific medical record"""
    context = {}
    
    # Map record types to models
    model_mapping = {
        'Encounter': Encounter,
        'Observation': Observation,
        'Condition': Condition,
        'Medication': MedicationStatement,
        'Allergy': AllergyIntolerance,
        'Procedure': Procedure,
        'Immunization': Immunization,
    }
    
    if record_type not in model_mapping:
        messages.error(request, f"Invalid record type: {record_type}")
        return redirect('MedicalRecords')
    
    model_class = model_mapping[record_type]
    
    try:
        record = get_object_or_404(model_class, id=record_id)
        
        # Get FHIR representation
        fhir_data = record.to_fhir_dict()
        
        context = {
            'record': record,
            'record_type': record_type,
            'fhir_data': fhir_data,
            'patient': record.patient,
            'formatted_fhir': json.dumps(fhir_data, indent=2)
        }
        
        # Add encounter context if the record has one
        if hasattr(record, 'encounter') and record.encounter:
            context['encounter'] = record.encounter
            
    except Exception as e:
        messages.error(request, f"Error retrieving {record_type} record: {str(e)}")
        return redirect('MedicalRecords')
    
    return render(request, 'MedicalRecords/record_detail.html', context)


def delete_medical_record(request, record_type, record_id):
    """Delete a specific medical record"""
    model_mapping = {
        'Encounter': Encounter,
        'Observation': Observation,
        'Condition': Condition,
        'Medication': MedicationStatement,
        'Allergy': AllergyIntolerance,
        'Procedure': Procedure,
        'Immunization': Immunization,
    }
    
    if record_type not in model_mapping:
        messages.error(request, f"Invalid record type: {record_type}")
        return redirect('MedicalRecords')
    
    model_class = model_mapping[record_type]
    record = get_object_or_404(model_class, id=record_id)
    
    if request.method == 'POST':
        try:
            # Store patient info for success message
            patient_name = record.patient.full_name
            record.delete()
            messages.success(request, f"{record_type} record for {patient_name} has been deleted successfully.")
        except Exception as e:
            messages.error(request, f"Error deleting record: {str(e)}")
        
        return redirect('MedicalRecords')
    
    # For GET request, show confirmation page
    context = {
        'record': record,
        'record_type': record_type,
        'patient': record.patient
    }
    
    return render(request, 'MedicalRecords/confirm_delete.html', context)


def edit_medical_record(request, record_type, record_id):
    """Edit a specific medical record"""
    model_mapping = {
        'Encounter': (Encounter, EncounterForm),
        'Observation': (Observation, ObservationForm),
        'Condition': (Condition, ConditionForm),
        'Medication': (MedicationStatement, MedicationStatementForm),
        'Allergy': (AllergyIntolerance, AllergyIntoleranceForm),
        'Procedure': (Procedure, ProcedureForm),
        'Immunization': (Immunization, ImmunizationForm),
    }
    
    if record_type not in model_mapping:
        messages.error(request, f"Invalid record type: {record_type}")
        return redirect('MedicalRecords')
    
    model_class, form_class = model_mapping[record_type]
    record = get_object_or_404(model_class, id=record_id)
    
    if request.method == 'POST':
        form = form_class(request.POST, instance=record)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, f"{record_type} record updated successfully.")
                return redirect('view_medical_record_detail', record_type=record_type, record_id=record_id)
            except Exception as e:
                messages.error(request, f"Error updating record: {str(e)}")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = form_class(instance=record)
    
    context = {
        'form': form,
        'record': record,
        'record_type': record_type,
        'patient': record.patient
    }
    
    return render(request, 'MedicalRecords/edit_record.html', context)


@csrf_exempt
def get_record_fhir_json(request, record_type, record_id):
    """API endpoint to get FHIR JSON for a record"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    model_mapping = {
        'Encounter': Encounter,
        'Observation': Observation,
        'Condition': Condition,
        'Medication': MedicationStatement,
        'Allergy': AllergyIntolerance,
        'Procedure': Procedure,
        'Immunization': Immunization,
    }
    
    if record_type not in model_mapping:
        return JsonResponse({'error': f'Invalid record type: {record_type}'}, status=400)
    
    model_class = model_mapping[record_type]
    
    try:
        record = get_object_or_404(model_class, id=record_id)
        fhir_data = record.to_fhir_dict()
        return JsonResponse(fhir_data, json_dumps_params={'indent': 2})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)