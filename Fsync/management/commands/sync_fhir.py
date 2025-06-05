from django.core.management.base import BaseCommand
from django.utils import timezone
from Fsync.services import SyncQueueManager, FHIRSyncService
from Fsync.tasks import full_sync_task, process_sync_queue_task
from Fsync.models import SyncQueue, FHIRSyncConfig


class Command(BaseCommand):
    help = 'FHIR Sync Management Command'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            choices=['process', 'full-sync', 'retry', 'stats', 'test-connection'],
            required=True,
            help='Action to perform'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='Limit for processing queue items'
        )
        parser.add_argument(
            '--resource-types',
            nargs='+',
            help='Resource types for full sync'
        )
        parser.add_argument(
            '--config',
            default='default',
            help='FHIR config name for connection test'
        )
    
    def handle(self, *args, **options):
        action = options['action']
        
        if action == 'process':
            self.stdout.write('Processing sync queue...')
            results = SyncQueueManager.process_queue(limit=options['limit'])
            self.stdout.write(
                self.style.SUCCESS(
                    f"Processed {results['total']} items: "
                    f"{results['success']} success, {results['failed']} failed"
                )
            )
        
        elif action == 'full-sync':
            self.stdout.write('Starting full sync...')
            task = full_sync_task.delay(resource_types=options['resource_types'])
            self.stdout.write(
                self.style.SUCCESS(f"Full sync started with task ID: {task.id}")
            )
        
        elif action == 'retry':
            self.stdout.write('Retrying failed items...')
            results = SyncQueueManager.retry_failed_items()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Retried {results['retried']} items: "
                    f"{results['success']} success, {results['failed']} failed"
                )
            )
        
        elif action == 'stats':
            stats = SyncQueueManager.get_statistics()
            self.stdout.write('\n=== SYNC QUEUE STATISTICS ===')
            self.stdout.write(f"Total: {stats['total']}")
            self.stdout.write(f"Pending: {stats['pending']}")
            self.stdout.write(f"Processing: {stats['processing']}")
            self.stdout.write(f"Success: {stats['success']}")
            self.stdout.write(f"Failed: {stats['failed']}")
            
            self.stdout.write('\n=== BY RESOURCE TYPE ===')
            for resource_type, type_stats in stats['by_resource_type'].items():
                if type_stats['total'] > 0:
                    self.stdout.write(
                        f"{resource_type}: {type_stats['total']} "
                        f"(P:{type_stats['pending']}, S:{type_stats['success']}, F:{type_stats['failed']})"
                    )
        
        elif action == 'test-connection':
            try:
                service = FHIRSyncService(options['config'])
                result = service.test_connection()
                if result['connected']:
                    self.stdout.write(
                        self.style.SUCCESS(f"✓ Connected to FHIR server")
                    )
                    self.stdout.write(f"Server: {result.get('server_info', {})}")
                    self.stdout.write(f"FHIR Version: {result.get('fhir_version', 'Unknown')}")
                else:
                    self.stdout.write(
                        self.style.ERROR(f"✗ Connection failed: {result['status']}")
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ Connection test failed: {e}")
                )
