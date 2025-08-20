# MedicalRecords/urls.py - Updated with new views

from django.urls import path
from . import views

urlpatterns = [
    path('', views.medical_records_view, name='MedicalRecords'),
    path('add/', views.add_medical_record, name='add_medical_record'),
    
    # Detail, Edit, and Delete views
    path('detail/<str:record_type>/<int:record_id>/', views.view_medical_record_detail, name='view_medical_record_detail'),
    path('edit/<str:record_type>/<int:record_id>/', views.edit_medical_record, name='edit_medical_record'),
    path('delete/<str:record_type>/<int:record_id>/', views.delete_medical_record, name='delete_medical_record'),
    
    # API endpoint for FHIR JSON
    path('fhir/<str:record_type>/<int:record_id>/', views.get_record_fhir_json, name='get_record_fhir_json'),
]