"""
Comprehensive RBAC tests covering all requirements from task 6.10.

Tests:
- Unit tests: scope resolution with multiple roles
- Unit tests: deny override wins over role grant
- Unit tests: four-eyes validation rejects same user
- API tests: GET /v1/products with/without catalog:view (200/403)
- API tests: POST /v1/products with/without catalog:edit (200/403)
- API tests: finance withdrawal initiate and approve with different users
- API tests: finance withdrawal approval by same user returns 409
- API tests: user permission override denies access despite role grant
- API tests: switching X-TENANT-ID without membership returns 403
- API tests: user with membership in multiple tenants sees correct data per tenant
- API tests: same phone number in different tenants creates separate Customer records
- Seeder tests: seed_permissions is idempotent
- Seeder tests: seed_tenant_roles is idempotent
"""
import pytest
from decimal import Decimal
from django.core.management import call_command
from django.test import RequestFactory
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.tenants.models import Tenant, SubscriptionTier, TenantWallet, Transaction, Customer
from apps.catalog.models import Product
from apps.rbac.models import (
    User, TenantUser, Permission, Role, RolePermission,
    TenantUserRole, UserPermission, AuditLog
)
from apps.rbac.services import RBACService
from apps.tenants.services import WalletService


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def subscription_tier(db):
    """Create a subscription tier."""
    return SubscriptionTier.objects.create(
        name='Growth',
        monthly_price=Decimal('99.00'),
        yearly_price=Decimal('950.00'),
        monthly_messages=10000,
        max_products=1000,
        max_services=50,
        payment_facilitation=True,
        transaction_fee_percentage=Decimal('3.5')
    )


@pytest.fixture
def tenant_a(db, subscription_tier):
    """Create tenant A."""
    return Tenant.objects.create(
        name='Tenant A Business',
        slug='tenant-a',
        status='active',
        subscription_tier=subscription_tier,
        whatsapp_number='+1234567890',
        twilio_sid='tenant_a_sid',
        twilio_token='tenant_a_token',
        webhook_secret='tenant_a_secret',
        subscription_waived=True
    )


@pytest.fixture
def tenant_b(db, subscription_tier):
    """Create tenant B."""
    return Tenant.objects.create(
        name='Tenant B Business',
        slug='tenant-b',
        status='active',
        subscription_tier=subscription_tier,
        whatsapp_number='+0987654321',
        twilio_sid='tenant_b_sid',
        twilio_token='tenant_b_token',
        webhook_secret='tenant_b_secret',
        subscription_waived=True
    )


@pytest.fixture
def user1(db):
    """Create user 1."""
    return User.objects.create_user(
        email='user1@test.com',
        password='testpass123',
        first_name='User',
        last_name='One'
    )


@pytest.fixture
def user2(db):
    """Create user 2."""
    return User.objects.create_user(
        email='user2@test.com',
        password='testpass123',
        first_name='User',
        last_name='Two'
    )


@pytest.fixture
def permissions(db):
    """Create test permissions."""
    return {
        'catalog_view': Permission.objects.get_or_create(
            code='catalog:view',
            defaults={'label': 'View Catalog', 'category': 'catalog'}
        )[0],
        'catalog_edit': Permission.objects.get_or_create(
            code='catalog:edit',
            defaults={'label': 'Edit Catalog', 'category': 'catalog'}
        )[0],
        'finance_withdraw_initiate': Permission.objects.get_or_create(
            code='finance:withdraw:initiate',
            defaults={'label': 'Initiate Withdrawal', 'category': 'finance'}
        )[0],
        'finance_withdraw_approve': Permission.objects.get_or_create(
            code='finance:withdraw:approve',
            defaults={'label': 'Approve Withdrawal', 'category': 'finance'}
        )[0],
    }


@pytest.fixture
def request_factory():
    """Create request factory."""
    return APIRequestFactory()


# ============================================================================
# UNIT TESTS: Scope Resolution
# ============================================================================

