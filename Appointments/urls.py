from django.urls import path
from . import views

urlpatterns = [
        path("", views.AppointmentView, name="Appointment"),
        path('addappointment/', views.AddAppointment, name='add_appointment'),
        path('deleteappointment/<int:appointment_id>/', views.DeleteAppointment, name='DeleteAppointment'),
        path('editappointment/<int:appointment_id>/', views.EditAppointment, name='EditAppointment'),
]
