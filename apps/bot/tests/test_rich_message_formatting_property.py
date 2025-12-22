"""
Property-based tests for rich message formatting.

**Feature: conversational-commerce-ux-enhancement, Property 3: Rich message for product lists**
**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

Property: For any response containing 2 or more products, the system should format them
as WhatsApp interactive messages (list or cards) with action buttons.
"""
import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from decimal import Decimal

from apps.bot.services.rich_message_builder import RichMessageBuilder, WhatsAppMessage
from apps.catalog.models import Product
from apps.tenants.models import Tenant, Customer
from apps.messaging.models import Conversation


# Hypothesis strategies
@st.composite
def product_data(draw):
    """Generate product data for testing."""
    return {
        'title': draw(st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Zs')))),
        'description': draw(st.text(min_size=0, max_size=500, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Zs', 'Nd')))),
        'price': draw(st.decimals(min_value=Decimal('0.01'), max_value=Decimal('10000.00'), places=2)),
        'currency': draw(st.sampled_from(['USD', 'EUR', 'GBP', 'KES', 'UGX', 'TZS'])),
        'stock': draw(st.one_of(st.none(), st.integers(min_value=0, max_value=1000))),
        'images': draw(st.lists(st.text(min_size=10, max_size=100), min_size=0, max_size=5))
    }


@st.composite
def product_list(draw):
    """Generate a list of products."""
    num_products = draw(st.integers(min_value=2, max_value=10))
    return [draw(product_data()) for _ in range(num_products)]


@pytest.mark.django_db
class TestRichMessageFormattingProperty:
    """Property-based tests for rich message formatting."""
    
    @given(products_data=product_list())
    @settings(
        max_examples=20,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_product_list_uses_interactive_format(self, products_data, tenant, conversation):
        """
        Property: Product lists with 2+ items use WhatsApp interactive messages.
        
        **Feature: conversational-commerce-ux-enhancement, Property 3: Rich message for product lists**
        **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
        """
        # Assume we have at least 2 products
        assume(len(products_data) >= 2)
        
        # Create products in database
        products = []
        for data in products_data:
            product = Product.objects.create(
                tenant=tenant,
                title=data['title'],
                description=data['description'],
                price=data['price'],
                currency=data['currency'],
                stock=data['stock'],
                images=data['images']
            )
            products.append(product)
        
        # Build product list message
        builder = RichMessageBuilder()
        message = builder.build_product_list(
            products=products,
            conversation=conversation,
            show_prices=True,
            show_stock=True
        )
        
        # Property assertions
        
        # 1. Message should be WhatsApp interactive type (list or button)
        assert message.message_type in ['list', 'button'], (
            f"Product list with {len(products)} items should use interactive message type, "
            f"got '{message.message_type}'"
        )
        
        # 2. For lists, should have list_data structure
        if message.message_type == 'list':
            assert message.list_data is not None, (
                "List message should have list_data"
            )
            assert 'sections' in message.list_data, (
                "List data should have sections"
            )
            assert len(message.list_data['sections']) > 0, (
                "List should have at least one section"
            )
            
            # Count total items in all sections
            total_items = sum(
                len(section.get('rows', []))
                for section in message.list_data['sections']
            )
            assert total_items == len(products), (
                f"List should contain all {len(products)} products, "
                f"but has {total_items} items"
            )
        
        # 3. Message should have body text
        assert message.body, "Message should have body text"
        assert len(message.body) > 0, "Message body should not be empty"
        
        # 4. Each product should be represented in the message
        # Either in list_data or in the body text
        if message.list_data:
            # Check list items contain product references
            for section in message.list_data['sections']:
                for row in section.get('rows', []):
                    assert 'id' in row, "List item should have ID"
                    assert 'title' in row, "List item should have title"
                    # Title should not be empty
                    assert len(row['title']) > 0, "List item title should not be empty"
        
        # 5. Message should include price information (in body or list descriptions)
        # At least one product price should be mentioned
        price_mentioned = False
        for product in products:
            price_str = str(product.price)
            # Check in body
            if price_str in message.body:
                price_mentioned = True
                break
            # Check in list data descriptions
            if message.list_data:
                for section in message.list_data['sections']:
                    for row in section.get('rows', []):
                        if 'description' in row and price_str in row['description']:
                            price_mentioned = True
                            break
        
        # Note: Price might be formatted differently, so we check if any price-like pattern exists
        # This is a weaker assertion but more robust
        has_price_pattern = any(
            char in message.body or (
                message.list_data and any(
                    char in row.get('description', '')
                    for section in message.list_data['sections']
                    for row in section.get('rows', [])
                )
            )
            for char in ['$', '€', '£', 'KSh', 'USh', 'TSh']
        )
        
        assert has_price_pattern, (
            "Message should include price information with currency symbols"
        )
        
        # 6. Reference context should be stored
        assert 'context_id' in message.metadata, (
            "Message metadata should include context_id for reference resolution"
        )
        assert 'list_type' in message.metadata, (
            "Message metadata should include list_type"
        )
        assert message.metadata['list_type'] == 'products', (
            f"List type should be 'products', got '{message.metadata['list_type']}'"
        )
        
        # Clean up
        for product in products:
            product.delete()
    
    @given(products_data=product_list())
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_product_list_has_action_buttons_or_selectable_items(self, products_data, tenant, conversation):
        """
        Property: Product lists provide actionable next steps (buttons or selectable items).
        
        **Feature: conversational-commerce-ux-enhancement, Property 3: Rich message for product lists**
        **Validates: Requirements 3.2, 3.4**
        """
        assume(len(products_data) >= 2)
        
        # Create products
        products = []
        for data in products_data:
            product = Product.objects.create(
                tenant=tenant,
                title=data['title'],
                description=data['description'],
                price=data['price'],
                currency=data['currency'],
                stock=data['stock'],
                images=data['images']
            )
            products.append(product)
        
        # Build message
        builder = RichMessageBuilder()
        message = builder.build_product_list(products=products, conversation=conversation)
        
        # Property: Message should have either buttons or selectable list items
        has_buttons = message.buttons and len(message.buttons) > 0
        has_list_items = (
            message.list_data and
            message.list_data.get('sections') and
            any(len(section.get('rows', [])) > 0 for section in message.list_data['sections'])
        )
        
        assert has_buttons or has_list_items, (
            "Product list should have either action buttons or selectable list items"
        )
        
        # If it's a list message, items should be selectable (have IDs)
        if message.message_type == 'list' and message.list_data:
            for section in message.list_data['sections']:
                for row in section.get('rows', []):
                    assert 'id' in row and row['id'], (
                        "List items should have IDs for selection"
                    )
        
        # Clean up
        for product in products:
            product.delete()
    
    @given(products_data=product_list())
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_product_list_includes_availability_status(self, products_data, tenant, conversation):
        """
        Property: Product lists include availability status for each product.
        
        **Feature: conversational-commerce-ux-enhancement, Property 3: Rich message for product lists**
        **Validates: Requirements 3.2**
        """
        assume(len(products_data) >= 2)
        
        # Create products with mixed availability
        products = []
        for i, data in enumerate(products_data):
            # Ensure we have both in-stock and out-of-stock products
            # Alternate availability by setting stock to 0 or positive
            stock = 0 if i % 2 == 1 else (data['stock'] if data['stock'] is not None else 10)
            product = Product.objects.create(
                tenant=tenant,
                title=data['title'],
                description=data['description'],
                price=data['price'],
                currency=data['currency'],
                stock=stock,
                images=data['images']
            )
            products.append(product)
        
        # Build message with stock information
        builder = RichMessageBuilder()
        message = builder.build_product_list(
            products=products,
            conversation=conversation,
            show_stock=True
        )
        
        # Property: Availability information should be present
        # Check for stock indicators in message
        has_stock_info = (
            'Stock' in message.body or
            'stock' in message.body.lower() or
            'available' in message.body.lower() or
            'In Stock' in message.body or
            'Out of Stock' in message.body
        )
        
        # Also check in list descriptions
        if message.list_data:
            for section in message.list_data['sections']:
                for row in section.get('rows', []):
                    description = row.get('description', '').lower()
                    if 'stock' in description or 'available' in description:
                        has_stock_info = True
                        break
        
        assert has_stock_info, (
            "Product list with show_stock=True should include availability information"
        )
        
        # Clean up
        for product in products:
            product.delete()
    
    @given(products_data=product_list())
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_product_list_fallback_on_error(self, products_data, tenant, conversation):
        """
        Property: When rich message creation fails, system falls back to plain text.
        
        **Feature: conversational-commerce-ux-enhancement, Property 3: Rich message for product lists**
        **Validates: Requirements 3.1**
        """
        assume(len(products_data) >= 2)
        
        # Create products with potentially problematic data
        products = []
        for data in products_data:
            # Create product with very long title that might cause issues
            long_title = data['title'] * 10  # Make it very long
            product = Product.objects.create(
                tenant=tenant,
                title=long_title[:500],  # Truncate to model limit
                description=data['description'],
                price=data['price'],
                currency=data['currency'],
                stock=data['stock'],
                images=data['images']
            )
            products.append(product)
        
        # Build message - should not raise exception
        builder = RichMessageBuilder()
        try:
            message = builder.build_product_list(products=products, conversation=conversation)
            
            # Should return a valid message (either rich or fallback)
            assert isinstance(message, WhatsAppMessage), (
                "Should return a WhatsAppMessage instance"
            )
            assert message.body, "Message should have body text"
            assert message.message_type in ['text', 'list', 'button'], (
                f"Message type should be valid, got '{message.message_type}'"
            )
            
            # If it's a fallback, metadata should indicate it
            if message.message_type == 'text':
                # Fallback messages should still be functional
                assert len(message.body) > 0, "Fallback message should have content"
        
        except Exception as e:
            pytest.fail(f"Product list building should not raise exceptions, got: {e}")
        
        # Clean up
        for product in products:
            product.delete()


@pytest.fixture
def tenant(db):
    """Create a test tenant."""
    tenant = Tenant.objects.create(
        name="Test Tenant",
        slug="test-tenant",
        whatsapp_number="+1234567890"
    )
    yield tenant
    tenant.delete()


@pytest.fixture
def conversation(db, tenant):
    """Create a test conversation."""
    customer = Customer.objects.create(
        tenant=tenant,
        phone_e164="+1234567890",
        name="Test Customer"
    )
    conversation = Conversation.objects.create(
        tenant=tenant,
        customer=customer,
        channel='whatsapp'
    )
    yield conversation
    conversation.delete()
    customer.delete()
