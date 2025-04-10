from django.urls import path
from . import views

urlpatterns = [
    path('', views.Practitioner, name="Practitioner"),
    path('addPract', views.NewPractitioner, name="NewPractitioner"),
]
