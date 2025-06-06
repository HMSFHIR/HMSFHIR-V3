
# services.py - Core Business Logic

import requests
import json
import logging
from typing import Dict, List, Optional, Any
from django.apps import apps
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import SyncQueue, SyncRule, FHIRSyncConfig, SyncLog
from django.contrib.contenttypes.models import ContentType


logger = logging.getLogger(__name__)

class FHIRSyncService:
    """Core service for FHIR synchronization"""
    
    def __init__(self, config_name: str = 'default'):
        self.config = FHIRSyncConfig.objects.get(name=config_name, is_active=True)
        self.session = requests.Session()
        self._setup_authentication()
    
    def _setup_authentication(self):
        """Setup authentication for FHIR requests"""
        if self.config.auth_type == 'basic':
            username = self.config.auth_credentials.get('username')
            password = self.config.auth_credentials.get('password')
            if username and password:
                self.session.auth = (username, password)
        
        elif self.config.auth_type == 'bearer':
            token = self.config.auth_credentials.get('token')
            if token:
                self.session.headers.update({'Authorization': f'Bearer {token}'})
        
        # Add common headers
        self.session.headers.update({
            'Content-Type': 'application/fhir+json',
            'Accept': 'application/fhir+json'
        })
    
    def test_connection(self) -> Dict[str, Any]:
        """Test connection to FHIR server"""
        try:
            response = self.session.get(
                f"{self.config.base_url}/metadata",
                timeout=self.config.timeout
            )
            
            if response.status_code == 200:
                metadata = response.json()
                return {
                    'connected': True,
                    'server_info': metadata.get('software', {}),
                    'fhir_version': metadata.get('fhirVersion', 'Unknown'),
                    'status': 'Connected successfully'
                }
            else:
                return {
                    'connected': False,
                    'status': f'HTTP {response.status_code}: {response.text[:200]}'
                }
        except requests.exceptions.RequestException as e:
            return {
                'connected': False,
                'status': f'Connection error: {str(e)}'
            }
    
    def sync_resource(self, queue_item: SyncQueue) -> bool:
        """Sync a single resource to FHIR server"""
        queue_item.mark_processing()
        
        try:
            # Prepare FHIR data
            fhir_data = queue_item.fhir_data.copy()
            if 'resourceType' not in fhir_data:
                fhir_data['resourceType'] = queue_item.resource_type
            
            # Determine operation
            if queue_item.operation == 'create':
                success = self._create_resource(queue_item, fhir_data)
            elif queue_item.operation == 'update':
                success = self._update_resource(queue_item, fhir_data)
            elif queue_item.operation == 'delete':
                success = self._delete_resource(queue_item)
            else:
                raise ValueError(f"Unknown operation: {queue_item.operation}")
            
            return success
            
        except Exception as e:
            logger.error(f"Sync failed for {queue_item}: {e}")
            queue_item.mark_failed(str(e))
            self._log_sync_event(queue_item, 'ERROR', f"Sync failed: {e}")
            return False
    
    def _create_resource(self, queue_item: SyncQueue, fhir_data: Dict) -> bool:
        """Create new FHIR resource"""
        url = f"{self.config.base_url}/{queue_item.resource_type}"
        
        response = self.session.post(url, json=fhir_data, timeout=self.config.timeout)
        
        if response.status_code in [200, 201]:
            response_data = response.json()
            fhir_id = response_data.get('id')
            queue_item.mark_success(fhir_id=fhir_id, response_data=response_data)
            self._log_sync_event(queue_item, 'INFO', f"Resource created with ID: {fhir_id}")
            return True
        else:
            error_msg = f"HTTP {response.status_code}: {response.text[:500]}"
            queue_item.mark_failed(error_msg, response_data={'status_code': response.status_code})
            self._log_sync_event(queue_item, 'ERROR', error_msg)
            return False
    
    def _update_resource(self, queue_item: SyncQueue, fhir_data: Dict) -> bool:
        """Update existing FHIR resource"""
        fhir_id = queue_item.fhir_id or fhir_data.get('id')
        if not fhir_id:
            # Try to create instead
            return self._create_resource(queue_item, fhir_data)
        
        url = f"{self.config.base_url}/{queue_item.resource_type}/{fhir_id}"
        
        response = self.session.put(url, json=fhir_data, timeout=self.config.timeout)
        
        if response.status_code in [200, 201]:
            response_data = response.json()
            queue_item.mark_success(fhir_id=fhir_id, response_data=response_data)
            self._log_sync_event(queue_item, 'INFO', f"Resource updated: {fhir_id}")
            return True
        elif response.status_code == 404:
            # Resource not found, create new one
            return self._create_resource(queue_item, fhir_data)
        else:
            error_msg = f"HTTP {response.status_code}: {response.text[:500]}"
            queue_item.mark_failed(error_msg, response_data={'status_code': response.status_code})
            self._log_sync_event(queue_item, 'ERROR', error_msg)
            return False
    
    def _delete_resource(self, queue_item: SyncQueue) -> bool:
        """Delete FHIR resource"""
        fhir_id = queue_item.fhir_id
        if not fhir_id:
            queue_item.mark_failed("No FHIR ID available for deletion")
            return False
        
        url = f"{self.config.base_url}/{queue_item.resource_type}/{fhir_id}"
        
        response = self.session.delete(url, timeout=self.config.timeout)
        
        if response.status_code in [200, 204]:
            queue_item.mark_success()
            self._log_sync_event(queue_item, 'INFO', f"Resource deleted: {fhir_id}")
            return True
        elif response.status_code == 404:
            # Already deleted
            queue_item.mark_success()
            self._log_sync_event(queue_item, 'INFO', f"Resource already deleted: {fhir_id}")
            return True
        else:
            error_msg = f"HTTP {response.status_code}: {response.text[:500]}"
            queue_item.mark_failed(error_msg, response_data={'status_code': response.status_code})
            self._log_sync_event(queue_item, 'ERROR', error_msg)
            return False
    
    def _log_sync_event(self, queue_item: SyncQueue, level: str, message: str, details: Dict = None):
        """Log sync event"""
        SyncLog.objects.create(
            queue_item=queue_item,
            level=level,
            message=message,
            details=details or {}
        )

