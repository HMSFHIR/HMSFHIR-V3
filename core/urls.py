from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('Patients/', include('Patients.urls')),
    path('Appointments/', include('Appointments.urls')),
    path('Practitioners/', include('Practitioner.urls')),
    path('Sync/', include('fhir_sync.urls') ),
    path('MedicalRecords/', include('MedicalRecords.urls')),
]
