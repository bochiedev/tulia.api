"""
Core middleware for request processing.
"""
import uuid
import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class RequestIDMiddleware(MiddlewareMixin):
    """
    Inject a unique request_id into each request for tracing.
    The request_id is added to the request object and to log records.
    """
    
    def process_request(self, request):
        """Generate and attach request_id to the request."""
        request_id = request.META.get('HTTP_X_REQUEST_ID', str(uuid.uuid4()))
        request.request_id = request_id
        
        # Add to thread-local storage for logging
        import threading
        if not hasattr(threading.current_thread(), 'request_id'):
            threading.current_thread().request_id = request_id
    
    def process_response(self, request, response):
        """Add request_id to response headers."""
        if hasattr(request, 'request_id'):
            response['X-Request-ID'] = request.request_id
        return response


class LoggingFilter(logging.Filter):
    """
    Add request_id and tenant_id to log records from thread-local storage.
    """
    
    def filter(self, record):
        import threading
        thread = threading.current_thread()
        
        # Add request_id if available
        if hasattr(thread, 'request_id'):
            record.request_id = thread.request_id
        
        # Add tenant_id if available
        if hasattr(thread, 'tenant_id'):
            record.tenant_id = thread.tenant_id
        
        return True
