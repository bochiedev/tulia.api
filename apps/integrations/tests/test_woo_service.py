"""
Tests for WooCommerce integration service.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from requests.exceptions import HTTPError, Timeout, RequestException

from apps.integrations.services.woo_service import (
    WooService,
    WooServiceError,
    create_woo_service_for_tenant
)
from apps.catalog.models import Product, ProductVariant
from apps.tenants.models import Tenant, SubscriptionTier


@pytest.fixture
def subscription_tier():
    """Create a subscription tier for testing."""
    return SubscriptionTier.objects.create(
        name='Growth',
        monthly_price=99.00,
        yearly_price=950.00,
        monthly_messages=10000,
        max_products=1000,
        max_services=50
    )


@pytest.fixture
def tenant(subscription_tier):
    """Create a tenant for testing."""
    tenant = Tenant.objects.create(
        name='Test Store',
        slug='test-store',
        whatsapp_number='+14155551234',
        twilio_sid='test_sid',
        twilio_token='test_token',
        webhook_secret='test_secret',
        subscription_tier=subscription_tier
    )
    return tenant


@pytest.fixture
def woo_service():
    """Create WooService instance for testing."""
    return WooService(
        store_url='https://example.com',
        consumer_key='ck_test123',
        consumer_secret='cs_test456'
    )


@pytest.fixture
def sample_woo_product():
    """Sample WooCommerce product data."""
    return {
        'id': 123,
        'name': 'Test Product',
        'description': 'Test description',
        'price': '29.99',
        'status': 'publish',
        'sku': 'TEST-SKU-001',
        'manage_stock': True,
        'stock_quantity': 10,
        'type': 'simple',
        'permalink': 'https://example.com/product/test',
        'images': [
            {'src': 'https://example.com/image1.jpg'},
            {'src': 'https://example.com/image2.jpg'}
        ],
        'categories': [{'name': 'Electronics'}],
        'tags': [{'name': 'Featured'}]
    }


@pytest.fixture
def sample_woo_variable_product():
    """Sample WooCommerce variable product with variations."""
    return {
        'id': 456,
        'name': 'Variable Product',
        'description': 'Product with variations',
        'price': '19.99',
        'status': 'publish',
        'sku': 'VAR-PROD-001',
        'type': 'variable',
        'permalink': 'https://example.com/product/variable',
        'images': [{'src': 'https://example.com/var-image.jpg'}],
        'categories': [],
        'tags': [],
        'variations': [
            {
                'id': 789,
                'sku': 'VAR-PROD-001-RED',
                'price': '19.99',
                'manage_stock': True,
                'stock_quantity': 5,
                'attributes': [
                    {'name': 'pa_color', 'option': 'Red'}
                ],
                'permalink': 'https://example.com/product/variable?color=red'
            },
            {
                'id': 790,
                'sku': 'VAR-PROD-001-BLUE',
                'price': '24.99',
                'manage_stock': True,
                'stock_quantity': 3,
                'attributes': [
                    {'name': 'pa_color', 'option': 'Blue'}
                ],
                'permalink': 'https://example.com/product/variable?color=blue'
            }
        ]
    }


@pytest.mark.django_db
class TestWooServiceInit:
    """Test WooService initialization."""
    
    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is removed from store URL."""
        service = WooService(
            store_url='https://example.com/',
            consumer_key='key',
            consumer_secret='secret'
        )
        assert service.store_url == 'https://example.com'
        assert service.api_base == 'https://example.com/wp-json/wc/v3'
    
    def test_init_sets_auth(self):
        """Test that authentication is configured."""
        service = WooService(
            store_url='https://example.com',
            consumer_key='key',
            consumer_secret='secret'
        )
        assert service.consumer_key == 'key'
        assert service.consumer_secret == 'secret'
        assert service.auth is not None


