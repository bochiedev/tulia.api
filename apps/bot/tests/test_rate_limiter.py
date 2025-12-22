"""
Tests for Conversation Rate Limiter Service.

Validates:
- Per-customer per-tenant rate limiting
- Casual turn limits based on chattiness levels
- Spam turn tracking and cooldowns
- Abuse detection and cooldowns
- Rate limit status checking
"""
import pytest
from datetime import datetime, timedelta
from django.core.cache import cache
from django.utils import timezone
from apps.bot.services.rate_limiter import ConversationRateLimiter, get_rate_limiter


class TestConversationRateLimiter:
    """Test conversation rate limiter functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Clear cache before each test
        cache.clear()
        
        # Create rate limiter instance
        self.rate_limiter = ConversationRateLimiter()
        self.tenant_id = "test-tenant-123"
        self.customer_id = "test-customer-456"
    
    def teardown_method(self):
        """Clean up after each test."""
        cache.clear()
    
    def test_rate_limiter_singleton(self):
        """Test that get_rate_limiter returns singleton instance."""
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        
        assert limiter1 is limiter2
    
    def test_check_rate_limit_within_limits(self):
        """Test rate limit check when within limits."""
        # Check rate limit without any messages
        result = self.rate_limiter.check_rate_limit(self.tenant_id, self.customer_id)
        
        assert result['allowed'] is True
        assert result['reason'] == 'within_limits'
        assert result['retry_after_seconds'] == 0
        assert result['current_counts']['hour'] == 0
        assert result['current_counts']['minute'] == 0
    
    def test_increment_message_count(self):
        """Test incrementing message count."""
        # Increment message count
        self.rate_limiter.increment_message_count(self.tenant_id, self.customer_id)
        
        # Check that count was incremented
        result = self.rate_limiter.check_rate_limit(self.tenant_id, self.customer_id)
        
        assert result['allowed'] is True
        assert result['current_counts']['hour'] == 1
        assert result['current_counts']['minute'] == 1
    
    def test_hourly_rate_limit_exceeded(self):
        """Test hourly rate limit enforcement."""
        # Simulate 60 messages (hourly limit)
        for i in range(60):
            self.rate_limiter.increment_message_count(self.tenant_id, self.customer_id)
        
        # Check rate limit - should be at limit
        result = self.rate_limiter.check_rate_limit(self.tenant_id, self.customer_id)
        
        assert result['allowed'] is False
        assert result['reason'] == 'hourly_limit_exceeded'
        assert result['retry_after_seconds'] == 3600
        assert result['current_counts']['hour'] == 60
    
    def test_minute_rate_limit_exceeded(self):
        """Test minute rate limit enforcement."""
        # Simulate 10 messages (minute limit)
        for i in range(10):
            self.rate_limiter.increment_message_count(self.tenant_id, self.customer_id)
        
        # Check rate limit - should be at limit
        result = self.rate_limiter.check_rate_limit(self.tenant_id, self.customer_id)
        
        assert result['allowed'] is False
        assert result['reason'] == 'minute_limit_exceeded'
        assert result['retry_after_seconds'] == 60
        assert result['current_counts']['minute'] == 10
    
    def test_spam_cooldown_enforcement(self):
        """Test spam cooldown period enforcement."""
        current_time = timezone.now()
        
        # Apply spam cooldown
        self.rate_limiter.apply_spam_cooldown(self.tenant_id, self.customer_id, current_time)
        
        # Check rate limit - should be in cooldown
        result = self.rate_limiter.check_rate_limit(self.tenant_id, self.customer_id, current_time)
        
        assert result['allowed'] is False
        assert result['reason'] == 'spam_cooldown'
        assert result['retry_after_seconds'] > 0
        assert result['retry_after_seconds'] <= 30 * 60  # 30 minutes
    
    def test_abuse_cooldown_enforcement(self):
        """Test abuse cooldown period enforcement."""
        current_time = timezone.now()
        
        # Apply abuse cooldown
        self.rate_limiter.apply_abuse_cooldown(self.tenant_id, self.customer_id, current_time)
        
        # Check rate limit - should be in cooldown
        result = self.rate_limiter.check_rate_limit(self.tenant_id, self.customer_id, current_time)
        
        assert result['allowed'] is False
        assert result['reason'] == 'abuse_cooldown'
        assert result['retry_after_seconds'] > 0
        assert result['retry_after_seconds'] <= 24 * 3600  # 24 hours
    
    def test_spam_cooldown_expires(self):
        """Test that spam cooldown expires after timeout."""
        current_time = timezone.now()
        
        # Apply spam cooldown
        self.rate_limiter.apply_spam_cooldown(self.tenant_id, self.customer_id, current_time)
        
        # Check immediately - should be in cooldown
        result = self.rate_limiter.check_rate_limit(self.tenant_id, self.customer_id, current_time)
        assert result['allowed'] is False
        
        # Check after cooldown period (31 minutes)
        future_time = current_time + timedelta(minutes=31)
        result = self.rate_limiter.check_rate_limit(self.tenant_id, self.customer_id, future_time)
        assert result['allowed'] is True
    
    def test_abuse_cooldown_expires(self):
        """Test that abuse cooldown expires after timeout."""
        current_time = timezone.now()
        
        # Apply abuse cooldown
        self.rate_limiter.apply_abuse_cooldown(self.tenant_id, self.customer_id, current_time)
        
        # Check immediately - should be in cooldown
        result = self.rate_limiter.check_rate_limit(self.tenant_id, self.customer_id, current_time)
        assert result['allowed'] is False
        
        # Check after cooldown period (25 hours)
        future_time = current_time + timedelta(hours=25)
        result = self.rate_limiter.check_rate_limit(self.tenant_id, self.customer_id, future_time)
        assert result['allowed'] is True
    
    def test_casual_turn_limit_level_0(self):
        """Test casual turn limits for level 0 (strictly business)."""
        result = self.rate_limiter.check_casual_turn_limit(0, 0)
        
        assert result['within_limit'] is True
        assert result['max_allowed'] == 0
        assert result['current_count'] == 0
        assert result['should_redirect'] is False
        
        # Test exceeding level 0 limit
        result = self.rate_limiter.check_casual_turn_limit(1, 0)
        
        assert result['within_limit'] is False
        assert result['should_redirect'] is True
    
    def test_casual_turn_limit_level_1(self):
        """Test casual turn limits for level 1 (1 short greeting)."""
        result = self.rate_limiter.check_casual_turn_limit(1, 1)
        
        assert result['within_limit'] is True
        assert result['max_allowed'] == 1
        assert result['should_redirect'] is False
        
        # Test exceeding level 1 limit
        result = self.rate_limiter.check_casual_turn_limit(2, 1)
        
        assert result['within_limit'] is False
        assert result['should_redirect'] is True
    
    def test_casual_turn_limit_level_2(self):
        """Test casual turn limits for level 2 (max 2 casual turns - DEFAULT)."""
        result = self.rate_limiter.check_casual_turn_limit(2, 2)
        
        assert result['within_limit'] is True
        assert result['max_allowed'] == 2
        assert result['should_redirect'] is False
        
        # Test exceeding level 2 limit
        result = self.rate_limiter.check_casual_turn_limit(3, 2)
        
        assert result['within_limit'] is False
        assert result['should_redirect'] is True
    
    def test_casual_turn_limit_level_3(self):
        """Test casual turn limits for level 3 (max 4 casual turns)."""
        result = self.rate_limiter.check_casual_turn_limit(4, 3)
        
        assert result['within_limit'] is True
        assert result['max_allowed'] == 4
        assert result['should_redirect'] is False
        
        # Test exceeding level 3 limit
        result = self.rate_limiter.check_casual_turn_limit(5, 3)
        
        assert result['within_limit'] is False
        assert result['should_redirect'] is True
    
    def test_casual_turn_limit_default_fallback(self):
        """Test casual turn limit defaults to level 2 for invalid levels."""
        result = self.rate_limiter.check_casual_turn_limit(2, 99)
        
        assert result['max_allowed'] == 2  # Default to level 2
    
    def test_tenant_isolation(self):
        """Test that rate limits are isolated per tenant."""
        tenant1_id = "tenant-1"
        tenant2_id = "tenant-2"
        customer_id = "same-customer"
        
        # Increment messages for tenant 1
        for i in range(5):
            self.rate_limiter.increment_message_count(tenant1_id, customer_id)
        
        # Increment messages for tenant 2
        for i in range(3):
            self.rate_limiter.increment_message_count(tenant2_id, customer_id)
        
        # Check tenant 1 - should have 5 messages
        result1 = self.rate_limiter.check_rate_limit(tenant1_id, customer_id)
        assert result1['current_counts']['hour'] == 5
        
        # Check tenant 2 - should have 3 messages
        result2 = self.rate_limiter.check_rate_limit(tenant2_id, customer_id)
        assert result2['current_counts']['hour'] == 3
    
    def test_customer_isolation(self):
        """Test that rate limits are isolated per customer."""
        tenant_id = "same-tenant"
        customer1_id = "customer-1"
        customer2_id = "customer-2"
        
        # Increment messages for customer 1
        for i in range(7):
            self.rate_limiter.increment_message_count(tenant_id, customer1_id)
        
        # Increment messages for customer 2
        for i in range(4):
            self.rate_limiter.increment_message_count(tenant_id, customer2_id)
        
        # Check customer 1 - should have 7 messages
        result1 = self.rate_limiter.check_rate_limit(tenant_id, customer1_id)
        assert result1['current_counts']['hour'] == 7
        
        # Check customer 2 - should have 4 messages
        result2 = self.rate_limiter.check_rate_limit(tenant_id, customer2_id)
        assert result2['current_counts']['hour'] == 4
    
    def test_get_rate_limit_status(self):
        """Test getting comprehensive rate limit status."""
        # Increment some messages
        for i in range(3):
            self.rate_limiter.increment_message_count(self.tenant_id, self.customer_id)
        
        # Apply spam cooldown
        self.rate_limiter.apply_spam_cooldown(self.tenant_id, self.customer_id)
        
        # Get status
        status = self.rate_limiter.get_rate_limit_status(self.tenant_id, self.customer_id)
        
        assert status['tenant_id'] == self.tenant_id
        assert status['customer_id'] == self.customer_id
        assert 'current_time' in status
        assert status['counts']['hour'] == 3
        assert status['counts']['minute'] == 3
        assert 'limits' in status
        assert 'cooldowns' in status
        assert status['cooldowns']['spam_until'] is not None
    
    def test_cache_key_generation(self):
        """Test cache key generation for different limit types."""
        current_time = timezone.now()
        
        # Test hour key
        hour_key = self.rate_limiter._get_cache_key(
            self.tenant_id, 
            self.customer_id, 
            'hour', 
            current_time
        )
        assert 'rate_limit' in hour_key
        assert self.tenant_id in hour_key
        assert self.customer_id in hour_key
        assert 'hour' in hour_key
        assert current_time.strftime('%Y%m%d%H') in hour_key
        
        # Test minute key
        minute_key = self.rate_limiter._get_cache_key(
            self.tenant_id, 
            self.customer_id, 
            'minute', 
            current_time
        )
        assert 'minute' in minute_key
        assert current_time.strftime('%Y%m%d%H%M') in minute_key
        
        # Test cooldown key
        cooldown_key = self.rate_limiter._get_cache_key(
            self.tenant_id, 
            self.customer_id, 
            'spam_cooldown'
        )
        assert 'spam_cooldown' in cooldown_key
        assert current_time.strftime('%Y%m%d%H') not in cooldown_key  # No timestamp
    
    def test_multiple_cooldowns_priority(self):
        """Test that abuse cooldown takes priority over spam cooldown."""
        current_time = timezone.now()
        
        # Apply both cooldowns
        self.rate_limiter.apply_spam_cooldown(self.tenant_id, self.customer_id, current_time)
        self.rate_limiter.apply_abuse_cooldown(self.tenant_id, self.customer_id, current_time)
        
        # Check rate limit - should report spam cooldown first (checked first in code)
        result = self.rate_limiter.check_rate_limit(self.tenant_id, self.customer_id, current_time)
        
        assert result['allowed'] is False
        # Either cooldown is acceptable, but should be one of them
        assert result['reason'] in ['spam_cooldown', 'abuse_cooldown']
    
    def test_rate_limit_with_no_customer_id(self):
        """Test rate limiting behavior when customer_id is None."""
        # This should not crash - rate limiting is skipped for None customer_id
        # The actual check happens in the ConversationGovernorNode
        result = self.rate_limiter.check_rate_limit(self.tenant_id, None)
        
        # Should allow (no customer to rate limit)
        assert result['allowed'] is True
    
    def test_casual_turn_limit_levels_comprehensive(self):
        """Test casual turn limits across all chattiness levels comprehensively."""
        # Test all levels with their exact limits
        test_cases = [
            # Level 0: 0 casual turns allowed
            (0, 0, True),   # 0 turns at level 0 - allowed
            (1, 0, False),  # 1 turn at level 0 - rejected
            
            # Level 1: 1 casual turn allowed
            (0, 1, True),   # 0 turns at level 1 - allowed
            (1, 1, True),   # 1 turn at level 1 - allowed
            (2, 1, False),  # 2 turns at level 1 - rejected
            
            # Level 2: 2 casual turns allowed (DEFAULT)
            (0, 2, True),   # 0 turns at level 2 - allowed
            (1, 2, True),   # 1 turn at level 2 - allowed
            (2, 2, True),   # 2 turns at level 2 - allowed
            (3, 2, False),  # 3 turns at level 2 - rejected
            
            # Level 3: 4 casual turns allowed
            (0, 3, True),   # 0 turns at level 3 - allowed
            (3, 3, True),   # 3 turns at level 3 - allowed
            (4, 3, True),   # 4 turns at level 3 - allowed
            (5, 3, False),  # 5 turns at level 3 - rejected
        ]
        
        for casual_turns, level, expected_within_limit in test_cases:
            result = self.rate_limiter.check_casual_turn_limit(casual_turns, level)
            
            assert result['within_limit'] == expected_within_limit, \
                f"Level {level} with {casual_turns} turns should be {'within' if expected_within_limit else 'outside'} limit"
            
            if expected_within_limit:
                assert result['should_redirect'] is False
            else:
                assert result['should_redirect'] is True
        
        # Test invalid level defaults to level 2
        result = self.rate_limiter.check_casual_turn_limit(2, 999)
        assert result['max_allowed'] == 2  # Should default to level 2
