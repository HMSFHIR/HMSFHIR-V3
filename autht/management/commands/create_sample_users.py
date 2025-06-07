from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Create sample hospital users'
    
    def handle(self, *args, **options):
        sample_users = [
            {
                'practitioner_id': 'ADMIN001',
                'username': 'ADMIN001',
                'email': 'admin@hospital.com',
                'first_name': 'System',
                'last_name': 'Administrator',
                'user_type': 'admin',
                'department': 'IT',
                'password': 'admin123'
            },
            {
                'practitioner_id': 'DOC001',
                'username': 'DOC001',
                'email': 'doctor1@hospital.com',
                'first_name': 'John',
                'last_name': 'Smith',
                'user_type': 'doctor',
                'department': 'Cardiology',
                'password': 'doctor123'
            },
            {
                'practitioner_id': 'NUR001',
                'username': 'NUR001',
                'email': 'nurse1@hospital.com',
                'first_name': 'Mary',
                'last_name': 'Johnson',
                'user_type': 'nurse',
                'department': 'Emergency',
                'password': 'nurse123'
            }
        ]
        
        for user_data in sample_users:
            if not User.objects.filter(practitioner_id=user_data['practitioner_id']).exists():
                password = user_data.pop('password')
                user = User.objects.create_user(**user_data)
                user.set_password(password)
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(f'Created user: {user_data["practitioner_id"]}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'User already exists: {user_data["practitioner_id"]}')
                )