"""
Logging configuration for comprehensive observability.

This module provides centralized logging configuration for the Tulia AI V2 system
with structured JSON logging, PII masking, and monitoring integration.

Requirements: 10.1, 10.4, 10.5
"""

import logging
import logging.config
import os
from typing import Dict, Any
from django.conf import settings

from apps.core.logging import JSONFormatter, PIIMasker


def get_logging_config() -> Dict[str, Any]:
    """
    Get comprehensive logging configuration for Tulia AI V2.
    
    Returns:
        Dictionary with logging configuration
    """
    
    # Base log level from settings or environment
    log_level = getattr(settings, 'LOG_LEVEL', os.getenv('LOG_LEVEL', 'INFO')).upper()
    
    # Log file paths
    log_dir = getattr(settings, 'LOG_DIR', os.getenv('LOG_DIR', 'logs'))
    os.makedirs(log_dir, exist_ok=True)
    
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'json': {
                '()': 'apps.core.logging.JSONFormatter',
            },
            'enhanced_json': {
                '()': 'apps.bot.services.logging_service.EnhancedJSONFormatter',
            },
            'simple': {
                'format': '{asctime} {levelname} {name} {message}',
                'style': '{',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'json',
                'level': log_level,
            },
            'file_all': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(log_dir, 'tulia_all.log'),
                'maxBytes': 50 * 1024 * 1024,  # 50MB
                'backupCount': 10,
                'formatter': 'json',
                'level': 'DEBUG',
            },
            'file_error': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(log_dir, 'tulia_error.log'),
                'maxBytes': 10 * 1024 * 1024,  # 10MB
                'backupCount': 5,
                'formatter': 'json',
                'level': 'ERROR',
            },
            'file_performance': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(log_dir, 'tulia_performance.log'),
                'maxBytes': 20 * 1024 * 1024,  # 20MB
                'backupCount': 5,
                'formatter': 'enhanced_json',
                'level': 'INFO',
            },
            'file_business': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(log_dir, 'tulia_business.log'),
                'maxBytes': 20 * 1024 * 1024,  # 20MB
                'backupCount': 5,
                'formatter': 'enhanced_json',
                'level': 'INFO',
            },
            'file_security': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(log_dir, 'tulia_security.log'),
                'maxBytes': 10 * 1024 * 1024,  # 10MB
                'backupCount': 10,
                'formatter': 'json',
                'level': 'WARNING',
            },
        },
        'loggers': {
            # Root logger
            '': {
                'handlers': ['console', 'file_all'],
                'level': log_level,
                'propagate': False,
            },
            # Django loggers
            'django': {
                'handlers': ['console', 'file_all'],
                'level': 'INFO',
                'propagate': False,
            },
            'django.request': {
                'handlers': ['console', 'file_error'],
                'level': 'ERROR',
                'propagate': False,
            },
            'django.security': {
                'handlers': ['console', 'file_security'],
                'level': 'WARNING',
                'propagate': False,
            },
            # Tulia AI specific loggers
            'tulia': {
                'handlers': ['console', 'file_all'],
                'level': log_level,
                'propagate': False,
            },
            'tulia.enhanced': {
                'handlers': ['console', 'file_all'],
                'level': 'INFO',
                'propagate': False,
            },
            'tulia.performance': {
                'handlers': ['console', 'file_performance'],
                'level': 'INFO',
                'propagate': False,
            },
            'tulia.business': {
                'handlers': ['console', 'file_business'],
                'level': 'INFO',
                'propagate': False,
            },
            'tulia.error': {
                'handlers': ['console', 'file_error'],
                'level': 'WARNING',
                'propagate': False,
            },
            'tulia.structured': {
                'handlers': ['console', 'file_all'],
                'level': 'INFO',
                'propagate': False,
            },
            'tulia.metrics': {
                'handlers': ['console', 'file_business'],
                'level': 'INFO',
                'propagate': False,
            },
            'tulia.monitoring': {
                'handlers': ['console', 'file_all'],
                'level': 'INFO',
                'propagate': False,
            },
            'tulia.monitoring.prometheus': {
                'handlers': ['console', 'file_all'],
                'level': 'INFO',
                'propagate': False,
            },
            'tulia.monitoring.webhook': {
                'handlers': ['console', 'file_all'],
                'level': 'INFO',
                'propagate': False,
            },
            # Security logger
            'security': {
                'handlers': ['console', 'file_security'],
                'level': 'WARNING',
                'propagate': False,
            },
            # Bot-specific loggers
            'apps.bot': {
                'handlers': ['console', 'file_all'],
                'level': log_level,
                'propagate': False,
            },
            'apps.bot.langgraph': {
                'handlers': ['console', 'file_all'],
                'level': log_level,
                'propagate': False,
            },
            'apps.bot.services': {
                'handlers': ['console', 'file_all'],
                'level': log_level,
                'propagate': False,
            },
            'apps.bot.tools': {
                'handlers': ['console', 'file_all'],
                'level': log_level,
                'propagate': False,
            },
            # Third-party loggers
            'requests': {
                'handlers': ['console', 'file_all'],
                'level': 'WARNING',
                'propagate': False,
            },
            'urllib3': {
                'handlers': ['console', 'file_all'],
                'level': 'WARNING',
                'propagate': False,
            },
            'openai': {
                'handlers': ['console', 'file_all'],
                'level': 'WARNING',
                'propagate': False,
            },
            'langchain': {
                'handlers': ['console', 'file_all'],
                'level': 'WARNING',
                'propagate': False,
            },
            'langgraph': {
                'handlers': ['console', 'file_all'],
                'level': 'INFO',
                'propagate': False,
            },
        },
    }
    
    # Add development-specific configuration
    if settings.DEBUG:
        # More verbose logging in development
        config['loggers']['tulia']['level'] = 'DEBUG'
        config['loggers']['apps.bot']['level'] = 'DEBUG'
        
        # Add console handler to all loggers in development
        for logger_config in config['loggers'].values():
            if 'console' not in logger_config['handlers']:
                logger_config['handlers'].append('console')
    
    # Add production-specific configuration
    else:
        # Add syslog handler for production if available
        try:
            import logging.handlers
            config['handlers']['syslog'] = {
                'class': 'logging.handlers.SysLogHandler',
                'address': '/dev/log',
                'formatter': 'json',
                'level': 'INFO',
            }
            
            # Add syslog to critical loggers
            config['loggers']['tulia']['handlers'].append('syslog')
            config['loggers']['security']['handlers'].append('syslog')
            config['loggers']['tulia.error']['handlers'].append('syslog')
            
        except Exception:
            # Syslog not available, continue without it
            pass
    
    return config