@pytest.mark.django_db
class TestScopeResolutionMultipleRoles:
    """Test scope resolution with multiple roles."""
    
    def test_scope_resolution_aggregates_from_multiple_roles(self, tenant_a, user1, permissions):
        """Test that scopes are aggregated from multiple roles."""
        # Create tenant user
        tenant_user = TenantUser.objects.create(
            tenant=tenant_a,
            user=user1,
            invite_status='accepted'
        )
        
        # Create role 1 with catalog:view
        role1 = Role.objects.create(tenant=tenant_a, name='Viewer')
        RolePermission.objects.create(role=role1, permission=permissions['catalog_view'])
        
        # Create role 2 with catalog:edit
        role2 = Role.objects.create(tenant=tenant_a, name='Editor')
        RolePermission.objects.create(role=role2, permission=permissions['catalog_edit'])
        
        # Assign both roles
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role1)
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role2)
        
        # Resolve scopes
        scopes = RBACService.resolve_scopes(tenant_user)
        
        # Should have both permissions
        assert 'catalog:view' in scopes
        assert 'catalog:edit' in scopes
        assert len(scopes) == 2
    
    def test_scope_resolution_deduplicates_permissions(self, tenant_a, user1, permissions):
        """Test that duplicate permissions from multiple roles are deduplicated."""
        tenant_user = TenantUser.objects.create(
            tenant=tenant_a,
            user=user1,
            invite_status='accepted'
        )
        
        # Create two roles with same permission
        role1 = Role.objects.create(tenant=tenant_a, name='Role1')
        role2 = Role.objects.create(tenant=tenant_a, name='Role2')
        RolePermission.objects.create(role=role1, permission=permissions['catalog_view'])
        RolePermission.objects.create(role=role2, permission=permissions['catalog_view'])
        
        # Assign both roles
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role1)
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role2)
        
        # Resolve scopes
        scopes = RBACService.resolve_scopes(tenant_user)
        
        # Should have permission only once
        assert 'catalog:view' in scopes
        assert len(scopes) == 1


# ============================================================================
# UNIT TESTS: Deny Override
# ============================================================================

@pytest.mark.django_db
class TestDenyOverrideWinsOverRoleGrant:
    """Test that deny override wins over role grant."""
    
    def test_user_permission_deny_overrides_role_grant(self, tenant_a, user1, permissions):
        """Test that UserPermission deny overrides role grant."""
        tenant_user = TenantUser.objects.create(
            tenant=tenant_a,
            user=user1,
            invite_status='accepted'
        )
        
        # Create role with catalog:edit permission
        role = Role.objects.create(tenant=tenant_a, name='Editor')
        RolePermission.objects.create(role=role, permission=permissions['catalog_edit'])
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role)
        
        # Verify user has permission from role
        scopes_before = RBACService.resolve_scopes(tenant_user)
        assert 'catalog:edit' in scopes_before
        
        # Add deny override
        UserPermission.objects.deny_permission(
            tenant_user,
            permissions['catalog_edit'],
            reason='Temporary restriction'
        )
        
        # Resolve scopes again
        scopes_after = RBACService.resolve_scopes(tenant_user)
        
        # Should NOT have catalog:edit anymore
        assert 'catalog:edit' not in scopes_after
    
    def test_deny_override_does_not_affect_other_permissions(self, tenant_a, user1, permissions):
        """Test that deny override only affects the specific permission."""
        tenant_user = TenantUser.objects.create(
            tenant=tenant_a,
            user=user1,
            invite_status='accepted'
        )
        
        # Create role with both permissions
        role = Role.objects.create(tenant=tenant_a, name='Manager')
        RolePermission.objects.create(role=role, permission=permissions['catalog_view'])
        RolePermission.objects.create(role=role, permission=permissions['catalog_edit'])
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role)
        
        # Deny only catalog:edit
        UserPermission.objects.deny_permission(
            tenant_user,
            permissions['catalog_edit']
        )
        
        # Resolve scopes
        scopes = RBACService.resolve_scopes(tenant_user)
        
        # Should have catalog:view but not catalog:edit
        assert 'catalog:view' in scopes
        assert 'catalog:edit' not in scopes


# ============================================================================
# UNIT TESTS: Four-Eyes Validation
# ============================================================================

@pytest.mark.django_db
class TestFourEyesValidationRejectsSameUser:
    """Test four-eyes validation rejects same user."""
    
    def test_validate_four_eyes_rejects_same_user(self, user1):
        """Test that validate_four_eyes raises error for same user."""
        with pytest.raises(ValueError) as exc_info:
            RBACService.validate_four_eyes(user1.id, user1.id)
        
        assert 'Four-eyes validation failed' in str(exc_info.value)
        assert 'must be different users' in str(exc_info.value)
    
    def test_validate_four_eyes_accepts_different_users(self, user1, user2):
        """Test that validate_four_eyes passes for different users."""
        result = RBACService.validate_four_eyes(user1.id, user2.id)
        assert result is True


