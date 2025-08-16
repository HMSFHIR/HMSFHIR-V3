from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date, datetime
import re
from .models import (
    Encounter, Observation, Condition,
    MedicationStatement, AllergyIntolerance,
    Procedure, Immunization
    )



class EncounterForm(forms.ModelForm):
    class Meta:
        model = Encounter
        fields = ['patient', 'encounter_type', 'reason', 'location', 'start_time', 'end_time', 'status']
        widgets = {
            'start_time': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control',
                'required': True
            }),
            'end_time': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'reason': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Enter the reason for this encounter...'
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Emergency Room, Clinic Room 101'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Enhanced labels and help text
        self.fields['patient'].label = "Patient *"
        self.fields['encounter_type'].label = "Encounter Type *"
        self.fields['reason'].label = "Reason for Encounter *"
        self.fields['location'].label = "Location *"
        self.fields['start_time'].label = "Start Time *"
        self.fields['end_time'].label = "End Time"
        self.fields['status'].label = "Encounter Status *"

        # Add CSS classes for styling
        for field_name, field in self.fields.items():
            if field_name not in ['start_time', 'end_time', 'reason', 'location']:
                field.widget.attrs['class'] = 'form-control'
            
            # Mark required fields
            if field.required:
                field.widget.attrs['required'] = True

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        
        # Validate time logic
        if start_time and end_time:
            if end_time <= start_time:
                raise ValidationError("End time must be after start time.")
        
        # Validate start time is not in the future (unless it's a scheduled encounter)
        if start_time and start_time > timezone.now():
            status = cleaned_data.get('status')
            if status and status.lower() not in ['scheduled', 'planned']:
                raise ValidationError("Start time cannot be in the future for current encounters.")
        
        return cleaned_data


# ✅ Enhanced Inline Forms
class ObservationForm(forms.ModelForm):
    class Meta:
        model = Observation
        fields = ['patient', 'code', 'value', 'unit', 'observation_time']
        widgets = {
            'observation_time': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'value': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 120/80, 36.5, 72'
            }),
            'unit': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., mmHg, °C, bpm'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Blood Pressure, Temperature, Heart Rate'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['code'].label = "Observation Type *"
        self.fields['value'].label = "Value *"
        self.fields['unit'].label = "Unit *"
        self.fields['observation_time'].label = "Date & Time Observed *"
        
        # Set default observation time to now
        if not self.instance.pk:
            self.fields['observation_time'].initial = timezone.now()

    def clean_value(self):
        value = self.cleaned_data.get('value')
        if value:
            value = value.strip()
            if not value:
                raise ValidationError("Value cannot be empty.")
        return value

    def clean_observation_time(self):
        obs_time = self.cleaned_data.get('observation_time')
        if obs_time and obs_time > timezone.now():
            raise ValidationError("Observation time cannot be in the future.")
        return obs_time


