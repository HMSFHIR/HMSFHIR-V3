from django import forms
from .models import Patient

class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = [
            "given_name", "family_name", "middle_name", "name_prefix", "name_suffix",
            "gender", "birth_date", "national_id", "medical_record_number",
            "primary_phone", "secondary_phone", "email",
            "address_line1", "address_line2", "city", "state_province", "postal_code", "country",
            "marital_status", "preferred_language", "blood_type", "allergies",
            "emergency_contact_name", "emergency_contact_relationship", "emergency_contact_phone"
        ]
        
        widgets = {
            # Name fields
            "given_name": forms.TextInput(attrs={
                "class": "form-control modern-input",
                "placeholder": "Enter first name",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';"
            }),
            "family_name": forms.TextInput(attrs={
                "class": "form-control modern-input",
                "placeholder": "Enter last name",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';"
            }),
            "middle_name": forms.TextInput(attrs={
                "class": "form-control modern-input",
                "placeholder": "Enter middle name (optional)",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';"
            }),
            "name_prefix": forms.TextInput(attrs={
                "class": "form-control modern-input",
                "placeholder": "Dr., Mr., Mrs., etc. (optional)",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';"
            }),
            "name_suffix": forms.TextInput(attrs={
                "class": "form-control modern-input",
                "placeholder": "Jr., Sr., III, etc. (optional)",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';"
            }),
            
            # Demographics
            "gender": forms.Select(attrs={
                "class": "form-select modern-select",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease; background-color: white;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';"
            }),
            "birth_date": forms.DateInput(attrs={
                "class": "form-control modern-input",
                "type": "date",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';"
            }),
            "marital_status": forms.Select(attrs={
                "class": "form-select modern-select",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease; background-color: white;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';"
            }),
            "preferred_language": forms.Select(attrs={
                "class": "form-select modern-select",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease; background-color: white;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';"
            }),
            
            # Identifiers
            "national_id": forms.TextInput(attrs={
                "class": "form-control modern-input",
                "placeholder": "Enter national ID number",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';",
                "pattern": "[0-9]{10,15}",
                "title": "Please enter a valid national ID (10-15 digits)"
            }),
            "medical_record_number": forms.TextInput(attrs={
                "class": "form-control modern-input",
                "placeholder": "Enter medical record number (optional)",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';"
            }),
            
            # Contact Information
            "primary_phone": forms.TextInput(attrs={
                "class": "form-control modern-input",
                "placeholder": "+233XXXXXXXXX",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';"
            }),
            "secondary_phone": forms.TextInput(attrs={
                "class": "form-control modern-input",
                "placeholder": "+233XXXXXXXXX (optional)",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';"
            }),
            "email": forms.EmailInput(attrs={
                "class": "form-control modern-input",
                "placeholder": "patient@example.com (optional)",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';"
            }),
            
            # Address Information
            "address_line1": forms.TextInput(attrs={
                "class": "form-control modern-input",
                "placeholder": "Street address",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';"
            }),
            "address_line2": forms.TextInput(attrs={
                "class": "form-control modern-input",
                "placeholder": "Apartment, suite, etc. (optional)",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';"
            }),
            "city": forms.TextInput(attrs={
                "class": "form-control modern-input",
                "placeholder": "City",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';"
            }),
            "state_province": forms.TextInput(attrs={
                "class": "form-control modern-input",
                "placeholder": "State/Province/Region",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';"
            }),
            "postal_code": forms.TextInput(attrs={
                "class": "form-control modern-input",
                "placeholder": "Postal code",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';"
            }),
            "country": forms.TextInput(attrs={
                "class": "form-control modern-input",
                "placeholder": "Country",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';"
            }),
            
            # Clinical Information
            "blood_type": forms.Select(attrs={
                "class": "form-select modern-select",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease; background-color: white;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';"
            }),
            "allergies": forms.Textarea(attrs={
                "class": "form-control modern-input",
                "placeholder": "List known allergies (comma-separated)",
                "rows": 3,
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease; resize: vertical;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';"
            }),
            
            # Emergency Contact
            "emergency_contact_name": forms.TextInput(attrs={
                "class": "form-control modern-input",
                "placeholder": "Emergency contact name",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';"
            }),
            "emergency_contact_relationship": forms.TextInput(attrs={
                "class": "form-control modern-input",
                "placeholder": "Relationship (e.g., Spouse, Parent, Child)",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';"
            }),
            "emergency_contact_phone": forms.TextInput(attrs={
                "class": "form-control modern-input",
                "placeholder": "+233XXXXXXXXX",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';"
            }),
        }
        
        labels = {
            # Name fields
            "given_name": "First Name",
            "family_name": "Last Name", 
            "middle_name": "Middle Name",
            "name_prefix": "Prefix",
            "name_suffix": "Suffix",
            
            # Demographics
            "gender": "Gender",
            "birth_date": "Date of Birth",
            "marital_status": "Marital Status",
            "preferred_language": "Preferred Language",
            
            # Identifiers
            "national_id": "National ID",
            "medical_record_number": "Medical Record Number",
            
            # Contact Information
            "primary_phone": "Primary Phone",
            "secondary_phone": "Secondary Phone",
            "email": "Email Address",
            
            # Address
            "address_line1": "Address Line 1",
            "address_line2": "Address Line 2",
            "city": "City",
            "state_province": "State/Province/Region",
            "postal_code": "Postal Code",
            "country": "Country",
            
            # Clinical
            "blood_type": "Blood Type",
            "allergies": "Known Allergies",
            
            # Emergency Contact
            "emergency_contact_name": "Emergency Contact Name",
            "emergency_contact_relationship": "Emergency Contact Relationship",
            "emergency_contact_phone": "Emergency Contact Phone",
        }
        
        help_texts = {
            "given_name": "Enter the patient's first name(s)",
            "family_name": "Enter the patient's last name/surname",
            "middle_name": "Enter middle name(s) if applicable",
            "name_prefix": "Title such as Dr., Mr., Mrs., etc.",
            "name_suffix": "Suffix such as Jr., Sr., III, etc.",
            "gender": "Select the patient's gender",
            "birth_date": "Select the patient's date of birth",
            "national_id": "Enter a valid national identification number",
            "medical_record_number": "Internal medical record number",
            "primary_phone": "Primary contact phone number",
            "secondary_phone": "Alternative contact phone number",
            "email": "Email address for communication",
            "address_line1": "Street address, P.O. Box, company name, etc.",
            "address_line2": "Apartment, suite, unit, building, floor, etc.",
            "city": "City or town",
            "state_province": "State, province, or region",
            "postal_code": "ZIP or postal code",
            "country": "Country name",
            "marital_status": "Current marital status",
            "preferred_language": "Preferred language for communication",
            "blood_type": "Patient's blood type",
            "allergies": "List all known allergies, separated by commas",
            "emergency_contact_name": "Full name of emergency contact person",
            "emergency_contact_relationship": "Relationship to patient",
            "emergency_contact_phone": "Emergency contact's phone number",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add custom CSS classes and styling
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'data-field': field_name,
                'autocomplete': 'off' if field_name in ['national_id', 'medical_record_number'] else 'on'
            })
            
            # Add required attribute for non-optional fields
            if field.required:
                field.widget.attrs['required'] = True
                field.widget.attrs['aria-required'] = 'true'
            
            # Add accessibility attributes
            field.widget.attrs.update({
                'aria-label': self.Meta.labels.get(field_name, field_name.replace('_', ' ').title()),
                'aria-describedby': f'{field_name}-help' if field_name in self.Meta.help_texts else None
            })
        
        # Set default country to Ghana
        if 'country' in self.fields:
            self.fields['country'].initial = 'Ghana'

    def clean_national_id(self):
        national_id = self.cleaned_data.get('national_id')
        if national_id:
            # Remove any non-digit characters
            national_id = ''.join(filter(str.isdigit, national_id))
            
            # Validate length
            if len(national_id) < 10 or len(national_id) > 15:
                raise forms.ValidationError("National ID must be between 10 and 15 digits.")
            
            # Check if another patient has the same national_id (excluding current instance)
            existing_patient = Patient.objects.filter(national_id=national_id)
            if self.instance.pk:
                existing_patient = existing_patient.exclude(pk=self.instance.pk)
            
            if existing_patient.exists():
                raise forms.ValidationError("A patient with this National ID already exists.")
                
        return national_id

    def clean_medical_record_number(self):
        mrn = self.cleaned_data.get('medical_record_number')
        if mrn:
            # Check if another patient has the same MRN (excluding current instance)
            existing_patient = Patient.objects.filter(medical_record_number=mrn)
            if self.instance.pk:
                existing_patient = existing_patient.exclude(pk=self.instance.pk)
            
            if existing_patient.exists():
                raise forms.ValidationError("A patient with this Medical Record Number already exists.")
                
        return mrn

    def clean_given_name(self):
        given_name = self.cleaned_data.get('given_name')
        if given_name:
            # Clean and validate name
            given_name = ' '.join(given_name.split())  # Remove extra spaces
            if len(given_name) < 1:
                raise forms.ValidationError("First name is required.")
            if not all(char.isalpha() or char.isspace() or char in "'-." for char in given_name):
                raise forms.ValidationError("First name should only contain letters, spaces, hyphens, apostrophes, and periods.")
        return given_name

    def clean_family_name(self):
        family_name = self.cleaned_data.get('family_name')
        if family_name:
            # Clean and validate name
            family_name = ' '.join(family_name.split())  # Remove extra spaces
            if len(family_name) < 1:
                raise forms.ValidationError("Last name is required.")
            if not all(char.isalpha() or char.isspace() or char in "'-." for char in family_name):
                raise forms.ValidationError("Last name should only contain letters, spaces, hyphens, apostrophes, and periods.")
        return family_name

    def clean_middle_name(self):
        middle_name = self.cleaned_data.get('middle_name')
        if middle_name:
            # Clean and validate name
            middle_name = ' '.join(middle_name.split())  # Remove extra spaces
            if not all(char.isalpha() or char.isspace() or char in "'-." for char in middle_name):
                raise forms.ValidationError("Middle name should only contain letters, spaces, hyphens, apostrophes, and periods.")
        return middle_name

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Check if another patient has the same email (excluding current instance)
            existing_patient = Patient.objects.filter(email=email)
            if self.instance.pk:
                existing_patient = existing_patient.exclude(pk=self.instance.pk)
            
            if existing_patient.exists():
                raise forms.ValidationError("A patient with this email address already exists.")
                
        return email

    def clean(self):
        cleaned_data = super().clean()
        
        # Validate that at least given_name and family_name are provided
        given_name = cleaned_data.get('given_name')
        family_name = cleaned_data.get('family_name')
        
        if not given_name or not family_name:
            raise forms.ValidationError("Both first name and last name are required.")
            
        return cleaned_data


