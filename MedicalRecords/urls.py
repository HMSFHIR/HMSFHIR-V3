from django.urls import path
from . import views

urlpatterns = [
    path('', views.medical_records_view, name='MedicalRecords'),
    path('add/', views.add_medical_record, name='add_medical_record'),
]