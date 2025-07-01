# ============================================================================
# mappers.py - FHIR Resource Mappers
# ============================================================================
from typing import Dict, Any, Optional, List
from django.db import models
from datetime import datetime
from django.utils import timezone

class FHIRMapper:
    """Base class for FHIR resource mappers"""
    
    @staticmethod
    def safe_get_attr(obj, attr_path: str, default=None):
        """Safely get nested attribute from object"""
        try:
            attrs = attr_path.split('.')
            result = obj
            for attr in attrs:
                result = getattr(result, attr, default)
                if result is None:
                    return default
            return result
        except (AttributeError, TypeError):
            return default
    
    @staticmethod
    def format_datetime(dt) -> Optional[str]:
        """Format datetime for FHIR"""
        if dt is None:
            return None
        if isinstance(dt, str):
            return dt
        return dt.isoformat()
    
    @staticmethod
    def format_date(dt) -> Optional[str]:
        """Format date for FHIR"""
        if dt is None:
            return None
        if isinstance(dt, str):
            return dt
        return dt.strftime('%Y-%m-%d')

