from django.urls import path
from . import views
from Patients.views import Dashboard

urlpatterns = [
    path('dashboard/', Dashboard, name='Dashboard'),
    path('request/', views.ExtendedPatientRequestView.as_view(), name='PatientRequest'),
    path('save/', views.save_fhir_data, name='Save_To_DB'),
    path('api/patient/', views.ajax_request_patient, name='AjaxPatientRequest'),
]