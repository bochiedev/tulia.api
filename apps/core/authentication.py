"""
Custom DRF authentication classes.
"""
from rest_framework.authentication import BaseAuthentication


class MiddlewareAuthentication(BaseAuthentication):
    """
    DRF authentication class that uses the user set by TenantContextMiddleware.
    
    This allows our middleware-based JWT authentication to work with DRF views.
    The middleware sets request.user, and this authentication class simply
    returns that user to DRF.
    """
    
    def authenticate(self, request):
        """
        Return the user from the middleware if present.
        
        Returns:
            tuple: (user, None) if user is authenticated, None otherwise
        """
        # Get the underlying Django request (DRF wraps it)
        django_request = request._request
        
        # Check if middleware set a user
        if hasattr(django_request, 'user') and django_request.user and django_request.user.is_authenticated:
            return (django_request.user, None)
        
        # No authenticated user from middleware
        return None
