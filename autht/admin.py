# admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """Admin interface for CustomUser"""
    list_display = ('practitioner_id', 'first_name', 'last_name', 'email', 'user_type', 'department', 'is_active', 'is_active_practitioner')
    list_filter = ('user_type', 'department', 'is_active', 'is_active_practitioner', 'date_joined')
    search_fields = ('practitioner_id', 'first_name', 'last_name', 'email')
    ordering = ('practitioner_id',)
    
    fieldsets = UserAdmin.fieldsets + (
        ('Hospital Information', {
            'fields': ('practitioner_id', 'user_type', 'department', 'phone_number', 'is_active_practitioner')
        }),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Hospital Information', {
            'fields': ('practitioner_id', 'user_type', 'department', 'phone_number', 'is_active_practitioner')
        }),
    )