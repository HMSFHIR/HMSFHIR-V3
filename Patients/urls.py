from django.urls import path
from . import views 

urlpatterns = [
    path("", views.Dashboard, name="Dashboard"),
    path("patientList/", views.PatientList, name="PatientList"),
    path("appointment/", views.AppointmentView, name="Appointment"),
    path("medicalRecord/", views.MedicalRecordView, name="MedicalRecord"),
    path("fhirsync/", views.FHIRSync, name="FHIRSync"),
    path("patients/add/", views.add_patient, name="add_patient"),
    path("patients/edit/<str:patient_id>/", views.EditPatient, name="EditPatient"),
    path("patients/<str:patient_id>/summary/", views.ViewRecordsSummary, name="ViewRecordsSummary"),
    path("patients/delete/<str:patient_id>/", views.DeletePatient, name="DeletePatient"),
]


