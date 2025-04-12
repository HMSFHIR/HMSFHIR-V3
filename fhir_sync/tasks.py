from celery import shared_task
from .services import sync_pending_resources

@shared_task
def sync_pending_resources_task():
    sync_pending_resources()
