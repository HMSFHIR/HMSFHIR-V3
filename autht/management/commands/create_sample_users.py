from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Create sample hospital users including admin user'
    
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
                'password': 'admin123',
                'is_staff': True,
                'is_superuser': True,  # This makes them an admin user
                'is_active': True
            },
            {
                'practitioner_id': 'ADMIN002',
                'username': 'ADMIN002',
                'email': 'admin2@hospital.com',
                'first_name': 'Super',
                'last_name': 'Admin',
                'user_type': 'admin',
                'department': 'Administration',
                'password': 'superadmin123',
                'is_staff': True,
                'is_superuser': True,  # This makes them an admin user
                'is_active': True
            },
            {
                'practitioner_id': 'DOC001',
                'username': 'DOC001',
                'email': 'doctor1@hospital.com',
                'first_name': 'John',
                'last_name': 'Smith',
                'user_type': 'doctor',
                'department': 'Cardiology',
                'password': 'doctor123',
                'is_staff': False,
                'is_superuser': False,
                'is_active': True
            },
            {
                'practitioner_id': 'NUR001',
                'username': 'NUR001',
                'email': 'nurse1@hospital.com',
                'first_name': 'Mary',
                'last_name': 'Johnson',
                'user_type': 'nurse',
                'department': 'Emergency',
                'password': 'nurse123',
                'is_staff': False,
                'is_superuser': False,
                'is_active': True
            }
        ]
        
        for user_data in sample_users:
            if not User.objects.filter(practitioner_id=user_data['practitioner_id']).exists():
                password = user_data.pop('password')
                user = User.objects.create_user(**user_data)
                user.set_password(password)
                user.save()
                
                # Display appropriate message based on user type
                if user.is_superuser:
                    self.stdout.write(
                        self.style.SUCCESS(f'Created ADMIN user: {user.practitioner_id} (can access Django admin)')
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(f'Created user: {user.practitioner_id}')
                    )
            else:
                self.stdout.write(
                    self.style.WARNING(f'User already exists: {user_data["practitioner_id"]}')
                )
        
        # Display login information
        self.stdout.write(
            self.style.SUCCESS('\n--- ADMIN LOGIN DETAILS ---')
        )
        self.stdout.write(
            self.style.SUCCESS('Option 1 - Practitioner ID: ADMIN001, Password: admin123')
        )
        self.stdout.write(
            self.style.SUCCESS('Option 2 - Practitioner ID: ADMIN002, Password: superadmin123')
        )
        self.stdout.write(
            self.style.SUCCESS('Admin URL: http://127.0.0.1:8000/admin/')
        )