class SyncQueueManager:
    """Manager for sync queue operations"""
    
    @staticmethod
    def queue_resource(resource_type: str, resource_id: str, fhir_data: Dict, 
                      operation: str = 'create', priority: int = 100,
                      source_object=None, sync_rule=None) -> SyncQueue:
        """Add resource to sync queue"""
        
        # Check for existing queue item
        existing = SyncQueue.objects.filter(
            resource_type=resource_type,
            resource_id=resource_id,
            status__in=['pending', 'processing']
        ).first()
        
        if existing:
            # Update existing item
            existing.fhir_data = fhir_data
            existing.operation = operation
            existing.priority = priority
            existing.status = 'pending'
            existing.attempts = 0
            existing.error_message = None
            existing.save()
            return existing
        else:
            # Create new queue item
            content_type = None
            object_id = None
            
            if source_object:
                content_type = ContentType.objects.get_for_model(source_object)
                object_id = source_object.pk
            
            return SyncQueue.objects.create(
                resource_type=resource_type,
                resource_id=resource_id,
                operation=operation,
                fhir_data=fhir_data,
                priority=priority,
                sync_rule=sync_rule,
                content_type=content_type,
                object_id=object_id
            )
    
    @staticmethod
    def process_queue(limit: int = 50) -> Dict[str, int]:
        """Process pending queue items"""
        sync_service = FHIRSyncService()
        
        # Get pending items
        pending_items = SyncQueue.objects.filter(
            status='pending',
            scheduled_at__lte=timezone.now()
        ).order_by('priority', 'created_at')[:limit]
        
        results = {'success': 0, 'failed': 0, 'total': len(pending_items)}
        
        for item in pending_items:
            success = sync_service.sync_resource(item)
            if success:
                results['success'] += 1
            else:
                results['failed'] += 1
        
        return results
    
    @staticmethod
    def retry_failed_items(max_retries: int = 3) -> Dict[str, int]:
        """Retry failed queue items"""
        failed_items = SyncQueue.objects.filter(
            status='failed',
            attempts__lt=max_retries
        ).order_by('last_attempt_at')
        
        results = {'retried': 0, 'success': 0, 'failed': 0}
        sync_service = FHIRSyncService()
        
        for item in failed_items:
            item.status = 'pending'
            item.save()
            results['retried'] += 1
            
            success = sync_service.sync_resource(item)
            if success:
                results['success'] += 1
            else:
                results['failed'] += 1
        
        return results
    
    @staticmethod
    def get_statistics() -> Dict[str, Any]:
        """Get queue statistics"""
        stats = {}
        
        # Overall stats
        stats['total'] = SyncQueue.objects.count()
        stats['pending'] = SyncQueue.objects.filter(status='pending').count()
        stats['processing'] = SyncQueue.objects.filter(status='processing').count()
        stats['success'] = SyncQueue.objects.filter(status='success').count()
        stats['failed'] = SyncQueue.objects.filter(status='failed').count()
        
        # By resource type
        stats['by_resource_type'] = {}
        for resource_type, _ in SyncRule.RESOURCE_TYPES:
            type_stats = {
                'pending': SyncQueue.objects.filter(
                    resource_type=resource_type, status='pending'
                ).count(),
                'success': SyncQueue.objects.filter(
                    resource_type=resource_type, status='success'
                ).count(),
                'failed': SyncQueue.objects.filter(
                    resource_type=resource_type, status='failed'
                ).count(),
            }
            type_stats['total'] = sum(type_stats.values())
            stats['by_resource_type'][resource_type] = type_stats
        
        return stats
