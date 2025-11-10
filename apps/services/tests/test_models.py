"""
Tests for service models.
"""
import pytest
from datetime import datetime, time as dt_time, timedelta
from django.core.exceptions import ValidationError
from django.utils import timezone
import pytz

from apps.services.models import (
    Service,
    ServiceVariant,
    AvailabilityWindow,
    Appointment
)
from apps.tenants.models import Tenant, Customer, SubscriptionTier


@pytest.mark.django_db
class TestServiceModel:
    """Tests for Service model."""
    
    def test_create_service(self, tenant):
        """Test creating a service."""
        service = Service.objects.create(
            tenant=tenant,
            title="Haircut",
            description="Professional haircut service",
            base_price=25.00,
            currency="USD",
            is_active=True
        )
        
        assert service.id is not None
        assert service.title == "Haircut"
        assert service.tenant == tenant
        assert service.is_active is True
    
    def test_service_get_price(self, tenant):
        """Test getting service price."""
        service = Service.objects.create(
            tenant=tenant,
            title="Haircut",
            base_price=25.00,
            currency="USD"
        )
        
        assert service.get_price() == 25.00


@pytest.mark.django_db
class TestServiceVariantModel:
    """Tests for ServiceVariant model."""
    
    def test_create_variant(self, service):
        """Test creating a service variant."""
        variant = ServiceVariant.objects.create(
            service=service,
            title="Men's Cut",
            duration_minutes=30,
            price=25.00
        )
        
        assert variant.id is not None
        assert variant.title == "Men's Cut"
        assert variant.duration_minutes == 30
        assert variant.service == service
    
    def test_variant_validation(self, service):
        """Test variant validation."""
        variant = ServiceVariant(
            service=service,
            title="Invalid",
            duration_minutes=-10,
            price=25.00
        )
        
        with pytest.raises(ValidationError):
            variant.clean()


@pytest.mark.django_db
class TestAvailabilityWindowModel:
    """Tests for AvailabilityWindow model."""
    
    def test_create_recurring_window(self, tenant, service):
        """Test creating a recurring availability window."""
        window = AvailabilityWindow.objects.create(
            tenant=tenant,
            service=service,
            weekday=0,  # Monday
            start_time=dt_time(9, 0),
            end_time=dt_time(17, 0),
            capacity=3,
            timezone='UTC'
        )
        
        assert window.id is not None
        assert window.weekday == 0
        assert window.is_recurring() is True
        assert window.is_specific_date() is False
    
    def test_create_specific_date_window(self, tenant, service):
        """Test creating a specific date availability window."""
        date = timezone.now().date()
        window = AvailabilityWindow.objects.create(
            tenant=tenant,
            service=service,
            date=date,
            start_time=dt_time(10, 0),
            end_time=dt_time(14, 0),
            capacity=1,
            timezone='UTC'
        )
        
        assert window.id is not None
        assert window.date == date
        assert window.is_recurring() is False
        assert window.is_specific_date() is True
    
    def test_window_validation_weekday_range(self, tenant, service):
        """Test weekday validation."""
        window = AvailabilityWindow(
            tenant=tenant,
            service=service,
            weekday=7,  # Invalid
            start_time=dt_time(9, 0),
            end_time=dt_time(17, 0),
            capacity=1,
            timezone='UTC'
        )
        
        with pytest.raises(ValidationError):
            window.clean()
    
    def test_window_validation_time_range(self, tenant, service):
        """Test time range validation."""
        window = AvailabilityWindow(
            tenant=tenant,
            service=service,
            weekday=0,
            start_time=dt_time(17, 0),
            end_time=dt_time(9, 0),  # End before start
            capacity=1,
            timezone='UTC'
        )
        
        with pytest.raises(ValidationError):
            window.clean()


@pytest.mark.django_db
class TestAppointmentModel:
    """Tests for Appointment model."""
    
    def test_create_appointment(self, tenant, customer, service):
        """Test creating an appointment."""
        start_dt = timezone.now() + timedelta(days=1)
        end_dt = start_dt + timedelta(hours=1)
        
        appointment = Appointment.objects.create(
            tenant=tenant,
            customer=customer,
            service=service,
            start_dt=start_dt,
            end_dt=end_dt,
            status='pending'
        )
        
        assert appointment.id is not None
        assert appointment.customer == customer
        assert appointment.service == service
        assert appointment.status == 'pending'
    
    def test_appointment_duration(self, tenant, customer, service):
        """Test appointment duration calculation."""
        start_dt = timezone.now() + timedelta(days=1)
        end_dt = start_dt + timedelta(minutes=45)
        
        appointment = Appointment.objects.create(
            tenant=tenant,
            customer=customer,
            service=service,
            start_dt=start_dt,
            end_dt=end_dt,
            status='pending'
        )
        
        assert appointment.duration_minutes() == 45
    
    def test_appointment_can_cancel(self, tenant, customer, service):
        """Test appointment cancellation check."""
        # Future appointment
        start_dt = timezone.now() + timedelta(days=1)
        end_dt = start_dt + timedelta(hours=1)
        
        appointment = Appointment.objects.create(
            tenant=tenant,
            customer=customer,
            service=service,
            start_dt=start_dt,
            end_dt=end_dt,
            status='pending'
        )
        
        assert appointment.can_cancel() is True
        
        # Past appointment
        past_start = timezone.now() - timedelta(days=1)
        past_end = past_start + timedelta(hours=1)
        
        past_appointment = Appointment.objects.create(
            tenant=tenant,
            customer=customer,
            service=service,
            start_dt=past_start,
            end_dt=past_end,
            status='pending'
        )
        
        assert past_appointment.can_cancel() is False


# Fixtures

@pytest.fixture
def subscription_tier():
    """Create a subscription tier."""
    return SubscriptionTier.objects.create(
        name="Test Tier",
        monthly_price=29.00,
        yearly_price=278.00,
        max_services=10
    )


@pytest.fixture
def tenant(subscription_tier):
    """Create a test tenant."""
    return Tenant.objects.create(
        name="Test Business",
        slug="test-business",
        status="active",
        subscription_tier=subscription_tier,
        whatsapp_number="+1234567890",
        twilio_sid="test_sid",
        twilio_token="test_token",
        webhook_secret="test_secret"
    )


@pytest.fixture
def customer(tenant):
    """Create a test customer."""
    return Customer.objects.create(
        tenant=tenant,
        phone_e164="+1234567891",
        name="Test Customer"
    )


@pytest.fixture
def service(tenant):
    """Create a test service."""
    return Service.objects.create(
        tenant=tenant,
        title="Test Service",
        description="Test service description",
        base_price=50.00,
        currency="USD",
        is_active=True
    )
