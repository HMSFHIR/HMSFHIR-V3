from django.shortcuts import render,redirect
from rest_framework.views import APIView
from rest_framework.response import Response
from .services import sync_pending_resources
from django.conf import settings
import requests
from .models import PendingSyncQueue
from django.views.decorators.csrf import csrf_exempt
from Patients.sync_logic import run_sync
from Patients.models import FHIRSyncTask


def sync_status_view(request):
    try:
        # 🔌 Check FHIR server connectivity
        response = requests.get("http://localhost:8080/fhir/metadata", timeout=3)
        server_connected = response.status_code == 200
    except requests.RequestException:
        server_connected = False

    # ⏳ Get pending + synced tasks
    pending_tasks = FHIRSyncTask.objects.filter(status="pending").order_by("-created_at")
    synced_tasks = FHIRSyncTask.objects.exclude(status="pending").order_by("-created_at")

    context = {
        "server_connected": server_connected,
        "pending_tasks": pending_tasks,
        "synced_tasks": synced_tasks,
    }
    return render(request, "fhir_sync/sync_status.html", context)

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

@csrf_exempt
def manual_sync_view(request):
    if request.method == "POST":
        run_sync()
        return redirect("sync-status")  # Name of your sync status URL

    # Optional GET handler if needed
    return redirect("sync-status")




def fhir_sync_status(request):
    try:
        response = requests.get(f"{settings.FHIR_SERVER_BASE_URL}/metadata", timeout=2)
        server_connected = response.status_code == 200
    except Exception:
        server_connected = False

    pending_tasks = FHIRSyncTask.objects.filter(status="pending")
    synced_tasks = FHIRSyncTask.objects.filter(status="synced")

    return render(request, "Patients/fhir_sync_status.html", {
        "server_connected": server_connected,
        "pending_tasks": pending_tasks,
        "synced_tasks": synced_tasks,
    })
