from django.urls import path
from . import views

urlpatterns = [
        path("", views.AppointmentView, name="Appointment"),
        path('addappointment/', views.AddAppointment, name='add_appointment'),
        path('deleteappointment/<int:appointment_id>/', views.DeleteAppointment, name='delete_appointment'),
]
