"""
Tests for Redis-based rate limiting on authentication endpoints.

Verifies that:
1. Rate limits are stored in Redis
2. Rate limits work across multiple requests
3. Rate limits reset after the time window
4. Rate limits are enforced correctly
"""
import pytest
from django.test import Client
from django.core.cache import cache
from django_redis import get_redis_connection
from apps.rbac.models import User


@pytest.mark.django_db
class TestRateLimitingRedis:
    """Test Redis-based rate limiting."""
    
    def setup_method(self):
        """Set up test client and clear Redis."""
        self.client = Client()
        # Clear Redis cache before each test
        cache.clear()
    
    def test_redis_connection(self):
        """Test that Redis connection is working."""
        redis_client = get_redis_connection('default')
        
        # Test basic Redis operations
        redis_client.set('test_key', 'test_value')
        value = redis_client.get('test_key')
        
        assert value == b'test_value'
        
        # Clean up
        redis_client.delete('test_key')
    
    def test_rate_limit_stored_in_redis(self):
        """Test that rate limit counters are stored in Redis."""
        redis_client = get_redis_connection('default')
        
        # Make a request to a rate-limited endpoint
        response = self.client.post(
            '/v1/auth/register',
            data={
                'email': 'test@example.com',
                'password': 'TestPass123!',
                'first_name': 'Test',
                'last_name': 'User',
                'business_name': 'Test Business'
            },
            content_type='application/json'
        )
        
        # Check that rate limit keys exist in Redis
        # django-ratelimit uses keys like: "rl:ip:127.0.0.1:register"
        keys = redis_client.keys('rl:*')
        
        # Should have at least one rate limit key
        assert len(keys) > 0, "No rate limit keys found in Redis"
    
    def test_rate_limit_enforced_across_requests(self):
        """Test that rate limits are enforced across multiple requests."""
        # Registration is limited to 3/hour per IP
        # Make 3 successful requests
        for i in range(3):
            response = self.client.post(
                '/v1/auth/register',
                data={
                    'email': f'test{i}@example.com',
                    'password': 'TestPass123!',
                    'first_name': 'Test',
                    'last_name': 'User',
                    'business_name': f'Test Business {i}'
                },
                content_type='application/json'
            )
            
            # Should succeed (201) or fail validation (400), but not rate limited
            assert response.status_code in [201, 400], \
                f"Request {i+1} failed with status {response.status_code}"
        
        # 4th request should be rate limited
        response = self.client.post(
            '/v1/auth/register',
            data={
                'email': 'test4@example.com',
                'password': 'TestPass123!',
                'first_name': 'Test',
                'last_name': 'User',
                'business_name': 'Test Business 4'
            },
            content_type='application/json'
        )
        
        # Should be rate limited
        assert response.status_code == 429, \
            f"Expected 429 (rate limited), got {response.status_code}"
        
        # Check response contains rate limit error
        data = response.json()
        assert 'error' in data
        assert 'rate limit' in data['error'].lower()
    
    def test_login_rate_limit_per_ip(self):
        """Test login rate limit (5/min per IP)."""
        # Create a user first
        user = User.objects.create_user(
            email='test@example.com',
            password='TestPass123!',
            first_name='Test',
            last_name='User'
        )
        
        # Make 5 login attempts (should succeed)
        for i in range(5):
            response = self.client.post(
                '/v1/auth/login',
                data={
                    'email': 'test@example.com',
                    'password': 'WrongPassword'  # Wrong password, but not rate limited yet
                },
                content_type='application/json'
            )
            
            # Should fail auth (401) but not rate limited
            assert response.status_code == 401, \
                f"Request {i+1} failed with status {response.status_code}"
        
        # 6th request should be rate limited
        response = self.client.post(
            '/v1/auth/login',
            data={
                'email': 'test@example.com',
                'password': 'WrongPassword'
            },
            content_type='application/json'
        )
        
        # Should be rate limited
        assert response.status_code == 429, \
            f"Expected 429 (rate limited), got {response.status_code}"
    
    def test_rate_limit_includes_retry_after_header(self):
        """Test that rate limit response includes Retry-After header."""
        # Make requests until rate limited
        for i in range(4):  # Registration limit is 3/hour
            self.client.post(
                '/v1/auth/register',
                data={
                    'email': f'test{i}@example.com',
                    'password': 'TestPass123!',
                    'first_name': 'Test',
                    'last_name': 'User',
                    'business_name': f'Test Business {i}'
                },
                content_type='application/json'
            )
        
        # This should be rate limited
        response = self.client.post(
            '/v1/auth/register',
            data={
                'email': 'test5@example.com',
                'password': 'TestPass123!',
                'first_name': 'Test',
                'last_name': 'User',
                'business_name': 'Test Business 5'
            },
            content_type='application/json'
        )
        
        # Check response status
        assert response.status_code == 429, \
            f"Expected 429 (rate limited), got {response.status_code}"
        
        # Check for Retry-After header
        assert 'Retry-After' in response, \
            "Response should include Retry-After header"
        
        retry_after = response['Retry-After']
        assert retry_after.isdigit(), \
            f"Retry-After should be a number, got '{retry_after}'"
        
        retry_after_seconds = int(retry_after)
        assert retry_after_seconds > 0, \
            f"Retry-After should be positive, got {retry_after_seconds}"
        
        # For registration endpoint, should be 3600 seconds (1 hour)
        assert retry_after_seconds == 3600, \
            f"Expected Retry-After=3600 for registration, got {retry_after_seconds}"
        
        # Check response body includes retry_after
        data = response.json()
        assert 'retry_after' in data, \
            "Response body should include retry_after field"
        assert data['retry_after'] == 3600, \
            f"Expected retry_after=3600 in body, got {data['retry_after']}"
    
    def test_login_rate_limit_includes_retry_after_header(self):
        """Test that login rate limit response includes Retry-After header."""
        # Create a user first
        user = User.objects.create_user(
            email='test@example.com',
            password='TestPass123!',
            first_name='Test',
            last_name='User'
        )
        
        # Make 5 login attempts to hit the rate limit
        for i in range(5):
            self.client.post(
                '/v1/auth/login',
                data={
                    'email': 'test@example.com',
                    'password': 'WrongPassword'
                },
                content_type='application/json'
            )
        
        # 6th request should be rate limited
        response = self.client.post(
            '/v1/auth/login',
            data={
                'email': 'test@example.com',
                'password': 'WrongPassword'
            },
            content_type='application/json'
        )
        
        # Check response status
        assert response.status_code == 429, \
            f"Expected 429 (rate limited), got {response.status_code}"
        
        # Check for Retry-After header
        assert 'Retry-After' in response, \
            "Response should include Retry-After header"
        
        retry_after = response['Retry-After']
        assert retry_after.isdigit(), \
            f"Retry-After should be a number, got '{retry_after}'"
        
        retry_after_seconds = int(retry_after)
        assert retry_after_seconds > 0, \
            f"Retry-After should be positive, got {retry_after_seconds}"
        
        # For login endpoint, should be 60 seconds (1 minute)
        assert retry_after_seconds == 60, \
            f"Expected Retry-After=60 for login, got {retry_after_seconds}"
        
        # Check response body includes retry_after
        data = response.json()
        assert 'retry_after' in data, \
            "Response body should include retry_after field"
        assert data['retry_after'] == 60, \
            f"Expected retry_after=60 in body, got {data['retry_after']}"
    
    def test_redis_cache_configuration(self):
        """Test that Redis cache is properly configured."""
        from django.conf import settings
        
        # Check that Redis is configured as the cache backend
        assert 'default' in settings.CACHES
        cache_config = settings.CACHES['default']
        
        assert 'redis' in cache_config['BACKEND'].lower(), \
            "Redis should be configured as the cache backend"
        
        # Check that rate limiting is configured to use cache
        assert hasattr(settings, 'RATELIMIT_USE_CACHE'), \
            "RATELIMIT_USE_CACHE should be configured"
        
        assert settings.RATELIMIT_USE_CACHE == 'default', \
            "Rate limiting should use the default cache"
    
    def test_rate_limit_keys_expire(self):
        """Test that rate limit keys have expiration set."""
        redis_client = get_redis_connection('default')
        
        # Make a request to create rate limit keys
        self.client.post(
            '/v1/auth/register',
            data={
                'email': 'test@example.com',
                'password': 'TestPass123!',
                'first_name': 'Test',
                'last_name': 'User',
                'business_name': 'Test Business'
            },
            content_type='application/json'
        )
        
        # Get rate limit keys
        keys = redis_client.keys('rl:*')
        
        # Check that keys have TTL set
        for key in keys:
            ttl = redis_client.ttl(key)
            assert ttl > 0, f"Key {key} should have TTL set, got {ttl}"
            assert ttl <= 3600, f"Key {key} TTL should be <= 1 hour, got {ttl}"
