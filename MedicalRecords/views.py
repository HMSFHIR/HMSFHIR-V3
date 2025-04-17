from django.shortcuts import render

# Create your views here.
def MedicalRecordsView(request):
    return render(request, 'MedicalRecords/medical_records.html')