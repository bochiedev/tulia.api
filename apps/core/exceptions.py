"""
Custom exception handlers for DRF.
"""
import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django_ratelimit.exceptions import Ratelimited

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that logs errors and returns consistent format.
    """
    # Handle django-ratelimit exceptions
    if isinstance(exc, Ratelimited):
        request = context.get('request')
        request_id = getattr(request, 'request_id', None) if request else None
        
        logger.warning(
            f"Rate limit exceeded",
            extra={
                'request_id': request_id,
                'path': request.path if request else None,
                'method': request.method if request else None,
                'ip': request.META.get('REMOTE_ADDR') if request else None,
            }
        )
        
        return Response(
            {
                'error': 'Rate limit exceeded. Please try again later.',
                'code': 'RATE_LIMIT_EXCEEDED',
                'request_id': request_id,
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )
    
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
