from django.contrib import admin
from .models import Patient, Practitioner, Encounter, Condition, Observation, Appointment

# Register your models here.
admin.site.register(Patient)
admin.site.register(Practitioner)
admin.site.register(Encounter)
admin.site.register(Observation)
admin.site.register(Appointment)
admin.site.register(Condition)