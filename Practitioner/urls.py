#urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.Practitioners, name="Practitioner"),
    path('add', views.AddPractitioner, name="NewPractitioner"),
    path('edit/<str:practitioner_id>/', views.EditPractitioner, name="EditPractitioner"),
    path('delete/<str:practitioner_id>/', views.DeletePractitioner, name='DeletePractitioner'),
]