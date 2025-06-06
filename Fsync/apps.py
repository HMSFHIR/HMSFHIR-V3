from django.apps import AppConfig

class FSyncConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Fsync'
    
    def ready(self):
        """Setup signals when app is ready"""
        try:
            from .signals import setup_sync_signals
            setup_sync_signals()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to setup sync signals: {e}")