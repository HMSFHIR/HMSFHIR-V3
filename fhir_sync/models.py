from django.db import models

# Create your models here.
class PendingSyncQueue(models.Model):
    resource_type = models.CharField(max_length=50, choices=[
        ("Patient", "Patient"), ("Practitioner", "Practitioner"),
        ("Encounter", "Encounter"), ("Observation", "Observation")
    ])
    resource_id = models.CharField(max_length=100)
    json_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, default="pending")
    retry_count = models.IntegerField(default=0)
    last_retry_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.resource_type} {self.resource_id} - {self.status}"