# ============================================================================
# API TESTS: Catalog View Permissions
# ============================================================================

@pytest.mark.django_db
class TestCatalogViewAPIPermissions:
    """Test GET /v1/products with/without catalog:view."""
    
    def test_get_products_with_catalog_view_returns_200(
        self, request_factory, tenant_a, user1, permissions
    ):
        """Test GET /v1/products with catalog:view returns 200."""
        from apps.catalog.views import ProductListView
        
        # Create tenant user with catalog:view
        tenant_user = TenantUser.objects.create(
            tenant=tenant_a,
            user=user1,
            invite_status='accepted'
        )
        role = Role.objects.create(tenant=tenant_a, name='Viewer')
        RolePermission.objects.create(role=role, permission=permissions['catalog_view'])
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role)
        
        # Create request
        request = request_factory.get('/v1/products')
        force_authenticate(request, user=user1)
        request.tenant = tenant_a
        request.membership = tenant_user
        request.scopes = RBACService.resolve_scopes(tenant_user)
        
        # Call view
        view = ProductListView.as_view()
        response = view(request)
        
        assert response.status_code == 200
    
    def test_get_products_without_catalog_view_returns_403(
        self, request_factory, tenant_a, user1
    ):
        """Test GET /v1/products without catalog:view returns 403."""
        from apps.catalog.views import ProductListView
        
        # Create tenant user without any permissions
        tenant_user = TenantUser.objects.create(
            tenant=tenant_a,
            user=user1,
            invite_status='accepted'
        )
        
        # Create request
        request = request_factory.get('/v1/products')
        force_authenticate(request, user=user1)
        request.tenant = tenant_a
        request.membership = tenant_user
        request.scopes = set()  # No scopes
        
        # Call view
        view = ProductListView.as_view()
        response = view(request)
        
        assert response.status_code == 403


# ============================================================================
# API TESTS: Catalog Edit Permissions
# ============================================================================

@pytest.mark.django_db
class TestCatalogEditAPIPermissions:
    """Test POST /v1/products with/without catalog:edit."""
    
    def test_post_products_with_catalog_edit_returns_201(
        self, request_factory, tenant_a, user1, permissions
    ):
        """Test POST /v1/products with catalog:edit returns 201."""
        from apps.catalog.views import ProductListView
        
        # Create tenant user with catalog:edit
        tenant_user = TenantUser.objects.create(
            tenant=tenant_a,
            user=user1,
            invite_status='accepted'
        )
        role = Role.objects.create(tenant=tenant_a, name='Editor')
        RolePermission.objects.create(role=role, permission=permissions['catalog_view'])
        RolePermission.objects.create(role=role, permission=permissions['catalog_edit'])
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role)
        
        # Create request
        request = request_factory.post('/v1/products', {
            'title': 'Test Product',
            'price': '99.99',
            'currency': 'USD'
        }, format='json')
        force_authenticate(request, user=user1)
        request.tenant = tenant_a
        request.membership = tenant_user
        request.scopes = RBACService.resolve_scopes(tenant_user)
        
        # Call view
        view = ProductListView.as_view()
        response = view(request)
        
        assert response.status_code == 201
    
    def test_post_products_without_catalog_edit_returns_403(
        self, request_factory, tenant_a, user1, permissions
    ):
        """Test POST /v1/products without catalog:edit returns 403."""
        from apps.catalog.views import ProductListView
        
        # Create tenant user with only catalog:view
        tenant_user = TenantUser.objects.create(
            tenant=tenant_a,
            user=user1,
            invite_status='accepted'
        )
        role = Role.objects.create(tenant=tenant_a, name='Viewer')
        RolePermission.objects.create(role=role, permission=permissions['catalog_view'])
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role)
        
        # Create request
        request = request_factory.post('/v1/products', {
            'title': 'Test Product',
            'price': '99.99',
            'currency': 'USD'
        }, format='json')
        force_authenticate(request, user=user1)
        request.tenant = tenant_a
        request.membership = tenant_user
        request.scopes = RBACService.resolve_scopes(tenant_user)
        
        # Call view
        view = ProductListView.as_view()
        response = view(request)
        
        assert response.status_code == 403


