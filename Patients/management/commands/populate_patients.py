from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from faker import Faker
from datetime import date, timedelta
import random
from Patients.models import Patient  # Replace 'myapp' with your actual app name

User = get_user_model()

class Command(BaseCommand):
    help = 'Populate the database with sample patient data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=100,
            help='Number of patients to create (default: 100)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing patients before creating new ones'
        )

    def handle(self, *args, **options):
        fake = Faker()
        count = options['count']
        
        if options['clear']:
            self.stdout.write('Clearing existing patients...')
            Patient.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Existing patients cleared.'))

        self.stdout.write(f'Creating {count} sample patients...')

        # Get a default user for created_by field (optional)
        try:
            default_user = User.objects.first()
        except:
            default_user = None

        # Ghanaian-specific data
        ghanaian_cities = [
            'Accra', 'Kumasi', 'Tamale', 'Takoradi', 'Cape Coast', 
            'Sunyani', 'Koforidua', 'Ho', 'Wa', 'Bolgatanga'
        ]
        
        ghanaian_regions = [
            'Greater Accra', 'Ashanti', 'Northern', 'Western', 'Central',
            'Brong-Ahafo', 'Eastern', 'Volta', 'Upper West', 'Upper East'
        ]

        # Common Ghanaian surnames
        ghanaian_surnames = [
            'Asante', 'Osei', 'Mensah', 'Boateng', 'Adjei', 'Owusu', 'Appiah',
            'Yeboah', 'Kwame', 'Agyei', 'Nkrumah', 'Ofori', 'Gyasi', 'Bonsu',
            'Acheampong', 'Nyong', 'Addo', 'Tetteh', 'Quaye', 'Larbi'
        ]

        # Phone number prefixes for Ghana
        ghana_prefixes = ['0233', '0244', '0245', '0246', '0254', '0255', '0256', '0257']

        patients_created = 0
        
        for i in range(count):
            try:
                # Decide if this should be a Ghanaian name or international
                use_ghanaian_name = random.choice([True, False])
                
                # Generate names
                if use_ghanaian_name:
                    given_name = fake.first_name()
                    family_name = random.choice(ghanaian_surnames)
                else:
                    given_name = fake.first_name()
                    family_name = fake.last_name()
                
                middle_name = fake.first_name() if random.choice([True, False, False]) else None
                
                # Generate other demographics
                gender = random.choice(['male', 'female', 'other', 'unknown'])
                birth_date = fake.date_of_birth(minimum_age=0, maximum_age=100)
                
                # Generate phone numbers with Ghanaian format
                primary_phone = f"+233{random.choice(ghana_prefixes)[1:]}{fake.random_number(digits=7, fix_len=True)}"
                secondary_phone = f"+233{random.choice(ghana_prefixes)[1:]}{fake.random_number(digits=7, fix_len=True)}" if random.choice([True, False, False]) else None
                
                # Generate address - mix of Ghanaian and international
                city = random.choice(ghanaian_cities) if random.choice([True, False]) else fake.city()
                state_province = random.choice(ghanaian_regions) if city in ghanaian_cities else fake.state()
                country = 'Ghana' if city in ghanaian_cities else fake.country()
                
                # Generate medical record number
                mrn = f"MRN-{fake.random_number(digits=8, fix_len=True)}"
                
                # Generate national ID (Ghana Card format simulation)
                national_id = f"GHA-{fake.random_number(digits=9, fix_len=True)}-{random.randint(1, 9)}"
                
                # Create patient
                patient = Patient.objects.create(
                    # Name fields
                    given_name=given_name,
                    family_name=family_name,
                    middle_name=middle_name,
                    name_prefix=random.choice(['Dr.', 'Mr.', 'Mrs.', 'Ms.', '']) if random.random() < 0.3 else None,
                    name_suffix=random.choice(['Jr.', 'Sr.', 'III', '']) if random.random() < 0.1 else None,
                    
                    # Demographics
                    gender=gender,
                    birth_date=birth_date,
                    
                    # Identifiers
                    national_id=national_id,
                    medical_record_number=mrn,
                    insurance_number=f"INS-{fake.random_number(digits=10, fix_len=True)}" if random.choice([True, False]) else None,
                    
                    # Contact info
                    primary_phone=primary_phone,
                    secondary_phone=secondary_phone,
                    email=fake.email() if random.choice([True, False]) else None,
                    
                    # Address
                    address_line1=fake.street_address(),
                    address_line2=fake.secondary_address() if random.choice([True, False, False]) else None,
                    city=city,
                    state_province=state_province,
                    postal_code=fake.postcode() if random.choice([True, False]) else None,
                    country=country,
                    
                    # Additional demographics
                    marital_status=random.choice(['single', 'married', 'divorced', 'widowed', 'separated', 'unknown']),
                    preferred_language=random.choice(['en', 'tw', 'ga', 'ee', 'fr', 'ha']),
                    
                    # Emergency contact
                    emergency_contact_name=fake.name() if random.choice([True, False]) else None,
                    emergency_contact_relationship=random.choice(['spouse', 'parent', 'sibling', 'friend', 'child']) if random.choice([True, False]) else None,
                    emergency_contact_phone=f"+233{random.choice(ghana_prefixes)[1:]}{fake.random_number(digits=7, fix_len=True)}" if random.choice([True, False]) else None,
                    
                    # Clinical info
                    blood_type=random.choice(['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']) if random.choice([True, False]) else None,
                    allergies=', '.join(fake.words(nb=random.randint(0, 3))) if random.choice([True, False, False, False]) else None,
                    
                    # Status
                    active=random.choice([True, True, True, False]),  # Most patients are active
                    deceased=random.choice([True, False, False, False, False]),  # Few are deceased
                    deceased_date=fake.date_between(start_date=birth_date, end_date='today') if random.choice([True, False, False, False, False]) else None,
                    
                    # Practice management
                    last_arrived=fake.date_between(start_date='-2y', end_date='today') if random.choice([True, False]) else None,
                    registration_date=fake.date_time_between(start_date='-5y', end_date='now'),
                    
                    # User tracking
                    created_by=default_user,
                    updated_by=default_user,
                )
                
                patients_created += 1
                
                # Progress indicator
                if patients_created % 10 == 0:
                    self.stdout.write(f'Created {patients_created}/{count} patients...')
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error creating patient {i+1}: {str(e)}')
                )
                continue

        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {patients_created} patients!')
        )
        
        # Show some statistics
        total_patients = Patient.objects.count()
        active_patients = Patient.objects.filter(active=True).count()
        deceased_patients = Patient.objects.filter(deceased=True).count()
        
        self.stdout.write('\n--- Database Statistics ---')
        self.stdout.write(f'Total patients: {total_patients}')
        self.stdout.write(f'Active patients: {active_patients}')
        self.stdout.write(f'Deceased patients: {deceased_patients}')
        self.stdout.write(f'Patients with phone numbers: {Patient.objects.exclude(primary_phone__isnull=True).count()}')
        self.stdout.write(f'Patients with email: {Patient.objects.exclude(email__isnull=True).count()}')