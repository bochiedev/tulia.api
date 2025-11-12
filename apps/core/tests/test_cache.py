"""
Tests for caching utilities.
"""
import pytest
from django.core.cache import cache
from apps.core.cache import (
    CacheService, CacheKeys, CacheTTL, TenantCacheInvalidator
)


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before and after each test."""
    cache.clear()
    yield
    cache.clear()


class TestCacheService:
    """Test CacheService basic operations."""
    
    def test_get_set(self):
        """Test basic get and set operations."""
        key = "test:key"
        value = {"data": "test"}
        
        # Set value
        result = CacheService.set(key, value, ttl=60)
        assert result is True
        
        # Get value
        cached_value = CacheService.get(key)
        assert cached_value == value
    
    def test_get_default(self):
        """Test get with default value."""
        key = "nonexistent:key"
        default = "default_value"
        
        result = CacheService.get(key, default=default)
        assert result == default
    
    def test_delete(self):
        """Test delete operation."""
        key = "test:key"
        value = "test_value"
        
        # Set and verify
        CacheService.set(key, value)
        assert CacheService.get(key) == value
        
        # Delete and verify
        result = CacheService.delete(key)
        assert result is True
        assert CacheService.get(key) is None
    
    def test_get_or_set(self):
        """Test get_or_set operation."""
        key = "test:key"
        value = "computed_value"
        
        # First call should compute
        result = CacheService.get_or_set(
            key,
            lambda: value,
            ttl=60
        )
        assert result == value
        
        # Second call should use cache
        result = CacheService.get_or_set(
            key,
            lambda: "different_value",
            ttl=60
        )
        assert result == value  # Should still be original value


class TestCacheKeys:
    """Test cache key formatting."""
    
    def test_format_tenant_config(self):
        """Test tenant config key formatting."""
        tenant_id = "123e4567-e89b-12d3-a456-426614174000"
        key = CacheKeys.format(CacheKeys.TENANT_CONFIG, tenant_id=tenant_id)
        assert key == f"tenant:config:{tenant_id}"
    
    def test_format_product_detail(self):
        """Test product detail key formatting."""
        tenant_id = "tenant-123"
        product_id = "product-456"
        key = CacheKeys.format(
            CacheKeys.PRODUCT_DETAIL,
            tenant_id=tenant_id,
            product_id=product_id
        )
        assert key == f"product:detail:{tenant_id}:{product_id}"
    
    def test_format_customer_preferences(self):
        """Test customer preferences key formatting."""
        tenant_id = "tenant-123"
        customer_id = "customer-456"
        key = CacheKeys.format(
            CacheKeys.CUSTOMER_PREFERENCES,
            tenant_id=tenant_id,
            customer_id=customer_id
        )
        assert key == f"customer:preferences:{tenant_id}:{customer_id}"


class TestTenantCacheInvalidator:
    """Test cache invalidation utilities."""
    
    def test_invalidate_tenant_config(self):
        """Test tenant config cache invalidation."""
        tenant_id = "tenant-123"
        
        # Set some cache values
        config_key = CacheKeys.format(CacheKeys.TENANT_CONFIG, tenant_id=tenant_id)
        settings_key = CacheKeys.format(CacheKeys.TENANT_SETTINGS, tenant_id=tenant_id)
        
        CacheService.set(config_key, {"config": "data"})
        CacheService.set(settings_key, {"settings": "data"})
        
        # Verify they exist
        assert CacheService.get(config_key) is not None
        assert CacheService.get(settings_key) is not None
        
        # Invalidate
        TenantCacheInvalidator.invalidate_tenant_config(tenant_id)
        
        # Verify they're gone
        assert CacheService.get(config_key) is None
        assert CacheService.get(settings_key) is None
    
    def test_invalidate_product_catalog(self):
        """Test product catalog cache invalidation."""
        tenant_id = "tenant-123"
        product_id = "product-456"
        
        # Set product cache
        product_key = CacheKeys.format(
            CacheKeys.PRODUCT_DETAIL,
            tenant_id=tenant_id,
            product_id=product_id
        )
        CacheService.set(product_key, {"product": "data"})
        
        # Verify it exists
        assert CacheService.get(product_key) is not None
        
        # Invalidate specific product
        TenantCacheInvalidator.invalidate_product_catalog(tenant_id, product_id)
        
        # Verify it's gone
        assert CacheService.get(product_key) is None
    
    def test_invalidate_customer_preferences(self):
        """Test customer preferences cache invalidation."""
        tenant_id = "tenant-123"
        customer_id = "customer-456"
        
        # Set preferences cache
        prefs_key = CacheKeys.format(
            CacheKeys.CUSTOMER_PREFERENCES,
            tenant_id=tenant_id,
            customer_id=customer_id
        )
        CacheService.set(prefs_key, {"preferences": "data"})
        
        # Verify it exists
        assert CacheService.get(prefs_key) is not None
        
        # Invalidate
        TenantCacheInvalidator.invalidate_customer_preferences(tenant_id, customer_id)
        
        # Verify it's gone
        assert CacheService.get(prefs_key) is None
    
    def test_invalidate_user_scopes(self):
        """Test user scopes cache invalidation."""
        tenant_id = "tenant-123"
        user_id = "user-456"
        
        # Set scopes cache
        scopes_key = CacheKeys.format(
            CacheKeys.USER_SCOPES,
            tenant_id=tenant_id,
            user_id=user_id
        )
        CacheService.set(scopes_key, {"catalog:view", "catalog:edit"})
        
        # Verify it exists
        assert CacheService.get(scopes_key) is not None
        
        # Invalidate
        TenantCacheInvalidator.invalidate_user_scopes(tenant_id, user_id)
        
        # Verify it's gone
        assert CacheService.get(scopes_key) is None


class TestCacheTTL:
    """Test TTL constants are reasonable."""
    
    def test_ttl_values(self):
        """Test that TTL values are within reasonable ranges."""
        assert CacheTTL.TENANT_CONFIG == 3600  # 1 hour
        assert CacheTTL.CATALOG == 900  # 15 minutes
        assert CacheTTL.CUSTOMER_PREFERENCES == 300  # 5 minutes
        assert CacheTTL.AVAILABILITY == 3600  # 1 hour
        assert CacheTTL.RBAC_SCOPES == 300  # 5 minutes
        
        # All TTLs should be positive
        assert all([
            CacheTTL.TENANT_CONFIG > 0,
            CacheTTL.CATALOG > 0,
            CacheTTL.CUSTOMER_PREFERENCES > 0,
            CacheTTL.AVAILABILITY > 0,
            CacheTTL.RBAC_SCOPES > 0,
        ])
