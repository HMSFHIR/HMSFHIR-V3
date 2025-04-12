from django.contrib import admin
from .models import Patient, Encounter, Condition, Observation

# Register your models here.
admin.site.register(Patient)
admin.site.register(Encounter)
admin.site.register(Observation)
admin.site.register(Condition)