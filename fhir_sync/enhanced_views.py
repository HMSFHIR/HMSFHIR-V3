# fhir_sync/enhanced_views.py
from django.shortcuts import render, redirect
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import requests
import json

from .models import PendingSyncQueue
from .enhanced_services import get_sync_statistics
from .enhanced_tasks import (
    sync_hms_to_fhir_task,
    sync_pending_resources_enhanced_task,
    full_sync_task,
    retry_failed_syncs,
    cleanup_sync_tasks
)

def enhanced_sync_dashboard(request):
    """
    Enhanced dashboard with comprehensive sync statistics
    """
    try:
        response = requests.get(f"{settings.FHIR_SERVER_BASE_URL}/metadata", timeout=3)
        server_connected = response.status_code == 200
    except requests.RequestException:
        server_connected = False
    
    # Get detailed statistics
    stats = get_sync_statistics()
    
    # Get recent sync activities
    recent_pending = PendingSyncQueue.objects.filter(status="pending").order_by("-created_at")[:10]
    recent_completed = PendingSyncQueue.objects.filter(status="success").order_by("-completed_at")[:10]
    recent_failed = PendingSyncQueue.objects.filter(status="failed").order_by("-last_retry_at")[:10]
    
    context = {
        "server_connected": server_connected,
        "stats": stats,
        "recent_pending": recent_pending,
        "recent_completed": recent_completed,
        "recent_failed": recent_failed,
        "total_pending": sum(stat['pending'] for stat in stats.values()),
        "total_success": sum(stat['success'] for stat in stats.values()),
        "total_failed": sum(stat['failed'] for stat in stats.values()),
    }
    
    return render(request, "fhir_sync/enhanced_dashboard.html", context)

@csrf_exempt
def sync_hms_data(request):
    """
    Queue all HMS data for FHIR sync
    """
    if request.method == "POST":
        sync_hms_to_fhir_task.delay()
        return JsonResponse({
            "success": True, 
            "message": "HMS data queued for FHIR sync"
        })
    return JsonResponse({"success": False, "message": "POST required"})

@csrf_exempt
def process_sync_queue(request):
    """
    Process pending sync queue
    """
    if request.method == "POST":
        sync_pending_resources_enhanced_task.delay()
        return JsonResponse({
            "success": True, 
            "message": "Sync queue processing started"
        })
    return JsonResponse({"success": False, "message": "POST required"})

@csrf_exempt
def full_sync(request):
    """
    Complete sync: HMS -> Queue -> FHIR Server
    """
    if request.method == "POST":
        full_sync_task.delay()
        return JsonResponse({
            "success": True, 
            "message": "Full sync started (HMS -> FHIR)"
        })
    return JsonResponse({"success": False, "message": "POST required"})

@csrf_exempt
def retry_failed(request):
    """
    Retry failed sync tasks
    """
    if request.method == "POST":
        retry_failed_syncs.delay()
        return JsonResponse({
            "success": True, 
            "message": "Retrying failed sync tasks"
        })
    return JsonResponse({"success": False, "message": "POST required"})

@csrf_exempt
def cleanup_old_tasks(request):
    """
    Clean up old completed sync tasks
    """
    if request.method == "POST":
        cleanup_sync_tasks.delay()
        return JsonResponse({
            "success": True, 
            "message": "Cleanup task started"
        })
    return JsonResponse({"success": False, "message": "POST required"})

def sync_statistics_api(request):
    """
    API endpoint for sync statistics
    """
    stats = get_sync_statistics()
    return JsonResponse({
        "statistics": stats,
        "summary": {
            "total_pending": sum(stat['pending'] for stat in stats.values()),
            "total_success": sum(stat['success'] for stat in stats.values()),
            "total_failed": sum(stat['failed'] for stat in stats.values()),
        }
    })

def resource_details(request, resource_type):
    """
    Get detailed information about a specific resource type sync status
    """
    if resource_type not in ['Patient', 'Practitioner', 'Encounter', 'Observation', 
                           'Condition', 'MedicationStatement', 'AllergyIntolerance',
                           'Procedure', 'Immunization', 'DocumentReference']:
        return JsonResponse({"error": "Invalid resource type"}, status=400)
    
    resources = PendingSyncQueue.objects.filter(resource_type=resource_type).order_by('-created_at')
    
    data = {
        "resource_type": resource_type,
        "total_count": resources.count(),
        "pending_count": resources.filter(status='pending').count(),
        "success_count": resources.filter(status='success').count(),
        "failed_count": resources.filter(status='failed').count(),
        "recent_items": [
            {
                "id": r.id,
                "resource_id": r.resource_id,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "retry_count": r.retry_count,
                "error_message": r.error_message[:100] if r.error_message else None
            }
            for r in resources[:20]  # Last 20 items
        ]
    }
    
    return JsonResponse(data)

def clear_resource_queue(request, resource_type):
    """
    Clear all queue items for a specific resource type
    """
    if request.method == "POST":
        if resource_type not in ['Patient', 'Practitioner', 'Encounter', 'Observation', 
                               'Condition', 'MedicationStatement', 'AllergyIntolerance',
                               'Procedure', 'Immunization', 'DocumentReference']:
            return JsonResponse({"error": "Invalid resource type"}, status=400)
        
        # Delete all queue items for this resource type
        deleted_count, _ = PendingSyncQueue.objects.filter(resource_type=resource_type).delete()
        
        return JsonResponse({
            "success": True,
            "message": f"Cleared {deleted_count} items from {resource_type} queue",
            "deleted_count": deleted_count
        })
    
    return JsonResponse({"error": "POST method required"}, status=405)

def bulk_queue_operations(request):
    """
    Handle bulk operations on the sync queue
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            operation = data.get('operation')
            resource_types = data.get('resource_types', [])
            
            if operation == 'clear_all':
                # Clear all queue items
                deleted_count, _ = PendingSyncQueue.objects.all().delete()
                return JsonResponse({
                    "success": True,
                    "message": f"Cleared all {deleted_count} items from queue",
                    "deleted_count": deleted_count
                })
            
            elif operation == 'clear_selected':
                # Clear selected resource types
                if not resource_types:
                    return JsonResponse({"error": "No resource types specified"}, status=400)
                
                deleted_count, _ = PendingSyncQueue.objects.filter(
                    resource_type__in=resource_types
                ).delete()
                
                return JsonResponse({
                    "success": True,
                    "message": f"Cleared {deleted_count} items for selected resource types",
                    "deleted_count": deleted_count,
                    "resource_types": resource_types
                })
            
            elif operation == 'clear_failed':
                # Clear only failed items
                deleted_count, _ = PendingSyncQueue.objects.filter(status='failed').delete()
                return JsonResponse({
                    "success": True,
                    "message": f"Cleared {deleted_count} failed items from queue",
                    "deleted_count": deleted_count
                })
            
            elif operation == 'clear_completed':
                # Clear only successfully completed items
                deleted_count, _ = PendingSyncQueue.objects.filter(status='success').delete()
                return JsonResponse({
                    "success": True,
                    "message": f"Cleared {deleted_count} completed items from queue",
                    "deleted_count": deleted_count
                })
            
            else:
                return JsonResponse({"error": "Invalid operation"}, status=400)
                
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    
    return JsonResponse({"error": "POST method required"}, status=405)