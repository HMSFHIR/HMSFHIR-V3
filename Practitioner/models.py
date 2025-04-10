from django.db import models


# Create your models here.
class Practitioner(models.Model):
    practitioner_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=50, choices=[
        ("doctor", "Doctor"), ("nurse", "Nurse"),
        ("technician", "Technician"), ("admin", "Admin")
    ])
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(unique=True)
    hospital_affiliation = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.name} - {self.role}"
