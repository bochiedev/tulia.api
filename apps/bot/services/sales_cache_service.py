"""
Caching Service for sales orchestration refactor.

This service provides Redis-based caching for frequently accessed data.

Design principles:
- Cache product catalogs per tenant (5-minute TTL)
- Cache service lists per tenant (5-minute TTL)
- Cache tenant settings (10-minute TTL)
- Cache menu contexts (5-minute TTL)
- Cache popular FAQ answers (1-hour TTL)
- Implement cache invalidation on data updates
"""
import logging
import json
from typing import Any, Optional, List
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class SalesCacheService:
    """
    Redis-based caching service for sales orchestration.
    
    Responsibilities:
    - Cache product catalogs per tenant
    - Cache service lists per tenant
    - Cache tenant settings
    - Cache menu contexts
    - Cache FAQ answers
    - Handle cache invalidation
    """
    
    # Cache TTLs (in seconds)
    PRODUCT_CATALOG_TTL = 300  # 5 minutes
    SERVICE_LIST_TTL = 300  # 5 minutes
    TENANT_SETTINGS_TTL = 600  # 10 minutes
    MENU_CONTEXT_TTL = 300  # 5 minutes
    FAQ_ANSWER_TTL = 3600  # 1 hour
    
    # Cache key prefixes
    PREFIX_PRODUCTS = "sales:products"
    PREFIX_SERVICES = "sales:services"
    PREFIX_SETTINGS = "sales:settings"
    PREFIX_MENU = "sales:menu"
    PREFIX_FAQ = "sales:faq"
    
    def get_product_catalog(
        self,
        tenant_id: str,
        category: Optional[str] = None
    ) -> Optional[List[dict]]:
        """
        Get cached product catalog for tenant.
        
        Args:
            tenant_id: Tenant ID
            category: Optional category filter
            
        Returns:
            List of product dicts or None if not cached
        """
        cache_key = self._make_key(
            self.PREFIX_PRODUCTS,
            tenant_id,
            category or "all"
        )
        
        try:
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.debug(f"Cache hit for products: {cache_key}")
                return json.loads(cached_data)
        except Exception as e:
            logger.error(f"Error reading from cache: {e}")
        
        return None
    
    def set_product_catalog(
        self,
        tenant_id: str,
        products: List[dict],
        category: Optional[str] = None
    ) -> None:
        """
        Cache product catalog for tenant.
        
        Args:
            tenant_id: Tenant ID
            products: List of product dicts
            category: Optional category filter
        """
        cache_key = self._make_key(
            self.PREFIX_PRODUCTS,
            tenant_id,
            category or "all"
        )
        
        try:
            cache.set(
                cache_key,
                json.dumps(products),
                self.PRODUCT_CATALOG_TTL
            )
            logger.debug(f"Cached products: {cache_key}")
        except Exception as e:
            logger.error(f"Error writing to cache: {e}")
    
    def invalidate_product_catalog(
        self,
        tenant_id: str,
        category: Optional[str] = None
    ) -> None:
        """
        Invalidate cached product catalog.
        
        Args:
            tenant_id: Tenant ID
            category: Optional specific category to invalidate
        """
        if category:
            # Invalidate specific category
            cache_key = self._make_key(
                self.PREFIX_PRODUCTS,
                tenant_id,
                category
            )
            cache.delete(cache_key)
        else:
            # Invalidate all categories for tenant
            pattern = f"{self.PREFIX_PRODUCTS}:{tenant_id}:*"
            self._delete_pattern(pattern)
        
        logger.debug(f"Invalidated product cache for tenant {tenant_id}")
    
    def get_service_list(
        self,
        tenant_id: str
    ) -> Optional[List[dict]]:
        """
        Get cached service list for tenant.
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            List of service dicts or None if not cached
        """
        cache_key = self._make_key(
            self.PREFIX_SERVICES,
            tenant_id
        )
        
        try:
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.debug(f"Cache hit for services: {cache_key}")
                return json.loads(cached_data)
        except Exception as e:
            logger.error(f"Error reading from cache: {e}")
        
        return None
    
    def set_service_list(
        self,
        tenant_id: str,
        services: List[dict]
    ) -> None:
        """
        Cache service list for tenant.
        
        Args:
            tenant_id: Tenant ID
            services: List of service dicts
        """
        cache_key = self._make_key(
            self.PREFIX_SERVICES,
            tenant_id
        )
        
        try:
            cache.set(
                cache_key,
                json.dumps(services),
                self.SERVICE_LIST_TTL
            )
            logger.debug(f"Cached services: {cache_key}")
        except Exception as e:
            logger.error(f"Error writing to cache: {e}")
    
    def invalidate_service_list(
        self,
        tenant_id: str
    ) -> None:
        """
        Invalidate cached service list.
        
        Args:
            tenant_id: Tenant ID
        """
        cache_key = self._make_key(
            self.PREFIX_SERVICES,
            tenant_id
        )
        cache.delete(cache_key)
        logger.debug(f"Invalidated service cache for tenant {tenant_id}")
    
    def get_tenant_settings(
        self,
        tenant_id: str
    ) -> Optional[dict]:
        """
        Get cached tenant settings.
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            Settings dict or None if not cached
        """
        cache_key = self._make_key(
            self.PREFIX_SETTINGS,
            tenant_id
        )
        
        try:
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.debug(f"Cache hit for settings: {cache_key}")
                return json.loads(cached_data)
        except Exception as e:
            logger.error(f"Error reading from cache: {e}")
        
        return None
    
    def set_tenant_settings(
        self,
        tenant_id: str,
        settings: dict
    ) -> None:
        """
        Cache tenant settings.
        
        Args:
            tenant_id: Tenant ID
            settings: Settings dict
        """
        cache_key = self._make_key(
            self.PREFIX_SETTINGS,
            tenant_id
        )
        
        try:
            cache.set(
                cache_key,
                json.dumps(settings),
                self.TENANT_SETTINGS_TTL
            )
            logger.debug(f"Cached settings: {cache_key}")
        except Exception as e:
            logger.error(f"Error writing to cache: {e}")
    
    def invalidate_tenant_settings(
        self,
        tenant_id: str
    ) -> None:
        """
        Invalidate cached tenant settings.
        
        Args:
            tenant_id: Tenant ID
        """
        cache_key = self._make_key(
            self.PREFIX_SETTINGS,
            tenant_id
        )
        cache.delete(cache_key)
        logger.debug(f"Invalidated settings cache for tenant {tenant_id}")
    
    def get_menu_context(
        self,
        conversation_id: str
    ) -> Optional[dict]:
        """
        Get cached menu context for conversation.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Menu context dict or None if not cached
        """
        cache_key = self._make_key(
            self.PREFIX_MENU,
            conversation_id
        )
        
        try:
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.debug(f"Cache hit for menu: {cache_key}")
                return json.loads(cached_data)
        except Exception as e:
            logger.error(f"Error reading from cache: {e}")
        
        return None
    
    def set_menu_context(
        self,
        conversation_id: str,
        menu_context: dict
    ) -> None:
        """
        Cache menu context for conversation.
        
        Args:
            conversation_id: Conversation ID
            menu_context: Menu context dict
        """
        cache_key = self._make_key(
            self.PREFIX_MENU,
            conversation_id
        )
        
        try:
            cache.set(
                cache_key,
                json.dumps(menu_context),
                self.MENU_CONTEXT_TTL
            )
            logger.debug(f"Cached menu: {cache_key}")
        except Exception as e:
            logger.error(f"Error writing to cache: {e}")
    
    def invalidate_menu_context(
        self,
        conversation_id: str
    ) -> None:
        """
        Invalidate cached menu context.
        
        Args:
            conversation_id: Conversation ID
        """
        cache_key = self._make_key(
            self.PREFIX_MENU,
            conversation_id
        )
        cache.delete(cache_key)
        logger.debug(f"Invalidated menu cache for conversation {conversation_id}")
    
    def get_faq_answer(
        self,
        tenant_id: str,
        question_hash: str
    ) -> Optional[str]:
        """
        Get cached FAQ answer.
        
        Args:
            tenant_id: Tenant ID
            question_hash: Hash of the question
            
        Returns:
            Cached answer or None
        """
        cache_key = self._make_key(
            self.PREFIX_FAQ,
            tenant_id,
            question_hash
        )
        
        try:
            cached_answer = cache.get(cache_key)
            if cached_answer:
                logger.debug(f"Cache hit for FAQ: {cache_key}")
                return cached_answer
        except Exception as e:
            logger.error(f"Error reading from cache: {e}")
        
        return None
    
    def set_faq_answer(
        self,
        tenant_id: str,
        question_hash: str,
        answer: str
    ) -> None:
        """
        Cache FAQ answer.
        
        Args:
            tenant_id: Tenant ID
            question_hash: Hash of the question
            answer: Answer text
        """
        cache_key = self._make_key(
            self.PREFIX_FAQ,
            tenant_id,
            question_hash
        )
        
        try:
            cache.set(
                cache_key,
                answer,
                self.FAQ_ANSWER_TTL
            )
            logger.debug(f"Cached FAQ answer: {cache_key}")
        except Exception as e:
            logger.error(f"Error writing to cache: {e}")
    
    def invalidate_faq_cache(
        self,
        tenant_id: str
    ) -> None:
        """
        Invalidate all FAQ cache for tenant.
        
        Args:
            tenant_id: Tenant ID
        """
        pattern = f"{self.PREFIX_FAQ}:{tenant_id}:*"
        self._delete_pattern(pattern)
        logger.debug(f"Invalidated FAQ cache for tenant {tenant_id}")
    
    def _make_key(self, *parts: str) -> str:
        """Create cache key from parts."""
        return ":".join(str(p) for p in parts)
    
    def _delete_pattern(self, pattern: str) -> None:
        """
        Delete all keys matching pattern.
        
        Note: This requires Redis and may not work with other cache backends.
        """
        try:
            # Try to use Redis-specific delete pattern
            from django_redis import get_redis_connection
            conn = get_redis_connection("default")
            keys = conn.keys(pattern)
            if keys:
                conn.delete(*keys)
                logger.debug(f"Deleted {len(keys)} keys matching {pattern}")
        except Exception as e:
            logger.warning(f"Could not delete pattern {pattern}: {e}")


__all__ = ['SalesCacheService']
