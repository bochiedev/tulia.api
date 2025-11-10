"""
Custom exception handlers for DRF.
"""
import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that logs errors and returns consistent format.
    """
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


# Legacy aliases for backward compatibility
TenantNotFoundError = TenantNotFound
SubscriptionInactiveError = SubscriptionInactive
FeatureLimitExceededError = FeatureLimitExceeded
ConsentRequiredError = ConsentRequired
RateLimitExceededError = RateLimitExceeded
