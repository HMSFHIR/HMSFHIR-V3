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
    
    # Override fieldsets to use practitioner_id instead of username
    fieldsets = (
        (None, {'fields': ('practitioner_id', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Hospital Information', {
            'fields': ('user_type', 'department', 'phone_number', 'is_active_practitioner')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    # Override add_fieldsets for creating new users
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('practitioner_id', 'password1', 'password2'),
        }),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Hospital Information', {
            'fields': ('user_type', 'department', 'phone_number', 'is_active_practitioner')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser'),
        }),
    )