"""
Catalog Cache Service for AI Agent performance optimization.

Provides caching for product and service catalog data with configurable TTL
to reduce database queries and improve response times.
"""
import logging
from typing import List, Optional, Dict, Any
from django.core.cache import cache
from decimal import Decimal

logger = logging.getLogger(__name__)


class CatalogCacheService:
    """
    Service for caching catalog data (products and services).
    
    Implements caching strategy with 1-minute TTL for catalog data
    to balance freshness with performance. Uses Redis for distributed
    caching across multiple workers.
    """
    
    # Cache TTL in seconds (1 minute for catalog data)
    CATALOG_CACHE_TTL = 60
    
    # Cache key prefixes
    PRODUCTS_KEY_PREFIX = "catalog:products"
    SERVICES_KEY_PREFIX = "catalog:services"
    PRODUCT_KEY_PREFIX = "catalog:product"
    SERVICE_KEY_PREFIX = "catalog:service"
    
    @classmethod
    def _get_products_cache_key(cls, tenant_id: str, active_only: bool = True) -> str:
        """Generate cache key for tenant products list."""
        active_str = "active" if active_only else "all"
        return f"{cls.PRODUCTS_KEY_PREFIX}:{tenant_id}:{active_str}"
    
    @classmethod
    def _get_services_cache_key(cls, tenant_id: str, active_only: bool = True) -> str:
        """Generate cache key for tenant services list."""
        active_str = "active" if active_only else "all"
        return f"{cls.SERVICES_KEY_PREFIX}:{tenant_id}:{active_str}"
    
    @classmethod
    def _get_product_cache_key(cls, product_id: str, tenant_id: Optional[str] = None) -> str:
        """Generate cache key for single product."""
        if tenant_id:
            return f"{cls.PRODUCT_KEY_PREFIX}:{tenant_id}:{product_id}"
        return f"{cls.PRODUCT_KEY_PREFIX}:{product_id}"
    
    @classmethod
    def _get_service_cache_key(cls, service_id: str, tenant_id: Optional[str] = None) -> str:
        """Generate cache key for single service."""
        if tenant_id:
            return f"{cls.SERVICE_KEY_PREFIX}:{tenant_id}:{service_id}"
        return f"{cls.SERVICE_KEY_PREFIX}:{service_id}"
    
    @classmethod
    def get_products(cls, tenant, active_only: bool = True, use_cache: bool = True) -> List:
        """
        Get products for tenant with caching.
        
        Retrieves products from cache if available, otherwise fetches from
        database and caches for 1 minute.
        
        Args:
            tenant: Tenant instance
            active_only: Whether to return only active products
            use_cache: Whether to use cache (default: True)
            
        Returns:
            List of Product instances
        """
        if not use_cache:
            return cls._fetch_products_from_db(tenant, active_only)
        
        cache_key = cls._get_products_cache_key(str(tenant.id), active_only)
        
        # Try to get from cache
        products = cache.get(cache_key)
        
        if products is None:
            # Fetch from database
            products = cls._fetch_products_from_db(tenant, active_only)
            
            # Cache for 1 minute
            cache.set(cache_key, products, cls.CATALOG_CACHE_TTL)
            
            logger.debug(
                f"Cached {len(products)} products for tenant {tenant.id} "
                f"(active_only={active_only})"
            )
        else:
            logger.debug(
                f"Retrieved {len(products)} products from cache for tenant {tenant.id}"
            )
        
        return products
    
    @classmethod
    def get_services(cls, tenant, active_only: bool = True, use_cache: bool = True) -> List:
        """
        Get services for tenant with caching.
        
        Retrieves services from cache if available, otherwise fetches from
        database and caches for 1 minute.
        
        Args:
            tenant: Tenant instance
            active_only: Whether to return only active services
            use_cache: Whether to use cache (default: True)
            
        Returns:
            List of Service instances
        """
        if not use_cache:
            return cls._fetch_services_from_db(tenant, active_only)
        
        cache_key = cls._get_services_cache_key(str(tenant.id), active_only)
        
        # Try to get from cache
        services = cache.get(cache_key)
        
        if services is None:
            # Fetch from database
            services = cls._fetch_services_from_db(tenant, active_only)
            
            # Cache for 1 minute
            cache.set(cache_key, services, cls.CATALOG_CACHE_TTL)
            
            logger.debug(
                f"Cached {len(services)} services for tenant {tenant.id} "
                f"(active_only={active_only})"
            )
        else:
            logger.debug(
                f"Retrieved {len(services)} services from cache for tenant {tenant.id}"
            )
        
        return services
    
    @classmethod
    def get_product(cls, product_id: str, tenant_id: Optional[str] = None, use_cache: bool = True):
        """
        Get single product by ID with caching.
        
        Args:
            product_id: Product UUID
            tenant_id: Optional tenant UUID for cache key scoping
            use_cache: Whether to use cache (default: True)
            
        Returns:
            Product instance or None if not found
        """
        from apps.catalog.models import Product
        
        if not use_cache:
            try:
                return Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                return None
        
        cache_key = cls._get_product_cache_key(str(product_id), tenant_id)
        
        # Try to get from cache
        product = cache.get(cache_key)
        
        if product is None:
            # Fetch from database
            try:
                product = Product.objects.select_related('tenant').get(id=product_id)
                
                # Cache for 1 minute with tenant-scoped key if tenant_id provided
                if tenant_id:
                    cache_key = cls._get_product_cache_key(str(product_id), str(product.tenant_id))
                cache.set(cache_key, product, cls.CATALOG_CACHE_TTL)
                
                logger.debug(f"Cached product {product_id}")
            except Product.DoesNotExist:
                logger.debug(f"Product {product_id} not found")
                return None
        else:
            logger.debug(f"Retrieved product {product_id} from cache")
        
        return product
    
    @classmethod
    def get_service(cls, service_id: str, tenant_id: Optional[str] = None, use_cache: bool = True):
        """
        Get single service by ID with caching.
        
        Args:
            service_id: Service UUID
            tenant_id: Optional tenant UUID for cache key scoping
            use_cache: Whether to use cache (default: True)
            
        Returns:
            Service instance or None if not found
        """
        from apps.services.models import Service
        
        if not use_cache:
            try:
                return Service.objects.get(id=service_id)
            except Service.DoesNotExist:
                return None
        
        cache_key = cls._get_service_cache_key(str(service_id), tenant_id)
        
        # Try to get from cache
        service = cache.get(cache_key)
        
        if service is None:
            # Fetch from database
            try:
                service = Service.objects.select_related('tenant').get(id=service_id)
                
                # Cache for 1 minute with tenant-scoped key if tenant_id provided
                if tenant_id:
                    cache_key = cls._get_service_cache_key(str(service_id), str(service.tenant_id))
                cache.set(cache_key, service, cls.CATALOG_CACHE_TTL)
                
                logger.debug(f"Cached service {service_id}")
            except Service.DoesNotExist:
                logger.debug(f"Service {service_id} not found")
                return None
        else:
            logger.debug(f"Retrieved service {service_id} from cache")
        
        return service
    
    @classmethod
    def invalidate_products(cls, tenant_id: str) -> None:
        """
        Invalidate all product caches for a tenant.
        
        Call this when products are created, updated, or deleted.
        
        Args:
            tenant_id: Tenant UUID
        """
        # Invalidate both active and all products caches
        cache_key_active = cls._get_products_cache_key(str(tenant_id), active_only=True)
        cache_key_all = cls._get_products_cache_key(str(tenant_id), active_only=False)
        
        cache.delete_many([cache_key_active, cache_key_all])
        
        logger.debug(f"Invalidated product caches for tenant {tenant_id}")
    
    @classmethod
    def invalidate_services(cls, tenant_id: str) -> None:
        """
        Invalidate all service caches for a tenant.
        
        Call this when services are created, updated, or deleted.
        
        Args:
            tenant_id: Tenant UUID
        """
        # Invalidate both active and all services caches
        cache_key_active = cls._get_services_cache_key(str(tenant_id), active_only=True)
        cache_key_all = cls._get_services_cache_key(str(tenant_id), active_only=False)
        
        cache.delete_many([cache_key_active, cache_key_all])
        
        logger.debug(f"Invalidated service caches for tenant {tenant_id}")
    
    @classmethod
    def invalidate_product(cls, product_id: str, tenant_id: Optional[str] = None) -> None:
        """
        Invalidate cache for a specific product.
        
        Call this when a product is updated or deleted.
        
        Args:
            product_id: Product UUID
            tenant_id: Optional tenant UUID to also invalidate tenant product list
        """
        # Invalidate both tenant-scoped and non-scoped keys for safety
        cache_key = cls._get_product_cache_key(str(product_id))
        cache.delete(cache_key)
        
        if tenant_id:
            cache_key_scoped = cls._get_product_cache_key(str(product_id), str(tenant_id))
            cache.delete(cache_key_scoped)
            cls.invalidate_products(tenant_id)
        
        logger.debug(f"Invalidated cache for product {product_id}")
    
    @classmethod
    def invalidate_service(cls, service_id: str, tenant_id: Optional[str] = None) -> None:
        """
        Invalidate cache for a specific service.
        
        Call this when a service is updated or deleted.
        
        Args:
            service_id: Service UUID
            tenant_id: Optional tenant UUID to also invalidate tenant service list
        """
        # Invalidate both tenant-scoped and non-scoped keys for safety
        cache_key = cls._get_service_cache_key(str(service_id))
        cache.delete(cache_key)
        
        if tenant_id:
            cache_key_scoped = cls._get_service_cache_key(str(service_id), str(tenant_id))
            cache.delete(cache_key_scoped)
            cls.invalidate_services(tenant_id)
        
        logger.debug(f"Invalidated cache for service {service_id}")
    
    @classmethod
    def _fetch_products_from_db(cls, tenant, active_only: bool) -> List:
        """
        Fetch products from database with optimized query.
        
        Args:
            tenant: Tenant instance
            active_only: Whether to return only active products
            
        Returns:
            List of Product instances
        """
        from apps.catalog.models import Product
        
        query = Product.objects.filter(tenant=tenant)
        
        if active_only:
            query = query.filter(is_active=True)
        
        # Use select_related for foreign keys if needed
        # Use prefetch_related for reverse foreign keys if needed
        products = list(query.select_related('tenant').order_by('-created_at'))
        
        logger.debug(
            f"Fetched {len(products)} products from database for tenant {tenant.id} "
            f"(active_only={active_only})"
        )
        
        return products
    
    @classmethod
    def _fetch_services_from_db(cls, tenant, active_only: bool) -> List:
        """
        Fetch services from database with optimized query.
        
        Args:
            tenant: Tenant instance
            active_only: Whether to return only active services
            
        Returns:
            List of Service instances
        """
        from apps.services.models import Service
        
        query = Service.objects.filter(tenant=tenant)
        
        if active_only:
            query = query.filter(is_active=True)
        
        # Use select_related for foreign keys if needed
        services = list(query.select_related('tenant').order_by('-created_at'))
        
        logger.debug(
            f"Fetched {len(services)} services from database for tenant {tenant.id} "
            f"(active_only={active_only})"
        )
        
        return services
    
    @classmethod
    def warm_cache(cls, tenant) -> Dict[str, int]:
        """
        Warm up cache for a tenant by pre-loading catalog data.
        
        Useful for ensuring fast first response after cache expiration
        or system restart.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            Dictionary with counts of cached items
        """
        logger.info(f"Warming cache for tenant {tenant.id}")
        
        # Pre-load products
        products = cls.get_products(tenant, active_only=True, use_cache=False)
        cache_key_products = cls._get_products_cache_key(str(tenant.id), active_only=True)
        cache.set(cache_key_products, products, cls.CATALOG_CACHE_TTL)
        
        # Pre-load services
        services = cls.get_services(tenant, active_only=True, use_cache=False)
        cache_key_services = cls._get_services_cache_key(str(tenant.id), active_only=True)
        cache.set(cache_key_services, services, cls.CATALOG_CACHE_TTL)
        
        result = {
            'products': len(products),
            'services': len(services)
        }
        
        logger.info(
            f"Cache warmed for tenant {tenant.id}: "
            f"{result['products']} products, {result['services']} services"
        )
        
        return result


def create_catalog_cache_service() -> CatalogCacheService:
    """
    Factory function to create CatalogCacheService instance.
    
    Returns:
        CatalogCacheService instance
    """
    return CatalogCacheService()
