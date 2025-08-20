
#Views.py
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.db import IntegrityError
from .forms import NewPractitioner 
from .models import Practitioner

# Create your views here.
def Practitioners(request):
    practitioners = Practitioner.objects.all()
    context ={'practitioners':practitioners}
    return render(request, "Practitioner/practlist.html", context)

def AddPractitioner(request):
    if request.method == 'POST':
        form = NewPractitioner(request.POST)
        if form.is_valid():
            try:
                form.save()
                return redirect('Practitioner') 
            except IntegrityError as e:
                form.add_error(None, f"Database error: {str(e)}")
    else:
        form = NewPractitioner() 
    return render(request, 'Practitioner/addpract.html', {'form': form})

    
def EditPractitioner(request, practitioner_id):
    practitioner = get_object_or_404(Practitioner, practitioner_id=practitioner_id)

    if request.method == 'POST':
        form = NewPractitioner(request.POST, instance=practitioner)
        if form.is_valid():
            try:
                # Update user fields
                user = practitioner.user
                user.username = form.cleaned_data['username']
                user.email = form.cleaned_data['email']
                user.first_name = form.cleaned_data['first_name']
                user.last_name = form.cleaned_data['last_name']
                user.save()
                
                # Update practitioner fields
                form.save()
                return redirect('Practitioner')
            except Exception as e:
                form.add_error(None, f"An error occurred: {e}")
    else:
        # Pre-populate form with existing data
        initial_data = {
            'username': practitioner.user.username,
            'email': practitioner.user.email,
            'first_name': practitioner.user.first_name,
            'last_name': practitioner.user.last_name,
        }
        form = NewPractitioner(instance=practitioner, initial=initial_data)

    return render(request, 'Practitioner/editpract.html', {'form': form})


@require_POST
def DeletePractitioner(request, practitioner_id):
    practitioner = get_object_or_404(Practitioner, practitioner_id=practitioner_id)
    practitioner.delete()
    return redirect('Practitioner')  # update with your list view name