def configure_logging():
    """Configure logging for the Tulia AI V2 system."""
    config = get_logging_config()
    logging.config.dictConfig(config)
    
    # Log configuration success
    logger = logging.getLogger('tulia')
    logger.info(
        "Logging configuration applied successfully",
        extra={
            'log_level': config['loggers']['tulia']['level'],
            'handlers': config['loggers']['tulia']['handlers'],
            'debug_mode': settings.DEBUG
        }
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    
    Args:
        name: Logger name
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def get_structured_logger(name: str) -> logging.Logger:
    """
    Get a structured logger for JSON output.
    
    Args:
        name: Logger name
        
    Returns:
        Structured logger instance
    """
    return logging.getLogger(f'tulia.structured.{name}')


def get_performance_logger() -> logging.Logger:
    """Get performance-specific logger."""
    return logging.getLogger('tulia.performance')


def get_business_logger() -> logging.Logger:
    """Get business metrics logger."""
    return logging.getLogger('tulia.business')


def get_security_logger() -> logging.Logger:
    """Get security events logger."""
    return logging.getLogger('security')


def get_monitoring_logger() -> logging.Logger:
    """Get monitoring integration logger."""
    return logging.getLogger('tulia.monitoring')


# Convenience functions for common logging patterns

def log_with_context(logger: logging.Logger, level: str, message: str, 
                    tenant_id: str = None, conversation_id: str = None,
                    request_id: str = None, **kwargs):
    """
    Log message with common context fields.
    
    Args:
        logger: Logger instance
        level: Log level (info, warning, error, etc.)
        message: Log message
        tenant_id: Tenant identifier
        conversation_id: Conversation identifier
        request_id: Request identifier
        **kwargs: Additional context fields
    """
    extra = {}
    if tenant_id:
        extra['tenant_id'] = tenant_id
    if conversation_id:
        extra['conversation_id'] = conversation_id
    if request_id:
        extra['request_id'] = request_id
    
    extra.update(kwargs)
    
    log_method = getattr(logger, level.lower(), logger.info)
    log_method(message, extra=extra)


def log_performance_metric(operation: str, duration: float, success: bool = True, **kwargs):
    """
    Log performance metric with standard format.
    
    Args:
        operation: Operation name
        duration: Duration in seconds
        success: Whether operation was successful
        **kwargs: Additional context
    """
    logger = get_performance_logger()
    logger.info(
        f"Performance: {operation}",
        extra={
            'operation': operation,
            'duration_ms': duration * 1000,
            'success': success,
            'metric_type': 'performance',
            **kwargs
        }
    )


def log_business_event(event_type: str, **kwargs):
    """
    Log business event with standard format.
    
    Args:
        event_type: Type of business event
        **kwargs: Event details
    """
    logger = get_business_logger()
    logger.info(
        f"Business event: {event_type}",
        extra={
            'event_type': event_type,
            'metric_type': 'business',
            **kwargs
        }
    )


def log_security_event(event_type: str, severity: str = 'warning', **kwargs):
    """
    Log security event with standard format.
    
    Args:
        event_type: Type of security event
        severity: Event severity (info, warning, error, critical)
        **kwargs: Event details
    """
    logger = get_security_logger()
    log_method = getattr(logger, severity.lower(), logger.warning)
    log_method(
        f"Security event: {event_type}",
        extra={
            'event_type': event_type,
            'severity': severity,
            'metric_type': 'security',
            **kwargs
        }
    )