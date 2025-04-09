from django.urls import path
from . import views

urlpatterns = [
        path("", views.AppointmentView, name="Appointment"),
]
