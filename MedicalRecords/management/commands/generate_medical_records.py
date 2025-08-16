import random
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

from Patients.models import Patient
from MedicalRecords.models import (
    Encounter, Observation, Condition, 
    MedicationStatement, AllergyIntolerance,
    Procedure, Immunization
)
from Practitioner.models import Practitioner
from Appointments.models import Appointment


class Command(BaseCommand):
    help = 'Generate medical records for existing patients in the HMS'

    def add_arguments(self, parser):
        parser.add_argument(
            '--patients',
            type=int,
            default=10,
            help='Number of patients to generate records for (default: 10)'
        )
        parser.add_argument(
            '--records-per-patient',
            type=int,
            default=5,
            help='Average number of records per patient (default: 5)'
        )
        parser.add_argument(
            '--patient-id',
            type=str,
            help='Generate records for a specific patient ID'
        )
        parser.add_argument(
            '--list-patients',
            action='store_true',
            help='List all patients in the system with their IDs'
        )
        parser.add_argument(
            '--filter-by-name',
            type=str,
            help='Filter patients by name (partial match)'
        )
        parser.add_argument(
            '--random-selection',
            action='store_true',
            help='Randomly select patients instead of first N patients'
        )
        parser.add_argument(
            '--sync-to-fhir',
            action='store_true',
            help='Queue generated records for FHIR sync'
        )
        parser.add_argument(
            '--days-back',
            type=int,
            default=365,
            help='Generate records within the last N days (default: 365)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be generated without creating records'
        )

    def handle(self, *args, **options):
        if options['list_patients']:
            self.list_all_patients()
            return
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No records will be created'))
        
        self.stdout.write(self.style.SUCCESS('Starting medical records generation...'))
        
        patients = self.get_target_patients(options)
        
        if not patients.exists():
            raise CommandError("No patients found matching the criteria")

        practitioners = list(Practitioner.objects.all())
        if not practitioners:
            self.stdout.write(self.style.WARNING('No practitioners found. Creating sample practitioner...'))
            practitioners = [self.create_sample_practitioner()]

        total_records = 0
        
        for patient in patients:
            if options['dry_run']:
                self.stdout.write(f'Would generate records for: {patient.patient_id} - {patient.get_full_name()}')
                continue
                
            try:
                with transaction.atomic():
                    records_count = self.generate_patient_records(
                        patient, 
                        practitioners, 
                        options['records_per_patient'],
                        options['days_back']
                    )
                    total_records += records_count
                    
                    if options['sync_to_fhir']:
                        self.queue_for_fhir_sync(patient)
                    
                    self.stdout.write(
                        f'Generated {records_count} records for patient {patient.patient_id} - {patient.get_full_name()}'
                    )
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error generating records for patient {patient.patient_id}: {e}')
                )
                continue
        
        if not options['dry_run']:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully generated {total_records} medical records for {patients.count()} patients'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN: Would have generated records for {patients.count()} patients'
                )
            )

    def get_target_patients(self, options):
        if options['patient_id']:
            try:
                patients = Patient.objects.filter(
                    models.Q(patient_id=options['patient_id']) |
                    models.Q(id=options['patient_id']) |
                    models.Q(pk=options['patient_id'])
                )
                if not patients.exists():
                    if options['patient_id'].isdigit():
                        patients = Patient.objects.filter(id=int(options['patient_id']))
                    
                if not patients.exists():
                    raise CommandError(f"Patient with ID {options['patient_id']} not found")
                return patients
            except Exception as e:
                raise CommandError(f"Error fetching patient: {e}")
        
        if options['filter_by_name']:
            patients = Patient.objects.filter(
                models.Q(first_name__icontains=options['filter_by_name']) |
                models.Q(last_name__icontains=options['filter_by_name'])
            )
        else:
            patients = Patient.objects.all()
        
        if options['random_selection']:
            total_patients = patients.count()
            if total_patients > options['patients']:
                random_ids = random.sample(
                    list(patients.values_list('id', flat=True)), 
                    options['patients']
                )
                patients = patients.filter(id__in=random_ids)
        else:
            patients = patients[:options['patients']]
        
        return patients

    def list_all_patients(self):
        patients = Patient.objects.all()
        
        if not patients.exists():
            self.stdout.write(self.style.WARNING('No patients found in the system'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'Found {patients.count()} patients:'))
        self.stdout.write('-' * 60)
        
        for patient in patients:
            patient_info = []
            
            if hasattr(patient, 'patient_id'):
                patient_info.append(f"ID: {patient.patient_id}")
            elif hasattr(patient, 'registration_number'):
                patient_info.append(f"Reg: {patient.registration_number}")
            else:
                patient_info.append(f"PK: {patient.pk}")
            
            if hasattr(patient, 'get_full_name'):
                patient_info.append(f"Name: {patient.get_full_name()}")
            else:
                name_parts = []
                if hasattr(patient, 'first_name') and patient.first_name:
                    name_parts.append(patient.first_name)
                if hasattr(patient, 'last_name') and patient.last_name:
                    name_parts.append(patient.last_name)
                if name_parts:
                    patient_info.append(f"Name: {' '.join(name_parts)}")
            
            if hasattr(patient, 'date_of_birth') and patient.date_of_birth:
                age = self.calculate_age(patient.date_of_birth)
                patient_info.append(f"Age: {age}")
            
            if hasattr(patient, 'gender') and patient.gender:
                patient_info.append(f"Gender: {patient.gender}")
            
            self.stdout.write(' | '.join(patient_info))
        
        self.stdout.write('-' * 60)
        self.stdout.write(f'Total: {patients.count()} patients')

    def generate_patient_records(self, patient: Patient, practitioners: List[Practitioner], 
                               avg_records: int, days_back: int) -> int:
        num_records = random.randint(max(1, avg_records - 2), avg_records + 3)
        records_created = 0
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days_back)
        
        for i in range(num_records):
            days_offset = random.randint(0, days_back)
            record_date = end_date - timedelta(days=days_offset)
            
            encounter = self.create_encounter(patient, random.choice(practitioners), record_date)

            record_types = random.sample([
                'observation', 'condition', 'medication', 
                'allergy', 'procedure', 'immunization'
            ], k=random.randint(1, 3))
            
            for record_type in record_types:
                if record_type == 'observation':
                    self.create_observation(patient, encounter, record_date)
                elif record_type == 'condition':
                    self.create_condition(patient, encounter, record_date)
                elif record_type == 'medication':
                    self.create_medication(patient, encounter, record_date)
                elif record_type == 'allergy':
                    self.create_allergy(patient, record_date)
                elif record_type == 'procedure':
                    self.create_procedure(patient, encounter, record_date)
                elif record_type == 'immunization':
                    self.create_immunization(patient, record_date)
                
                records_created += 1
        
        return records_created

    def create_encounter(self, patient: Patient, practitioner: Practitioner, date: date) -> Encounter:
        encounter_types = ['outpatient', 'inpatient', 'emergency', 'virtual']
        start = datetime.combine(date, datetime.min.time()) + timedelta(hours=9)  # 9 AM
        end = start + timedelta(hours=random.randint(1, 3))
        
        return Encounter.objects.create(
            patient=patient,
            encounter_type=random.choice(encounter_types),
            reason=f"Auto-generated encounter for {patient.get_full_name()}",
            location=random.choice(['Main Clinic', 'Emergency Dept', 'Virtual Visit']),
            start_time=start,
            end_time=end,
            status='completed'
        )

    def create_observation(self, patient: Patient, encounter: Encounter, date: date):
        observations = [
            ("blood-pressure", "120/80", "mmHg"),
            ("heart-rate", "72", "bpm"),
            ("temperature", "98.6", "°F"),
            ("height", "68", "in"),
            ("weight", "150", "lbs"),
            ("oxygen-saturation", "98", "%")
        ]
        
        code, value, unit = random.choice(observations)
        
        Observation.objects.create(
            patient=patient,
            encounter=encounter,
            code=code,
            value=value,
            unit=unit,
            observation_time=datetime.combine(date, datetime.min.time()) + timedelta(hours=10)
        )

    def create_condition(self, patient: Patient, encounter: Encounter, date: date):
        conditions = [
            ("J18.9", "Pneumonia, unspecified"),
            ("E11.65", "Type 2 diabetes with hyperglycemia"),
            ("I10", "Essential (primary) hypertension"),
            ("M54.5", "Low back pain"),
            ("J45.909", "Asthma, unspecified")
        ]
        
        code, description = random.choice(conditions)
        
        Condition.objects.create(
            patient=patient,
            encounter=encounter,
            code=code,
            description=description,
            onset_date=date - timedelta(days=random.randint(1, 365)),
            status=random.choice(['active', 'resolved'])
        )

    def create_medication(self, patient: Patient, encounter: Encounter, date: date):
        medications = [
            ("Amoxicillin", "500mg", "oral", "every 8 hours"),
            ("Lisinopril", "10mg", "oral", "daily"),
            ("Metformin", "1000mg", "oral", "twice daily"),
            ("Albuterol", "90mcg", "inhalation", "as needed"),
            ("Ibuprofen", "400mg", "oral", "every 6 hours as needed")
        ]
        
        name, dosage, route, frequency = random.choice(medications)
        
        MedicationStatement.objects.create(
            patient=patient,
            encounter=encounter,
            medication_name=name,
            dosage=f"{dosage} {frequency}",
            route=route,
            start_date=date,
            end_date=date + timedelta(days=random.randint(7, 30))
        )

    def create_allergy(self, patient: Patient, date: date):
        allergies = [
            ("Penicillin", "Hives, difficulty breathing"),
            ("Sulfa drugs", "Rash"),
            ("Peanuts", "Anaphylaxis"),
            ("Latex", "Contact dermatitis"),
            ("Iodine", "Hives")
        ]
        
        substance, reaction = random.choice(allergies)
        
        AllergyIntolerance.objects.create(
            patient=patient,
            substance=substance,
            reaction=reaction,
            severity=random.choice(['mild', 'moderate', 'severe']),
            recorded_date=date
        )

    def create_procedure(self, patient: Patient, encounter: Encounter, date: date):
        procedures = [
            ("CPT-99213", "Office visit"),
            ("CPT-90658", "Influenza vaccine"),
            ("CPT-85025", "Complete blood count"),
            ("CPT-71045", "Chest X-ray"),
            ("CPT-93000", "Electrocardiogram")
        ]
        
        code, name = random.choice(procedures)
        
        Procedure.objects.create(
            patient=patient,
            encounter=encounter,
            procedure_name=name,
            code=code,
            performed_date=date,
            outcome="Procedure completed successfully"
        )

    def create_immunization(self, patient: Patient, date: date):
        vaccines = [
            ("Influenza", "FLU2023"),
            ("Tetanus", "TDAP-2022"),
            ("COVID-19", "COVID-BOOSTER"),
            ("Pneumococcal", "PNEUMO-2021"),
            ("Hepatitis B", "HEP-B-SERIES")
        ]
        
        name, lot = random.choice(vaccines)
        
        Immunization.objects.create(
            patient=patient,
            vaccine_name=name,
            date_administered=date,
            lot_number=lot,
            performer="Dr. Smith"
        )

    def create_sample_practitioner(self) -> Practitioner:
        return Practitioner.objects.create(
            first_name='Dr. Sample',
            last_name='Generator',
            specialization='General Medicine',
            license_number='GEN001',
            email='sample.doctor@hospital.com',
            phone='555-0123'
        )

    def calculate_age(self, birth_date) -> int:
        today = timezone.now().date()
        return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

    def queue_for_fhir_sync(self, patient: Patient):
        try:
            from Fsync.queueManager import SyncQueueManager
            
            SyncQueueManager.queue_patient(patient, operation='update')
            
            recent_encounters = Encounter.objects.filter(
                patient=patient,
                start_time__gte=timezone.now() - timedelta(days=30)
            )
            
            for encounter in recent_encounters:
                SyncQueueManager.queue_encounter(encounter, operation='create')
                for observation in encounter.observation_set.all():
                    SyncQueueManager.queue_observation(observation, operation='create')
                
            self.stdout.write(f'Queued {patient.patient_id} for FHIR sync')
            
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'Could not queue for sync: {e}')
            )