"""
Rate limiting utilities for API requests.

Implements Redis-based rate limiting using sliding window algorithm
to prevent abuse and ensure fair resource usage across tenants.
"""
import logging
import time
from typing import Optional, Tuple
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, message: str, retry_after: int):
        """
        Initialize exception.
        
        Args:
            message: Error message
            retry_after: Seconds until rate limit resets
        """
        super().__init__(message)
        self.retry_after = retry_after


class RateLimiter:
    """
    Redis-based rate limiter using sliding window algorithm.
    
    Tracks requests per tenant per time window and enforces limits
    based on subscription tier or custom configuration.
    """
    
    # Default rate limits (requests per hour)
    DEFAULT_LIMITS = {
        'api': 1000,  # API requests per hour
        'webhook': 10000,  # Webhook calls per hour
    }
    
    # Rate limit window (1 hour in seconds)
    WINDOW_SIZE = 3600
    
    # Redis key prefixes
    API_RATE_LIMIT_PREFIX = 'rate_limit:api:tenant:'
    WEBHOOK_RATE_LIMIT_PREFIX = 'rate_limit:webhook:tenant:'
    
    @staticmethod
    def check_rate_limit(
        tenant_id: str,
        limit_type: str = 'api',
        custom_limit: Optional[int] = None
    ) -> Tuple[bool, int]:
        """
        Check if request is within rate limit.
        
        Args:
            tenant_id: Tenant UUID
            limit_type: Type of limit ('api' or 'webhook')
            custom_limit: Optional custom limit override
            
        Returns:
            Tuple of (is_allowed, retry_after_seconds)
            - is_allowed: True if request is within limit
            - retry_after_seconds: Seconds until limit resets (0 if allowed)
        """
        # Get limit for this tenant
        limit = custom_limit or RateLimiter._get_limit(tenant_id, limit_type)
        
        # Get Redis key
        key = RateLimiter._get_key(tenant_id, limit_type)
        
        # Get current count
        current_count = RateLimiter._get_count(key)
        
        # Check if limit exceeded
        if current_count >= limit:
            # Calculate retry_after (time until oldest request expires)
            retry_after = RateLimiter._get_retry_after(key)
            logger.warning(
                f"Rate limit exceeded for tenant {tenant_id} ({limit_type}): "
                f"{current_count}/{limit} requests. Retry after {retry_after}s"
            )
            return False, retry_after
        
        return True, 0
    
    @staticmethod
    def increment(tenant_id: str, limit_type: str = 'api') -> None:
        """
        Increment rate limit counter for tenant.
        
        Args:
            tenant_id: Tenant UUID
            limit_type: Type of limit ('api' or 'webhook')
        """
        key = RateLimiter._get_key(tenant_id, limit_type)
        current_time = time.time()
        
        # Get Redis client
        from django_redis import get_redis_connection
        redis_client = get_redis_connection('default')
        
        # Add current timestamp to sorted set
        redis_client.zadd(key, {str(current_time): current_time})
        
        # Remove old entries outside the window
        window_start = current_time - RateLimiter.WINDOW_SIZE
        redis_client.zremrangebyscore(key, '-inf', window_start)
        
        # Set expiry on key (window size + buffer)
        redis_client.expire(key, RateLimiter.WINDOW_SIZE + 60)
        
        logger.debug(
            f"Incremented rate limit for tenant {tenant_id} ({limit_type})"
        )
    
    @staticmethod
    def get_status(tenant_id: str, limit_type: str = 'api') -> dict:
        """
        Get current rate limit status for tenant.
        
        Args:
            tenant_id: Tenant UUID
            limit_type: Type of limit ('api' or 'webhook')
            
        Returns:
            Dict with:
            - limit: Maximum requests allowed
            - current: Current request count
            - remaining: Remaining requests
            - reset_at: Unix timestamp when limit resets
        """
        limit = RateLimiter._get_limit(tenant_id, limit_type)
        key = RateLimiter._get_key(tenant_id, limit_type)
        current_count = RateLimiter._get_count(key)
        remaining = max(0, limit - current_count)
        
        # Calculate reset time (oldest request + window size)
        reset_at = RateLimiter._get_reset_time(key)
        
        return {
            'limit': limit,
            'current': current_count,
            'remaining': remaining,
            'reset_at': reset_at,
            'window_size': RateLimiter.WINDOW_SIZE,
        }
    
    @staticmethod
    def _get_key(tenant_id: str, limit_type: str) -> str:
        """Get Redis key for rate limit."""
        if limit_type == 'api':
            return f"{RateLimiter.API_RATE_LIMIT_PREFIX}{tenant_id}"
        elif limit_type == 'webhook':
            return f"{RateLimiter.WEBHOOK_RATE_LIMIT_PREFIX}{tenant_id}"
        else:
            raise ValueError(f"Invalid limit_type: {limit_type}")
    
    @staticmethod
    def _get_limit(tenant_id: str, limit_type: str) -> int:
        """
        Get rate limit for tenant.
        
        Can be customized based on subscription tier in the future.
        For now, uses default limits.
        """
        # TODO: Fetch from tenant's subscription tier
        # For now, use default limits
        return RateLimiter.DEFAULT_LIMITS.get(limit_type, 1000)
    
    @staticmethod
    def _get_count(key: str) -> int:
        """Get current request count from Redis."""
        current_time = time.time()
        window_start = current_time - RateLimiter.WINDOW_SIZE
        
        # Count entries in the current window
        try:
            from django_redis import get_redis_connection
            redis_client = get_redis_connection('default')
            count = redis_client.zcount(key, window_start, current_time)
            return count
        except Exception as e:
            logger.error(f"Error getting rate limit count: {e}")
            # On error, allow request (fail open)
            return 0
    
    @staticmethod
    def _get_retry_after(key: str) -> int:
        """Calculate seconds until rate limit resets."""
        current_time = time.time()
        
        try:
            from django_redis import get_redis_connection
            redis_client = get_redis_connection('default')
            
            # Get oldest entry in the window
            oldest_entries = redis_client.zrange(key, 0, 0, withscores=True)
            
            if oldest_entries:
                oldest_timestamp = oldest_entries[0][1]
                # Time until oldest entry expires
                retry_after = int(oldest_timestamp + RateLimiter.WINDOW_SIZE - current_time)
                return max(1, retry_after)  # At least 1 second
            
            return 60  # Default to 1 minute if can't determine
        except Exception as e:
            logger.error(f"Error calculating retry_after: {e}")
            return 60
    
    @staticmethod
    def _get_reset_time(key: str) -> int:
        """Get Unix timestamp when rate limit resets."""
        current_time = time.time()
        
        try:
            from django_redis import get_redis_connection
            redis_client = get_redis_connection('default')
            
            # Get oldest entry in the window
            oldest_entries = redis_client.zrange(key, 0, 0, withscores=True)
            
            if oldest_entries:
                oldest_timestamp = oldest_entries[0][1]
                reset_time = int(oldest_timestamp + RateLimiter.WINDOW_SIZE)
                return reset_time
            
            # No entries, resets immediately
            return int(current_time)
        except Exception as e:
            logger.error(f"Error calculating reset_time: {e}")
            return int(current_time + 60)


