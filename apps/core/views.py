"""
Core API views.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import connection
from django.core.cache import cache
from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
import logging

from apps.core.permissions import HasTenantScopes

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



class TestSendWhatsAppView(APIView):
    """
    Test utility endpoint for sending WhatsApp messages.
    
    POST /v1/test/send-whatsapp
    
    This endpoint is for testing purposes only and should be disabled in production.
    Allows sending test WhatsApp messages through the tenant's Twilio configuration.
    
    Required scope: integrations:manage
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'integrations:manage'}
    
    @extend_schema(
        summary="Send test WhatsApp message",
        description="""
        Send a test WhatsApp message using the tenant's Twilio configuration.
        
        **Note:** This endpoint is only available in development/testing environments (DEBUG=True).
        It is automatically disabled in production for security reasons.
        
        Required scope: `integrations:manage`
        """,
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'to': {
                        'type': 'string',
                        'description': 'Recipient phone number in E.164 format (e.g., +1234567890)',
                        'example': '+1234567890'
                    },
                    'body': {
                        'type': 'string',
                        'description': 'Message text content',
                        'example': 'This is a test message from Tulia AI'
                    },
                    'media_url': {
                        'type': 'string',
                        'description': 'Optional media URL to send with the message',
                        'example': 'https://example.com/image.jpg',
                        'nullable': True
                    }
                },
                'required': ['to', 'body']
            }
        },
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message_sid': {'type': 'string'},
                    'status': {'type': 'string'},
                    'to': {'type': 'string'},
                    'from': {'type': 'string'},
                }
            },
            400: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'},
                    'details': {'type': 'object'}
                }
            },
            403: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'},
                    'message': {'type': 'string'}
                }
            },
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'},
                    'message': {'type': 'string'}
                }
            },
            500: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Test Utilities']
    )
    def post(self, request):
        """Send a test WhatsApp message."""
        # Restrict to development/testing environments only
        if not settings.DEBUG:
            return Response(
                {
                    'error': 'Endpoint not available',
                    'message': 'This test utility endpoint is only available in development environments (DEBUG=True)'
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            # Get tenant from request context (set by TenantContextMiddleware)
            tenant = request.tenant
            
            # Validate request data
            to_number = request.data.get('to')
            body = request.data.get('body')
            media_url = request.data.get('media_url')
            
            if not to_number:
                return Response(
                    {'error': 'Missing required field: to'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not body:
                return Response(
                    {'error': 'Missing required field: body'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate phone number format (basic E.164 check)
            if not to_number.startswith('+'):
                return Response(
                    {
                        'error': 'Invalid phone number format',
                        'details': {'message': 'Phone number must be in E.164 format (e.g., +1234567890)'}
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if tenant has Twilio configuration
            if not tenant.settings.twilio_sid or not tenant.settings.twilio_token:
                return Response(
                    {
                        'error': 'Twilio not configured',
                        'details': {'message': 'Tenant does not have Twilio credentials configured'}
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Import TwilioService
            from apps.integrations.services.twilio_service import create_twilio_service_for_tenant
            
            # Create Twilio service for tenant
            twilio_service = create_twilio_service_for_tenant(tenant)
            
            # Send message
            result = twilio_service.send_whatsapp(
                to=to_number,
                body=body,
                media_url=media_url
            )
            
            logger.info(
                f"Test WhatsApp message sent",
                extra={
                    'tenant_id': str(tenant.id),
                    'to': to_number,
                    'message_sid': result.get('sid')
                }
            )
            
            return Response({
                'success': True,
                'message_sid': result.get('sid'),
                'status': result.get('status'),
                'to': to_number,
                'from': tenant.whatsapp_number
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(
                f"Error sending test WhatsApp message",
                extra={'tenant_id': str(request.tenant.id) if hasattr(request, 'tenant') else None},
                exc_info=True
            )
            
            return Response(
                {
                    'success': False,
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
