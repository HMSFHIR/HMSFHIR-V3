from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from .models import CustomUser


class PractitionerLoginForm(AuthenticationForm):
    """
    Custom login form for practitioners using practitioner_id
    """
    
    practitioner_id = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_practitioner_id',
            'placeholder': 'Enter your practitioner ID',
            'required': True,
            'autofocus': True,
            'autocomplete': 'username',
        }),
        label='Practitioner ID'
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'id_password',
            'placeholder': 'Enter your password',
            'required': True,
            'autocomplete': 'current-password',
        }),
        label='Password'
    )
    
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        label='Remember me'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove the default username field since we're using practitioner_id
        if 'username' in self.fields:
            del self.fields['username']
    
    def clean(self):
        practitioner_id = self.cleaned_data.get('practitioner_id')
        password = self.cleaned_data.get('password')
        
        if practitioner_id and password:
            # Authenticate using practitioner_id as username
            self.user_cache = authenticate(
                self.request,
                username=practitioner_id,  # Django auth backend uses 'username' parameter
                password=password
            )
            
            if self.user_cache is None:
                raise ValidationError(
                    "Invalid practitioner ID or password. Please try again.",
                    code='invalid_login',
                )
            else:
                self.confirm_login_allowed(self.user_cache)
        
        return self.cleaned_data
    
    def confirm_login_allowed(self, user):
        """
        Controls whether the given User may log in.
        """
        if not user.is_active:
            raise ValidationError(
                "This account is inactive. Please contact your administrator.",
                code='inactive',
            )
        
        if not user.is_active_practitioner:
            raise ValidationError(
                "Your practitioner account has been suspended. Please contact IT support.",
                code='suspended',
            )


class PractitionerRegistrationForm(forms.ModelForm):
    """
    Registration form for new practitioners
    """
    
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter password'
        }),
        help_text='Password must be at least 8 characters long.'
    )
    
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm password'
        })
    )
    
    class Meta:
        model = CustomUser
        fields = [
            'practitioner_id', 'first_name', 'last_name', 'email',
            'user_type', 'department', 'phone_number'
        ]
        widgets = {
            'practitioner_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter unique practitioner ID'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email address'
            }),
            'user_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'department': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Department (optional)'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Phone number (optional)'
            }),
        }
    
    def clean_practitioner_id(self):
        practitioner_id = self.cleaned_data.get('practitioner_id')
        
        if CustomUser.objects.filter(practitioner_id=practitioner_id).exists():
            raise ValidationError('A practitioner with this ID already exists.')
        
        return practitioner_id
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        
        if CustomUser.objects.filter(email=email).exists():
            raise ValidationError('A user with this email already exists.')
        
        return email
    
    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        
        if password1 and password2 and password1 != password2:
            raise ValidationError('Passwords do not match.')
        
        if password1 and len(password1) < 8:
            raise ValidationError('Password must be at least 8 characters long.')
        
        return password2
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.username = self.cleaned_data['practitioner_id']  # Set username to practitioner_id
        
        if commit:
            user.save()
        
        return user


class PractitionerUpdateForm(forms.ModelForm):
    """
    Form for updating practitioner information
    """
    
    class Meta:
        model = CustomUser
        fields = [
            'first_name', 'last_name', 'email',
            'department', 'phone_number'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control'
            }),
            'department': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control'
            }),
        }
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        
        # Check if email exists for other users (excluding current user)
        if CustomUser.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError('A user with this email already exists.')
        
        return email


class PasswordResetRequestForm(forms.Form):
    """
    Form for requesting password reset using practitioner ID
    """
    
    practitioner_id = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your practitioner ID',
            'autofocus': True,
        }),
        label='Practitioner ID'
    )
    
    def clean_practitioner_id(self):
        practitioner_id = self.cleaned_data.get('practitioner_id')
        
        try:
            user = CustomUser.objects.get(practitioner_id=practitioner_id)
            if not user.is_active:
                raise ValidationError('This account is inactive.')
            if not user.is_active_practitioner:
                raise ValidationError('This practitioner account is suspended.')
        except CustomUser.DoesNotExist:
            raise ValidationError('No practitioner found with this ID.')
        
        return practitioner_id


class PasswordChangeForm(forms.Form):
    """
    Form for changing password when logged in
    """
    
    current_password = forms.CharField(
        label='Current Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter current password',
            'autofocus': True,
        })
    )
    
    new_password1 = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter new password'
        }),
        help_text='Password must be at least 8 characters long.'
    )
    
    new_password2 = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password'
        })
    )
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_current_password(self):
        current_password = self.cleaned_data.get('current_password')
        
        if not self.user.check_password(current_password):
            raise ValidationError('Current password is incorrect.')
        
        return current_password
    
    def clean_new_password2(self):
        password1 = self.cleaned_data.get('new_password1')
        password2 = self.cleaned_data.get('new_password2')
        
        if password1 and password2 and password1 != password2:
            raise ValidationError('New passwords do not match.')
        
        if password1 and len(password1) < 8:
            raise ValidationError('Password must be at least 8 characters long.')
        
        return password2
    
    def save(self):
        """Save the new password"""
        password = self.cleaned_data['new_password1']
        self.user.set_password(password)
        self.user.save()
        return self.user


class AdminPractitionerForm(forms.ModelForm):
    """
    Form for admin to manage practitioner accounts
    """
    
    class Meta:
        model = CustomUser
        fields = [
            'practitioner_id', 'first_name', 'last_name', 'email',
            'user_type', 'department', 'phone_number', 'is_active', 'is_active_practitioner'
        ]
        widgets = {
            'practitioner_id': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control'
            }),
            'user_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'department': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_active_practitioner': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def clean_practitioner_id(self):
        practitioner_id = self.cleaned_data.get('practitioner_id')
        
        # Check if practitioner_id exists for other users (excluding current user if updating)
        query = CustomUser.objects.filter(practitioner_id=practitioner_id)
        if self.instance.pk:
            query = query.exclude(pk=self.instance.pk)
        
        if query.exists():
            raise ValidationError('A practitioner with this ID already exists.')
        
        return practitioner_id
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        
        # Check if email exists for other users (excluding current user if updating)
        query = CustomUser.objects.filter(email=email)
        if self.instance.pk:
            query = query.exclude(pk=self.instance.pk)
        
        if query.exists():
            raise ValidationError('A user with this email already exists.')
        
        return email