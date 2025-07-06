from rest_framework import serializers
from .models import Observation, Encounter, Condition, MedicationStatement, AllergyIntolerance, Procedure, Immunization

class ObservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Observation
        fields = '__all__'

class EncounterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Encounter
        fields = '__all__'

class ConditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Condition
        fields = '__all__'

class MedicationStatementSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicationStatement
        fields = '__all__'

class AllergyIntoleranceSerializer(serializers.ModelSerializer):
    class Meta:
        model = AllergyIntolerance
        fields = '__all__'

class ProcedureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Procedure
        fields = '__all__'

class ImmunizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Immunization
        fields = '__all__'