class RateLimitMiddleware:
    """
    Middleware to enforce rate limiting on API requests.
    
    Applies per-tenant rate limits and returns 429 responses
    when limits are exceeded.
    """
    
    def __init__(self, get_response):
        """Initialize middleware."""
        self.get_response = get_response
    
    def __call__(self, request):
        """Process request with rate limiting."""
        # Skip rate limiting for public paths
        if self._is_public_path(request.path):
            return self.get_response(request)
        
        # Skip if tenant not resolved
        if not hasattr(request, 'tenant') or request.tenant is None:
            return self.get_response(request)
        
        tenant_id = str(request.tenant.id)
        
        # Determine limit type based on path
        limit_type = 'webhook' if self._is_webhook_path(request.path) else 'api'
        
        # Check rate limit
        is_allowed, retry_after = RateLimiter.check_rate_limit(tenant_id, limit_type)
        
        if not is_allowed:
            # Rate limit exceeded
            from django.http import JsonResponse
            
            response = JsonResponse(
                {
                    'error': {
                        'code': 'RATE_LIMIT_EXCEEDED',
                        'message': f'Rate limit exceeded. Please try again in {retry_after} seconds.',
                        'retry_after': retry_after,
                    }
                },
                status=429
            )
            response['Retry-After'] = str(retry_after)
            
            # Log rate limit event
            logger.warning(
                f"Rate limit exceeded for tenant {request.tenant.slug}: "
                f"{limit_type} requests",
                extra={
                    'tenant_id': tenant_id,
                    'request_id': getattr(request, 'request_id', None),
                    'path': request.path,
                    'method': request.method,
                }
            )
            
            return response
        
        # Increment counter
        RateLimiter.increment(tenant_id, limit_type)
        
        # Add rate limit headers to response
        response = self.get_response(request)
        
        # Get current status
        status = RateLimiter.get_status(tenant_id, limit_type)
        response['X-RateLimit-Limit'] = str(status['limit'])
        response['X-RateLimit-Remaining'] = str(status['remaining'])
        response['X-RateLimit-Reset'] = str(status['reset_at'])
        
        return response
    
    def _is_public_path(self, path):
        """Check if path is public and doesn't require rate limiting."""
        public_paths = [
            '/v1/health',
            '/schema',
            '/admin/',
        ]
        return any(path.startswith(public_path) for public_path in public_paths)
    
    def _is_webhook_path(self, path):
        """Check if path is a webhook endpoint."""
        webhook_paths = [
            '/v1/webhooks/',
        ]
        return any(path.startswith(webhook_path) for webhook_path in webhook_paths)