# ============================================================================
# API TESTS: Finance Withdrawal Four-Eyes
# ============================================================================

@pytest.mark.django_db
class TestFinanceWithdrawalFourEyes:
    """Test finance withdrawal initiate and approve with four-eyes."""
    
    def test_withdrawal_initiate_and_approve_with_different_users(
        self, tenant_a, user1, user2, permissions
    ):
        """Test withdrawal initiate and approve with different users succeeds."""
        # Create wallet
        wallet = TenantWallet.objects.create(
            tenant=tenant_a,
            balance=Decimal('1000.00'),
            currency='USD',
            minimum_withdrawal=Decimal('10.00')
        )
        
        # Create tenant users
        tenant_user1 = TenantUser.objects.create(
            tenant=tenant_a,
            user=user1,
            invite_status='accepted'
        )
        tenant_user2 = TenantUser.objects.create(
            tenant=tenant_a,
            user=user2,
            invite_status='accepted'
        )
        
        # Assign permissions
        role1 = Role.objects.create(tenant=tenant_a, name='Initiator')
        RolePermission.objects.create(role=role1, permission=permissions['finance_withdraw_initiate'])
        TenantUserRole.objects.create(tenant_user=tenant_user1, role=role1)
        
        role2 = Role.objects.create(tenant=tenant_a, name='Approver')
        RolePermission.objects.create(role=role2, permission=permissions['finance_withdraw_approve'])
        TenantUserRole.objects.create(tenant_user=tenant_user2, role=role2)
        
        # User1 initiates withdrawal
        transaction = WalletService.request_withdrawal(
            tenant=tenant_a,
            amount=Decimal('100.00'),
            initiated_by=user1
        )
        
        assert transaction.status == 'pending'
        assert transaction.initiated_by == user1
        
        # User2 approves withdrawal
        approved_txn = WalletService.approve_withdrawal(
            transaction_id=transaction.id,
            approved_by=user2
        )
        
        assert approved_txn.status == 'completed'
        assert approved_txn.initiated_by == user1
        assert approved_txn.approved_by == user2
    
    def test_withdrawal_approval_by_same_user_raises_error(
        self, tenant_a, user1, permissions
    ):
        """Test withdrawal approval by same user raises ValueError."""
        # Create wallet
        wallet = TenantWallet.objects.create(
            tenant=tenant_a,
            balance=Decimal('1000.00'),
            currency='USD',
            minimum_withdrawal=Decimal('10.00')
        )
        
        # User1 initiates withdrawal
        transaction = WalletService.request_withdrawal(
            tenant=tenant_a,
            amount=Decimal('100.00'),
            initiated_by=user1
        )
        
        # User1 tries to approve (should fail)
        with pytest.raises(ValueError) as exc_info:
            WalletService.approve_withdrawal(
                transaction_id=transaction.id,
                approved_by=user1
            )
        
        assert 'Four-eyes validation failed' in str(exc_info.value)
        
        # Transaction should still be pending
        transaction.refresh_from_db()
        assert transaction.status == 'pending'


# ============================================================================
# API TESTS: User Permission Override
# ============================================================================

@pytest.mark.django_db
class TestUserPermissionOverrideDeniesAccess:
    """Test user permission override denies access despite role grant."""
    
    def test_user_override_denies_access_despite_role(
        self, request_factory, tenant_a, user1, permissions
    ):
        """Test that user permission override denies access despite role grant."""
        from apps.catalog.views import ProductListView
        
        # Create tenant user with catalog:edit from role
        tenant_user = TenantUser.objects.create(
            tenant=tenant_a,
            user=user1,
            invite_status='accepted'
        )
        role = Role.objects.create(tenant=tenant_a, name='Editor')
        RolePermission.objects.create(role=role, permission=permissions['catalog_view'])
        RolePermission.objects.create(role=role, permission=permissions['catalog_edit'])
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role)
        
        # Verify user can create products
        request = request_factory.post('/v1/products', {
            'title': 'Test Product',
            'price': '99.99',
            'currency': 'USD'
        }, format='json')
        force_authenticate(request, user=user1)
        request.tenant = tenant_a
        request.membership = tenant_user
        request.scopes = RBACService.resolve_scopes(tenant_user)
        
        view = ProductListView.as_view()
        response = view(request)
        assert response.status_code == 201
        
        # Add deny override for catalog:edit
        UserPermission.objects.deny_permission(
            tenant_user,
            permissions['catalog_edit'],
            reason='Temporary restriction'
        )
        
        # Try to create product again
        request2 = request_factory.post('/v1/products', {
            'title': 'Another Product',
            'price': '49.99',
            'currency': 'USD'
        }, format='json')
        force_authenticate(request2, user=user1)
        request2.tenant = tenant_a
        request2.membership = tenant_user
        request2.scopes = RBACService.resolve_scopes(tenant_user)  # Re-resolve with override
        
        response2 = view(request2)
        assert response2.status_code == 403


