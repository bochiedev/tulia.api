"""
Caching utilities for frequently accessed data.

Provides centralized cache management with consistent TTLs and invalidation patterns.
"""
import logging
from typing import Optional, Any, Callable
from functools import wraps
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class CacheKeys:
    """Centralized cache key definitions with consistent naming."""
    
    # Tenant configuration (TTL: 1 hour)
    TENANT_CONFIG = "tenant:config:{tenant_id}"
    TENANT_SETTINGS = "tenant:settings:{tenant_id}"
    TENANT_SUBSCRIPTION = "tenant:subscription:{tenant_id}"
    
    # Product catalog (TTL: 15 minutes)
    PRODUCT_DETAIL = "product:detail:{tenant_id}:{product_id}"
    PRODUCT_LIST = "product:list:{tenant_id}:{filters_hash}"
    PRODUCT_VARIANTS = "product:variants:{tenant_id}:{product_id}"
    
    # Service catalog (TTL: 15 minutes)
    SERVICE_DETAIL = "service:detail:{tenant_id}:{service_id}"
    SERVICE_LIST = "service:list:{tenant_id}:{filters_hash}"
    SERVICE_VARIANTS = "service:variants:{tenant_id}:{service_id}"
    
    # Customer preferences (TTL: 5 minutes)
    CUSTOMER_PREFERENCES = "customer:preferences:{tenant_id}:{customer_id}"
    CUSTOMER_CONSENT = "customer:consent:{tenant_id}:{customer_id}"
    
    # Availability windows (TTL: 1 hour)
    AVAILABILITY_WINDOWS = "availability:windows:{tenant_id}:{service_id}"
    AVAILABILITY_SLOTS = "availability:slots:{tenant_id}:{service_id}:{date_range_hash}"
    
    # RBAC scopes (TTL: 5 minutes)
    USER_SCOPES = "rbac:scopes:{tenant_id}:{user_id}"
    
    @classmethod
    def format(cls, key_template: str, **kwargs) -> str:
        """Format a cache key with provided parameters."""
        return key_template.format(**kwargs)


class CacheTTL:
    """Cache TTL (Time To Live) constants in seconds."""
    
    TENANT_CONFIG = 3600  # 1 hour
    CATALOG = 900  # 15 minutes
    CUSTOMER_PREFERENCES = 300  # 5 minutes
    AVAILABILITY = 3600  # 1 hour
    RBAC_SCOPES = 300  # 5 minutes


class CacheService:
    """Service for managing cached data with consistent patterns."""
    
    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            default: Default value if key not found
            
        Returns:
            Cached value or default
        """
        try:
            value = cache.get(key, default)
            if value is not None:
                logger.debug(f"Cache HIT: {key}")
            else:
                logger.debug(f"Cache MISS: {key}")
            return value
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {str(e)}")
            return default
    
    @staticmethod
    def set(key: str, value: Any, ttl: int = None) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (optional)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cache.set(key, value, timeout=ttl)
            logger.debug(f"Cache SET: {key} (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {str(e)}")
            return False
    
    @staticmethod
    def delete(key: str) -> bool:
        """
        Delete value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cache.delete(key)
            logger.debug(f"Cache DELETE: {key}")
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {str(e)}")
            return False
    
    @staticmethod
    def delete_pattern(pattern: str) -> bool:
        """
        Delete all keys matching a pattern.
        
        Args:
            pattern: Pattern to match (e.g., "tenant:*:123")
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Use django-redis delete_pattern if available
            if hasattr(cache, 'delete_pattern'):
                cache.delete_pattern(pattern)
                logger.debug(f"Cache DELETE_PATTERN: {pattern}")
                return True
            else:
                logger.warning(f"delete_pattern not supported by cache backend")
                return False
        except Exception as e:
            logger.error(f"Cache delete_pattern error for pattern {pattern}: {str(e)}")
            return False
    
    @staticmethod
    def get_or_set(key: str, default_func: Callable, ttl: int = None) -> Any:
        """
        Get value from cache or set it using default_func if not found.
        
        Args:
            key: Cache key
            default_func: Function to call if cache miss
            ttl: Time to live in seconds (optional)
            
        Returns:
            Cached or computed value
        """
        value = CacheService.get(key)
        if value is None:
            value = default_func()
            if value is not None:
                CacheService.set(key, value, ttl)
        return value


def cache_result(key_template: str, ttl: int = 300):
    """
    Decorator to cache function results.
    
    Args:
        key_template: Cache key template with {arg_name} placeholders
        ttl: Time to live in seconds
        
    Example:
        @cache_result("product:detail:{tenant_id}:{product_id}", ttl=900)
        def get_product(tenant_id, product_id):
            return Product.objects.get(id=product_id)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key from template and function arguments
            import inspect
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            try:
                cache_key = key_template.format(**bound_args.arguments)
            except KeyError as e:
                logger.warning(f"Cache key template missing argument: {e}")
                return func(*args, **kwargs)
            
            # Try to get from cache
            result = CacheService.get(cache_key)
            if result is not None:
                return result
            
            # Compute and cache result
            result = func(*args, **kwargs)
            if result is not None:
                CacheService.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator


