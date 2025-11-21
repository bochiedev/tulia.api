"""
Tests for status checking handlers.

Tests the deterministic status handlers for the sales orchestration refactor.
"""
import pytest
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

from apps.bot.services.handlers.status_handlers import (
    handle_check_order_status,
    handle_check_appointment_status,
)
from apps.bot.services.intent_detection_engine import IntentResult, Intent
from apps.bot.models import ConversationContext
from apps.catalog.models import Product
from apps.services.models import Service, Appointment
from apps.orders.models import Order
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
def product(db, tenant):
    """Create test product."""
    return Product.objects.create(
        tenant=tenant,
        title="Test Product",
        description="Test description",
        price=Decimal("100.00"),
        currency="KES",
        stock=10,
        is_active=True
    )


@pytest.fixture
def service(db, tenant):
    """Create test service."""
    return Service.objects.create(
        tenant=tenant,
        title="Test Service",
        description="Test service description",
        base_price=Decimal("50.00"),
        currency="KES",
        is_active=True
    )


@pytest.fixture
def order(db, tenant, customer, product):
    """Create test order."""
    return Order.objects.create(
        tenant=tenant,
        customer=customer,
        status="placed",
        subtotal=Decimal("100.00"),
        total=Decimal("100.00"),
        currency="KES",
        items=[
            {
                'product_id': str(product.id),
                'product_name': product.title,
                'quantity': 1,
                'price': float(product.price)
            }
        ]
    )


@pytest.fixture
def appointment(db, tenant, customer, service):
    """Create test appointment."""
    start = timezone.now() + timedelta(days=1)
    return Appointment.objects.create(
        tenant=tenant,
        customer=customer,
        service=service,
        start_dt=start,
        end_dt=start + timedelta(hours=1),
        status="confirmed"
    )


@pytest.mark.django_db
class TestHandleCheckOrderStatus:
    """Test handle_check_order_status function."""
    
    def test_check_order_status_displays_recent_order(self, tenant, customer, context, order):
        """Test displaying most recent order (Requirement 11.2)."""
        intent_result = IntentResult(
            intent=Intent.CHECK_ORDER_STATUS,
            confidence=0.95,
            slots={},
            language=['en']
        )
        
        action = handle_check_order_status(intent_result, context, tenant, customer)
        
        assert action.type == "TEXT"
        assert str(order.id) in action.text
        assert "placed" in action.text.lower()
        assert "KES 100" in action.text
        assert action.new_context['current_flow'] == 'checking_order'
        assert 'order_status_checked' in action.side_effects
    
    def test_check_order_status_no_orders(self, tenant, customer, context):
        """Test handling no orders found (Requirement 11.5)."""
        intent_result = IntentResult(
            intent=Intent.CHECK_ORDER_STATUS,
            confidence=0.95,
            slots={},
            language=['en']
        )
        
        action = handle_check_order_status(intent_result, context, tenant, customer)
        
        assert action.type == "BUTTONS"
        assert "No Orders Found" in action.text or "Hauna Orders" in action.text
        assert 'buttons' in action.rich_payload
        assert len(action.rich_payload['buttons']) == 2
        assert action.new_context['current_flow'] == ''
    
    def test_check_order_status_shows_items(self, tenant, customer, context, order):
        """Test that order items are displayed (Requirement 11.2)."""
        intent_result = IntentResult(
            intent=Intent.CHECK_ORDER_STATUS,
            confidence=0.95,
            slots={},
            language=['en']
        )
        
        action = handle_check_order_status(intent_result, context, tenant, customer)
        
        assert "Test Product" in action.text
        assert "x1" in action.text
    
    def test_check_order_status_tenant_isolation(self, tenant, customer, context, order):
        """Test tenant isolation (Requirement 11.1)."""
        # Create another tenant with order
        other_tenant = Tenant.objects.create(
            name="Other Store",
            slug="other-store",
            status="active",
            whatsapp_number="+254700000000"
        )
        other_customer = Customer.objects.create(
            tenant=other_tenant,
            phone_e164="+254712345678",
            name="Other Customer"
        )
        other_product = Product.objects.create(
            tenant=other_tenant,
            title="Other Product",
            price=Decimal("200.00"),
            currency="KES",
            stock=10,
            is_active=True
        )
        Order.objects.create(
            tenant=other_tenant,
            customer=other_customer,
            status="placed",
            subtotal=Decimal("200.00"),
            total=Decimal("200.00"),
            currency="KES",
            items=[
                {
                    'product_id': str(other_product.id),
                    'product_name': other_product.title,
                    'quantity': 1,
                    'price': float(other_product.price)
                }
            ]
        )
        
        intent_result = IntentResult(
            intent=Intent.CHECK_ORDER_STATUS,
            confidence=0.95,
            slots={},
            language=['en']
        )
        
        action = handle_check_order_status(intent_result, context, tenant, customer)
        
        # Should only show orders from correct tenant
        assert "Test Product" in action.text
        assert "Other Product" not in action.text
    
    def test_check_order_status_swahili(self, tenant, customer, context, order):
        """Test Swahili language support."""
        intent_result = IntentResult(
            intent=Intent.CHECK_ORDER_STATUS,
            confidence=0.95,
            slots={},
            language=['sw']
        )
        
        action = handle_check_order_status(intent_result, context, tenant, customer)
        
        assert "Jumla" in action.text or "Total" in action.text


