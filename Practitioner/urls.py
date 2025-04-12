from django.urls import path
from . import views

urlpatterns = [
    path('', views.Practitioners, name="Practitioner"),
    path('add', views.AddPractitioner, name="NewPractitioner"),
    path('edit/<int:practitioner_id>/', views.EditPractitioner, name="EditPractitioner"),
    path('delete/<int:practitioner_id>/', views.DeletePractitioner, name='DeletePractitioner'),

]
