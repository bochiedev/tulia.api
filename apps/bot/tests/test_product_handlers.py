"""
Tests for product browsing and selection handlers.

Tests the deterministic product handlers for the sales orchestration refactor.
"""
import pytest
from decimal import Decimal
from django.utils import timezone

from apps.bot.services.handlers.product_handlers import (
    handle_browse_products,
    handle_product_details,
    handle_place_order,
)
from apps.bot.services.intent_detection_engine import IntentResult, Intent
from apps.bot.models import ConversationContext
from apps.catalog.models import Product
from apps.tenants.models import Tenant, Customer
from apps.messaging.models import Conversation


@pytest.fixture
def tenant(db):
    """Create test tenant."""
    return Tenant.objects.create(
        name="Test Store",
        slug="test-store",
        status="active"
    )


@pytest.fixture
def customer(db, tenant):
    """Create test customer."""
    return Customer.objects.create(
        tenant=tenant,
        phone_e164="+254712345678",
        name="Test Customer"
    )


@pytest.fixture
def conversation(db, tenant, customer):
    """Create test conversation."""
    return Conversation.objects.create(
        tenant=tenant,
        customer=customer,
        status="open"
    )


@pytest.fixture
def context(db, conversation):
    """Create conversation context."""
    return ConversationContext.objects.create(
        conversation=conversation
    )


@pytest.fixture
def products(db, tenant):
    """Create test products."""
    products = []
    for i in range(5):
        product = Product.objects.create(
            tenant=tenant,
            title=f"Product {i+1}",
            description=f"Description for product {i+1}",
            price=Decimal(f"{(i+1)*10}.00"),
            currency="KES",
            stock=10,
            is_active=True
        )
        products.append(product)
    return products


@pytest.mark.django_db
class TestHandleBrowseProducts:
    """Test handle_browse_products function."""
    
    def test_browse_products_returns_list(self, tenant, customer, context, products):
        """Test that browsing products returns a product list."""
        intent_result = IntentResult(
            intent=Intent.BROWSE_PRODUCTS,
            confidence=0.95,
            slots={},
            language=['en']
        )
        
        action = handle_browse_products(intent_result, context, tenant, customer)
        
        assert action.type == "PRODUCT_CARDS"
        assert 'products' in action.rich_payload
        assert len(action.rich_payload['products']) == 5
        assert action.new_context['current_flow'] == 'browsing_products'
    
    def test_browse_products_limits_to_10(self, tenant, customer, context):
        """Test that product list is limited to 10 items (Requirement 5.2)."""
        # Create 15 products
        for i in range(15):
            Product.objects.create(
                tenant=tenant,
                title=f"Product {i+1}",
                price=Decimal("10.00"),
                currency="KES",
                stock=10,
                is_active=True
            )
        
        intent_result = IntentResult(
            intent=Intent.BROWSE_PRODUCTS,
            confidence=0.95,
            slots={},
            language=['en']
        )
        
        action = handle_browse_products(intent_result, context, tenant, customer)
        
        assert len(action.rich_payload['products']) == 10
    
    def test_browse_products_filters_by_category(self, tenant, customer, context):
        """Test filtering products by category."""
        # Create products with different categories
        Product.objects.create(
            tenant=tenant,
            title="Laptop HP",
            description="Gaming laptop",
            price=Decimal("50000.00"),
            currency="KES",
            stock=5,
            is_active=True
        )
        Product.objects.create(
            tenant=tenant,
            title="Phone Samsung",
            description="Smartphone",
            price=Decimal("30000.00"),
            currency="KES",
            stock=10,
            is_active=True
        )
        
        intent_result = IntentResult(
            intent=Intent.BROWSE_PRODUCTS,
            confidence=0.95,
            slots={'category': 'laptop'},
            language=['en']
        )
        
        action = handle_browse_products(intent_result, context, tenant, customer)
        
        assert len(action.rich_payload['products']) == 1
        assert 'Laptop' in action.rich_payload['products'][0]['title']
    
    def test_browse_products_filters_by_budget(self, tenant, customer, context, products):
        """Test filtering products by budget."""
        intent_result = IntentResult(
            intent=Intent.BROWSE_PRODUCTS,
            confidence=0.95,
            slots={'budget': '25'},
            language=['en']
        )
        
        action = handle_browse_products(intent_result, context, tenant, customer)
        
        # Should only return products with price <= 25
        for product in action.rich_payload['products']:
            assert product['price'] <= 25
    
    def test_browse_products_empty_catalog(self, tenant, customer, context):
        """Test handling empty catalog (Requirement 5.5)."""
        intent_result = IntentResult(
            intent=Intent.BROWSE_PRODUCTS,
            confidence=0.95,
            slots={},
            language=['en']
        )
        
        action = handle_browse_products(intent_result, context, tenant, customer)
        
        assert action.type == "TEXT"
        assert "don't have any products" in action.text
        assert action.new_context['current_flow'] == 'empty_catalog'
    
    def test_browse_products_stores_menu_context(self, tenant, customer, context, products):
        """Test that last_menu is stored in context (Requirement 5.3)."""
        intent_result = IntentResult(
            intent=Intent.BROWSE_PRODUCTS,
            confidence=0.95,
            slots={},
            language=['en']
        )
        
        action = handle_browse_products(intent_result, context, tenant, customer)
        
        assert 'last_menu' in action.new_context
        assert action.new_context['last_menu']['type'] == 'products'
        assert len(action.new_context['last_menu']['items']) == 5
    
    def test_browse_products_tenant_isolation(self, tenant, customer, context, products):
        """Test that products are tenant-scoped (Requirement 4.3)."""
        # Create another tenant with products
        other_tenant = Tenant.objects.create(
            name="Other Store",
            slug="other-store",
            status="active",
            whatsapp_number="+254700000000"  # Different WhatsApp number
        )
        Product.objects.create(
            tenant=other_tenant,
            title="Other Product",
            price=Decimal("100.00"),
            currency="KES",
            stock=10,
            is_active=True
        )
        
        intent_result = IntentResult(
            intent=Intent.BROWSE_PRODUCTS,
            confidence=0.95,
            slots={},
            language=['en']
        )
        
        action = handle_browse_products(intent_result, context, tenant, customer)
        
        # Should only return products from the correct tenant
        assert len(action.rich_payload['products']) == 5
        for product in action.rich_payload['products']:
            assert 'Other Product' not in product['title']


