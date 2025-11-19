"""
Caching service for multi-provider LLM responses and routing decisions.

Implements intelligent caching to reduce costs and improve performance.
"""

import logging
import hashlib
import json
from typing import Optional, List, Dict, Any
from django.core.cache import cache
from decimal import Decimal

logger = logging.getLogger(__name__)


class LLMCachingService:
    """
    Service for caching LLM responses and routing decisions.
    
    Features:
    - Response caching with content-based keys
    - Routing decision caching
    - Provider selection caching
    - Automatic cache invalidation
    - Cache hit rate tracking
    """
    
    # Cache TTLs (in seconds)
    RESPONSE_CACHE_TTL = 60  # 1 minute for responses
    ROUTING_CACHE_TTL = 300  # 5 minutes for routing decisions
    PROVIDER_HEALTH_CACHE_TTL = 60  # 1 minute for provider health
    
    # Cache key prefixes
    RESPONSE_PREFIX = 'llm_response'
    ROUTING_PREFIX = 'llm_routing'
    PROVIDER_HEALTH_PREFIX = 'provider_health'
    
    # Cache statistics
    _stats = {
        'hits': 0,
        'misses': 0,
        'invalidations': 0
    }
    
    @classmethod
    def get_cached_response(
        cls,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        tenant_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached LLM response if available.
        
        Args:
            messages: List of message dicts
            model: Model identifier
            temperature: Temperature parameter
            tenant_id: Tenant ID for isolation
            
        Returns:
            Cached response dict or None
        """
        cache_key = cls._generate_response_cache_key(
            messages, model, temperature, tenant_id
        )
        
        cached = cache.get(cache_key)
        
        if cached:
            cls._stats['hits'] += 1
            logger.debug(f"Cache HIT for key: {cache_key[:50]}...")
            return cached
        
        cls._stats['misses'] += 1
        logger.debug(f"Cache MISS for key: {cache_key[:50]}...")
        return None
    
    @classmethod
    def cache_response(
        cls,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        tenant_id: str,
        response: Dict[str, Any],
        ttl: Optional[int] = None
    ):
        """
        Cache LLM response.
        
        Args:
            messages: List of message dicts
            model: Model identifier
            temperature: Temperature parameter
            tenant_id: Tenant ID for isolation
            response: Response dict to cache
            ttl: Optional custom TTL in seconds
        """
        cache_key = cls._generate_response_cache_key(
            messages, model, temperature, tenant_id
        )
        
        ttl = ttl or cls.RESPONSE_CACHE_TTL
        
        cache.set(cache_key, response, ttl)
        logger.debug(f"Cached response with key: {cache_key[:50]}... (TTL: {ttl}s)")
    
    @classmethod
    def get_cached_routing_decision(
        cls,
        messages: List[Dict[str, str]],
        context_size: int,
        tenant_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached routing decision if available.
        
        Args:
            messages: List of message dicts
            context_size: Context size in tokens
            tenant_id: Tenant ID for isolation
            
        Returns:
            Cached routing decision dict or None
        """
        cache_key = cls._generate_routing_cache_key(
            messages, context_size, tenant_id
        )
        
        cached = cache.get(cache_key)
        
        if cached:
            cls._stats['hits'] += 1
            logger.debug(f"Routing cache HIT for key: {cache_key[:50]}...")
            return cached
        
        cls._stats['misses'] += 1
        logger.debug(f"Routing cache MISS for key: {cache_key[:50]}...")
        return None
    
    @classmethod
    def cache_routing_decision(
        cls,
        messages: List[Dict[str, str]],
        context_size: int,
        tenant_id: str,
        decision: Dict[str, Any],
        ttl: Optional[int] = None
    ):
        """
        Cache routing decision.
        
        Args:
            messages: List of message dicts
            context_size: Context size in tokens
            tenant_id: Tenant ID for isolation
            decision: Routing decision dict to cache
            ttl: Optional custom TTL in seconds
        """
        cache_key = cls._generate_routing_cache_key(
            messages, context_size, tenant_id
        )
        
        ttl = ttl or cls.ROUTING_CACHE_TTL
        
        cache.set(cache_key, decision, ttl)
        logger.debug(f"Cached routing decision with key: {cache_key[:50]}... (TTL: {ttl}s)")
    
    @classmethod
    def invalidate_provider_cache(cls, provider: str, tenant_id: str):
        """
        Invalidate cache for a specific provider.
        
        Called when provider fails or becomes unhealthy.
        
        Args:
            provider: Provider name
            tenant_id: Tenant ID
        """
        # We can't easily iterate cache keys, so we use a marker
        marker_key = f"{cls.PROVIDER_HEALTH_PREFIX}:{tenant_id}:{provider}:invalid"
        cache.set(marker_key, True, cls.PROVIDER_HEALTH_CACHE_TTL)
        
        cls._stats['invalidations'] += 1
        logger.info(f"Invalidated cache for provider: {provider}, tenant: {tenant_id}")
    
    @classmethod
    def is_provider_cache_valid(cls, provider: str, tenant_id: str) -> bool:
        """
        Check if provider cache is valid.
        
        Args:
            provider: Provider name
            tenant_id: Tenant ID
            
        Returns:
            bool: True if cache is valid
        """
        marker_key = f"{cls.PROVIDER_HEALTH_PREFIX}:{tenant_id}:{provider}:invalid"
        return not cache.get(marker_key)
    
    @classmethod
    def get_cache_stats(cls) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dict with cache hit/miss statistics
        """
        total = cls._stats['hits'] + cls._stats['misses']
        hit_rate = cls._stats['hits'] / total if total > 0 else 0.0
        
        return {
            'hits': cls._stats['hits'],
            'misses': cls._stats['misses'],
            'total': total,
            'hit_rate': hit_rate,
            'invalidations': cls._stats['invalidations']
        }
    
    @classmethod
    def reset_stats(cls):
        """Reset cache statistics."""
        cls._stats = {
            'hits': 0,
            'misses': 0,
            'invalidations': 0
        }
    
    @classmethod
    def _generate_response_cache_key(
        cls,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        tenant_id: str
    ) -> str:
        """
        Generate cache key for LLM response.
        
        Uses content-based hashing to ensure identical requests
        get the same cache key.
        
        Args:
            messages: List of message dicts
            model: Model identifier
            temperature: Temperature parameter
            tenant_id: Tenant ID
            
        Returns:
            Cache key string
        """
        # Create deterministic representation
        key_data = {
            'messages': messages,
            'model': model,
            'temperature': temperature,
            'tenant_id': str(tenant_id)
        }
        
        # Convert to JSON and hash
        key_json = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.sha256(key_json.encode()).hexdigest()
        
        return f"{cls.RESPONSE_PREFIX}:{key_hash}"
    
    @classmethod
    def _generate_routing_cache_key(
        cls,
        messages: List[Dict[str, str]],
        context_size: int,
        tenant_id: str
    ) -> str:
        """
        Generate cache key for routing decision.
        
        Args:
            messages: List of message dicts
            context_size: Context size in tokens
            tenant_id: Tenant ID
            
        Returns:
            Cache key string
        """
        # Use last user message for routing cache key
        # (routing is based on query complexity, not full history)
        last_user_message = None
        for msg in reversed(messages):
            if msg.get('role') == 'user':
                last_user_message = msg.get('content', '')
                break
        
        if not last_user_message:
            last_user_message = ''
        
        # Create deterministic representation
        key_data = {
            'message': last_user_message,
            'context_size': context_size,
            'tenant_id': str(tenant_id)
        }
        
        # Convert to JSON and hash
        key_json = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.sha256(key_json.encode()).hexdigest()
        
        return f"{cls.ROUTING_PREFIX}:{key_hash}"
