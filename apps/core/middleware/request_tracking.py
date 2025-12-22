"""
Request ID tracking middleware for conversation flow correlation.

Provides request_id tracking throughout conversation flow and integrates
with logging infrastructure for comprehensive observability.
"""
import uuid
import logging
import time
from typing import Optional
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpRequest, HttpResponse

from apps.core.logging import PIIMasker


class RequestTrackingMiddleware(MiddlewareMixin):
    """
    Middleware to track request IDs and add them to logging context.
    
    Generates unique request IDs for each incoming request and makes them
    available throughout the request lifecycle for correlation and debugging.
    """
    
    def __init__(self, get_response=None):
        """Initialize request tracking middleware."""
        super().__init__(get_response)
        self.logger = logging.getLogger('apps.core.request_tracking')
    
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        Process incoming request and set up tracking context.
        
        Args:
            request: Django HTTP request
            
        Returns:
            None to continue processing
        """
        # Generate or extract request ID
        request_id = self._get_or_generate_request_id(request)
        
        # Store request ID on request object
        request.request_id = request_id
        
        # Store request start time for performance tracking
        request.start_time = time.time()
        
        # Add request ID to logging context for this thread
        self._set_logging_context(request)
        
        # Log request start
        self._log_request_start(request)
        
        return None
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """
        Process outgoing response and log completion metrics.
        
        Args:
            request: Django HTTP request
            response: Django HTTP response
            
        Returns:
            Modified response with request ID header
        """
        # Calculate request duration
        duration = time.time() - getattr(request, 'start_time', time.time())
        
        # Add request ID to response headers for client correlation
        if hasattr(request, 'request_id'):
            response['X-Request-ID'] = request.request_id
        
        # Log request completion
        self._log_request_completion(request, response, duration)
        
        return response
    
    def process_exception(self, request: HttpRequest, exception: Exception) -> Optional[HttpResponse]:
        """
        Process exceptions and log error context.
        
        Args:
            request: Django HTTP request
            exception: Exception that occurred
            
        Returns:
            None to continue exception handling
        """
        # Calculate request duration
        duration = time.time() - getattr(request, 'start_time', time.time())
        
        # Log exception with request context
        self._log_request_exception(request, exception, duration)
        
        return None
    
    def _get_or_generate_request_id(self, request: HttpRequest) -> str:
        """
        Get existing request ID from headers or generate new one.
        
        Args:
            request: Django HTTP request
            
        Returns:
            Request ID string
        """
        # Check for existing request ID in headers
        request_id = request.META.get('HTTP_X_REQUEST_ID')
        
        if not request_id:
            # Check for conversation ID from webhook (for bot requests)
            conversation_id = request.META.get('HTTP_X_CONVERSATION_ID')
            if conversation_id:
                # Use conversation ID as base for request ID
                request_id = f"{conversation_id}_{uuid.uuid4().hex[:8]}"
            else:
                # Generate new UUID-based request ID
                request_id = uuid.uuid4().hex
        
        return request_id
    
    def _set_logging_context(self, request: HttpRequest):
        """
        Set logging context for this request thread.
        
        Args:
            request: Django HTTP request
        """
        # Add request ID to all log records in this thread
        # This is handled by the JSONFormatter in apps.core.logging
        pass
    
    def _log_request_start(self, request: HttpRequest):
        """
        Log request start with context.
        
        Args:
            request: Django HTTP request
        """
        # Extract basic request info
        method = request.method
        path = request.path
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        ip_address = self._get_client_ip(request)
        
        # Extract tenant context if available
        tenant_id = request.META.get('HTTP_X_TENANT_ID')
        
        # Log request start
        self.logger.info(
            f"Request started: {method} {path}",
            extra={
                'request_id': request.request_id,
                'method': method,
                'path': path,
                'ip_address': ip_address,
                'user_agent': PIIMasker.mask_text(user_agent),
                'tenant_id': tenant_id,
                'event_type': 'request_start'
            }
        )
    
    def _log_request_completion(self, request: HttpRequest, response: HttpResponse, duration: float):
        """
        Log request completion with metrics.
        
        Args:
            request: Django HTTP request
            response: Django HTTP response
            duration: Request duration in seconds
        """
        # Extract request info
        method = request.method
        path = request.path
        status_code = response.status_code
        
        # Extract tenant context if available
        tenant_id = request.META.get('HTTP_X_TENANT_ID')
        
        # Determine log level based on status code
        if status_code >= 500:
            log_level = 'error'
        elif status_code >= 400:
            log_level = 'warning'
        else:
            log_level = 'info'
        
        # Log request completion
        log_method = getattr(self.logger, log_level)
        log_method(
            f"Request completed: {method} {path} - {status_code} in {duration:.3f}s",
            extra={
                'request_id': request.request_id,
                'method': method,
                'path': path,
                'status_code': status_code,
                'duration_ms': round(duration * 1000, 2),
                'tenant_id': tenant_id,
                'event_type': 'request_completion'
            }
        )
    
    def _log_request_exception(self, request: HttpRequest, exception: Exception, duration: float):
        """
        Log request exception with context.
        
        Args:
            request: Django HTTP request
            exception: Exception that occurred
            duration: Request duration in seconds
        """
        # Extract request info
        method = request.method
        path = request.path
        
        # Extract tenant context if available
        tenant_id = request.META.get('HTTP_X_TENANT_ID')
        
        # Log exception
        self.logger.error(
            f"Request failed: {method} {path} - {type(exception).__name__}: {str(exception)}",
            extra={
                'request_id': request.request_id,
                'method': method,
                'path': path,
                'duration_ms': round(duration * 1000, 2),
                'tenant_id': tenant_id,
                'exception_type': type(exception).__name__,
                'exception_message': PIIMasker.mask_text(str(exception)),
                'event_type': 'request_exception'
            },
            exc_info=exception
        )
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """
        Get client IP address from request headers.
        
        Args:
            request: Django HTTP request
            
        Returns:
            Client IP address
        """
        # Check for forwarded IP headers (common in load balancer setups)
        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(',')[0].strip()
        
        # Check for real IP header
        real_ip = request.META.get('HTTP_X_REAL_IP')
        if real_ip:
            return real_ip
        
        # Fall back to remote address
        return request.META.get('REMOTE_ADDR', 'unknown')


class ConversationContextMiddleware(MiddlewareMixin):
    """
    Middleware to extract and track conversation context from webhook requests.
    
    Specifically designed for WhatsApp webhook requests to extract conversation
    and customer context for logging and metrics correlation.
    """
    
    def __init__(self, get_response=None):
        """Initialize conversation context middleware."""
        super().__init__(get_response)
        self.logger = logging.getLogger('apps.bot.conversation_context')
    
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        Process incoming request and extract conversation context.
        
        Args:
            request: Django HTTP request
            
        Returns:
            None to continue processing
        """
        # Only process webhook requests
        if not self._is_webhook_request(request):
            return None
        
        # Extract conversation context from request
        context = self._extract_conversation_context(request)
        
        # Store context on request object
        request.conversation_context = context
        
        # Log conversation context
        if context:
            self._log_conversation_context(request, context)
        
        return None
    
    def _is_webhook_request(self, request: HttpRequest) -> bool:
        """
        Check if request is a webhook request.
        
        Args:
            request: Django HTTP request
            
        Returns:
            True if webhook request
        """
        # Check for webhook paths
        webhook_paths = [
            '/v1/webhooks/twilio',
            '/v1/webhooks/woocommerce',
            '/v1/webhooks/shopify',
            '/v1/bot/webhook',
        ]
        
        return any(request.path.startswith(path) for path in webhook_paths)
    
    def _extract_conversation_context(self, request: HttpRequest) -> Optional[dict]:
        """
        Extract conversation context from webhook request.
        
        Args:
            request: Django HTTP request
            
        Returns:
            Conversation context dictionary or None
        """
        context = {}
        
        # Extract from headers
        context['tenant_id'] = request.META.get('HTTP_X_TENANT_ID')
        context['conversation_id'] = request.META.get('HTTP_X_CONVERSATION_ID')
        context['customer_id'] = request.META.get('HTTP_X_CUSTOMER_ID')
        
        # For Twilio webhooks, extract from POST data
        if request.path.startswith('/v1/webhooks/twilio') and request.method == 'POST':
            # Extract phone number (masked for logging)
            from_number = request.POST.get('From', '')
            if from_number:
                context['phone_e164'] = PIIMasker.mask_phone(from_number)
            
            # Extract message info
            message_body = request.POST.get('Body', '')
            if message_body:
                context['message_length'] = len(message_body)
                context['has_media'] = bool(request.POST.get('NumMedia', '0') != '0')
        
        # Return context only if we have meaningful data
        if any(context.values()):
            return context
        
        return None
    
    def _log_conversation_context(self, request: HttpRequest, context: dict):
        """
        Log conversation context for tracking.
        
        Args:
            request: Django HTTP request
            context: Conversation context dictionary
        """
        self.logger.info(
            f"Conversation context extracted",
            extra={
                'request_id': getattr(request, 'request_id', 'unknown'),
                'event_type': 'conversation_context',
                **context
            }
        )


def get_request_id() -> Optional[str]:
    """
    Get current request ID from thread-local storage.
    
    This function can be used in any part of the application to get
    the current request ID for logging correlation.
    
    Returns:
        Current request ID or None if not available
    """
    # This would require thread-local storage implementation
    # For now, return None - request ID should be passed explicitly
    return None


def add_request_context_to_logger(logger: logging.Logger, request_id: str, 
                                 tenant_id: str = None, conversation_id: str = None):
    """
    Add request context to logger for consistent logging.
    
    Args:
        logger: Logger instance
        request_id: Request ID
        tenant_id: Tenant ID (optional)
        conversation_id: Conversation ID (optional)
    """
    # Create a logger adapter that adds context to all log records
    class RequestContextAdapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            extra = kwargs.get('extra', {})
            extra.update({
                'request_id': request_id,
                'tenant_id': tenant_id,
                'conversation_id': conversation_id,
            })
            kwargs['extra'] = extra
            return msg, kwargs
    
    return RequestContextAdapter(logger, {})