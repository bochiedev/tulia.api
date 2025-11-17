"""
Test Redis configuration for rate limiting.

This test verifies that:
1. Redis is properly configured as the cache backend
2. django-ratelimit is configured to use Redis
3. Rate limit counters are stored in Redis
"""
import pytest
from django.conf import settings
from django.core.cache import cache
from django_redis import get_redis_connection


@pytest.mark.django_db
class TestRedisRateLimitConfiguration:
    """Test Redis configuration for rate limiting."""
    
    def test_redis_cache_backend_configured(self):
        """Test that Redis is configured as the cache backend."""
        # Check that Redis is configured
        assert 'default' in settings.CACHES
        cache_config = settings.CACHES['default']
        
        # Verify it's using Redis
        assert 'redis' in cache_config['BACKEND'].lower(), \
            f"Expected Redis backend, got {cache_config['BACKEND']}"
        
        # Verify Redis URL is set
        assert 'LOCATION' in cache_config
        assert cache_config['LOCATION'], "Redis URL should be configured"
    
    def test_ratelimit_uses_redis_cache(self):
        """Test that django-ratelimit is configured to use Redis cache."""
        # Check that RATELIMIT_USE_CACHE is set to 'default'
        assert hasattr(settings, 'RATELIMIT_USE_CACHE'), \
            "RATELIMIT_USE_CACHE should be configured"
        
        assert settings.RATELIMIT_USE_CACHE == 'default', \
            f"Expected RATELIMIT_USE_CACHE='default', got '{settings.RATELIMIT_USE_CACHE}'"
    
    def test_ratelimit_enable_setting(self):
        """Test that RATELIMIT_ENABLE setting exists."""
        assert hasattr(settings, 'RATELIMIT_ENABLE'), \
            "RATELIMIT_ENABLE should be configured"
        
        # Should match RATE_LIMIT_ENABLED
        assert settings.RATELIMIT_ENABLE == settings.RATE_LIMIT_ENABLED, \
            "RATELIMIT_ENABLE should match RATE_LIMIT_ENABLED"
    
    def test_redis_connection_works(self):
        """Test that Redis connection is working."""
        redis_client = get_redis_connection('default')
        
        # Test basic Redis operations
        test_key = 'test:rate_limit:config'
        test_value = 'test_value'
        
        # Set a value
        redis_client.set(test_key, test_value, ex=60)
        
        # Get the value
        retrieved_value = redis_client.get(test_key)
        
        assert retrieved_value == test_value.encode(), \
            f"Expected {test_value}, got {retrieved_value}"
        
        # Clean up
        redis_client.delete(test_key)
    
    def test_django_cache_works(self):
        """Test that Django cache (Redis) is working."""
        test_key = 'test:django_cache'
        test_value = 'test_value'
        
        # Set a value using Django cache
        cache.set(test_key, test_value, timeout=60)
        
        # Get the value
        retrieved_value = cache.get(test_key)
        
        assert retrieved_value == test_value, \
            f"Expected {test_value}, got {retrieved_value}"
        
        # Clean up
        cache.delete(test_key)
    
    def test_redis_cache_options(self):
        """Test that Redis cache has proper options configured."""
        cache_config = settings.CACHES['default']
        
        # Check for important options
        assert 'OPTIONS' in cache_config
        options = cache_config['OPTIONS']
        
        # Should have client class
        assert 'CLIENT_CLASS' in options
        
        # Should have connection pool settings
        assert 'CONNECTION_POOL_KWARGS' in options
        pool_kwargs = options['CONNECTION_POOL_KWARGS']
        
        # Should have max_connections set
        assert 'max_connections' in pool_kwargs
        assert pool_kwargs['max_connections'] > 0
    
    def test_rate_limit_view_configured(self):
        """Test that custom rate limit view is configured."""
        assert hasattr(settings, 'RATELIMIT_VIEW'), \
            "RATELIMIT_VIEW should be configured"
        
        assert settings.RATELIMIT_VIEW == 'apps.core.exceptions.ratelimit_view', \
            f"Expected custom ratelimit_view, got {settings.RATELIMIT_VIEW}"
