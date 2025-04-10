from django.shortcuts import render
from .forms import NewPractitioner 
from django.db import IntegrityError as e

# Create your views here.
def Practitioner(request):
    context ={}
    return render(request, "Practitioner/practlist.html")

def AddPractitioner(request):
    if request.method == 'POST':
        form = NewPractitioner(request.POST)
        if form.is_valid():
            try:
                form.save()
                return redirect('NewPractitioner')
            except IntegrityError as e:
                form.add_error(None, f"Database error: {str(e)}")
    else:
        form = NewPractitioner(request.POST)
    
    return render(request, 'Practitioner/addpract.html', {
        'form': form
    })