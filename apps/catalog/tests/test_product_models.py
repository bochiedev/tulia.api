"""
Tests for Product and ProductVariant models and managers.

Tests manager methods, QuerySet chaining, and model behavior.
"""
import pytest
from decimal import Decimal
from apps.catalog.models import Product, ProductVariant
from apps.tenants.models import Tenant


@pytest.fixture
def tenant(db):
    """Create a test tenant."""
    return Tenant.objects.create(
        name="Test Store",
        slug="test-store",
        whatsapp_number="+1234567890",
        timezone="UTC"
    )


@pytest.fixture
def other_tenant(db):
    """Create another test tenant for isolation tests."""
    return Tenant.objects.create(
        name="Other Store",
        slug="other-store",
        timezone="UTC",
        whatsapp_number="+1234567891"  # Different from default
    )


@pytest.fixture
def active_product(tenant):
    """Create an active product."""
    return Product.objects.create(
        tenant=tenant,
        title="Active Product",
        description="An active product",
        price=Decimal("10.00"),
        currency="USD",
        is_active=True,
        stock=10
    )


@pytest.fixture
def inactive_product(tenant):
    """Create an inactive product."""
    return Product.objects.create(
        tenant=tenant,
        title="Inactive Product",
        description="An inactive product",
        price=Decimal("20.00"),
        currency="USD",
        is_active=False,
        stock=5
    )


@pytest.mark.django_db
class TestProductManager:
    """Test Product manager methods."""
    
    def test_for_tenant(self, tenant, other_tenant, active_product):
        """Test for_tenant filters by tenant."""
        # Create product for other tenant
        Product.objects.create(
            tenant=other_tenant,
            title="Other Product",
            price=Decimal("15.00"),
            currency="USD"
        )
        
        # Query for tenant
        products = Product.objects.for_tenant(tenant)
        
        assert products.count() == 1
        assert products.first() == active_product
    
    def test_active(self, tenant, active_product, inactive_product):
        """Test active filters by is_active."""
        # Query active products (WARNING: not tenant-scoped)
        products = Product.objects.active()
        
        # Should include active from all tenants
        assert active_product in products
        assert inactive_product not in products
    
    def test_for_tenant_active_chaining(self, tenant, active_product, inactive_product):
        """Test chaining for_tenant and active."""
        # This is the critical test that was failing!
        products = Product.objects.for_tenant(tenant).active()
        
        assert products.count() == 1
        assert products.first() == active_product
        assert inactive_product not in products
    
    def test_active_for_tenant_chaining(self, tenant, active_product, inactive_product):
        """Test chaining active and for_tenant (reverse order)."""
        products = Product.objects.active().for_tenant(tenant)
        
        assert products.count() == 1
        assert products.first() == active_product
    
    def test_search(self, tenant):
        """Test search method."""
        Product.objects.create(
            tenant=tenant,
            title="Red Shirt",
            description="A red shirt",
            price=Decimal("25.00"),
            currency="USD",
            is_active=True
        )
        Product.objects.create(
            tenant=tenant,
            title="Blue Pants",
            description="Blue denim pants",
            price=Decimal("50.00"),
            currency="USD",
            is_active=True
        )
        Product.objects.create(
            tenant=tenant,
            title="Red Hat",
            description="A red hat",
            price=Decimal("15.00"),
            currency="USD",
            is_active=False  # Inactive, should not appear
        )
        
        # Search for "red"
        products = Product.objects.search(tenant, "red")
        
        assert products.count() == 1  # Only active red shirt
        assert "Red Shirt" in [p.title for p in products]
    
    def test_by_external_id(self, tenant):
        """Test by_external_id method."""
        product = Product.objects.create(
            tenant=tenant,
            title="WooCommerce Product",
            price=Decimal("30.00"),
            currency="USD",
            external_source="woocommerce",
            external_id="123"
        )
        
        found = Product.objects.by_external_id(tenant, "woocommerce", "123")
        
        assert found == product
    
    def test_by_external_id_not_found(self, tenant):
        """Test by_external_id returns None when not found."""
        found = Product.objects.by_external_id(tenant, "woocommerce", "999")
        
        assert found is None


