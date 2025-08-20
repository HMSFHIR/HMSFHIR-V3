from django.db import models

class Practitioner(models.Model):
    user = models.OneToOneField('autht.CustomUser', on_delete=models.CASCADE)
    practitioner_id = models.CharField(max_length=100, unique=True)
    user_type = models.CharField(max_length=50, choices=[
        ("doctor", "Doctor"), 
        ("nurse", "Nurse"),
        ("technician", "Technician"), 
        ("admin", "Admin"),
        ("IT", "IT")
    ])
    phone = models.CharField(max_length=20, blank=True, null=True)
    department = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} - {self.user_type}"
    
    @property
    def full_name(self):
        return f"{self.user.first_name} {self.user.last_name}"