@pytest.mark.django_db
class TestHandleProductDetails:
    """Test handle_product_details function."""
    
    def test_product_details_shows_info(self, tenant, customer, context, products):
        """Test showing product details."""
        product = products[0]
        
        intent_result = IntentResult(
            intent=Intent.BROWSE_PRODUCTS,
            confidence=0.95,
            slots={'product_id': str(product.id)},
            language=['en']
        )
        
        action = handle_product_details(intent_result, context, tenant, customer)
        
        assert action.type == "BUTTONS"
        assert product.title in action.text
        assert str(product.price) in action.text
    
    def test_product_details_not_found(self, tenant, customer, context):
        """Test handling product not found."""
        intent_result = IntentResult(
            intent=Intent.BROWSE_PRODUCTS,
            confidence=0.95,
            slots={'product_id': '00000000-0000-0000-0000-000000000000'},
            language=['en']
        )
        
        action = handle_product_details(intent_result, context, tenant, customer)
        
        assert action.type == "TEXT"
        assert "no longer available" in action.text


@pytest.mark.django_db
class TestHandlePlaceOrder:
    """Test handle_place_order function."""
    
    def test_place_order_creates_summary(self, tenant, customer, context, products):
        """Test creating order summary."""
        product = products[0]
        context.set_entity('product_id', str(product.id))
        context.save()
        
        intent_result = IntentResult(
            intent=Intent.PLACE_ORDER,
            confidence=0.95,
            slots={'quantity': 2},
            language=['en']
        )
        
        action = handle_place_order(intent_result, context, tenant, customer)
        
        assert action.type == "BUTTONS"
        assert product.title in action.text
        assert action.new_context['current_flow'] == 'payment'
        assert 'order_id' in action.new_context['entities']
        assert 'total' in action.new_context['entities']
        assert action.new_context['entities']['currency'] == 'KES'
    
    def test_place_order_checks_stock(self, tenant, customer, context, products):
        """Test stock validation."""
        product = products[0]
        product.stock = 2
        product.save()
        
        context.set_entity('product_id', str(product.id))
        context.save()
        
        intent_result = IntentResult(
            intent=Intent.PLACE_ORDER,
            confidence=0.95,
            slots={'quantity': 5},  # More than available
            language=['en']
        )
        
        action = handle_place_order(intent_result, context, tenant, customer)
        
        assert "only have 2 units" in action.text
        assert action.new_context['current_flow'] == 'checkout'