@pytest.mark.django_db
class TestProductVariantManager:
    """Test ProductVariant manager methods."""
    
    def test_for_product(self, tenant, active_product):
        """Test for_product filters by product."""
        variant1 = ProductVariant.objects.create(
            product=active_product,
            title="Small",
            sku="PROD-S",
            stock=5
        )
        variant2 = ProductVariant.objects.create(
            product=active_product,
            title="Large",
            sku="PROD-L",
            stock=10
        )
        
        # Create another product with variant
        other_product = Product.objects.create(
            tenant=tenant,
            title="Other Product",
            price=Decimal("20.00"),
            currency="USD"
        )
        ProductVariant.objects.create(
            product=other_product,
            title="Medium",
            sku="OTHER-M",
            stock=3
        )
        
        variants = ProductVariant.objects.for_product(active_product)
        
        assert variants.count() == 2
        assert variant1 in variants
        assert variant2 in variants
    
    def test_for_tenant(self, tenant, other_tenant, active_product):
        """Test for_tenant filters by tenant."""
        variant1 = ProductVariant.objects.create(
            product=active_product,
            title="Small",
            sku="PROD-S"
        )
        
        # Create product and variant for other tenant
        other_product = Product.objects.create(
            tenant=other_tenant,
            title="Other Product",
            price=Decimal("20.00"),
            currency="USD"
        )
        ProductVariant.objects.create(
            product=other_product,
            title="Medium",
            sku="OTHER-M"
        )
        
        variants = ProductVariant.objects.for_tenant(tenant)
        
        assert variants.count() == 1
        assert variants.first() == variant1
    
    def test_in_stock(self, tenant, active_product):
        """Test in_stock filters variants with stock."""
        in_stock = ProductVariant.objects.create(
            product=active_product,
            title="In Stock",
            sku="IN-STOCK",
            stock=5
        )
        out_of_stock = ProductVariant.objects.create(
            product=active_product,
            title="Out of Stock",
            sku="OUT-STOCK",
            stock=0
        )
        unlimited = ProductVariant.objects.create(
            product=active_product,
            title="Unlimited",
            sku="UNLIMITED",
            stock=None
        )
        
        variants = ProductVariant.objects.in_stock()
        
        assert in_stock in variants
        assert unlimited in variants
        assert out_of_stock not in variants
    
    def test_for_tenant_in_stock_chaining(self, tenant, other_tenant, active_product):
        """Test chaining for_tenant and in_stock."""
        # Create variants for tenant
        in_stock = ProductVariant.objects.create(
            product=active_product,
            title="In Stock",
            sku="IN-STOCK",
            stock=5
        )
        out_of_stock = ProductVariant.objects.create(
            product=active_product,
            title="Out of Stock",
            sku="OUT-STOCK",
            stock=0
        )
        
        # Create variant for other tenant
        other_product = Product.objects.create(
            tenant=other_tenant,
            title="Other Product",
            price=Decimal("20.00"),
            currency="USD"
        )
        ProductVariant.objects.create(
            product=other_product,
            title="Other In Stock",
            sku="OTHER-IN",
            stock=10
        )
        
        # Chain for_tenant and in_stock
        variants = ProductVariant.objects.for_tenant(tenant).in_stock()
        
        assert variants.count() == 1
        assert variants.first() == in_stock
    
    def test_by_sku(self, tenant, active_product):
        """Test by_sku method."""
        variant = ProductVariant.objects.create(
            product=active_product,
            title="Small",
            sku="PROD-S"
        )
        
        found = ProductVariant.objects.by_sku(tenant, "PROD-S")
        
        assert found == variant
    
    def test_by_sku_not_found(self, tenant):
        """Test by_sku returns None when not found."""
        found = ProductVariant.objects.by_sku(tenant, "NONEXISTENT")
        
        assert found is None


@pytest.mark.django_db
class TestProductModel:
    """Test Product model methods."""
    
    def test_has_stock_with_stock(self, active_product):
        """Test has_stock with available stock."""
        assert active_product.has_stock(5) is True
        assert active_product.has_stock(10) is True
        assert active_product.has_stock(11) is False
    
    def test_has_stock_unlimited(self, tenant):
        """Test has_stock with unlimited stock."""
        product = Product.objects.create(
            tenant=tenant,
            title="Unlimited Product",
            price=Decimal("10.00"),
            currency="USD",
            stock=None
        )
        
        assert product.has_stock(1000000) is True
    
    def test_reduce_stock(self, active_product):
        """Test reduce_stock method."""
        initial_stock = active_product.stock
        active_product.reduce_stock(3)
        
        active_product.refresh_from_db()
        assert active_product.stock == initial_stock - 3
    
    def test_increase_stock(self, active_product):
        """Test increase_stock method."""
        initial_stock = active_product.stock
        active_product.increase_stock(5)
        
        active_product.refresh_from_db()
        assert active_product.stock == initial_stock + 5
    
    def test_is_in_stock(self, active_product, inactive_product):
        """Test is_in_stock property."""
        assert active_product.is_in_stock is True
        
        # Set stock to 0
        active_product.stock = 0
        active_product.save()
        assert active_product.is_in_stock is False
