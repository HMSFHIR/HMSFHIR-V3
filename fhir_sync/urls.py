
from django.urls import path
from .views import sync_queue_view, sync_status_view  # import the sync_status_view

urlpatterns = [
    path('queue/', sync_queue_view, name='sync_queue'),
    path('status/', sync_status_view, name='sync-status'),  # add this route
]
