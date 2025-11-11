"""
Tests for order serializers.

Verifies serializer validation and data transformation.
"""
import pytest
from decimal import Decimal
from django.utils import timezone

from apps.tenants.models import Tenant, Customer, SubscriptionTier
from apps.orders.models import Order
from apps.orders.serializers import (
    OrderCreateSerializer,
    OrderUpdateSerializer,
    OrderDetailSerializer,
    OrderListSerializer
)


@pytest.fixture
def subscription_tier(db):
    """Create a subscription tier."""
    return SubscriptionTier.objects.create(
        name='Growth',
        monthly_price=Decimal('99.00'),
        yearly_price=Decimal('950.00'),
        max_products=1000
    )


@pytest.fixture
def tenant(db, subscription_tier):
    """Create a tenant."""
    return Tenant.objects.create(
        name='Test Business',
        slug='test-business',
        whatsapp_number='+1234567890',
        twilio_sid='test_sid',
        twilio_token='test_token',
        webhook_secret='test_secret',
        subscription_tier=subscription_tier,
        status='active',
        subscription_waived=True
    )


@pytest.fixture
def customer(db, tenant):
    """Create a customer."""
    return Customer.objects.create(
        tenant=tenant,
        phone_e164='+1234567890',
        name='Test Customer'
    )


@pytest.mark.django_db
class TestOrderCreateSerializer:
    """Tests for OrderCreateSerializer."""
    
    def test_valid_order_data(self, tenant, customer):
        """Test serializer with valid order data."""
        data = {
            'customer': str(customer.id),
            'currency': 'USD',
            'subtotal': '100.00',
            'shipping': '10.00',
            'total': '110.00',
            'status': 'draft',
            'items': [
                {
                    'product_id': '123e4567-e89b-12d3-a456-426614174000',
                    'variant_id': None,
                    'title': 'Test Product',
                    'quantity': 2,
                    'price': '50.00',
                    'currency': 'USD'
                }
            ]
        }
        
        # Create mock request with tenant
        class MockRequest:
            def __init__(self, tenant):
                self.tenant = tenant
        
        serializer = OrderCreateSerializer(
            data=data,
            context={'request': MockRequest(tenant)}
        )
        
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['customer'] == customer
        assert serializer.validated_data['total'] == Decimal('110.00')
    
    def test_empty_items_validation(self, tenant, customer):
        """Test that empty items list is rejected."""
        data = {
            'customer': str(customer.id),
            'currency': 'USD',
            'subtotal': '100.00',
            'shipping': '10.00',
            'total': '110.00',
            'status': 'draft',
            'items': []
        }
        
        class MockRequest:
            def __init__(self, tenant):
                self.tenant = tenant
        
        serializer = OrderCreateSerializer(
            data=data,
            context={'request': MockRequest(tenant)}
        )
        
        assert not serializer.is_valid()
        assert 'items' in serializer.errors
    
    def test_total_mismatch_validation(self, tenant, customer):
        """Test that total must match subtotal + shipping."""
        data = {
            'customer': str(customer.id),
            'currency': 'USD',
            'subtotal': '100.00',
            'shipping': '10.00',
            'total': '150.00',  # Wrong total
            'status': 'draft',
            'items': [
                {
                    'product_id': '123e4567-e89b-12d3-a456-426614174000',
                    'variant_id': None,
                    'title': 'Test Product',
                    'quantity': 2,
                    'price': '50.00',
                    'currency': 'USD'
                }
            ]
        }
        
        class MockRequest:
            def __init__(self, tenant):
                self.tenant = tenant
        
        serializer = OrderCreateSerializer(
            data=data,
            context={'request': MockRequest(tenant)}
        )
        
        assert not serializer.is_valid()
        assert 'total' in serializer.errors


@pytest.mark.django_db
class TestOrderUpdateSerializer:
    """Tests for OrderUpdateSerializer."""
    
    def test_valid_status_transition(self, tenant, customer):
        """Test valid status transition from draft to placed."""
        order = Order.objects.create(
            tenant=tenant,
            customer=customer,
            currency='USD',
            subtotal=Decimal('100.00'),
            shipping=Decimal('10.00'),
            total=Decimal('110.00'),
            status='draft',
            items=[]
        )
        
        serializer = OrderUpdateSerializer(
            instance=order,
            data={'status': 'placed'},
            partial=True
        )
        
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['status'] == 'placed'
    
    def test_invalid_status_transition(self, tenant, customer):
        """Test that invalid status transitions are rejected."""
        order = Order.objects.create(
            tenant=tenant,
            customer=customer,
            currency='USD',
            subtotal=Decimal('100.00'),
            shipping=Decimal('10.00'),
            total=Decimal('110.00'),
            status='fulfilled',  # Terminal state
            items=[]
        )
        
        serializer = OrderUpdateSerializer(
            instance=order,
            data={'status': 'paid'},
            partial=True
        )
        
        assert not serializer.is_valid()
        assert 'status' in serializer.errors
        assert 'Cannot transition' in str(serializer.errors['status'][0])


@pytest.mark.django_db
class TestOrderDetailSerializer:
    """Tests for OrderDetailSerializer."""
    
    def test_serialize_order_with_items(self, tenant, customer):
        """Test serializing order with items."""
        order = Order.objects.create(
            tenant=tenant,
            customer=customer,
            currency='USD',
            subtotal=Decimal('100.00'),
            shipping=Decimal('10.00'),
            total=Decimal('110.00'),
            status='placed',
            items=[
                {
                    'product_id': '123e4567-e89b-12d3-a456-426614174000',
                    'variant_id': None,
                    'title': 'Test Product',
                    'quantity': 2,
                    'price': 50.00,
                    'currency': 'USD'
                }
            ]
        )
        
        serializer = OrderDetailSerializer(instance=order)
        data = serializer.data
        
        assert data['id'] == str(order.id)
        assert data['tenant_name'] == 'Test Business'
        assert data['customer_name'] == 'Test Customer'
        assert data['total'] == '110.00'
        assert len(data['items']) == 1
        assert data['items'][0]['title'] == 'Test Product'
        assert data['item_count'] == 2  # Sum of quantities
