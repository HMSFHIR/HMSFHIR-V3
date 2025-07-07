from django.apps import AppConfig

class FSyncConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Fsync'
    
    def ready(self):
        """Setup sync signals and register Celery tasks"""
        import logging
        logger = logging.getLogger(__name__)

        # Import task modules for Celery registration
        try:
            import Fsync.maintenanceUtils
        except Exception as e:
            logger.error(f"Failed to import maintenanceUtils: {e}")

        # Setup Django signals
        try:
            from .signals import setup_sync_signals
            setup_sync_signals()
        except Exception as e:
            logger.error(f"Failed to setup sync signals: {e}")
