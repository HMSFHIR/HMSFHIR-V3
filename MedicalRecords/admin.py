from django.contrib import admin
from . models import Encounter, Observation, Condition, AllergyIntolerance, Procedure, Immunization

# Register your models here.
admin.site.register(Encounter),
admin.site.register(Observation),
admin.site.register(Condition),
admin.site.register(AllergyIntolerance),
admin.site.register(Procedure),
admin.site.register(Immunization),