"""
Property-based test for checkout guidance completeness.

**Feature: conversational-commerce-ux-enhancement, Property 5: Checkout guidance completeness**
**Validates: Requirements 5.1, 5.2, 5.3, 5.4**

This test verifies that for any customer expressing purchase intent,
the system provides a complete path to checkout including:
- Product selection confirmation
- Quantity confirmation
- Payment link or instructions
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from decimal import Decimal
from django.utils import timezone

from apps.tenants.models import Tenant, Customer
from apps.catalog.models import Product
from apps.messaging.models import Conversation
from apps.orders.models import Cart, Order
from apps.bot.services.product_handlers import ProductIntentHandler
from apps.integrations.services.twilio_service import TwilioService


# Hypothesis strategies for generating test data

@st.composite
def valid_cart_items(draw):
    """Generate valid cart items with products and quantities."""
    num_items = draw(st.integers(min_value=1, max_value=5))
    items = []
    
    for i in range(num_items):
        item = {
            'product_id': str(draw(st.uuids())),
            'variant_id': None,
            'title': draw(st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=('Cs',)))),
            'quantity': draw(st.integers(min_value=1, max_value=10)),
            'price': float(draw(st.decimals(min_value=Decimal('0.01'), max_value=Decimal('10000'), places=2))),
            'currency': draw(st.sampled_from(['USD', 'KES', 'EUR', 'GBP']))
        }
        items.append(item)
    
    return items


@st.composite
def checkout_slots(draw):
    """Generate checkout intent slots with various confirmation states."""
    return {
        'checkout_step': draw(st.sampled_from([
            'confirm_items',
            'confirm_quantity', 
            'generate_payment',
            None  # Default case
        ])),
        'confirmed': draw(st.booleans())
    }


@st.composite
def unique_tenant_data(draw):
    """Generate unique tenant data to avoid database constraint violations."""
    import uuid
    import hashlib
    
    # Generate a truly unique ID based on UUID
    unique_uuid = uuid.uuid4()
    unique_id = str(unique_uuid)[:8]
    
    # Generate unique phone number from UUID hash to ensure uniqueness
    phone_hash = hashlib.md5(str(unique_uuid).encode()).hexdigest()[:10]
    phone_number = f"+{int(phone_hash, 16) % 9000000000 + 1000000000}"
    
    return {
        'name': f"Test Tenant {unique_id}",
        'slug': f"test-tenant-{unique_id}",
        'contact_email': f"test-{unique_id}@example.com",
        'whatsapp_number': phone_number
    }


@pytest.mark.django_db
class TestCheckoutGuidanceProperty:
    """
    Property-based tests for checkout guidance completeness.
    
    These tests verify that the checkout flow always provides:
    1. Product selection confirmation
    2. Quantity confirmation
    3. Payment link or instructions
    4. Clear next steps at each stage
    """
    
    @given(
        cart_items=valid_cart_items(),
        slots=checkout_slots(),
        tenant_data=unique_tenant_data()
    )
    @settings(max_examples=100, deadline=5000)
    def test_checkout_provides_complete_guidance(self, cart_items, slots, tenant_data):
        """
        Property: For any cart with items and checkout intent, the system provides
        complete guidance including confirmation steps and payment information.
        
        **Validates: Requirements 5.1, 5.2, 5.3, 5.4**
        """
        # Setup: Create tenant, customer, conversation, and cart
        tenant = Tenant.objects.create(**tenant_data)
        
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
        
        # Calculate subtotal
        subtotal = sum(item['quantity'] * item['price'] for item in cart_items)
        
        cart = Cart.objects.create(
            conversation=conversation,
            items=cart_items,
            subtotal=subtotal
        )
        
        # Create mock Twilio service
        class MockTwilioService:
            def send_whatsapp(self, to, body):
                return {'sid': 'test_message_sid'}
        
        twilio_service = MockTwilioService()
        
        # Create handler
        handler = ProductIntentHandler(tenant, conversation, twilio_service)
        
        # Action: Process checkout intent
        response = handler.handle_checkout_link(slots)
        
        # Assert: Response must be valid
        assert response is not None, "Checkout handler must return a response"
        assert 'message' in response, "Response must contain a message"
        assert 'action' in response, "Response must contain an action"
        assert response['action'] == 'send', "Response action must be 'send'"
        
        message = response['message']
        metadata = response.get('metadata', {})
        
        # Property 1: Message must not be empty
        assert len(message) > 0, "Checkout message must not be empty"
        
        # Property 2: Message must contain order/cart information
        # At minimum, it should reference items or cart
        assert any(keyword in message.lower() for keyword in [
            'cart', 'order', 'item', 'product', 'total', 'checkout'
        ]), "Message must reference cart/order information"
        
        # Property 3: Determine checkout step and verify appropriate content
        checkout_step = slots.get('checkout_step', 'confirm_items')
        
        if checkout_step == 'confirm_items' or checkout_step is None:
            # Step 1: Product selection confirmation
            # Must show items and ask for confirmation
            assert any(keyword in message.lower() for keyword in [
                'review', 'confirm', 'correct', 'items'
            ]), "Product confirmation step must ask for confirmation"
            
            # Should list items
            assert 'qty' in message.lower() or 'quantity' in message.lower(), \
                "Product confirmation should show quantities"
            
        elif checkout_step == 'confirm_quantity':
            # Step 2: Quantity confirmation
            # Must show quantities and ask for confirmation
            assert 'quantity' in message.lower() or 'qty' in message.lower(), \
                "Quantity confirmation step must mention quantities"
            
            assert any(keyword in message.lower() for keyword in [
                'correct', 'confirm', 'proceed', 'payment'
            ]), "Quantity confirmation must ask for confirmation or mention next step"
            
        elif checkout_step == 'generate_payment':
            # Step 3: Payment generation
            # Must provide payment link OR instructions
            has_payment_link = 'http' in message.lower() or metadata.get('checkout_link')
            has_payment_instructions = any(keyword in message.lower() for keyword in [
                'payment', 'pay', 'complete', 'contact', 'instructions'
            ])
            
            assert has_payment_link or has_payment_instructions, \
                "Payment step must provide payment link or instructions"
            
            # Must show order summary
            assert 'total' in message.lower(), \
                "Payment step must show order total"
            
            # Should confirm order creation
            assert any(keyword in message.lower() for keyword in [
                'order', 'confirmed', 'thank'
            ]), "Payment step should confirm order"
        
        # Property 4: Message must provide clear next steps
        # Look for action words or questions
        has_next_step = any(keyword in message.lower() for keyword in [
            'reply', 'yes', 'no', 'confirm', 'proceed', 'click', 
            'complete', 'contact', 'modify', 'change', 'cancel'
        ])
        
        assert has_next_step, \
            "Message must provide clear next steps or call to action"
        
        # Property 5: Metadata should track checkout progress
        if checkout_step == 'generate_payment':
            # After payment generation, order should be created
            assert 'order_id' in metadata, \
                "Payment step must create and track order ID"
        
        # Cleanup
        tenant.delete()
    
    @given(
        cart_items=valid_cart_items(),
        tenant_data=unique_tenant_data()
    )
    @settings(max_examples=50, deadline=5000)
    def test_complete_checkout_flow_creates_order(self, cart_items, tenant_data):
        """
        Property: Completing the full checkout flow (generate_payment step)
        always creates an order with correct items and total.
        
        **Validates: Requirements 5.1, 5.4**
        """
        # Setup
        tenant = Tenant.objects.create(**tenant_data)
        
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
        
        subtotal = sum(item['quantity'] * item['price'] for item in cart_items)
        
        cart = Cart.objects.create(
            conversation=conversation,
            items=cart_items,
            subtotal=subtotal
        )
        
        class MockTwilioService:
            def send_whatsapp(self, to, body):
                return {'sid': 'test_message_sid'}
        
        twilio_service = MockTwilioService()
        handler = ProductIntentHandler(tenant, conversation, twilio_service)
        
        # Record initial order count
        initial_order_count = Order.objects.filter(tenant=tenant).count()
        
        # Action: Complete checkout (generate payment step)
        response = handler.handle_checkout_link({'checkout_step': 'generate_payment'})
        
        # Assert: Order must be created
        final_order_count = Order.objects.filter(tenant=tenant).count()
        assert final_order_count == initial_order_count + 1, \
            "Completing checkout must create exactly one order"
        
        # Get the created order
        order = Order.objects.filter(tenant=tenant).latest('created_at')
        
        # Property 1: Order must have correct customer
        assert order.customer == customer, \
            "Order must be associated with correct customer"
        
        # Property 2: Order must have correct items
        assert len(order.items) == len(cart_items), \
            "Order must contain all cart items"
        
        # Property 3: Order total must match cart subtotal
        assert abs(float(order.total) - subtotal) < 0.01, \
            f"Order total ({order.total}) must match cart subtotal ({subtotal})"
        
        # Property 4: Cart must be cleared after order creation
        cart.refresh_from_db()
        assert len(cart.items) == 0, \
            "Cart must be cleared after successful order creation"
        assert cart.subtotal == 0, \
            "Cart subtotal must be reset after order creation"
        
        # Property 5: Response must include order ID
        assert 'order_id' in response.get('metadata', {}), \
            "Response must include created order ID"
        
        assert response['metadata']['order_id'] == str(order.id), \
            "Response order ID must match created order"
        
        # Cleanup
        tenant.delete()
    
    @given(
        cart_items=valid_cart_items(),
        tenant_data=unique_tenant_data()
    )
    @settings(max_examples=50, deadline=5000)
    def test_checkout_message_includes_all_items(self, cart_items, tenant_data):
        """
        Property: Checkout confirmation messages must include information
        about all items in the cart.
        
        **Validates: Requirements 5.1, 5.2**
        """
        # Setup
        tenant = Tenant.objects.create(**tenant_data)
        
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
        
        subtotal = sum(item['quantity'] * item['price'] for item in cart_items)
        
        cart = Cart.objects.create(
            conversation=conversation,
            items=cart_items,
            subtotal=subtotal
        )
        
        class MockTwilioService:
            def send_whatsapp(self, to, body):
                return {'sid': 'test_message_sid'}
        
        twilio_service = MockTwilioService()
        handler = ProductIntentHandler(tenant, conversation, twilio_service)
        
        # Action: Get product confirmation message
        response = handler.handle_checkout_link({'checkout_step': 'confirm_items'})
        
        message = response['message'].lower()
        
        # Property: Each item's title should appear in the message
        # (or at least be referenced by number)
        for idx, item in enumerate(cart_items, 1):
            # Check if item title appears or if numbered list is used
            title_appears = item['title'].lower() in message
            number_appears = str(idx) in message
            
            assert title_appears or number_appears, \
                f"Item {idx} ('{item['title']}') must be referenced in checkout message"
        
        # Property: Total/subtotal must appear
        assert 'total' in message or 'subtotal' in message, \
            "Checkout message must show total or subtotal"
        
        # Cleanup
        tenant.delete()
    
    @pytest.mark.django_db
    def test_empty_cart_provides_helpful_message(self):
        """
        Property: Attempting checkout with empty cart provides helpful
        guidance to add items first.
        
        **Validates: Requirements 5.1**
        """
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        
        # Setup
        tenant = Tenant.objects.create(
            name=f"Test Tenant {unique_id}",
            slug=f"test-tenant-{unique_id}",
            contact_email=f"test-{unique_id}@example.com",
            whatsapp_number=f"+12345671234"
        )
        
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
        
        # Create empty cart
        cart = Cart.objects.create(
            conversation=conversation,
            items=[],
            subtotal=0
        )
        
        class MockTwilioService:
            def send_whatsapp(self, to, body):
                return {'sid': 'test_message_sid'}
        
        twilio_service = MockTwilioService()
        handler = ProductIntentHandler(tenant, conversation, twilio_service)
        
        # Action: Attempt checkout with empty cart
        response = handler.handle_checkout_link({})
        
        message = response['message'].lower()
        
        # Property 1: Must indicate cart is empty
        assert 'empty' in message or 'no items' in message, \
            "Empty cart message must indicate cart is empty"
        
        # Property 2: Must provide guidance to add items
        assert any(keyword in message for keyword in [
            'browse', 'add', 'products', 'items', 'shop'
        ]), "Empty cart message must guide user to add items"
        
        # Property 3: Should not create an order
        order_count = Order.objects.filter(tenant=tenant).count()
        assert order_count == 0, \
            "Empty cart checkout must not create an order"
        
        # Cleanup
        tenant.delete()
