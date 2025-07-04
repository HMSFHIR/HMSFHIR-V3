from django.urls import path
from . import views
from Patients.views import Dashboard

urlpatterns = [
    #path('inspect/', views.inspect_patient, name='inspect'),
    path('dashboard/', Dashboard, name='Dashboard'),
]