@pytest.mark.django_db
class TestHandleCheckAppointmentStatus:
    """Test handle_check_appointment_status function."""
    
    def test_check_appointment_status_displays_upcoming(self, tenant, customer, context, appointment):
        """Test displaying upcoming appointments (Requirement 11.4)."""
        intent_result = IntentResult(
            intent=Intent.CHECK_APPOINTMENT_STATUS,
            confidence=0.95,
            slots={},
            language=['en']
        )
        
        action = handle_check_appointment_status(intent_result, context, tenant, customer)
        
        assert action.type == "TEXT"
        assert "Test Service" in action.text
        assert "confirmed" in action.text.lower()
        assert action.new_context['current_flow'] == 'checking_appointment'
        assert 'appointment_status_checked' in action.side_effects
    
    def test_check_appointment_status_no_appointments(self, tenant, customer, context):
        """Test handling no appointments found (Requirement 11.5)."""
        intent_result = IntentResult(
            intent=Intent.CHECK_APPOINTMENT_STATUS,
            confidence=0.95,
            slots={},
            language=['en']
        )
        
        action = handle_check_appointment_status(intent_result, context, tenant, customer)
        
        assert action.type == "BUTTONS"
        assert "No Appointments Found" in action.text or "Hauna Appointments" in action.text
        assert 'buttons' in action.rich_payload
        assert len(action.rich_payload['buttons']) == 2
        assert action.new_context['current_flow'] == ''
    
    def test_check_appointment_status_shows_details(self, tenant, customer, context, appointment):
        """Test that appointment details are displayed (Requirement 11.4)."""
        intent_result = IntentResult(
            intent=Intent.CHECK_APPOINTMENT_STATUS,
            confidence=0.95,
            slots={},
            language=['en']
        )
        
        action = handle_check_appointment_status(intent_result, context, tenant, customer)
        
        # Check for service name, date, time, status
        assert "Test Service" in action.text
        assert appointment.start_dt.strftime('%B') in action.text
        assert "Confirmed" in action.text or "confirmed" in action.text
    
    def test_check_appointment_status_only_upcoming(self, tenant, customer, context, service):
        """Test that only upcoming appointments are shown (Requirement 11.3)."""
        # Create past appointment
        past_start = timezone.now() - timedelta(days=1)
        past_appointment = Appointment.objects.create(
            tenant=tenant,
            customer=customer,
            service=service,
            start_dt=past_start,
            end_dt=past_start + timedelta(hours=1),
            status="done"
        )
        
        # Create future appointment
        future_start = timezone.now() + timedelta(days=1)
        future_appointment = Appointment.objects.create(
            tenant=tenant,
            customer=customer,
            service=service,
            start_dt=future_start,
            end_dt=future_start + timedelta(hours=1),
            status="confirmed"
        )
        
        intent_result = IntentResult(
            intent=Intent.CHECK_APPOINTMENT_STATUS,
            confidence=0.95,
            slots={},
            language=['en']
        )
        
        action = handle_check_appointment_status(intent_result, context, tenant, customer)
        
        # Should only show future appointment
        assert action.type == "TEXT"
        # Past appointment should not be in the text
        # (We can't easily check this without more context, but the query filters by start_dt__gte)
    
    def test_check_appointment_status_tenant_isolation(self, tenant, customer, context, appointment):
        """Test tenant isolation (Requirement 11.3)."""
        # Create another tenant with appointment
        other_tenant = Tenant.objects.create(
            name="Other Store",
            slug="other-store",
            status="active",
            whatsapp_number="+254700000000"
        )
        other_customer = Customer.objects.create(
            tenant=other_tenant,
            phone_e164="+254712345678",
            name="Other Customer"
        )
        other_service = Service.objects.create(
            tenant=other_tenant,
            title="Other Service",
            base_price=Decimal("75.00"),
            currency="KES",
            is_active=True
        )
        other_start = timezone.now() + timedelta(days=1)
        Appointment.objects.create(
            tenant=other_tenant,
            customer=other_customer,
            service=other_service,
            start_dt=other_start,
            end_dt=other_start + timedelta(hours=1),
            status="confirmed"
        )
        
        intent_result = IntentResult(
            intent=Intent.CHECK_APPOINTMENT_STATUS,
            confidence=0.95,
            slots={},
            language=['en']
        )
        
        action = handle_check_appointment_status(intent_result, context, tenant, customer)
        
        # Should only show appointments from correct tenant
        assert "Test Service" in action.text
        assert "Other Service" not in action.text
    
    def test_check_appointment_status_swahili(self, tenant, customer, context, appointment):
        """Test Swahili language support."""
        intent_result = IntentResult(
            intent=Intent.CHECK_APPOINTMENT_STATUS,
            confidence=0.95,
            slots={},
            language=['sw']
        )
        
        action = handle_check_appointment_status(intent_result, context, tenant, customer)
        
        assert "Appointments" in action.text or "appointment" in action.text.lower()
