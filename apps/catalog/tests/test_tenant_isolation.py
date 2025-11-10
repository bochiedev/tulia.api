"""
Tenant isolation tests for catalog models.

Verifies that Tenant A cannot access Tenant B's products and variants.
"""
import pytest
from decimal import Decimal
from apps.tenants.models import Tenant, SubscriptionTier
from apps.catalog.models import Product, ProductVariant
from apps.catalog.services import CatalogService


@pytest.fixture
def subscription_tier(db):
    """Create a subscription tier."""
    return SubscriptionTier.objects.create(
        name='Starter',
        monthly_price=Decimal('29.00'),
        yearly_price=Decimal('290.00'),
        max_products=100
    )


@pytest.fixture
def tenant_a(db, subscription_tier):
    """Create Tenant A."""
    return Tenant.objects.create(
        name='Business A',
        slug='business-a',
        whatsapp_number='+1234567890',
        twilio_sid='test_sid_a',
        twilio_token='test_token_a',
        webhook_secret='test_secret_a',
        subscription_tier=subscription_tier,
        status='active'
    )


@pytest.fixture
def tenant_b(db, subscription_tier):
    """Create Tenant B."""
    return Tenant.objects.create(
        name='Business B',
        slug='business-b',
        whatsapp_number='+0987654321',
        twilio_sid='test_sid_b',
        twilio_token='test_token_b',
        webhook_secret='test_secret_b',
        subscription_tier=subscription_tier,
        status='active'
    )


@pytest.fixture
def product_a(tenant_a):
    """Create product for Tenant A."""
    return Product.objects.create(
        tenant=tenant_a,
        title='Product A',
        description='Product for Tenant A',
        price=Decimal('10.00'),
        currency='USD',
        is_active=True
    )


@pytest.fixture
def product_b(tenant_b):
    """Create product for Tenant B."""
    return Product.objects.create(
        tenant=tenant_b,
        title='Product B',
        description='Product for Tenant B',
        price=Decimal('20.00'),
        currency='USD',
        is_active=True
    )


