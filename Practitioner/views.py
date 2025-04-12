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
    practitioner = get_object_or_404(Practitioner, id=practitioner_id)

    if request.method == 'POST':
        form = NewPractitioner(request.POST, instance=practitioner)
        if form.is_valid():
            try:
                form.save()
                return redirect('Practitioner')  # Adjust redirect as needed
            except Exception as e:
                form.add_error(None, f"An error occurred: {e}")
    else:
        form = NewPractitioner(instance=practitioner)

    return render(request, 'Practitioner/editpract.html', {'form': form})


@require_POST
def DeletePractitioner(request, practitioner_id):
    practitioner = get_object_or_404(Practitioner, id=practitioner_id)
    practitioner.delete()
    return redirect('Practitioner')  # update with your list view name
