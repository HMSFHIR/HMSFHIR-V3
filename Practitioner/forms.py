from django import forms
from .models import Practitioner
from autht.models import CustomUser

class NewPractitioner(forms.ModelForm):
    # User fields
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    password = forms.CharField(widget=forms.PasswordInput())
    
    class Meta:
        model = Practitioner
        fields = ['practitioner_id', 'user_type', 'phone', 'department']
    
    def save(self, commit=True):
        # Create the CustomUser first
        user = CustomUser.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            password=self.cleaned_data['password']
        )
        
        # Create the Practitioner instance
        practitioner = super().save(commit=False)
        practitioner.user = user
        
        if commit:
            practitioner.save()
        
        return practitioner