from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('autht.urls')),    
    path('Patients/', include('Patients.urls')),
    path('Appointments/', include('Appointments.urls')),
    path('Practitioners/', include('Practitioner.urls')),
    path('MedicalRecords/', include('MedicalRecords.urls')),
    path('Fsync/', include('Fsync.urls')),
   # path('Bridge/', include('Bridge.urls')),
]
