from django.urls import path
from . import views

urlpatterns = [
    path('get/', views.index, name='bridge_index'),
]