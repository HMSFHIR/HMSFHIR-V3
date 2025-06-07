from django.urls import path
from . import views 
from MedicalRecords import views as Mdviews
from Fsync.views import admin_dashboard

urlpatterns = [
    path("dashboard", views.Dashboard, name="Dashboard"),
    path("patientList/", views.PatientList, name="PatientList"),
    path("appointment/", views.AppointmentView, name="Appointment"),
    path("medicalRecord/", Mdviews.medical_records_view, name="MedicalRecord"),
    path("fhirsync/", admin_dashboard , name="FHIRSync"),
    path("patients/add/", views.add_patient, name="add_patient"),
    path("patients/edit/<str:patient_id>/", views.EditPatient, name="EditPatient"),
    path("patients/<str:patient_id>/summary/", views.ViewRecordsSummary, name="ViewRecordsSummary"),
    path("patients/delete/<str:patient_id>/", views.DeletePatient, name="DeletePatient"),
]


