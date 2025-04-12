from django.db.models.signals import post_save
from django.dispatch import receiver
from Patients.models import Patient
from fhir_sync.models import PendingSyncQueue

@receiver(post_save, sender=Patient)
def queue_patient_for_sync(sender, instance, **kwargs):
    sync_data = instance.to_json()
    queue_entry, created = PendingSyncQueue.objects.get_or_create(
        resource_type='Patient',
        resource_id=instance.patient_id,
        defaults={
            'json_data': sync_data,
            'status': 'pending',
        }
    )

    if not created:
        queue_entry.json_data = sync_data
        queue_entry.status = 'pending'
        queue_entry.save()
