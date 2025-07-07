# Fsync/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# DRF Router for API endpoints
router = DefaultRouter()
router.register(r'configs', views.FHIRSyncConfigViewSet)
router.register(r'queue', views.SyncQueueViewSet)
router.register(r'operations', views.SyncOperationViewSet, basename='sync-operations')

urlpatterns = [
    # HTML Dashboard views
    path('', views.admin_dashboard, name='dashboard'),
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
    
    # Task management endpoints (for AJAX calls from dashboard)
    path('task/start/', views.start_task, name='start_task'),
    path('task/stop/', views.stop_task, name='stop_task'),
    
    # AJAX endpoints for real-time data
    path('api/logs/', views.task_logs, name='task_logs'),
    path('api/status/', views.system_status, name='system_status'),
    
    # DRF API endpoints
    path('api/fhir-sync/', include(router.urls)),
]