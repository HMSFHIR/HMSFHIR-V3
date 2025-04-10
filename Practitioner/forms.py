from django import forms
from .models import Practitioner 

class NewPractitioner(forms.ModelForm):
    class Meta:
        model = Practitioner
        fields = ['practitioner_id', 'name', 'role', 'phone', 'email', 'hospital_affiliation']