class TenantCacheInvalidator:
    """Utility for invalidating tenant-specific caches."""
    
    @staticmethod
    def invalidate_tenant_config(tenant_id: str):
        """Invalidate all tenant configuration caches."""
        CacheService.delete(CacheKeys.format(CacheKeys.TENANT_CONFIG, tenant_id=tenant_id))
        CacheService.delete(CacheKeys.format(CacheKeys.TENANT_SETTINGS, tenant_id=tenant_id))
        CacheService.delete(CacheKeys.format(CacheKeys.TENANT_SUBSCRIPTION, tenant_id=tenant_id))
        logger.info(f"Invalidated tenant config cache for tenant {tenant_id}")
    
    @staticmethod
    def invalidate_product_catalog(tenant_id: str, product_id: str = None):
        """Invalidate product catalog caches."""
        if product_id:
            # Invalidate specific product
            CacheService.delete(CacheKeys.format(
                CacheKeys.PRODUCT_DETAIL,
                tenant_id=tenant_id,
                product_id=product_id
            ))
            CacheService.delete(CacheKeys.format(
                CacheKeys.PRODUCT_VARIANTS,
                tenant_id=tenant_id,
                product_id=product_id
            ))
        
        # Invalidate product list caches (all filter combinations)
        CacheService.delete_pattern(f"product:list:{tenant_id}:*")
        logger.info(f"Invalidated product catalog cache for tenant {tenant_id}")
    
    @staticmethod
    def invalidate_service_catalog(tenant_id: str, service_id: str = None):
        """Invalidate service catalog caches."""
        if service_id:
            # Invalidate specific service
            CacheService.delete(CacheKeys.format(
                CacheKeys.SERVICE_DETAIL,
                tenant_id=tenant_id,
                service_id=service_id
            ))
            CacheService.delete(CacheKeys.format(
                CacheKeys.SERVICE_VARIANTS,
                tenant_id=tenant_id,
                service_id=service_id
            ))
        
        # Invalidate service list caches (all filter combinations)
        CacheService.delete_pattern(f"service:list:{tenant_id}:*")
        logger.info(f"Invalidated service catalog cache for tenant {tenant_id}")
    
    @staticmethod
    def invalidate_customer_preferences(tenant_id: str, customer_id: str):
        """Invalidate customer preferences cache."""
        CacheService.delete(CacheKeys.format(
            CacheKeys.CUSTOMER_PREFERENCES,
            tenant_id=tenant_id,
            customer_id=customer_id
        ))
        CacheService.delete(CacheKeys.format(
            CacheKeys.CUSTOMER_CONSENT,
            tenant_id=tenant_id,
            customer_id=customer_id
        ))
        logger.info(f"Invalidated customer preferences cache for customer {customer_id}")
    
    @staticmethod
    def invalidate_availability(tenant_id: str, service_id: str):
        """Invalidate availability caches."""
        CacheService.delete(CacheKeys.format(
            CacheKeys.AVAILABILITY_WINDOWS,
            tenant_id=tenant_id,
            service_id=service_id
        ))
        # Invalidate all availability slot caches for this service
        CacheService.delete_pattern(f"availability:slots:{tenant_id}:{service_id}:*")
        logger.info(f"Invalidated availability cache for service {service_id}")
    
    @staticmethod
    def invalidate_user_scopes(tenant_id: str, user_id: str):
        """Invalidate user RBAC scopes cache."""
        CacheService.delete(CacheKeys.format(
            CacheKeys.USER_SCOPES,
            tenant_id=tenant_id,
            user_id=user_id
        ))
        logger.info(f"Invalidated user scopes cache for user {user_id} in tenant {tenant_id}")
