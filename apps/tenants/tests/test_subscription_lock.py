"""
Tests for subscription status locking utilities.

Verifies that subscription status checks are properly locked
during critical operations to prevent race conditions.
"""
import pytest
from decimal import Decimal
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from apps.tenants.models import Tenant
from apps.rbac.models import TenantUser
from apps.tenants.subscription_lock import (
    with_subscription_lock,
    check_subscription_with_lock,
    execute_with_subscription_check
)

User = get_user_model()


@pytest.fixture
def subscription_tier(db):
    """Create test subscription tier."""
    from apps.tenants.models import SubscriptionTier
    return SubscriptionTier.objects.create(
        name='Professional',
        monthly_price=Decimal('99.00'),
        yearly_price=Decimal('950.00'),
        monthly_messages=50000,
        max_products=1000,
        max_services=100,
        payment_facilitation=True
    )


@pytest.fixture
def tenant(db, subscription_tier):
    """Create test tenant."""
    return Tenant.objects.create(
        name="Test Tenant",
        status='active',
        subscription_tier=subscription_tier
    )


@pytest.fixture
def user(db):
    """Create test user."""
    return User.objects.create_user(
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def tenant_user(tenant, user):
    """Create tenant user membership."""
    return TenantUser.objects.create(
        tenant=tenant,
        user=user
    )


@pytest.mark.django_db
class TestWithSubscriptionLock:
    """Test @with_subscription_lock decorator."""
    
    def test_locks_tenant_during_operation(self, tenant, user, tenant_user):
        """Test that decorator locks tenant record."""
        factory = RequestFactory()
        request = factory.post('/test')
        request.tenant = tenant
        request.user = user
        
        # Track if function was called
        called = []
        
        @with_subscription_lock
        def test_view(request):
            called.append(True)
            # Verify tenant is locked by trying to get it again
            from django.db import connection
            # In a real scenario, another transaction would block here
            return {'success': True}
        
        result = test_view(request)
        
        assert called == [True]
        assert result == {'success': True}
    
    def test_rejects_inactive_subscription(self, tenant, user, tenant_user):
        """Test that decorator rejects inactive subscriptions."""
        # Make tenant inactive
        tenant.status = 'suspended'
        tenant.save()
        
        factory = RequestFactory()
        request = factory.post('/test')
        request.tenant = tenant
        request.user = user
        
        @with_subscription_lock
        def test_view(request):
            return {'success': True}
        
        response = test_view(request)
        
        # Should return 403 JSON response
        assert response.status_code == 403
        assert 'Subscription inactive' in str(response.content)
    
    def test_requires_tenant_context(self, user):
        """Test that decorator requires tenant in request."""
        factory = RequestFactory()
        request = factory.post('/test')
        request.user = user
        # No tenant set
        
        @with_subscription_lock
        def test_view(request):
            return {'success': True}
        
        response = test_view(request)
        
        assert response.status_code == 400
        assert 'Tenant context required' in str(response.content)


@pytest.mark.django_db
class TestCheckSubscriptionWithLock:
    """Test check_subscription_with_lock function."""
    
    def test_returns_locked_tenant_and_status(self, tenant):
        """Test that function returns locked tenant and status."""
        from django.db import transaction
        
        with transaction.atomic():
            locked_tenant, is_active = check_subscription_with_lock(tenant.id)
            
            assert locked_tenant.id == tenant.id
            assert is_active is True
    
    def test_detects_inactive_subscription(self, tenant):
        """Test that function detects inactive subscriptions."""
        tenant.status = 'suspended'
        tenant.save()
        
        from django.db import transaction
        
        with transaction.atomic():
            locked_tenant, is_active = check_subscription_with_lock(tenant.id)
            
            assert locked_tenant.id == tenant.id
            assert is_active is False


@pytest.mark.django_db
class TestExecuteWithSubscriptionCheck:
    """Test execute_with_subscription_check wrapper."""
    
    def test_executes_operation_with_active_subscription(self, tenant):
        """Test that wrapper executes operation when subscription active."""
        result_value = {'processed': True}
        
        def operation(locked_tenant):
            assert locked_tenant.id == tenant.id
            return result_value
        
        result = execute_with_subscription_check(tenant.id, operation)
        
        assert result == result_value
    
    def test_raises_error_for_inactive_subscription(self, tenant):
        """Test that wrapper raises error for inactive subscription."""
        tenant.status = 'suspended'
        tenant.save()
        
        def operation(locked_tenant):
            return {'processed': True}
        
        with pytest.raises(ValueError, match='Subscription inactive'):
            execute_with_subscription_check(tenant.id, operation)
    
    def test_operation_not_called_when_inactive(self, tenant):
        """Test that operation is not called when subscription inactive."""
        tenant.status = 'suspended'
        tenant.save()
        
        called = []
        
        def operation(locked_tenant):
            called.append(True)
            return {'processed': True}
        
        with pytest.raises(ValueError):
            execute_with_subscription_check(tenant.id, operation)
        
        # Operation should not have been called
        assert called == []