class PatientSearchForm(forms.Form):
    """Form for searching patients"""
    search_query = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control modern-input",
            "placeholder": "Search by name, ID, phone, or email...",
            "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem;",
        }),
        label="Search Patients"
    )
    
    gender = forms.ChoiceField(
        choices=[('', 'All Genders')] + Patient._meta.get_field('gender').choices,
        required=False,
        widget=forms.Select(attrs={
            "class": "form-select modern-select",
            "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem;",
        }),
        label="Filter by Gender"
    )


class QuickPatientForm(forms.ModelForm):
    """Simplified form for quick patient registration"""
    class Meta:
        model = Patient
        fields = ["given_name", "family_name", "gender", "birth_date", "primary_phone"]
        
        widgets = {
            "given_name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "First name",
                "required": True
            }),
            "family_name": forms.TextInput(attrs={
                "class": "form-control", 
                "placeholder": "Last name",
                "required": True
            }),
            "gender": forms.Select(attrs={"class": "form-select"}),
            "birth_date": forms.DateInput(attrs={
                "class": "form-control",
                "type": "date"
            }),
            "primary_phone": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "+233XXXXXXXXX"
            }),
        }
        
        labels = {
            "given_name": "First Name",
            "family_name": "Last Name",
            "gender": "Gender", 
            "birth_date": "Date of Birth",
            "primary_phone": "Phone Number",
        }

    def clean(self):
        cleaned_data = super().clean()
        
        # Validate required fields
        given_name = cleaned_data.get('given_name')
        family_name = cleaned_data.get('family_name')
        
        if not given_name or not family_name:
            raise forms.ValidationError("Both first name and last name are required.")
            
        return cleaned_data