@pytest.mark.django_db
class TestProductTenantIsolation:
    """Test tenant isolation for Product model."""
    
    def test_tenant_cannot_see_other_tenant_products(self, tenant_a, tenant_b, product_a, product_b):
        """Tenant A cannot see Tenant B's products."""
        # Tenant A should only see their own product
        tenant_a_products = Product.objects.for_tenant(tenant_a)
        assert tenant_a_products.count() == 1
        assert tenant_a_products.first().id == product_a.id
        
        # Tenant B should only see their own product
        tenant_b_products = Product.objects.for_tenant(tenant_b)
        assert tenant_b_products.count() == 1
        assert tenant_b_products.first().id == product_b.id
    
    def test_search_products_tenant_scoped(self, tenant_a, tenant_b, product_a, product_b):
        """Search is tenant-scoped."""
        # Search for "Product" should only return tenant's own products
        tenant_a_results = CatalogService.search_products(tenant_a, query='Product')
        assert tenant_a_results.count() == 1
        assert tenant_a_results.first().id == product_a.id
        
        tenant_b_results = CatalogService.search_products(tenant_b, query='Product')
        assert tenant_b_results.count() == 1
        assert tenant_b_results.first().id == product_b.id
    
    def test_get_product_tenant_scoped(self, tenant_a, tenant_b, product_a, product_b):
        """Get product is tenant-scoped."""
        # Tenant A can get their own product
        result = CatalogService.get_product(tenant_a, product_a.id)
        assert result is not None
        assert result.id == product_a.id
        
        # Tenant A cannot get Tenant B's product
        result = CatalogService.get_product(tenant_a, product_b.id)
        assert result is None
        
        # Tenant B can get their own product
        result = CatalogService.get_product(tenant_b, product_b.id)
        assert result is not None
        assert result.id == product_b.id
        
        # Tenant B cannot get Tenant A's product
        result = CatalogService.get_product(tenant_b, product_a.id)
        assert result is None
    
    def test_update_product_tenant_scoped(self, tenant_a, tenant_b, product_a, product_b):
        """Update product is tenant-scoped."""
        # Tenant A can update their own product
        updated = CatalogService.update_product(
            tenant_a,
            product_a.id,
            {'title': 'Updated Product A'}
        )
        assert updated is not None
        assert updated.title == 'Updated Product A'
        
        # Tenant A cannot update Tenant B's product
        updated = CatalogService.update_product(
            tenant_a,
            product_b.id,
            {'title': 'Hacked Product B'}
        )
        assert updated is None
        
        # Verify Tenant B's product was not modified
        product_b.refresh_from_db()
        assert product_b.title == 'Product B'
    
    def test_delete_product_tenant_scoped(self, tenant_a, tenant_b, product_a, product_b):
        """Delete product is tenant-scoped."""
        # Tenant A can delete their own product
        deleted = CatalogService.delete_product(tenant_a, product_a.id)
        assert deleted is True
        
        # Tenant A cannot delete Tenant B's product
        deleted = CatalogService.delete_product(tenant_a, product_b.id)
        assert deleted is False
        
        # Verify Tenant B's product still exists
        assert Product.objects.filter(id=product_b.id).exists()
    
    def test_external_id_unique_per_tenant(self, tenant_a, tenant_b):
        """Same external_id can exist for different tenants."""
        # Create products with same external_id for different tenants
        product_a = Product.objects.create(
            tenant=tenant_a,
            external_source='woocommerce',
            external_id='123',
            title='Product A',
            price=Decimal('10.00')
        )
        
        product_b = Product.objects.create(
            tenant=tenant_b,
            external_source='woocommerce',
            external_id='123',  # Same external_id
            title='Product B',
            price=Decimal('20.00')
        )
        
        # Both should exist
        assert Product.objects.filter(id=product_a.id).exists()
        assert Product.objects.filter(id=product_b.id).exists()
        
        # Get by external_id should be tenant-scoped
        result_a = CatalogService.get_product_by_external_id(
            tenant_a, 'woocommerce', '123'
        )
        assert result_a.id == product_a.id
        
        result_b = CatalogService.get_product_by_external_id(
            tenant_b, 'woocommerce', '123'
        )
        assert result_b.id == product_b.id


