"""
CORS validation middleware for tenant-specific origin control.

Validates Origin header against tenant.allowed_origins to ensure
only authorized domains can make cross-origin requests.
"""
import logging
import re
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class TenantCORSMiddleware(MiddlewareMixin):
    """
    Validate CORS requests against tenant-specific allowed origins.
    
    This middleware:
    1. Checks Origin header against tenant.allowed_origins
    2. Supports wildcard patterns for development
    3. Applies strict mode for production
    4. Returns 403 for unauthorized origins
    """
    
    # Paths that bypass CORS validation
    BYPASS_PATHS = [
        '/v1/webhooks/',  # Webhooks don't use CORS
        '/v1/health',     # Health check is public
        '/admin/',        # Admin uses Django's CSRF
    ]
    
    def process_request(self, request):
        """
        Validate Origin header against tenant allowed origins.
        
        Only applies to requests with Origin header (CORS requests).
        """
        # Skip if no Origin header (not a CORS request)
        origin = request.headers.get('Origin')
        if not origin:
            return None
        
        # Skip for bypass paths
        if self._is_bypass_path(request.path):
            return None
        
        # Skip if tenant not resolved yet
        if not hasattr(request, 'tenant') or request.tenant is None:
            return None
        
        tenant = request.tenant
        
        # Check if origin is allowed
        if not self._is_origin_allowed(origin, tenant):
            logger.warning(
                f"CORS request blocked for tenant {tenant.slug}: "
                f"origin {origin} not in allowed_origins",
                extra={
                    'tenant_id': str(tenant.id),
                    'origin': origin,
                    'request_id': getattr(request, 'request_id', None),
                }
            )
            
            return JsonResponse(
                {
                    'error': {
                        'code': 'CORS_ORIGIN_NOT_ALLOWED',
                        'message': f'Origin {origin} is not allowed for this tenant.',
                    }
                },
                status=403
            )
        
        # Origin is allowed - continue processing
        return None
    
    def process_response(self, request, response):
        """
        Add CORS headers to response if origin is allowed.
        
        Only adds headers for CORS requests with allowed origins.
        """
        # Skip if no Origin header
        origin = request.headers.get('Origin')
        if not origin:
            return response
        
        # Skip for bypass paths
        if self._is_bypass_path(request.path):
            return response
        
        # Skip if tenant not resolved
        if not hasattr(request, 'tenant') or request.tenant is None:
            return response
        
        tenant = request.tenant
        
        # Check if origin is allowed
        if self._is_origin_allowed(origin, tenant):
            # Add CORS headers
            response['Access-Control-Allow-Origin'] = origin
            response['Access-Control-Allow-Credentials'] = 'true'
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
            response['Access-Control-Allow-Headers'] = (
                'Accept, Accept-Language, Content-Type, Authorization, '
                'X-TENANT-ID, X-TENANT-API-KEY, X-Request-ID'
            )
            response['Access-Control-Max-Age'] = '86400'  # 24 hours
        
        return response
    
    def _is_bypass_path(self, path):
        """Check if path bypasses CORS validation."""
        return any(path.startswith(bypass_path) for bypass_path in self.BYPASS_PATHS)
    
    def _is_origin_allowed(self, origin, tenant):
        """
        Check if origin is allowed for tenant.
        
        Supports:
        - Exact match: https://example.com
        - Wildcard subdomain: https://*.example.com
        - Wildcard for development: *
        
        Args:
            origin: Origin header value
            tenant: Tenant object
            
        Returns:
            True if origin is allowed, False otherwise
        """
        # Get allowed origins from tenant
        allowed_origins = tenant.allowed_origins or []
        
        # If no origins configured, deny all
        if not allowed_origins:
            return False
        
        # Check for wildcard (allow all - development only)
        if '*' in allowed_origins:
            logger.debug(
                f"CORS wildcard enabled for tenant {tenant.slug} - "
                f"allowing origin {origin}"
            )
            return True
        
        # Check for exact match
        if origin in allowed_origins:
            return True
        
        # Check for wildcard subdomain patterns
        for allowed_origin in allowed_origins:
            if '*' in allowed_origin:
                # Convert wildcard pattern to regex
                pattern = self._wildcard_to_regex(allowed_origin)
                if re.match(pattern, origin):
                    logger.debug(
                        f"CORS origin {origin} matched wildcard pattern "
                        f"{allowed_origin} for tenant {tenant.slug}"
                    )
                    return True
        
        return False
    
    def _wildcard_to_regex(self, pattern):
        """
        Convert wildcard pattern to regex.
        
        Examples:
        - https://*.example.com -> ^https://[^/]+\.example\.com$
        - http://*.localhost:* -> ^http://[^/]+\.localhost:[0-9]+$
        
        Args:
            pattern: Wildcard pattern
            
        Returns:
            Regex pattern string
        """
        # Escape special regex characters except *
        escaped = re.escape(pattern)
        
        # Replace escaped \* with regex pattern
        # For subdomain: match any characters except /
        regex = escaped.replace(r'\*', r'[^/]+')
        
        # Add anchors
        regex = f'^{regex}$'
        
        return regex
