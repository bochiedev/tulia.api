"""
Tests for wallet API endpoints with RBAC enforcement.
"""
import pytest
from decimal import Decimal
from django.test import TestCase, RequestFactory
from rest_framework.test import APIClient, force_authenticate
from rest_framework import status

from apps.tenants.models import Tenant, SubscriptionTier, TenantWallet
from apps.tenants.views import WalletBalanceView
from apps.rbac.models import User, TenantUser, Permission, Role, RolePermission, TenantUserRole
from apps.rbac.services import RBACService


@pytest.mark.django_db
class TestWalletBalanceView(TestCase):
    """Test wallet balance endpoint with RBAC."""
    
    def setUp(self):
        """Set up test data."""
        # Create subscription tier
        self.tier = SubscriptionTier.objects.create(
            name='Growth',
            monthly_price=Decimal('99.00'),
            yearly_price=Decimal('950.00'),
            payment_facilitation=True,
            transaction_fee_percentage=Decimal('3.5')
        )
        
        # Create tenant
        self.tenant = Tenant.objects.create(
            name='Test Business',
            slug='test-business',
            status='active',
            subscription_tier=self.tier,
            whatsapp_number='+1234567890',
            twilio_sid='test_sid',
            twilio_token='test_token',
            webhook_secret='test_secret'
        )
        
        # Create wallet
        self.wallet = TenantWallet.objects.create(
            tenant=self.tenant,
            balance=Decimal('1000.00'),
            currency='USD',
            minimum_withdrawal=Decimal('10.00')
        )
        
        # Create finance:view permission
        self.perm_finance_view = Permission.objects.create(
            code='finance:view',
            label='View Finance',
            description='Can view wallet balance and transactions',
            category='finance'
        )
        
        # Create users
        self.user_with_access = User.objects.create_user(
            email='finance@test.com',
            password='password123',
            first_name='Finance',
            last_name='User'
        )
        self.user_without_access = User.objects.create_user(
            email='nofinance@test.com',
            password='password123',
            first_name='No',
            last_name='Finance'
        )
        
        # Create tenant users
        self.tenant_user_with_access = TenantUser.objects.create(
            tenant=self.tenant,
            user=self.user_with_access,
            invite_status='accepted'
        )
        self.tenant_user_without_access = TenantUser.objects.create(
            tenant=self.tenant,
            user=self.user_without_access,
            invite_status='accepted'
        )
        
        # Create role with finance:view
        self.role_finance = Role.objects.create(
            tenant=self.tenant,
            name='Finance Viewer',
            description='Can view finance data'
        )
        RolePermission.objects.create(role=self.role_finance, permission=self.perm_finance_view)
        
        # Assign role to user with access
        TenantUserRole.objects.create(tenant_user=self.tenant_user_with_access, role=self.role_finance)
        
        # Request factory for direct view testing
        self.factory = RequestFactory()
    
    def test_wallet_balance_with_finance_view_scope(self):
        """Test that user with finance:view can access wallet balance."""
        # Create request and mock middleware context
        request = self.factory.get('/v1/wallet/balance')
        force_authenticate(request, user=self.user_with_access)
        request.tenant = self.tenant
        request.membership = self.tenant_user_with_access
        request.scopes = RBACService.resolve_scopes(self.tenant_user_with_access)
        
        # Call view directly
        view = WalletBalanceView.as_view()
        response = view(request)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'balance' in response.data
        assert Decimal(response.data['balance']) == Decimal('1000.00')
        assert response.data['currency'] == 'USD'
    
    def test_wallet_balance_without_finance_view_scope(self):
        """Test that user without finance:view gets 403."""
        # Create request and mock middleware context (no finance:view scope)
        request = self.factory.get('/v1/wallet/balance')
        force_authenticate(request, user=self.user_without_access)
        request.tenant = self.tenant
        request.membership = self.tenant_user_without_access
        request.scopes = RBACService.resolve_scopes(self.tenant_user_without_access)
        
        # Call view directly
        view = WalletBalanceView.as_view()
        response = view(request)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_wallet_balance_missing_scopes_attribute(self):
        """Test that request without scopes attribute gets 403."""
        # Create request without scopes (edge case)
        request = self.factory.get('/v1/wallet/balance')
        force_authenticate(request, user=self.user_with_access)
        request.tenant = self.tenant
        request.membership = self.tenant_user_with_access
        # No scopes attribute set
        
        # Call view directly
        view = WalletBalanceView.as_view()
        response = view(request)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
