# views.py
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from .forms import PractitionerLoginForm

def practitioner_login(request):
    """Handle practitioner login"""
    if request.user.is_authenticated:
        return redirect('dashboard')  # Redirect to dashboard if already logged in
    
    if request.method == 'POST':
        form = PractitionerLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            
            # Add success message
            messages.success(
                request,
                f'Welcome back, {user.get_full_name()}! You are logged in as {user.get_user_type_display()}.'
            )
            
            # Redirect based on user type or next parameter
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            
            # Default redirects based on user type
            if user.user_type == 'admin':
                return redirect('admin_dashboard')
            elif user.user_type == 'doctor':
                return redirect('doctor_dashboard')
            elif user.user_type == 'nurse':
                return redirect('nurse_dashboard')
            else:
                return redirect('dashboard')  # Generic dashboard
        else:
            # Add error message for invalid form
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PractitionerLoginForm()
    
    return render(request, 'autht/login.html', {'form': form})

def practitioner_logout(request):
    """Handle practitioner logout"""
    user_name = request.user.get_full_name() if request.user.is_authenticated else None
    logout(request)
    
    if user_name:
        messages.success(request, f'Goodbye, {user_name}! You have been logged out successfully.')
    
    return redirect('login')

@login_required
def dashboard(request):
    """Generic dashboard - redirect based on user type"""
    user = request.user
    
    if user.user_type == 'admin':
        return redirect('admin_dashboard')
    elif user.user_type == 'doctor':
        return redirect('doctor_dashboard')
    elif user.user_type == 'nurse':
        return redirect('nurse_dashboard')
    
    # Fallback dashboard
    return render(request, 'dashboard/generic.html', {'user': user})

@login_required
def admin_dashboard(request):
    """Admin dashboard"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('dashboard')
    
    return render(request, 'dashboard/admin.html', {'user': request.user})

@login_required
def doctor_dashboard(request):
    """Doctor dashboard"""
    if request.user.user_type != 'doctor':
        messages.error(request, 'Access denied. Doctor privileges required.')
        return redirect('dashboard')
    
    return render(request, 'autht/doctor.html', {'user': request.user})

@login_required
def nurse_dashboard(request):
    """Nurse dashboard"""
    if request.user.user_type != 'nurse':
        messages.error(request, 'Access denied. Nurse privileges required.')
        return redirect('dashboard')
    
    return render(request, 'autht/nurse.html', {'user': request.user})
