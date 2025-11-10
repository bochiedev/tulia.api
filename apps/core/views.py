"""
Core API views.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import connection
from django.core.cache import cache
from drf_spectacular.utils import extend_schema
import logging

logger = logging.getLogger(__name__)


class HealthCheckView(APIView):
    """
    Health check endpoint to verify system dependencies.
    
    GET /v1/health
    
    Returns 200 if all dependencies are healthy, 503 otherwise.
    """
    authentication_classes = []
    permission_classes = []
    
    @extend_schema(
        summary="Health check",
        description="Check the health of the system and its dependencies",
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'string'},
                    'database': {'type': 'string'},
                    'cache': {'type': 'string'},
                    'celery': {'type': 'string'},
                }
            },
            503: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'string'},
                    'database': {'type': 'string'},
                    'cache': {'type': 'string'},
                    'celery': {'type': 'string'},
                    'errors': {'type': 'array', 'items': {'type': 'string'}},
                }
            }
        }
    )
    def get(self, request):
        """Check health of all dependencies."""
        health_status = {
            'status': 'healthy',
            'database': 'unknown',
            'cache': 'unknown',
            'celery': 'unknown',
        }
        errors = []
        
        # Check database connectivity
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            health_status['database'] = 'healthy'
        except Exception as e:
            health_status['database'] = 'unhealthy'
            errors.append(f"Database: {str(e)}")
            logger.error("Database health check failed", exc_info=True)
        
        # Check Redis cache connectivity
        try:
            cache.set('health_check', 'ok', timeout=10)
            if cache.get('health_check') == 'ok':
                health_status['cache'] = 'healthy'
            else:
                health_status['cache'] = 'unhealthy'
                errors.append("Cache: Unable to read test key")
        except Exception as e:
            health_status['cache'] = 'unhealthy'
            errors.append(f"Cache: {str(e)}")
            logger.error("Cache health check failed", exc_info=True)
        
        # Check Celery worker availability
        try:
            from config.celery import app as celery_app
            inspect = celery_app.control.inspect(timeout=2.0)
            stats = inspect.stats()
            if stats:
                health_status['celery'] = 'healthy'
            else:
                health_status['celery'] = 'unhealthy'
                errors.append("Celery: No workers available")
        except Exception as e:
            health_status['celery'] = 'unhealthy'
            errors.append(f"Celery: {str(e)}")
            logger.error("Celery health check failed", exc_info=True)
        
        # Determine overall status
        if errors:
            health_status['status'] = 'unhealthy'
            health_status['errors'] = errors
            return Response(health_status, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        return Response(health_status, status=status.HTTP_200_OK)