@pytest.mark.django_db
class TestFetchProductsBatch:
    """Test fetching products from WooCommerce API."""
    
    def test_fetch_products_success(self, woo_service):
        """Test successful product fetch."""
        mock_response = Mock()
        mock_response.json.return_value = [
            {'id': 1, 'name': 'Product 1'},
            {'id': 2, 'name': 'Product 2'}
        ]
        
        with patch.object(woo_service.session, 'get', return_value=mock_response):
            products = woo_service.fetch_products_batch(page=1, per_page=10)
        
        assert len(products) == 2
        assert products[0]['id'] == 1
    
    def test_fetch_products_http_error(self, woo_service):
        """Test handling of HTTP errors."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = 'Unauthorized'
        mock_response.raise_for_status.side_effect = HTTPError(response=mock_response)
        
        with patch.object(woo_service.session, 'get', return_value=mock_response):
            with pytest.raises(WooServiceError) as exc_info:
                woo_service.fetch_products_batch()
        
        assert 'HTTP error' in str(exc_info.value)
    
    def test_fetch_products_timeout(self, woo_service):
        """Test handling of timeout errors."""
        with patch.object(woo_service.session, 'get', side_effect=Timeout()):
            with pytest.raises(WooServiceError) as exc_info:
                woo_service.fetch_products_batch()
        
        assert 'timeout' in str(exc_info.value).lower()
    
    def test_fetch_products_request_exception(self, woo_service):
        """Test handling of general request errors."""
        with patch.object(woo_service.session, 'get', side_effect=RequestException('Connection error')):
            with pytest.raises(WooServiceError) as exc_info:
                woo_service.fetch_products_batch()
        
        assert 'Request error' in str(exc_info.value)


@pytest.mark.django_db
class TestTransformProduct:
    """Test transforming WooCommerce products to Tulia format."""
    
    def test_transform_simple_product(self, woo_service, tenant, sample_woo_product):
        """Test transforming a simple product."""
        product = woo_service.transform_product(tenant, sample_woo_product)
        
        assert product.tenant == tenant
        assert product.external_source == 'woocommerce'
        assert product.external_id == '123'
        assert product.title == 'Test Product'
        assert product.description == 'Test description'
        assert product.price == Decimal('29.99')
        assert product.sku == 'TEST-SKU-001'
        assert product.stock == 10
        assert product.is_active is True
        assert len(product.images) == 2
    
    def test_transform_product_creates_default_variant(self, woo_service, tenant, sample_woo_product):
        """Test that simple products get a default variant."""
        product = woo_service.transform_product(tenant, sample_woo_product)
        
        variants = ProductVariant.objects.filter(product=product)
        assert variants.count() == 1
        assert variants.first().title == 'Default'
        assert variants.first().metadata.get('is_default') is True
    
    def test_transform_variable_product(self, woo_service, tenant, sample_woo_variable_product):
        """Test transforming a variable product with variations."""
        product = woo_service.transform_product(tenant, sample_woo_variable_product)
        
        assert product.title == 'Variable Product'
        
        variants = ProductVariant.objects.filter(product=product)
        assert variants.count() == 2
        
        # Check first variant
        red_variant = variants.filter(attrs__Color='Red').first()
        assert red_variant is not None
        assert red_variant.sku == 'VAR-PROD-001-RED'
        assert red_variant.price == Decimal('19.99')
        assert red_variant.stock == 5
    
    def test_transform_product_idempotent(self, woo_service, tenant, sample_woo_product):
        """Test that transforming same product twice updates existing record."""
        product1 = woo_service.transform_product(tenant, sample_woo_product)
        
        # Modify product data
        sample_woo_product['name'] = 'Updated Product'
        sample_woo_product['price'] = '39.99'
        
        product2 = woo_service.transform_product(tenant, sample_woo_product)
        
        # Should be same product
        assert product1.id == product2.id
        assert product2.title == 'Updated Product'
        assert product2.price == Decimal('39.99')
        
        # Should only have one product
        assert Product.objects.filter(tenant=tenant, external_id='123').count() == 1


@pytest.mark.django_db
class TestSyncProducts:
    """Test full product synchronization."""
    
    def test_sync_products_success(self, woo_service, tenant, sample_woo_product):
        """Test successful product sync."""
        mock_response = Mock()
        mock_response.json.return_value = [sample_woo_product]
        
        with patch.object(woo_service.session, 'get', return_value=mock_response):
            result = woo_service.sync_products(tenant)
        
        assert result['status'] == 'success'
        assert result['synced_count'] == 1
        assert result['error_count'] == 0
        
        # Verify product was created
        product = Product.objects.get(tenant=tenant, external_id='123')
        assert product.title == 'Test Product'
    
    def test_sync_products_marks_inactive(self, woo_service, tenant, sample_woo_product):
        """Test that products not in sync are marked inactive."""
        # Create an existing product
        old_product = Product.objects.create(
            tenant=tenant,
            external_source='woocommerce',
            external_id='999',
            title='Old Product',
            price=Decimal('10.00'),
            is_active=True
        )
        
        # Sync with only one product (not the old one)
        mock_response = Mock()
        mock_response.json.return_value = [sample_woo_product]
        
        with patch.object(woo_service.session, 'get', return_value=mock_response):
            result = woo_service.sync_products(tenant)
        
        assert result['inactive_count'] == 1
        
        # Verify old product is now inactive
        old_product.refresh_from_db()
        assert old_product.is_active is False
    
    def test_sync_products_handles_errors(self, woo_service, tenant):
        """Test that sync handles individual product errors gracefully."""
        # Create a product that will cause an error during transformation
        # by having a price that can't be converted to Decimal
        bad_product = {
            'id': 999,
            'name': 'Bad Product',
            'price': 'invalid_price',  # This will cause Decimal conversion error
            'status': 'publish',
            'type': 'simple',
            'images': [],
            'categories': [],
            'tags': []
        }
        good_product = {
            'id': 123,
            'name': 'Good Product',
            'price': '10.00',
            'status': 'publish',
            'type': 'simple',
            'images': [],
            'categories': [],
            'tags': []
        }
        
        mock_response = Mock()
        mock_response.json.return_value = [bad_product, good_product]
        
        with patch.object(woo_service.session, 'get', return_value=mock_response):
            result = woo_service.sync_products(tenant)
        
        # Should have partial success
        assert result['synced_count'] == 1  # Only good product synced
        assert result['error_count'] == 1  # Bad product failed
        assert result['status'] == 'partial'


@pytest.mark.django_db
class TestHelperMethods:
    """Test helper methods."""
    
    def test_parse_stock_managed(self, woo_service):
        """Test parsing stock when stock management is enabled."""
        item = {'manage_stock': True, 'stock_quantity': 5}
        assert woo_service._parse_stock(item) == 5
    
    def test_parse_stock_unmanaged(self, woo_service):
        """Test parsing stock when stock management is disabled."""
        item = {'manage_stock': False}
        assert woo_service._parse_stock(item) is None
    
    def test_parse_stock_negative(self, woo_service):
        """Test that negative stock is converted to zero."""
        item = {'manage_stock': True, 'stock_quantity': -5}
        assert woo_service._parse_stock(item) == 0
    
    def test_extract_images(self, woo_service):
        """Test extracting image URLs."""
        product = {
            'images': [
                {'src': 'https://example.com/img1.jpg'},
                {'src': 'https://example.com/img2.jpg'},
                {'src': ''}  # Empty src should be skipped
            ]
        }
        images = woo_service._extract_images(product)
        assert len(images) == 2
        assert 'img1.jpg' in images[0]
    
    def test_extract_attributes(self, woo_service):
        """Test extracting variation attributes."""
        variation = {
            'attributes': [
                {'name': 'pa_color', 'option': 'Red'},
                {'name': 'pa_size', 'option': 'Large'}
            ]
        }
        attrs = woo_service._extract_attributes(variation)
        assert attrs['Color'] == 'Red'
        assert attrs['Size'] == 'Large'
    
    def test_build_variant_title(self, woo_service):
        """Test building variant title from attributes."""
        variation = {
            'id': 123,
            'attributes': [
                {'name': 'pa_color', 'option': 'Red'},
                {'name': 'pa_size', 'option': 'Large'}
            ]
        }
        title = woo_service._build_variant_title(variation)
        assert 'Red' in title
        assert 'Large' in title


@pytest.mark.django_db
class TestCreateWooServiceForTenant:
    """Test factory function for creating WooService."""
    
    def test_create_service_requires_metadata_field(self, tenant):
        """Test that factory function requires metadata field on tenant."""
        # Note: The current Tenant model doesn't have a metadata field.
        # This test documents that the factory function expects it.
        # In production, WooCommerce credentials should be stored in a
        # separate IntegrationConfig model or added as a metadata JSONField.
        
        with pytest.raises(AttributeError):
            # This will fail because tenant.metadata doesn't exist
            create_woo_service_for_tenant(tenant)
