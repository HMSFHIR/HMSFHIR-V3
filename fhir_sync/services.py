import requests
from .models import PendingSyncQueue
from django.conf import settings


def sync_pending_resources():
    # Fetch all pending sync items
    pending_resources = PendingSyncQueue.objects.filter(status="pending")

    for resource in pending_resources:
        try:
            # Construct the URL for the FHIR resource type

            url = f"{settings.FHIR_SERVER_BASE_URL}/{resource.resource_type.lower()}"
            
            # Send a POST or PUT request to sync the data
            response = requests.post(url, json=resource.json_data)
            
            if response.status_code == 201:  # FHIR resource created
                resource.status = 'success'
                resource.completed_at = timezone.now()
            else:
                resource.status = 'failed'
                resource.error_message = response.text
                resource.retry_count += 1
            resource.save()
        except Exception as e:
            # Handle connection or other issues
            resource.status = 'failed'
            resource.error_message = str(e)
            resource.retry_count += 1
            resource.save()
