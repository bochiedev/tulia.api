"""
Custom exception handlers for DRF.
"""
import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django_ratelimit.exceptions import Ratelimited
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def ratelimit_view(request, exception):
    """
    Custom view for django-ratelimit to return 429 instead of 403.
    
    This is called when rate limit is exceeded with block=True.
    Returns 429 with Retry-After header indicating when to retry.
    """
    from apps.core.logging import SecurityLogger
    
    # Get client IP and email (if available)
    ip_address = request.META.get('REMOTE_ADDR', 'unknown')
    email = None
    tenant_id = None
    
    # Try to get email from request data
    if hasattr(request, 'data') and isinstance(request.data, dict):
        email = request.data.get('email')
    elif request.method == 'POST' and request.POST:
        email = request.POST.get('email')
    elif request.method == 'POST' and request.body:
        try:
            import json
            data = json.loads(request.body)
            email = data.get('email')
        except:
            pass
    
    # Try to get tenant_id from request
    if hasattr(request, 'tenant') and request.tenant:
        tenant_id = str(request.tenant.id)
    
    # Determine retry-after time based on endpoint
    retry_after = 60  # Default: 1 minute
    if '/auth/register' in request.path or '/auth/forgot-password' in request.path:
        retry_after = 3600  # 1 hour for registration and password reset
    elif '/auth/login' in request.path:
        retry_after = 60  # 1 minute for login
    elif '/auth/verify-email' in request.path or '/auth/reset-password' in request.path:
        retry_after = 3600  # 1 hour for verification and reset
    
    # Log security event
    SecurityLogger.log_rate_limit_exceeded(
        endpoint=request.path,
        ip_address=ip_address,
        user_email=email,
        tenant_id=tenant_id,
        limit='Rate limit exceeded'
    )
    
    logger.warning(
        f"Rate limit exceeded",
        extra={
            'request_id': getattr(request, 'request_id', None),
            'path': request.path,
            'method': request.method,
            'ip': ip_address,
            'retry_after': retry_after,
        }
    )
    
    response = JsonResponse(
        {
            'error': 'Rate limit exceeded. Please try again later.',
            'code': 'RATE_LIMIT_EXCEEDED',
            'retry_after': retry_after,
        },
        status=429
    )
    
    # Add Retry-After header (RFC 6585)
    response['Retry-After'] = str(retry_after)
    
    return response


def custom_exception_handler(exc, context):
    """
    Custom exception handler that logs errors and returns consistent format.
    """
    # Handle django-ratelimit exceptions
    if isinstance(exc, Ratelimited):
        from apps.core.logging import SecurityLogger
        
        request = context.get('request')
        request_id = getattr(request, 'request_id', None) if request else None
        
        # Get client IP and email (if available)
        ip_address = request.META.get('REMOTE_ADDR', 'unknown') if request else 'unknown'
        email = None
        tenant_id = None
        
        if request:
            # Try to get email from request data
            if hasattr(request, 'data') and isinstance(request.data, dict):
                email = request.data.get('email')
            
            # Try to get tenant_id from request
            if hasattr(request, 'tenant') and request.tenant:
                tenant_id = str(request.tenant.id)
        
        # Determine retry-after time based on endpoint
        retry_after = 60  # Default: 1 minute
        if request and request.path:
            if '/auth/register' in request.path or '/auth/forgot-password' in request.path:
                retry_after = 3600  # 1 hour for registration and password reset
            elif '/auth/login' in request.path:
                retry_after = 60  # 1 minute for login
            elif '/auth/verify-email' in request.path or '/auth/reset-password' in request.path:
                retry_after = 3600  # 1 hour for verification and reset
        
        # Log security event
        SecurityLogger.log_rate_limit_exceeded(
            endpoint=request.path if request else 'unknown',
            ip_address=ip_address,
            user_email=email,
            tenant_id=tenant_id,
            limit='Rate limit exceeded'
        )
        
        logger.warning(
            f"Rate limit exceeded",
            extra={
                'request_id': request_id,
                'path': request.path if request else None,
                'method': request.method if request else None,
                'ip': ip_address,
                'retry_after': retry_after,
            }
        )
        
        response = Response(
            {
                'error': 'Rate limit exceeded. Please try again later.',
                'code': 'RATE_LIMIT_EXCEEDED',
                'request_id': request_id,
                'retry_after': retry_after,
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )
        
        # Add Retry-After header (RFC 6585)
        response['Retry-After'] = str(retry_after)
        
        return response
    
    # Call DRF's default exception handler first
    response = exception_handler(exc, context)
    
    # Log the exception
    request = context.get('request')
    request_id = getattr(request, 'request_id', None) if request else None
    
    logger.error(
        f"API Exception: {exc.__class__.__name__}",
        extra={
            'exception': str(exc),
            'request_id': request_id,
            'path': request.path if request else None,
            'method': request.method if request else None,
        },
        exc_info=True
    )
    
    # If DRF didn't handle it, return a generic 500 error
    if response is None:
        return Response(
            {
                'error': 'Internal server error',
                'detail': str(exc) if logger.level == logging.DEBUG else 'An unexpected error occurred',
                'request_id': request_id,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # Add request_id to all error responses
    if request_id and isinstance(response.data, dict):
        response.data['request_id'] = request_id
    
    return response


class TuliaException(Exception):
    """Base exception for Tulia-specific errors."""
    
    def __init__(self, message, details=None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class TenantNotFound(TuliaException):
    """Raised when tenant cannot be resolved."""
    pass


class SubscriptionInactive(TuliaException):
    """Raised when tenant subscription is not active."""
    pass


class FeatureLimitExceeded(TuliaException):
    """Raised when tenant exceeds feature limits."""
    pass


class ConsentRequired(TuliaException):
    """Raised when customer consent is required but not granted."""
    pass


class RateLimitExceeded(TuliaException):
    """Raised when rate limit is exceeded."""
    pass


class AuthenticationError(TuliaException):
    """Raised when authentication fails."""
    status_code = 401


class PermissionDeniedError(TuliaException):
    """Raised when user lacks required permissions."""
    status_code = 403


class ValidationError(TuliaException):
    """Raised when input validation fails."""
    status_code = 400


class CredentialValidationError(ValidationError):
    """Raised when external credential validation fails."""
    pass


class OnboardingIncompleteError(TuliaException):
    """Raised when action requires completed onboarding."""
    status_code = 403


# Legacy aliases for backward compatibility
TenantNotFoundError = TenantNotFound
SubscriptionInactiveError = SubscriptionInactive
FeatureLimitExceededError = FeatureLimitExceeded
ConsentRequiredError = ConsentRequired
RateLimitExceededError = RateLimitExceeded
