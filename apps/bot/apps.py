"""
Bot app configuration with enhanced logging and observability setup.
"""

from django.apps import AppConfig
import logging


class BotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.bot'
    verbose_name = 'Tulia AI Bot'

    def ready(self):
        """Initialize bot app with enhanced logging and observability."""
        # Configure comprehensive logging
        try:
            from apps.bot.services.logging_config import configure_logging
            configure_logging()
        except Exception as e:
            # Fallback to basic logging if configuration fails
            logging.basicConfig(level=logging.INFO)
            logging.getLogger(__name__).warning(f"Failed to configure enhanced logging: {e}")
        
        # Initialize observability services
        try:
            from apps.bot.services.observability import observability_service
            from apps.bot.services.metrics_collector import metrics_collector
            from apps.bot.services.monitoring_integration import monitoring_integration
            
            # Services are initialized on import, just log success
            logger = logging.getLogger('tulia')
            logger.info(
                "Observability services initialized successfully",
                extra={
                    'observability_service': 'ready',
                    'metrics_collector': 'ready',
                    'monitoring_integration': 'ready'
                }
            )
            
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to initialize observability services: {e}")
        
        # Set up monitoring integration if configured
        try:
            from django.conf import settings
            
            monitoring_config = getattr(settings, 'TULIA_MONITORING', {})
            if monitoring_config:
                from apps.bot.services.monitoring_integration import setup_monitoring
                setup_monitoring(monitoring_config)
                
                logger = logging.getLogger('tulia.monitoring')
                logger.info(
                    "Monitoring integration configured",
                    extra={'config': monitoring_config}
                )
        except Exception as e:
            logging.getLogger(__name__).warning(f"Monitoring integration setup failed: {e}")
        
        # Import signals to ensure they are registered
        try:
            from apps.bot import signals  # noqa
        except ImportError:
            pass
    verbose_name = 'Bot'