# ============================================================================
# API TESTS: Cross-Tenant Access
# ============================================================================

@pytest.mark.django_db
class TestCrossTenantAccessBlocked:
    """Test switching X-TENANT-ID without membership returns 403."""
    
    def test_switching_tenant_without_membership_returns_403(
        self, tenant_a, tenant_b, user1
    ):
        """Test that user cannot access tenant they're not a member of."""
        from apps.tenants.middleware import TenantContextMiddleware
        from django.test import RequestFactory
        import hashlib
        from django.utils import timezone
        
        # Create membership in tenant_a only
        tenant_user_a = TenantUser.objects.create(
            tenant=tenant_a,
            user=user1,
            invite_status='accepted'
        )
        
        # Setup API key for tenant_b
        api_key = 'test-api-key'
        api_key_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
        tenant_b.api_keys = [{
            'key_hash': api_key_hash,
            'name': 'Test Key',
            'created_at': timezone.now().isoformat()
        }]
        tenant_b.save()
        
        # Create request for tenant_b
        factory = RequestFactory()
        request = factory.get(
            '/v1/products',
            HTTP_X_TENANT_ID=str(tenant_b.id),
            HTTP_X_TENANT_API_KEY=api_key
        )
        request.user = user1
        
        # Process with middleware
        middleware = TenantContextMiddleware(get_response=lambda r: None)
        response = middleware.process_request(request)
        
        # Should return 403
        assert response is not None
        assert response.status_code == 403


# ============================================================================
# API TESTS: Multi-Tenant User
# ============================================================================

@pytest.mark.django_db
class TestMultiTenantUserSeesCorrectData:
    """Test user with membership in multiple tenants sees correct data per tenant."""
    
    def test_user_sees_correct_products_per_tenant(
        self, request_factory, tenant_a, tenant_b, user1, permissions
    ):
        """Test that user sees only products for the current tenant."""
        from apps.catalog.views import ProductListView
        
        # Create memberships in both tenants
        tenant_user_a = TenantUser.objects.create(
            tenant=tenant_a,
            user=user1,
            invite_status='accepted'
        )
        tenant_user_b = TenantUser.objects.create(
            tenant=tenant_b,
            user=user1,
            invite_status='accepted'
        )
        
        # Create roles with catalog:view
        role_a = Role.objects.create(tenant=tenant_a, name='Viewer')
        RolePermission.objects.create(role=role_a, permission=permissions['catalog_view'])
        TenantUserRole.objects.create(tenant_user=tenant_user_a, role=role_a)
        
        role_b = Role.objects.create(tenant=tenant_b, name='Viewer')
        RolePermission.objects.create(role=role_b, permission=permissions['catalog_view'])
        TenantUserRole.objects.create(tenant_user=tenant_user_b, role=role_b)
        
        # Create products for each tenant
        product_a = Product.objects.create(
            tenant=tenant_a,
            title='Product A',
            price=Decimal('99.99'),
            currency='USD'
        )
        product_b = Product.objects.create(
            tenant=tenant_b,
            title='Product B',
            price=Decimal('49.99'),
            currency='USD'
        )
        
        # Request products for tenant_a
        request_a = request_factory.get('/v1/products')
        force_authenticate(request_a, user=user1)
        request_a.tenant = tenant_a
        request_a.membership = tenant_user_a
        request_a.scopes = RBACService.resolve_scopes(tenant_user_a)
        
        view = ProductListView.as_view()
        response_a = view(request_a)
        
        assert response_a.status_code == 200
        # Response uses pagination, so data is in 'results' key
        product_ids_a = [p['id'] for p in response_a.data['results']]
        assert str(product_a.id) in product_ids_a
        assert str(product_b.id) not in product_ids_a
        
        # Request products for tenant_b
        request_b = request_factory.get('/v1/products')
        force_authenticate(request_b, user=user1)
        request_b.tenant = tenant_b
        request_b.membership = tenant_user_b
        request_b.scopes = RBACService.resolve_scopes(tenant_user_b)
        
        response_b = view(request_b)
        
        assert response_b.status_code == 200
        product_ids_b = [p['id'] for p in response_b.data['results']]
        assert str(product_b.id) in product_ids_b
        assert str(product_a.id) not in product_ids_b


