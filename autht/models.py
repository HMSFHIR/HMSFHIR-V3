from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models

class CustomUser(AbstractUser):
    """Extended User model for hospital staff"""
    USER_TYPES = [
        ('doctor', 'Doctor'),
        ('nurse', 'Nurse'),
        ('admin', 'Admin'),
    ]
    
    practitioner_id = models.CharField(max_length=20, unique=True)
    user_type = models.CharField(max_length=10, choices=USER_TYPES)
    department = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    is_active_practitioner = models.BooleanField(default=True)
    
    # Use practitioner_id as the username field
    USERNAME_FIELD = 'practitioner_id'
    REQUIRED_FIELDS = ['email', 'first_name', 'last_name', 'user_type']
    
    def __str__(self):
        return f"{self.practitioner_id} - {self.get_full_name()} ({self.get_user_type_display()})"
    
    class Meta:
        db_table = 'hospital_users'

# forms.py
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate
from .models import CustomUser

class PractitionerLoginForm(AuthenticationForm):
    """Custom login form for practitioners"""
    practitioner_id = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_practitioner_id',
            'placeholder': 'Enter your practitioner ID',
            'required': True,
        })
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'id_password',
            'placeholder': 'Enter your password',
            'required': True,
        })
    )
    
    # Remove the default username field
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove username field since we're using practitioner_id
        if 'username' in self.fields:
            del self.fields['username']
    
    def clean(self):
        practitioner_id = self.cleaned_data.get('practitioner_id')
        password = self.cleaned_data.get('password')
        
        if practitioner_id and password:
            # Authenticate using practitioner_id
            self.user_cache = authenticate(
                self.request,
                username=practitioner_id,  # Django auth uses 'username' parameter
                password=password
            )
            
            if self.user_cache is None:
                raise forms.ValidationError(
                    "Invalid practitioner ID or password.",
                    code='invalid_login',
                )
            elif not self.user_cache.is_active:
                raise forms.ValidationError(
                    "This account is inactive.",
                    code='inactive',
                )
            elif not self.user_cache.is_active_practitioner:
                raise forms.ValidationError(
                    "Your practitioner account has been suspended. Contact IT support.",
                    code='suspended',
                )
        
        return self.cleaned_data