from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FHIRSyncConfigViewSet, SyncQueueViewSet, SyncOperationViewSet

router = DefaultRouter()
router.register(r'configs', FHIRSyncConfigViewSet)
router.register(r'queue', SyncQueueViewSet)
router.register(r'operations', SyncOperationViewSet, basename='sync-operations')

urlpatterns = [
    path('api/fhir-sync/', include(router.urls)),
]

