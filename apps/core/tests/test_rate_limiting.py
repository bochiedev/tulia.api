"""
Tests for rate limiting functionality.
"""
import time
from django.test import TestCase, override_settings
from django.core.cache import cache
from apps.core.rate_limiting import RateLimiter, RateLimitExceeded


class RateLimiterTestCase(TestCase):
    """Test rate limiting functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Clear Redis cache before each test
        cache.clear()
        self.tenant_id = 'test-tenant-123'
    
    def tearDown(self):
        """Clean up after tests."""
        cache.clear()
    
    def test_check_rate_limit_allows_within_limit(self):
        """Test that requests within limit are allowed."""
        # Check rate limit (should be allowed)
        is_allowed, retry_after = RateLimiter.check_rate_limit(
            self.tenant_id,
            limit_type='api',
            custom_limit=10
        )
        
        self.assertTrue(is_allowed)
        self.assertEqual(retry_after, 0)
    
    def test_check_rate_limit_blocks_over_limit(self):
        """Test that requests over limit are blocked."""
        # Make requests up to limit
        for i in range(10):
            RateLimiter.increment(self.tenant_id, 'api')
        
        # Next request should be blocked
        is_allowed, retry_after = RateLimiter.check_rate_limit(
            self.tenant_id,
            limit_type='api',
            custom_limit=10
        )
        
        self.assertFalse(is_allowed)
        self.assertGreater(retry_after, 0)
    
    def test_increment_increases_count(self):
        """Test that increment increases request count."""
        # Get initial status
        status = RateLimiter.get_status(self.tenant_id, 'api')
        initial_count = status['current']
        
        # Increment
        RateLimiter.increment(self.tenant_id, 'api')
        
        # Check count increased
        status = RateLimiter.get_status(self.tenant_id, 'api')
        self.assertEqual(status['current'], initial_count + 1)
    
    def test_get_status_returns_correct_info(self):
        """Test that get_status returns correct rate limit info."""
        # Make some requests
        for i in range(5):
            RateLimiter.increment(self.tenant_id, 'api')
        
        # Get status
        status = RateLimiter.get_status(self.tenant_id, 'api')
        
        # Verify status
        self.assertEqual(status['current'], 5)
        self.assertGreater(status['limit'], 0)
        self.assertEqual(status['remaining'], status['limit'] - 5)
        self.assertGreater(status['reset_at'], time.time())
    
    def test_separate_limits_for_api_and_webhook(self):
        """Test that API and webhook have separate rate limits."""
        # Increment API requests
        for i in range(5):
            RateLimiter.increment(self.tenant_id, 'api')
        
        # Increment webhook requests
        for i in range(3):
            RateLimiter.increment(self.tenant_id, 'webhook')
        
        # Check separate counts
        api_status = RateLimiter.get_status(self.tenant_id, 'api')
        webhook_status = RateLimiter.get_status(self.tenant_id, 'webhook')
        
        self.assertEqual(api_status['current'], 5)
        self.assertEqual(webhook_status['current'], 3)
    
    def test_different_tenants_have_separate_limits(self):
        """Test that different tenants have separate rate limits."""
        tenant1 = 'tenant-1'
        tenant2 = 'tenant-2'
        
        # Increment for tenant 1
        for i in range(5):
            RateLimiter.increment(tenant1, 'api')
        
        # Increment for tenant 2
        for i in range(3):
            RateLimiter.increment(tenant2, 'api')
        
        # Check separate counts
        status1 = RateLimiter.get_status(tenant1, 'api')
        status2 = RateLimiter.get_status(tenant2, 'api')
        
        self.assertEqual(status1['current'], 5)
        self.assertEqual(status2['current'], 3)
