from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.contrib import messages
from .models import FHIRSyncConfig, SyncRule, SyncQueue, SyncLog
from .services import FHIRSyncService
from .tasks import process_sync_queue_task, full_sync_task

@admin.register(FHIRSyncConfig)
class FHIRSyncConfigAdmin(admin.ModelAdmin):
    list_display = ['name', 'base_url', 'auth_type', 'is_active', 'connection_status']
    list_filter = ['auth_type', 'is_active']
    search_fields = ['name', 'base_url']
    readonly_fields = ['created_at', 'updated_at']
    
    actions = ['test_connection']
    
    def connection_status(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green;">●</span> Active')
        return format_html('<span style="color: red;">●</span> Inactive')
    connection_status.short_description = 'Status'
    
    def test_connection(self, request, queryset):
        results = []
        for config in queryset:
            try:
                service = FHIRSyncService(config.name)
                result = service.test_connection()
                if result['connected']:
                    results.append(f"{config.name}: Connected")
                else:
                    results.append(f"{config.name}: Failed - {result['status']}")
            except Exception as e:
                results.append(f"{config.name}: Error - {str(e)}")
        
        messages.info(request, "\n".join(results))
    test_connection.short_description = "Test FHIR Connection"

@admin.register(SyncRule)
class SyncRuleAdmin(admin.ModelAdmin):
    list_display = ['resource_type', 'hms_model_app', 'hms_model_name', 'is_enabled', 'sync_frequency']
    list_filter = ['resource_type', 'is_enabled', 'sync_frequency']
    search_fields = ['resource_type', 'hms_model_name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('resource_type', 'hms_model_app', 'hms_model_name', 'is_enabled')
        }),
        ('Sync Settings', {
            'fields': ('sync_frequency', 'sync_filter', 'field_mappings')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

@admin.register(SyncQueue)
class SyncQueueAdmin(admin.ModelAdmin):
    list_display = ['resource_type', 'resource_id', 'operation', 'status', 'priority', 'attempts', 'created_at']
    list_filter = ['resource_type', 'status', 'operation', 'created_at']
    search_fields = ['resource_type', 'resource_id', 'fhir_id']
    readonly_fields = ['created_at', 'updated_at', 'completed_at', 'last_attempt_at']
    
    actions = ['requeue_items', 'cancel_items', 'process_selected']
    
    def requeue_items(self, request, queryset):
        count = queryset.filter(status__in=['failed', 'cancelled']).update(
            status='pending',
            attempts=0,
            error_message=None
        )
        messages.success(request, f"Requeued {count} items")
    requeue_items.short_description = "Requeue selected items"
    
    def cancel_items(self, request, queryset):
        count = queryset.filter(status__in=['pending', 'failed']).update(status='cancelled')
        messages.success(request, f"Cancelled {count} items")
    cancel_items.short_description = "Cancel selected items"
    
    def process_selected(self, request, queryset):
        pending_count = queryset.filter(status='pending').count()
        if pending_count > 0:
            process_sync_queue_task.delay(limit=pending_count)
            messages.success(request, f"Started processing {pending_count} pending items")
        else:
            messages.warning(request, "No pending items to process")
    process_selected.short_description = "Process selected items"

@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = ['queue_item', 'level', 'message_preview', 'timestamp']
    list_filter = ['level', 'timestamp']
    search_fields = ['message', 'queue_item__resource_type']
    readonly_fields = ['timestamp']
    
    def message_preview(self, obj):
        return obj.message[:100] + "..." if len(obj.message) > 100 else obj.message
    message_preview.short_description = 'Message'
