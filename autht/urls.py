# urls.py
from django.urls import path
from . import views
from Patients.views import Dashboard, PatientList, AppointmentView, FHIRSync
from MedicalRecords.views import MedicalRecordsView


urlpatterns = [
    path('', views.practitioner_login, name='login'),
    path('login/', views.practitioner_login, name='practitioner_login'),
    path('logout/', views.practitioner_logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('doctor-dashboard/', views.doctor_dashboard, name='doctor_dashboard'),
    path('nurse-dashboard/', views.nurse_dashboard, name='nurse_dashboard'),


    #Urls to access the views in Patients app
    path("PDashboard" , Dashboard, name="PDashboard"),
    path("PatientList" , PatientList, name="PatientList"),

    #Urls to access the views in Appointment app
    path("AppointmentView", AppointmentView, name="AppointmentView"),

    #Urls to access the views in Medical Records app
    path("MedicalRecordView", MedicalRecordsView, name="MedicalRecordView"),
]