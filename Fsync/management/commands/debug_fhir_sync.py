from django.core.management.base import BaseCommand
from django.db import models
from Fsync.models import SyncQueue, SyncLog
from Fsync.syncManager import FHIRSyncService

class Command(BaseCommand):
    help = 'Debug and manually sync FHIR resources'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sync-observation',
            type=int,
            help='Manually sync a specific observation by ID'
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            help='Show debug information about sync queue'
        )

    def handle(self, *args, **options):
        if options['debug']:
            self.debug_sync_queue()
        
        if options['sync_observation']:
            self.manually_sync_observation(options['sync_observation'])
    
    def debug_sync_queue(self):
        """Debug function to check sync queue status"""
        # Check pending items
        pending = SyncQueue.objects.filter(status='pending')
        self.stdout.write(f"Pending sync items: {pending.count()}")
        
        for item in pending[:5]:  # Show first 5
            self.stdout.write(f"  - {item.resource_type} {item.resource_id}: {item.operation}")
        
        # Check failed items
        failed = SyncQueue.objects.filter(status='failed')
        self.stdout.write(f"\nFailed sync items: {failed.count()}")
        
        for item in failed[:5]:  # Show first 5
            self.stdout.write(f"  - {item.resource_type} {item.resource_id}: {item.error_message[:100]}")
        
        # Check recent logs
        recent_errors = SyncLog.objects.filter(level='ERROR').order_by('-timestamp')[:5]
        self.stdout.write(f"\nRecent error logs:")
        
        for log in recent_errors:
            self.stdout.write(f"  - {log.timestamp}: {log.message[:100]}")
        
        return {
            'pending': pending.count(),
            'failed': failed.count(),
            'success': SyncQueue.objects.filter(status='success').count()
        }
    
    def manually_sync_observation(self, observation_id):
        """Manually trigger sync for a specific observation"""
        from Clinical.models import Observation  # Adjust import path
        
        try:
            observation = Observation.objects.get(id=observation_id)
            
            # Create or get queue item
            queue_item, created = SyncQueue.objects.get_or_create(
                resource_type='Observation',
                object_id=observation.id,
                defaults={
                    'resource_id': str(observation.id),
                    'operation': 'create',
                    'fhir_data': observation.to_fhir_dict(),
                    'status': 'pending'
                }
            )
            
            if not created and queue_item.status == 'failed':
                # Reset failed item
                queue_item.status = 'pending'
                queue_item.attempts = 0
                queue_item.fhir_data = observation.to_fhir_dict()
                queue_item.save()
            
            # Sync immediately
            sync_service = FHIRSyncService()
            success = sync_service.sync_resource(queue_item)
            
            if success:
                self.stdout.write(self.style.SUCCESS(f"✓ Sync successful! FHIR ID: {queue_item.fhir_id}"))
            else:
                self.stdout.write(self.style.ERROR(f"✗ Sync failed: {queue_item.error_message}"))
            
            return success
            
        except Observation.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Observation {observation_id} not found"))
            return False
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
            return False