# ============================================================================
# API TESTS: Customer Isolation
# ============================================================================

@pytest.mark.django_db
class TestSamePhoneNumberCreatesSeparateCustomers:
    """Test same phone number in different tenants creates separate Customer records."""
    
    def test_same_phone_creates_separate_customers(self, tenant_a, tenant_b):
        """Test that same phone number creates separate Customer records per tenant."""
        phone = '+1234567890'
        
        # Create customer in tenant_a
        customer_a = Customer.objects.create(
            tenant=tenant_a,
            phone_e164=phone,
            name='Customer A'
        )
        
        # Create customer in tenant_b with same phone
        customer_b = Customer.objects.create(
            tenant=tenant_b,
            phone_e164=phone,
            name='Customer B'
        )
        
        # Should be different customer records
        assert customer_a.id != customer_b.id
        assert customer_a.tenant == tenant_a
        assert customer_b.tenant == tenant_b
        # Note: phone_e164 is encrypted, so direct comparison may not work
        # but the fact that both were created successfully proves isolation
        
        # Verify we can retrieve them separately by tenant
        customers_a = Customer.objects.filter(tenant=tenant_a)
        customers_b = Customer.objects.filter(tenant=tenant_b)
        
        assert customers_a.count() >= 1
        assert customers_b.count() >= 1
        assert customer_a in customers_a
        assert customer_b in customers_b
        assert customer_a not in customers_b
        assert customer_b not in customers_a


# ============================================================================
# SEEDER TESTS: Idempotency
# ============================================================================

@pytest.mark.django_db
class TestSeedPermissionsIdempotent:
    """Test seed_permissions is idempotent."""
    
    def test_seed_permissions_is_idempotent(self):
        """Test that running seed_permissions multiple times doesn't create duplicates."""
        # Run seed_permissions first time
        call_command('seed_permissions')
        count_first = Permission.objects.count()
        
        # Run seed_permissions second time
        call_command('seed_permissions')
        count_second = Permission.objects.count()
        
        # Count should be the same
        assert count_first == count_second
        assert count_first > 0  # Should have created some permissions
        
        # Verify specific permissions exist
        assert Permission.objects.filter(code='catalog:view').exists()
        assert Permission.objects.filter(code='catalog:edit').exists()
        assert Permission.objects.filter(code='finance:withdraw:initiate').exists()
        assert Permission.objects.filter(code='finance:withdraw:approve').exists()


@pytest.mark.django_db
class TestSeedTenantRolesIdempotent:
    """Test seed_tenant_roles is idempotent."""
    
    def test_seed_tenant_roles_is_idempotent(self, tenant_a):
        """Test that running seed_tenant_roles multiple times doesn't create duplicates."""
        # Ensure permissions exist
        call_command('seed_permissions')
        
        # Run seed_tenant_roles first time
        call_command('seed_tenant_roles', '--tenant', tenant_a.slug)
        count_first = Role.objects.filter(tenant=tenant_a).count()
        
        # Run seed_tenant_roles second time
        call_command('seed_tenant_roles', '--tenant', tenant_a.slug)
        count_second = Role.objects.filter(tenant=tenant_a).count()
        
        # Count should be the same
        assert count_first == count_second
        assert count_first > 0  # Should have created some roles
        
        # Verify specific roles exist
        assert Role.objects.filter(tenant=tenant_a, name='Owner').exists()
        assert Role.objects.filter(tenant=tenant_a, name='Admin').exists()
        assert Role.objects.filter(tenant=tenant_a, name='Finance Admin').exists()
        
        # Verify roles have permissions
        owner_role = Role.objects.get(tenant=tenant_a, name='Owner')
        owner_perms = RolePermission.objects.filter(role=owner_role).count()
        assert owner_perms > 0
