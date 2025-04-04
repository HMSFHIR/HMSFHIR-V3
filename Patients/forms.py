from django import forms
from .models import Patient

class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ["name", "gender", "birth_date", "national_id"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Full Name"}),
            "gender": forms.Select(attrs={"class": "form-control"}, choices=[
                ("male", "Male"), ("female", "Female"), ("other", "Other")
            ]),
            "birth_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "national_id": forms.TextInput(attrs={"class": "form-control", "placeholder": "National ID"}),
        }
