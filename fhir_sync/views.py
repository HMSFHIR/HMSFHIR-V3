from django.shortcuts import render
from .models import PendingSyncQueue
from rest_framework.views import APIView
from rest_framework.response import Response
from .services import sync_pending_resources
from django.conf import settings
import requests
from django.shortcuts import render
from .models import PendingSyncQueue

def sync_status_view(request):
    try:
        response = requests.get('http://localhost:8080/fhir/metadata')
        fhir_connection_status = response.status_code == 200
    except requests.RequestException:
        fhir_connection_status = False

    pending_tasks = PendingSyncQueue.objects.filter(status='pending')
    synced_tasks = PendingSyncQueue.objects.exclude(status='pending')

    context = {
    'pending_tasks': pending_tasks,
    'synced_tasks': synced_tasks,
    'server_connected': fhir_connection_status,  
}


    return render(request, 'fhir_sync/sync_status.html', context)




def sync_queue_view(request):
    try:
        response = requests.get(f"{settings.FHIR_SERVER_BASE_URL}/metadata", timeout=2)
        fhir_connection_status = response.status_code == 200
    except Exception:
        fhir_connection_status = False

    pending_tasks = PendingSyncQueue.objects.filter(status="pending")
    synced_tasks = PendingSyncQueue.objects.exclude(status="pending")

    return render(request, "fhir_sync/queue.html", {
        "pending_tasks": pending_tasks,
        "synced_tasks": synced_tasks,
        "fhir_connection_status": fhir_connection_status
    })