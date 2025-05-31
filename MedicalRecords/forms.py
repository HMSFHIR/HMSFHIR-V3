from django import forms
from .models import (
    Encounter, Observation, Condition,
    MedicationStatement, AllergyIntolerance,
    Procedure, Immunization, DocumentReference
)


# 🌟 Main Encounter Form
class EncounterForm(forms.ModelForm):


    class Meta:
        model = Encounter
        fields = ['patient', 'encounter_type', 'reason', 'location', 'start_time', 'end_time', 'status']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['patient'].label = "Patient"
        self.fields['encounter_type'].label = "Encounter Type"
        self.fields['reason'].label = "Reason for Encounter"
        self.fields['location'].label = "Location"
        self.fields['start_time'].label = "Start Time"
        self.fields['end_time'].label = "End Time"
        self.fields['status'].label = "Encounter Status"

        self.fields['patient'].help_text = "Select the patient for the encounter"
        self.fields['encounter_type'].help_text = "Specify the type of encounter (e.g., Emergency, Routine)"
        self.fields['reason'].help_text = "Enter the reason for the encounter"
        self.fields['location'].help_text = "Specify the location of the encounter"
        self.fields['start_time'].help_text = "Enter the start time of the encounter"
        self.fields['end_time'].help_text = "Enter the end time of the encounter"
        self.fields['status'].help_text = "Specify the status of the encounter (e.g., Active, Completed)"

        self.fields['start_time'].widget = forms.DateTimeInput(attrs={'type': 'datetime-local'})
        self.fields['end_time'].widget = forms.DateTimeInput(attrs={'type': 'datetime-local'})


# ✅ Inline Forms
class ObservationForm(forms.ModelForm):
    class Meta:
        model = Observation
        fields = ['patient','code', 'value', 'unit', 'observation_time']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['code'].label = "Observation Type (e.g., Blood Pressure)"
        self.fields['value'].label = "Value (e.g., 120/80)"
        self.fields['unit'].label = "Unit (e.g., mmHg)"
        self.fields['observation_time'].label = "Date & Time Observed"

        self.fields['code'].help_text = "Specify the type of observation (e.g., blood pressure, temperature)"
        self.fields['value'].help_text = "Enter the value of the observation (e.g., 120/80)"
        self.fields['unit'].help_text = "Enter the unit of measurement (e.g., mmHg for blood pressure)"
        self.fields['observation_time'].help_text = "Enter the date and time when the observation was recorded"

        self.fields['observation_time'].widget = forms.DateTimeInput(attrs={'type': 'datetime-local'})


class ConditionForm(forms.ModelForm):
    class Meta:
        model = Condition
        fields = ['code', 'description', 'onset_date', 'status']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['code'].label = "Condition Code (e.g., ICD-10)"
        self.fields['description'].label = "Condition Description"
        self.fields['onset_date'].label = "Date of Onset"
        self.fields['status'].label = "Condition Status"
        
        self.fields['code'].help_text = "Enter the code of the condition (e.g., ICD-10, SNOMED)"
        self.fields['description'].help_text = "Provide a detailed description of the condition"
        self.fields['onset_date'].help_text = "Enter the date the condition was first observed"
        self.fields['status'].help_text = "Specify whether the condition is active, resolved, etc."
        
        self.fields['onset_date'].widget = forms.DateInput(attrs={'type': 'date'})


class MedicationStatementForm(forms.ModelForm):
    class Meta:
        model = MedicationStatement
        fields = ['medication_name', 'dosage', 'route', 'start_date', 'end_date']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['medication_name'].label = "Medication Name"
        self.fields['dosage'].label = "Dosage (e.g., 50mg)"
        self.fields['route'].label = "Route (e.g., Oral, IV)"
        self.fields['start_date'].label = "Start Date"
        self.fields['end_date'].label = "End Date (Optional)"

        self.fields['medication_name'].help_text = "Enter the name of the medication"
        self.fields['dosage'].help_text = "Specify the dosage of the medication"
        self.fields['route'].help_text = "Specify how the medication is administered (e.g., orally, intravenously)"
        self.fields['start_date'].help_text = "Enter the date when the medication was started"
        self.fields['end_date'].help_text = "Optional: Enter the date when the medication was discontinued"

        self.fields['start_date'].widget = forms.DateInput(attrs={'type': 'date'})
        self.fields['end_date'].widget = forms.DateInput(attrs={'type': 'date'})


class AllergyIntoleranceForm(forms.ModelForm):
    class Meta:
        model = AllergyIntolerance
        fields = ['substance', 'reaction', 'severity', 'recorded_date']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['substance'].label = "Allergen Substance"
        self.fields['reaction'].label = "Reaction"
        self.fields['severity'].label = "Severity"
        self.fields['recorded_date'].label = "Recorded Date"

        self.fields['substance'].help_text = "Enter the substance causing the allergy"
        self.fields['reaction'].help_text = "Enter the reaction caused by the allergen"
        self.fields['severity'].help_text = "Specify the severity of the reaction (e.g., Mild, Severe)"
        self.fields['recorded_date'].help_text = "Enter the date when the allergy was recorded"

        self.fields['recorded_date'].widget = forms.DateInput(attrs={'type': 'date'})


class ProcedureForm(forms.ModelForm):
    class Meta:
        model = Procedure
        fields = ['procedure_name', 'code', 'performed_date', 'outcome']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['procedure_name'].label = "Procedure Name"
        self.fields['code'].label = "Procedure Code"
        self.fields['performed_date'].label = "Date Performed"
        self.fields['outcome'].label = "Procedure Outcome"

        self.fields['procedure_name'].help_text = "Enter the name of the procedure performed"
        self.fields['code'].help_text = "Enter the code for the procedure (e.g., CPT, ICD-10)"
        self.fields['performed_date'].help_text = "Enter the date when the procedure was performed"
        self.fields['outcome'].help_text = "Optional: Provide any outcome or result of the procedure"

        self.fields['performed_date'].widget = forms.DateInput(attrs={'type': 'date'})


class ImmunizationForm(forms.ModelForm):
    class Meta:
        model = Immunization
        fields = ['vaccine_name', 'date_administered', 'lot_number', 'performer']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['vaccine_name'].label = "Vaccine Name"
        self.fields['date_administered'].label = "Date Administered"
        self.fields['lot_number'].label = "Lot Number"
        self.fields['performer'].label = "Vaccine Performer"

        self.fields['vaccine_name'].help_text = "Enter the name of the vaccine administered"
        self.fields['date_administered'].help_text = "Enter the date when the vaccine was administered"
        self.fields['lot_number'].help_text = "Enter the vaccine lot number"
        self.fields['performer'].help_text = "Enter the name of the person who administered the vaccine"

        self.fields['date_administered'].widget = forms.DateInput(attrs={'type': 'date'})


class DocumentReferenceForm(forms.ModelForm):
    class Meta:
        model = DocumentReference
        fields = ['file', 'title', 'type']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['file'].label = "File"
        self.fields['title'].label = "Document Title"
        self.fields['type'].label = "Document Type"

        self.fields['file'].help_text = "Upload the document file"
        self.fields['title'].help_text = "Provide a title for the document"
        self.fields['type'].help_text = "Specify the type of document (e.g., PDF, Word)"

