"""
Rate Limiting Service for Conversation Governance.

Implements per-customer per-tenant rate limiting to prevent abuse
and control conversation costs as specified in the design.
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class ConversationRateLimiter:
    """
    Rate limiter for conversation governance.
    
    Implements per-customer per-tenant rate limiting with:
    - Message count limits per time window
    - Casual turn limits based on chattiness level
    - Spam turn tracking and limits
    - Cooldown periods for abuse
    """
    
    def __init__(self):
        """Initialize rate limiter."""
        # Default rate limits (can be overridden by tenant configuration)
        self.default_limits = {
            'messages_per_hour': 60,      # Max messages per hour per customer
            'messages_per_minute': 10,    # Max messages per minute per customer
            'spam_cooldown_minutes': 30,  # Cooldown after spam detection
            'abuse_cooldown_hours': 24,   # Cooldown after abuse detection
        }
    
    def check_rate_limit(
        self, 
        tenant_id: str, 
        customer_id: str, 
        current_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Check if customer is within rate limits.
        
        Args:
            tenant_id: Tenant identifier
            customer_id: Customer identifier
            current_time: Current timestamp (defaults to now)
            
        Returns:
            Dict with rate limit status:
            {
                'allowed': bool,
                'reason': str,
                'retry_after_seconds': int,
                'current_counts': dict
            }
        """
        if current_time is None:
            current_time = timezone.now()
        
        # Generate cache keys
        hour_key = self._get_cache_key(tenant_id, customer_id, 'hour', current_time)
        minute_key = self._get_cache_key(tenant_id, customer_id, 'minute', current_time)
        spam_cooldown_key = self._get_cache_key(tenant_id, customer_id, 'spam_cooldown')
        abuse_cooldown_key = self._get_cache_key(tenant_id, customer_id, 'abuse_cooldown')
        
        # Check for active cooldowns
        spam_cooldown = cache.get(spam_cooldown_key)
        if spam_cooldown:
            remaining_seconds = int((spam_cooldown - current_time).total_seconds())
            if remaining_seconds > 0:
                return {
                    'allowed': False,
                    'reason': 'spam_cooldown',
                    'retry_after_seconds': remaining_seconds,
                    'current_counts': {}
                }
        
        abuse_cooldown = cache.get(abuse_cooldown_key)
        if abuse_cooldown:
            remaining_seconds = int((abuse_cooldown - current_time).total_seconds())
            if remaining_seconds > 0:
                return {
                    'allowed': False,
                    'reason': 'abuse_cooldown',
                    'retry_after_seconds': remaining_seconds,
                    'current_counts': {}
                }
        
        # Get current message counts
        hour_count = cache.get(hour_key, 0)
        minute_count = cache.get(minute_key, 0)
        
        # Check limits
        if hour_count >= self.default_limits['messages_per_hour']:
            return {
                'allowed': False,
                'reason': 'hourly_limit_exceeded',
                'retry_after_seconds': 3600,  # 1 hour
                'current_counts': {
                    'hour': hour_count,
                    'minute': minute_count
                }
            }
        
        if minute_count >= self.default_limits['messages_per_minute']:
            return {
                'allowed': False,
                'reason': 'minute_limit_exceeded',
                'retry_after_seconds': 60,  # 1 minute
                'current_counts': {
                    'hour': hour_count,
                    'minute': minute_count
                }
            }
        
        # Within limits
        return {
            'allowed': True,
            'reason': 'within_limits',
            'retry_after_seconds': 0,
            'current_counts': {
                'hour': hour_count,
                'minute': minute_count
            }
        }
    
    def increment_message_count(
        self, 
        tenant_id: str, 
        customer_id: str, 
        current_time: Optional[datetime] = None
    ) -> None:
        """
        Increment message count for rate limiting.
        
        Args:
            tenant_id: Tenant identifier
            customer_id: Customer identifier
            current_time: Current timestamp (defaults to now)
        """
        if current_time is None:
            current_time = timezone.now()
        
        # Generate cache keys
        hour_key = self._get_cache_key(tenant_id, customer_id, 'hour', current_time)
        minute_key = self._get_cache_key(tenant_id, customer_id, 'minute', current_time)
        
        # Increment counters with appropriate TTL
        cache.set(hour_key, cache.get(hour_key, 0) + 1, timeout=3600)  # 1 hour TTL
        cache.set(minute_key, cache.get(minute_key, 0) + 1, timeout=60)  # 1 minute TTL
        
        logger.debug(
            f"Incremented message count for tenant {tenant_id}, customer {customer_id}",
            extra={
                'tenant_id': tenant_id,
                'customer_id': customer_id,
                'hour_count': cache.get(hour_key, 0),
                'minute_count': cache.get(minute_key, 0)
            }
        )
    
    def apply_spam_cooldown(
        self, 
        tenant_id: str, 
        customer_id: str, 
        current_time: Optional[datetime] = None
    ) -> None:
        """
        Apply spam cooldown period.
        
        Args:
            tenant_id: Tenant identifier
            customer_id: Customer identifier
            current_time: Current timestamp (defaults to now)
        """
        if current_time is None:
            current_time = timezone.now()
        
        cooldown_until = current_time + timedelta(minutes=self.default_limits['spam_cooldown_minutes'])
        cooldown_key = self._get_cache_key(tenant_id, customer_id, 'spam_cooldown')
        
        cache.set(cooldown_key, cooldown_until, timeout=self.default_limits['spam_cooldown_minutes'] * 60)
        
        logger.warning(
            f"Applied spam cooldown for tenant {tenant_id}, customer {customer_id} until {cooldown_until}",
            extra={
                'tenant_id': tenant_id,
                'customer_id': customer_id,
                'cooldown_until': cooldown_until,
                'cooldown_minutes': self.default_limits['spam_cooldown_minutes']
            }
        )
    
    def apply_abuse_cooldown(
        self, 
        tenant_id: str, 
        customer_id: str, 
        current_time: Optional[datetime] = None
    ) -> None:
        """
        Apply abuse cooldown period.
        
        Args:
            tenant_id: Tenant identifier
            customer_id: Customer identifier
            current_time: Current timestamp (defaults to now)
        """
        if current_time is None:
            current_time = timezone.now()
        
        cooldown_until = current_time + timedelta(hours=self.default_limits['abuse_cooldown_hours'])
        cooldown_key = self._get_cache_key(tenant_id, customer_id, 'abuse_cooldown')
        
        cache.set(cooldown_key, cooldown_until, timeout=self.default_limits['abuse_cooldown_hours'] * 3600)
        
        logger.error(
            f"Applied abuse cooldown for tenant {tenant_id}, customer {customer_id} until {cooldown_until}",
            extra={
                'tenant_id': tenant_id,
                'customer_id': customer_id,
                'cooldown_until': cooldown_until,
                'cooldown_hours': self.default_limits['abuse_cooldown_hours']
            }
        )
    
    def check_casual_turn_limit(
        self, 
        casual_turns: int, 
        max_chattiness_level: int
    ) -> Dict[str, Any]:
        """
        Check if casual turns are within chattiness limits.
        
        EXACT levels as specified:
        - Level 0: 0 casual turns (strictly business)
        - Level 1: 1 casual turn (1 short greeting)
        - Level 2: 2 casual turns (DEFAULT)
        - Level 3: 4 casual turns
        
        Args:
            casual_turns: Current casual turn count
            max_chattiness_level: Tenant's max chattiness level (0-3)
            
        Returns:
            Dict with limit check result:
            {
                'within_limit': bool,
                'max_allowed': int,
                'current_count': int,
                'should_redirect': bool
            }
        """
        level_map = {
            0: 0,  # Strictly business
            1: 1,  # 1 short greeting
            2: 2,  # Max 2 casual turns (DEFAULT)
            3: 4   # Max 4 casual turns
        }
        
        max_allowed = level_map.get(max_chattiness_level, 2)  # Default to level 2
        within_limit = casual_turns <= max_allowed
        should_redirect = casual_turns > max_allowed
        
        return {
            'within_limit': within_limit,
            'max_allowed': max_allowed,
            'current_count': casual_turns,
            'should_redirect': should_redirect
        }
    
    def _get_cache_key(
        self, 
        tenant_id: str, 
        customer_id: str, 
        limit_type: str, 
        current_time: Optional[datetime] = None
    ) -> str:
        """
        Generate cache key for rate limiting.
        
        Args:
            tenant_id: Tenant identifier
            customer_id: Customer identifier
            limit_type: Type of limit (hour, minute, spam_cooldown, abuse_cooldown)
            current_time: Current timestamp for time-based keys
            
        Returns:
            Cache key string
        """
        base_key = f"rate_limit:{tenant_id}:{customer_id}:{limit_type}"
        
        if limit_type == 'hour' and current_time:
            # Hour-based key (resets every hour)
            hour_key = current_time.strftime('%Y%m%d%H')
            return f"{base_key}:{hour_key}"
        elif limit_type == 'minute' and current_time:
            # Minute-based key (resets every minute)
            minute_key = current_time.strftime('%Y%m%d%H%M')
            return f"{base_key}:{minute_key}"
        else:
            # Static key for cooldowns
            return base_key
    
    def get_rate_limit_status(
        self, 
        tenant_id: str, 
        customer_id: str
    ) -> Dict[str, Any]:
        """
        Get current rate limit status for debugging/monitoring.
        
        Args:
            tenant_id: Tenant identifier
            customer_id: Customer identifier
            
        Returns:
            Dict with current rate limit status
        """
        current_time = timezone.now()
        
        # Get current counts
        hour_key = self._get_cache_key(tenant_id, customer_id, 'hour', current_time)
        minute_key = self._get_cache_key(tenant_id, customer_id, 'minute', current_time)
        spam_cooldown_key = self._get_cache_key(tenant_id, customer_id, 'spam_cooldown')
        abuse_cooldown_key = self._get_cache_key(tenant_id, customer_id, 'abuse_cooldown')
        
        hour_count = cache.get(hour_key, 0)
        minute_count = cache.get(minute_key, 0)
        spam_cooldown = cache.get(spam_cooldown_key)
        abuse_cooldown = cache.get(abuse_cooldown_key)
        
        return {
            'tenant_id': tenant_id,
            'customer_id': customer_id,
            'current_time': current_time,
            'counts': {
                'hour': hour_count,
                'minute': minute_count
            },
            'limits': self.default_limits,
            'cooldowns': {
                'spam_until': spam_cooldown,
                'abuse_until': abuse_cooldown
            }
        }


# Global rate limiter instance
_rate_limiter_instance: Optional[ConversationRateLimiter] = None


def get_rate_limiter() -> ConversationRateLimiter:
    """
    Get the global conversation rate limiter instance.
    
    Returns:
        ConversationRateLimiter instance
    """
    global _rate_limiter_instance
    if _rate_limiter_instance is None:
        _rate_limiter_instance = ConversationRateLimiter()
    return _rate_limiter_instance