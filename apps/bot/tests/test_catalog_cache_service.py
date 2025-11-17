"""
Tests for CatalogCacheService.

Tests caching functionality for products and services with 1-minute TTL.
"""
import pytest
from unittest.mock import patch, MagicMock
from django.core.cache import cache
from apps.bot.services.catalog_cache_service import CatalogCacheService


@pytest.fixture
def tenant(db):
    """Create test tenant."""
    from apps.tenants.models import Tenant
    return Tenant.objects.create(
        name="Test Tenant",
        slug="test-tenant"
    )


@pytest.fixture
def products(db, tenant):
    """Create test products."""
    from apps.catalog.models import Product
    return [
        Product.objects.create(
            tenant=tenant,
            title=f"Product {i}",
            sku=f"SKU{i}",
            price=10.00 * i,
            is_active=True
        )
        for i in range(1, 4)
    ]


@pytest.fixture
def services(db, tenant):
    """Create test services."""
    from apps.services.models import Service
    return [
        Service.objects.create(
            tenant=tenant,
            title=f"Service {i}",
            description=f"Test service {i}",
            base_price=20.00 * i,
            is_active=True
        )
        for i in range(1, 3)
    ]


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before and after each test."""
    cache.clear()
    yield
    cache.clear()


class TestCatalogCacheService:
    """Test CatalogCacheService functionality."""
    
    def test_get_products_from_db(self, tenant, products):
        """Test fetching products from database."""
        result = CatalogCacheService.get_products(tenant, use_cache=False)
        
        assert len(result) == 3
        assert all(p.tenant == tenant for p in result)
    
    def test_get_products_caches_result(self, tenant, products):
        """Test that products are cached after first fetch."""
        # First call - should fetch from DB and cache
        result1 = CatalogCacheService.get_products(tenant)
        
        # Second call - should use cache
        with patch.object(CatalogCacheService, '_fetch_products_from_db') as mock_fetch:
            result2 = CatalogCacheService.get_products(tenant)
            
            # Should not call DB fetch
            mock_fetch.assert_not_called()
            
            # Results should be the same
            assert len(result2) == len(result1)
    
    def test_get_products_active_only(self, tenant, products):
        """Test filtering active products only."""
        # Make one product inactive
        products[0].is_active = False
        products[0].save()
        
        result = CatalogCacheService.get_products(tenant, active_only=True, use_cache=False)
        
        assert len(result) == 2
        assert all(p.is_active for p in result)
    
    def test_get_services_from_db(self, tenant, services):
        """Test fetching services from database."""
        result = CatalogCacheService.get_services(tenant, use_cache=False)
        
        assert len(result) == 2
        assert all(s.tenant == tenant for s in result)
    
    def test_get_services_caches_result(self, tenant, services):
        """Test that services are cached after first fetch."""
        # First call - should fetch from DB and cache
        result1 = CatalogCacheService.get_services(tenant)
        
        # Second call - should use cache
        with patch.object(CatalogCacheService, '_fetch_services_from_db') as mock_fetch:
            result2 = CatalogCacheService.get_services(tenant)
            
            # Should not call DB fetch
            mock_fetch.assert_not_called()
            
            # Results should be the same
            assert len(result2) == len(result1)
    
    def test_get_product_by_id(self, tenant, products):
        """Test fetching single product by ID."""
        product = products[0]
        
        result = CatalogCacheService.get_product(str(product.id), use_cache=False)
        
        assert result is not None
        assert result.id == product.id
        assert result.title == product.title
    
    def test_get_product_caches_result(self, tenant, products):
        """Test that single product is cached."""
        product = products[0]
        
        # First call - should fetch from DB and cache
        result1 = CatalogCacheService.get_product(str(product.id))
        
        # Second call - should use cache
        cache_key = CatalogCacheService._get_product_cache_key(str(product.id))
        cached = cache.get(cache_key)
        
        assert cached is not None
        assert cached.id == product.id
    
    def test_get_service_by_id(self, tenant, services):
        """Test fetching single service by ID."""
        service = services[0]
        
        result = CatalogCacheService.get_service(str(service.id), use_cache=False)
        
        assert result is not None
        assert result.id == service.id
        assert result.title == service.title
    
    def test_invalidate_products(self, tenant, products):
        """Test invalidating product cache."""
        # Cache products
        CatalogCacheService.get_products(tenant)
        
        # Verify cached
        cache_key = CatalogCacheService._get_products_cache_key(str(tenant.id), active_only=True)
        assert cache.get(cache_key) is not None
        
        # Invalidate
        CatalogCacheService.invalidate_products(str(tenant.id))
        
        # Verify cache cleared
        assert cache.get(cache_key) is None
    
    def test_invalidate_services(self, tenant, services):
        """Test invalidating service cache."""
        # Cache services
        CatalogCacheService.get_services(tenant)
        
        # Verify cached
        cache_key = CatalogCacheService._get_services_cache_key(str(tenant.id), active_only=True)
        assert cache.get(cache_key) is not None
        
        # Invalidate
        CatalogCacheService.invalidate_services(str(tenant.id))
        
        # Verify cache cleared
        assert cache.get(cache_key) is None
    
    def test_invalidate_product(self, tenant, products):
        """Test invalidating single product cache."""
        product = products[0]
        
        # Cache product
        CatalogCacheService.get_product(str(product.id))
        
        # Verify cached
        cache_key = CatalogCacheService._get_product_cache_key(str(product.id))
        assert cache.get(cache_key) is not None
        
        # Invalidate
        CatalogCacheService.invalidate_product(str(product.id))
        
        # Verify cache cleared
        assert cache.get(cache_key) is None
    
    def test_warm_cache(self, tenant, products, services):
        """Test warming cache for tenant."""
        result = CatalogCacheService.warm_cache(tenant)
        
        assert result['products'] == 3
        assert result['services'] == 2
        
        # Verify caches are populated
        products_key = CatalogCacheService._get_products_cache_key(str(tenant.id), active_only=True)
        services_key = CatalogCacheService._get_services_cache_key(str(tenant.id), active_only=True)
        
        assert cache.get(products_key) is not None
        assert cache.get(services_key) is not None
    
    def test_cache_key_generation(self, tenant):
        """Test cache key generation is consistent."""
        key1 = CatalogCacheService._get_products_cache_key(str(tenant.id), active_only=True)
        key2 = CatalogCacheService._get_products_cache_key(str(tenant.id), active_only=True)
        
        assert key1 == key2
        assert "catalog:products" in key1
        assert str(tenant.id) in key1
        assert "active" in key1
    
    def test_separate_cache_for_active_and_all(self, tenant, products):
        """Test that active and all products have separate caches."""
        # Make one product inactive
        products[0].is_active = False
        products[0].save()
        
        # Get active products
        active = CatalogCacheService.get_products(tenant, active_only=True, use_cache=False)
        
        # Get all products
        all_products = CatalogCacheService.get_products(tenant, active_only=False, use_cache=False)
        
        assert len(active) == 2
        assert len(all_products) == 3
