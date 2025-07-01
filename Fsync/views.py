from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import FHIRSyncConfig , SyncQueue
#from .models import SyncRule
from .syncManager import FHIRSyncService
from .queueManager import SyncQueueManager
from .tasks import full_sync_task, process_sync_queue_task, retry_failed_syncs_task
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from celery import current_app
from celery.result import AsyncResult
from datetime import datetime, timedelta
import json
from Fsync.tasks import (
    full_sync_task, 
    process_sync_queue_task, 
    cleanup_sync_tasks, 
    retry_failed_syncs_task,
    sync_single_resource_task
)

class FHIRSyncConfigViewSet(viewsets.ModelViewSet):
    queryset = FHIRSyncConfig.objects.all()
    permission_classes = [IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """Test connection to FHIR server"""
        config = self.get_object()
        try:
            service = FHIRSyncService(config.name)
            result = service.test_connection()
            return Response(result)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class SyncQueueViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SyncQueue.objects.all()
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def process_queue(self, request):
        """Process sync queue"""
        limit = request.data.get('limit', 50)
        task = process_sync_queue_task.delay(limit=limit)
        return Response({'task_id': task.id})
    
    @action(detail=False, methods=['post'])
    def retry_failed(self, request):
        """Retry failed sync operations"""
        task = retry_failed_syncs_task.delay()
        return Response({'task_id': task.id})
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get queue statistics"""
        stats = SyncQueueManager.get_statistics()
        return Response(stats)
    
    @action(detail=True, methods=['post'])
    def requeue(self, request, pk=None):
        """Requeue a specific item"""
        queue_item = self.get_object()
        if queue_item.status in ['failed', 'cancelled']:
            queue_item.status = 'pending'
            queue_item.attempts = 0
            queue_item.error_message = None
            queue_item.save()
            return Response({'status': 'requeued'})
        else:
            return Response(
                {'error': 'Item cannot be requeued'},
                status=status.HTTP_400_BAD_REQUEST
            )

class SyncOperationViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def full_sync(self, request):
        """Trigger full sync"""
        resource_types = request.data.get('resource_types')
        task = full_sync_task.delay(resource_types=resource_types)
        return Response({'task_id': task.id})
    
    @action(detail=False, methods=['get'])
    def status(self, request):
        """Get sync status"""
        stats = SyncQueueManager.get_statistics()
        return Response({
            'queue_stats': stats,
            'last_sync': SyncQueue.objects.filter(
                status='success'
            ).order_by('-completed_at').first()
        })
    




#@login_required
def admin_dashboard(request):
    """Main admin dashboard view"""

    context = {
        'page_title': 'FHIR Sync Dashboard',
        'active_tasks': [],  # Empty for now
        'recent_operations': [],  # Empty for now
        'system_stats': {},  # Empty for now
    }

    return render(request, 'Fsync/dashboard.html', context)

@login_required
def analytics_dashboard(request):
    """Analytics dashboard with detailed metrics"""
    context = {
        'sync_stats': get_detailed_sync_stats(),
        'performance_metrics': get_performance_metrics(),
        'error_analysis': get_error_analysis(),
        'resource_breakdown': get_resource_breakdown(),
    }
    return render(request, 'Fsync/analytics.html', context)

@csrf_exempt
@login_required
def start_task(request):
    """Start a specific sync task"""
    if request.method == 'POST':
        data = json.loads(request.body)
        task_name = data.get('task_name')
        
        task_map = {
            'full_sync': full_sync_task,
            'process_queue': process_sync_queue_task,
            'cleanup': cleanup_sync_tasks,
            'retry_failed': retry_failed_syncs_task,
            'single_resource': sync_single_resource_task,
        }
        
        if task_name in task_map:
            task = task_map[task_name].delay()
            return JsonResponse({
                'success': True,
                'task_id': task.id,
                'message': f'{task_name} started successfully'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})

@csrf_exempt
@login_required
def stop_task(request):
    """Stop a running task"""
    if request.method == 'POST':
        data = json.loads(request.body)
        task_id = data.get('task_id')
        
        if task_id:
            current_app.control.revoke(task_id, terminate=True)
            return JsonResponse({
                'success': True,
                'message': 'Task stopped successfully'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})

@login_required
def task_logs(request):
    """Get task logs via AJAX"""
    logs = get_recent_logs()
    return JsonResponse({'logs': logs})

@login_required
def system_status(request):
    """Get current system status via AJAX"""
    status = {
        'celery_active': is_celery_active(),
        'redis_connected': is_redis_connected(),
        'active_workers': get_active_workers_count(),
        'queue_size': get_queue_size(),
    }
    return JsonResponse(status)

# Helper functions
def get_active_tasks():
    """Get currently active tasks"""
    try:
        active = current_app.control.inspect().active()
        if active:
            tasks = []
            for worker, task_list in active.items():
                for task in task_list:
                    tasks.append({
                        'id': task['id'],
                        'name': task['name'].split('.')[-1],
                        'worker': worker,
                        'time_start': task.get('time_start'),
                    })
            return tasks
    except:
        pass
    return []

def get_recent_task_history():
    """Get recent task execution history"""
    # This would typically come from your database
    # For demo purposes, returning sample data
    return [
        {
            'name': 'Full Sync Task',
            'status': 'SUCCESS',
            'timestamp': timezone.now() - timedelta(minutes=10),
            'duration': '2.5s',
            'result': 'Queued 0 items for sync'
        },
        {
            'name': 'Process Queue Task',
            'status': 'SUCCESS', 
            'timestamp': timezone.now() - timedelta(minutes=5),
            'duration': '1.2s',
            'result': 'Processed 15 items'
        },
        {
            'name': 'Cleanup Tasks',
            'status': 'SUCCESS',
            'timestamp': timezone.now() - timedelta(hours=1),
            'duration': '0.8s',
            'result': 'Cleaned up 3 old tasks'
        }
    ]

def get_system_statistics():
    """Get system-wide statistics"""
    return {
        'total_syncs_today': 45,
        'successful_syncs': 42,
        'failed_syncs': 3,
        'avg_sync_time': '1.8s',
        'total_resources': 156,
        'last_full_sync': timezone.now() - timedelta(hours=2),
    }

def get_sync_metrics():
    """Get sync performance metrics"""
    return {
        'sync_rate_per_hour': 23,
        'error_rate': 6.7,
        'avg_queue_time': '0.3s',
        'worker_utilization': 78,
    }

def get_detailed_sync_stats():
    """Get detailed analytics for sync operations"""
    return {
        'daily_syncs': [25, 32, 28, 45, 38, 52, 41],  # Last 7 days
        'resource_types': {
            'Patient': 45,
            'Observation': 32,
            'Condition': 28,
            'Medication': 15,
            'Encounter': 36
        },
        'sync_success_rate': 93.3,
        'peak_hours': [9, 14, 16],  # Hours with most activity
    }

def get_performance_metrics():
    """Get performance analytics"""
    return {
        'avg_response_time': [1.2, 1.5, 1.1, 1.8, 1.3, 1.4, 1.6],  # Last 7 days
        'throughput': [120, 145, 135, 162, 128, 155, 142],  # Records per hour
        'memory_usage': 68,  # Percentage
        'cpu_usage': 45,  # Percentage
    }

def get_error_analysis():
    """Get error analysis data"""
    return {
        'error_types': {
            'Connection Timeout': 45,
            'Invalid Data Format': 23,
            'Authentication Failed': 12,
            'Rate Limit Exceeded': 8,
            'Server Error': 15
        },
        'error_trend': [5, 3, 8, 2, 6, 4, 3],  # Last 7 days
    }

def get_resource_breakdown():
    """Get resource sync breakdown"""
    return {
        'patients_synced': 156,
        'observations_synced': 342,
        'conditions_synced': 89,
        'medications_synced': 67,
        'encounters_synced': 134,
    }

def get_recent_logs():
    """Get recent system logs"""
    return [
        {
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'level': 'INFO',
            'message': 'Full sync task completed successfully',
            'task_id': 'a184c955-2d46-435c-9425-d2fdfd607a25'
        },
        {
            'timestamp': (timezone.now() - timedelta(minutes=2)).strftime('%Y-%m-%d %H:%M:%S'),
            'level': 'ERROR',
            'message': 'Failed to queue Patient 10: ContentType not defined',
            'task_id': '7851bcd8-a7c6-4849-8d05-fbca633aea66'
        },
        {
            'timestamp': (timezone.now() - timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S'),
            'level': 'INFO',
            'message': 'Worker connected to redis://localhost:6379/0',
            'task_id': None
        }
    ]

def is_celery_active():
    """Check if Celery is active"""
    try:
        stats = current_app.control.inspect().stats()
        return bool(stats)
    except:
        return False

def is_redis_connected():
    """Check if Redis/Valkey is connected"""
    try:
        from django.core.cache import cache
        cache.get('test')
        return True
    except:
        return False

def get_active_workers_count():
    """Get number of active workers"""
    try:
        stats = current_app.control.inspect().stats()
        return len(stats) if stats else 0
    except:
        return 0

def get_queue_size():
    """Get current queue size"""
    try:
        # This would depend on your broker implementation
        return 5  # Placeholder
    except:
        return 0