from django import forms
from .models import Patient

class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ["name", "gender", "birth_date", "national_id"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control modern-input",
                "placeholder": "Enter full name",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';"
            }),
            "gender": forms.Select(attrs={
                "class": "form-select modern-select",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease; background-color: white;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';"
            }, choices=[
                ("", "Select Gender"),
                ("male", "Male"),
                ("female", "Female"),
                ("other", "Other")
            ]),
            "birth_date": forms.DateInput(attrs={
                "class": "form-control modern-input",
                "type": "date",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';"
            }),
            "national_id": forms.TextInput(attrs={
                "class": "form-control modern-input",
                "placeholder": "Enter national ID number",
                "style": "padding: 0.75rem 1rem; border: 1px solid #E2E8F0; border-radius: 0.5rem; font-size: 0.875rem; transition: all 0.2s ease;",
                "onfocus": "this.style.borderColor='#4F46E5'; this.style.boxShadow='0 0 0 3px rgba(79, 70, 229, 0.1)';",
                "onblur": "this.style.borderColor='#E2E8F0'; this.style.boxShadow='none';",
                "pattern": "[0-9]{10,15}",
                "title": "Please enter a valid national ID (10-15 digits)"
            }),
        }
        
        labels = {
            "name": "Full Name",
            "gender": "Gender",
            "birth_date": "Date of Birth",
            "national_id": "National ID",
        }
        
        help_texts = {
            "name": "Enter the patient's complete full name",
            "gender": "Select the patient's gender",
            "birth_date": "Select the patient's date of birth",
            "national_id": "Enter a valid national identification number",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add custom CSS classes and styling
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'data-field': field_name,
                'autocomplete': 'off' if field_name == 'national_id' else 'on'
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

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            # Clean and validate name
            name = ' '.join(name.split())  # Remove extra spaces
            if len(name) < 2:
                raise forms.ValidationError("Name must be at least 2 characters long.")
            if not all(char.isalpha() or char.isspace() for char in name):
                raise forms.ValidationError("Name should only contain letters and spaces.")
        return name