class ConditionForm(forms.ModelForm):
    class Meta:
        model = Condition
        fields = ['code', 'description', 'onset_date', 'status']
        widgets = {
            'onset_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'max': date.today().isoformat()  # Prevent future dates
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Provide detailed description of the condition...'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., I10, E11.9, J44.1'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['code'].label = "Condition Code *"
        self.fields['description'].label = "Condition Description *"
        self.fields['onset_date'].label = "Date of Onset *"
        self.fields['status'].label = "Condition Status *"

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            code = code.strip().upper()
            # Basic ICD-10 format validation
            if not re.match(r'^[A-Z][0-9]{2}(\.[0-9X]*)?$', code):
                raise ValidationError("Please enter a valid ICD-10 code format (e.g., I10, E11.9)")
        return code

    def clean_onset_date(self):
        onset_date = self.cleaned_data.get('onset_date')
        if onset_date and onset_date > date.today():
            raise ValidationError("Onset date cannot be in the future.")
        return onset_date


class MedicationStatementForm(forms.ModelForm):
    class Meta:
        model = MedicationStatement
        fields = ['medication_name', 'dosage', 'route', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'end_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'medication_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Lisinopril, Metformin, Aspirin'
            }),
            'dosage': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 10mg, 500mg twice daily'
            }),
            'route': forms.Select(choices=[
                ('', 'Select route...'),
                ('oral', 'Oral'),
                ('iv', 'Intravenous'),
                ('im', 'Intramuscular'),
                ('sc', 'Subcutaneous'),
                ('topical', 'Topical'),
                ('inhaled', 'Inhaled'),
                ('rectal', 'Rectal'),
                ('other', 'Other')
            ], attrs={'class': 'form-control'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['medication_name'].label = "Medication Name *"
        self.fields['dosage'].label = "Dosage *"
        self.fields['route'].label = "Route of Administration *"
        self.fields['start_date'].label = "Start Date *"
        self.fields['end_date'].label = "End Date"

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date:
            if end_date <= start_date:
                raise ValidationError("End date must be after start date.")
        
        return cleaned_data

    def clean_dosage(self):
        dosage = self.cleaned_data.get('dosage')
        if dosage:
            dosage = dosage.strip()
            # Basic dosage format validation
            if not re.search(r'\d+\s*(mg|g|ml|units?|mcg|µg)', dosage.lower()):
                raise ValidationError("Please include a valid dosage with units (e.g., 50mg, 1g, 2ml)")
        return dosage


class AllergyIntoleranceForm(forms.ModelForm):
    SEVERITY_CHOICES = [
        ('', 'Select severity...'),
        ('mild', 'Mild'),
        ('moderate', 'Moderate'),
        ('severe', 'Severe'),
        ('life-threatening', 'Life-threatening')
    ]

    class Meta:
        model = AllergyIntolerance
        fields = ['substance', 'reaction', 'severity', 'recorded_date']
        widgets = {
            'recorded_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'max': date.today().isoformat()
            }),
            'substance': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Penicillin, Peanuts, Latex'
            }),
            'reaction': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Describe the allergic reaction...'
            }),
            'severity': forms.Select(attrs={
                'class': 'form-control'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['substance'].label = "Allergen Substance *"
        self.fields['reaction'].label = "Reaction *"
        self.fields['severity'].label = "Severity *"
        self.fields['recorded_date'].label = "Recorded Date *"
        
        # Set severity choices
        self.fields['severity'].choices = self.SEVERITY_CHOICES
        
        # Set default recorded date to today
        if not self.instance.pk:
            self.fields['recorded_date'].initial = date.today()

    def clean_recorded_date(self):
        recorded_date = self.cleaned_data.get('recorded_date')
        if recorded_date and recorded_date > date.today():
            raise ValidationError("Recorded date cannot be in the future.")
        return recorded_date


class ProcedureForm(forms.ModelForm):
    class Meta:
        model = Procedure
        fields = ['procedure_name', 'code', 'performed_date', 'outcome']
        widgets = {
            'performed_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'max': date.today().isoformat()
            }),
            'procedure_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Appendectomy, Blood Draw, X-ray'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 44970, 36415, 71020'
            }),
            'outcome': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Describe the outcome or results...'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['procedure_name'].label = "Procedure Name *"
        self.fields['code'].label = "Procedure Code"
        self.fields['performed_date'].label = "Date Performed *"
        self.fields['outcome'].label = "Procedure Outcome"

    def clean_performed_date(self):
        performed_date = self.cleaned_data.get('performed_date')
        if performed_date and performed_date > date.today():
            raise ValidationError("Procedure date cannot be in the future.")
        return performed_date


class ImmunizationForm(forms.ModelForm):
    class Meta:
        model = Immunization
        fields = ['vaccine_name', 'date_administered', 'lot_number', 'performer']
        widgets = {
            'date_administered': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'max': date.today().isoformat()
            }),
            'vaccine_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., COVID-19, Influenza, Hepatitis B'
            }),
            'lot_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Vaccine lot number'
            }),
            'performer': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Name of healthcare provider'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['vaccine_name'].label = "Vaccine Name *"
        self.fields['date_administered'].label = "Date Administered *"
        self.fields['lot_number'].label = "Lot Number *"
        self.fields['performer'].label = "Healthcare Provider *"

    def clean_date_administered(self):
        date_administered = self.cleaned_data.get('date_administered')
        if date_administered and date_administered > date.today():
            raise ValidationError("Administration date cannot be in the future.")
        return date_administered



# 🎨 Custom widget for better user experience
class DateTimePickerWidget(forms.DateTimeInput):
    def __init__(self, attrs=None):
        default_attrs = {
            'type': 'datetime-local',
            'class': 'form-control',
            'step': '1'
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)

    def format_value(self, value):
        if value is None:
            return ''
        if isinstance(value, datetime):
            return value.strftime('%Y-%m-%dT%H:%M')
        return value


# 🔧 Form validation mixins
class DateValidationMixin:
    """Mixin to add common date validation logic"""
    
    def clean_date_field(self, field_name, allow_future=False):
        date_value = self.cleaned_data.get(field_name)
        if date_value:
            if not allow_future and date_value > date.today():
                raise ValidationError(f"{field_name.replace('_', ' ').title()} cannot be in the future.")
        return date_value


class RequiredFieldsMixin:
    """Mixin to add visual indicators for required fields"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field.required:
                field.label = f"{field.label} *"
                field.widget.attrs['required'] = True
                field.widget.attrs['aria-required'] = 'true'