@pytest.mark.django_db
class TestProductVariantTenantIsolation:
    """Test tenant isolation for ProductVariant model."""
    
    def test_variant_inherits_tenant_from_product(self, tenant_a, tenant_b, product_a, product_b):
        """Variants inherit tenant isolation from their product."""
        # Create variants
        variant_a = ProductVariant.objects.create(
            product=product_a,
            title='Variant A',
            price=Decimal('15.00')
        )
        
        variant_b = ProductVariant.objects.create(
            product=product_b,
            title='Variant B',
            price=Decimal('25.00')
        )
        
        # Tenant A can only see their variant
        tenant_a_variants = ProductVariant.objects.for_tenant(tenant_a)
        assert tenant_a_variants.count() == 1
        assert tenant_a_variants.first().id == variant_a.id
        
        # Tenant B can only see their variant
        tenant_b_variants = ProductVariant.objects.for_tenant(tenant_b)
        assert tenant_b_variants.count() == 1
        assert tenant_b_variants.first().id == variant_b.id
    
    def test_get_variant_tenant_scoped(self, tenant_a, tenant_b, product_a, product_b):
        """Get variant is tenant-scoped."""
        variant_a = ProductVariant.objects.create(
            product=product_a,
            title='Variant A',
            price=Decimal('15.00')
        )
        
        variant_b = ProductVariant.objects.create(
            product=product_b,
            title='Variant B',
            price=Decimal('25.00')
        )
        
        # Tenant A can get their own variant
        result = CatalogService.get_variant(tenant_a, variant_a.id)
        assert result is not None
        assert result.id == variant_a.id
        
        # Tenant A cannot get Tenant B's variant
        result = CatalogService.get_variant(tenant_a, variant_b.id)
        assert result is None
    
    def test_create_variant_tenant_scoped(self, tenant_a, tenant_b, product_a, product_b):
        """Create variant is tenant-scoped."""
        # Tenant A can create variant for their product
        variant = CatalogService.create_variant(
            tenant_a,
            product_a.id,
            {'title': 'New Variant A', 'price': Decimal('12.00')}
        )
        assert variant is not None
        assert variant.product.id == product_a.id
        
        # Tenant A cannot create variant for Tenant B's product
        variant = CatalogService.create_variant(
            tenant_a,
            product_b.id,
            {'title': 'Hacked Variant B', 'price': Decimal('1.00')}
        )
        assert variant is None
        
        # Verify no variant was created for Tenant B's product
        assert ProductVariant.objects.filter(product=product_b).count() == 0
    
    def test_update_variant_tenant_scoped(self, tenant_a, tenant_b, product_a, product_b):
        """Update variant is tenant-scoped."""
        variant_a = ProductVariant.objects.create(
            product=product_a,
            title='Variant A',
            price=Decimal('15.00')
        )
        
        variant_b = ProductVariant.objects.create(
            product=product_b,
            title='Variant B',
            price=Decimal('25.00')
        )
        
        # Tenant A can update their own variant
        updated = CatalogService.update_variant(
            tenant_a,
            variant_a.id,
            {'title': 'Updated Variant A'}
        )
        assert updated is not None
        assert updated.title == 'Updated Variant A'
        
        # Tenant A cannot update Tenant B's variant
        updated = CatalogService.update_variant(
            tenant_a,
            variant_b.id,
            {'title': 'Hacked Variant B'}
        )
        assert updated is None
        
        # Verify Tenant B's variant was not modified
        variant_b.refresh_from_db()
        assert variant_b.title == 'Variant B'
    
    def test_delete_variant_tenant_scoped(self, tenant_a, tenant_b, product_a, product_b):
        """Delete variant is tenant-scoped."""
        variant_a = ProductVariant.objects.create(
            product=product_a,
            title='Variant A',
            price=Decimal('15.00')
        )
        
        variant_b = ProductVariant.objects.create(
            product=product_b,
            title='Variant B',
            price=Decimal('25.00')
        )
        
        # Tenant A can delete their own variant
        deleted = CatalogService.delete_variant(tenant_a, variant_a.id)
        assert deleted is True
        
        # Tenant A cannot delete Tenant B's variant
        deleted = CatalogService.delete_variant(tenant_a, variant_b.id)
        assert deleted is False
        
        # Verify Tenant B's variant still exists
        assert ProductVariant.objects.filter(id=variant_b.id).exists()


@pytest.mark.django_db
class TestBulkOperationsTenantIsolation:
    """Test tenant isolation for bulk operations."""
    
    def test_bulk_upsert_tenant_scoped(self, tenant_a, tenant_b):
        """Bulk upsert only affects the specified tenant."""
        # Create initial products for both tenants
        Product.objects.create(
            tenant=tenant_a,
            external_source='woocommerce',
            external_id='100',
            title='Product A1',
            price=Decimal('10.00')
        )
        
        Product.objects.create(
            tenant=tenant_b,
            external_source='woocommerce',
            external_id='200',
            title='Product B1',
            price=Decimal('20.00')
        )
        
        # Bulk upsert for Tenant A
        result = CatalogService.bulk_upsert_products(
            tenant_a,
            [
                {
                    'external_id': '100',
                    'title': 'Updated Product A1',
                    'price': Decimal('15.00')
                },
                {
                    'external_id': '101',
                    'title': 'New Product A2',
                    'price': Decimal('12.00')
                }
            ],
            'woocommerce'
        )
        
        assert result['updated'] == 1
        assert result['created'] == 1
        
        # Verify Tenant A has 2 products
        assert Product.objects.for_tenant(tenant_a).count() == 2
        
        # Verify Tenant B still has only 1 product (unchanged)
        assert Product.objects.for_tenant(tenant_b).count() == 1
        tenant_b_product = Product.objects.for_tenant(tenant_b).first()
        assert tenant_b_product.title == 'Product B1'
