"""
Tests for order API endpoints.

Verifies:
- Order listing with filtering
- Order creation
- Order detail retrieval
- Order status updates
- RBAC scope enforcement
- Automated message triggers
"""
import pytest
import hashlib
from decimal import Decimal
from django.utils import timezone
from rest_framework.test import APIClient
from unittest.mock import patch

from apps.tenants.models import Tenant, Customer, SubscriptionTier
from apps.orders.models import Order
from apps.rbac.models import User, TenantUser, Permission, Role, RolePermission, TenantUserRole


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
    """Create a tenant with valid API key."""
    # Hash the test API key
    test_api_key = 'test-key'
    api_key_hash = hashlib.sha256(test_api_key.encode('utf-8')).hexdigest()
    
    return Tenant.objects.create(
        name='Test Business',
        slug='test-business',
        whatsapp_number='+1234567890',
        twilio_sid='test_sid',
        twilio_token='test_token',
        webhook_secret='test_secret',
        subscription_tier=subscription_tier,
        status='active',
        subscription_waived=True,
        api_keys=[{
            'key_hash': api_key_hash,
            'name': 'Test Key',
            'created_at': timezone.now().isoformat()
        }]
    )


@pytest.fixture
def customer(db, tenant):
    """Create a customer."""
    return Customer.objects.create(
        tenant=tenant,
        phone_e164='+1234567890',
        name='Test Customer'
    )


@pytest.fixture
def user(db):
    """Create a user."""
    return User.objects.create_user(
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def orders_view_permission(db):
    """Create orders:view permission."""
    return Permission.objects.get_or_create(
        code='orders:view',
        defaults={
            'label': 'View Orders',
            'description': 'View orders',
            'category': 'orders'
        }
    )[0]


@pytest.fixture
def orders_edit_permission(db):
    """Create orders:edit permission."""
    return Permission.objects.get_or_create(
        code='orders:edit',
        defaults={
            'label': 'Edit Orders',
            'description': 'Create and update orders',
            'category': 'orders'
        }
    )[0]


@pytest.fixture
def viewer_membership(db, tenant, user, orders_view_permission):
    """Create a tenant membership with orders:view permission."""
    membership = TenantUser.objects.create(
        tenant=tenant,
        user=user,
        invite_status='accepted',
        joined_at=timezone.now()
    )
    
    role = Role.objects.create(
        tenant=tenant,
        name='Viewer',
        description='Can view orders'
    )
    RolePermission.objects.create(role=role, permission=orders_view_permission)
    TenantUserRole.objects.create(tenant_user=membership, role=role)
    
    return membership


@pytest.fixture
def editor_membership(db, tenant, user, orders_view_permission, orders_edit_permission):
    """Create a tenant membership with orders:view and orders:edit permissions."""
    membership = TenantUser.objects.create(
        tenant=tenant,
        user=user,
        invite_status='accepted',
        joined_at=timezone.now()
    )
    
    role = Role.objects.create(
        tenant=tenant,
        name='Editor',
        description='Can view and edit orders'
    )
    RolePermission.objects.create(role=role, permission=orders_view_permission)
    RolePermission.objects.create(role=role, permission=orders_edit_permission)
    TenantUserRole.objects.create(tenant_user=membership, role=role)
    
    return membership


@pytest.fixture
def sample_order(db, tenant, customer):
    """Create a sample order."""
    return Order.objects.create(
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


@pytest.mark.django_db
class TestOrderListAPI:
    """Tests for GET /v1/orders endpoint."""
    
    def test_list_orders_with_view_permission(self, tenant, user, viewer_membership, sample_order):
        """Test that user with orders:view can list orders."""
        from apps.rbac.services import RBACService
        
        client = APIClient()
        client.force_authenticate(user=user)
        
        # Mock middleware to inject tenant context
        def mock_process_request(request):
            request.tenant = tenant
            request.membership = viewer_membership
            request.scopes = RBACService.resolve_scopes(viewer_membership)
            return None
        
        with patch('apps.tenants.middleware.TenantContextMiddleware.process_request', side_effect=mock_process_request):
            response = client.get(
                '/v1/orders/',
                HTTP_X_TENANT_ID=str(tenant.id),
                HTTP_X_TENANT_API_KEY='test-key'
            )
        
        assert response.status_code == 200
        assert 'results' in response.data
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['id'] == str(sample_order.id)
    
    def test_list_orders_without_permission(self, tenant, user, sample_order):
        """Test that user without orders:view cannot list orders."""
        # Create membership without orders:view permission
        membership = TenantUser.objects.create(
            tenant=tenant,
            user=user,
            invite_status='accepted',
            joined_at=timezone.now()
        )
        
        client = APIClient()
        client.force_authenticate(user=user)
        
        # Mock middleware with empty scopes
        def mock_process_request(request):
            request.tenant = tenant
            request.membership = membership
            request.scopes = set()
            return None
        
        with patch('apps.tenants.middleware.TenantContextMiddleware.process_request', side_effect=mock_process_request):
            response = client.get(
                '/v1/orders/',
                HTTP_X_TENANT_ID=str(tenant.id),
                HTTP_X_TENANT_API_KEY='test-key'
            )
        
        assert response.status_code == 403
    
    def test_filter_orders_by_status(self, tenant, user, viewer_membership, customer):
        """Test filtering orders by status."""
        from apps.rbac.services import RBACService
        
        # Create orders with different statuses
        Order.objects.create(
            tenant=tenant,
            customer=customer,
            currency='USD',
            subtotal=Decimal('50.00'),
            shipping=Decimal('5.00'),
            total=Decimal('55.00'),
            status='draft',
            items=[]
        )
        Order.objects.create(
            tenant=tenant,
            customer=customer,
            currency='USD',
            subtotal=Decimal('100.00'),
            shipping=Decimal('10.00'),
            total=Decimal('110.00'),
            status='paid',
            items=[]
        )
        
        client = APIClient()
        client.force_authenticate(user=user)
        
        # Mock middleware
        def mock_process_request(request):
            request.tenant = tenant
            request.membership = viewer_membership
            request.scopes = RBACService.resolve_scopes(viewer_membership)
            return None
        
        with patch('apps.tenants.middleware.TenantContextMiddleware.process_request', side_effect=mock_process_request):
            response = client.get(
                '/v1/orders/?status=paid',
                HTTP_X_TENANT_ID=str(tenant.id),
                HTTP_X_TENANT_API_KEY='test-key'
            )
        
        assert response.status_code == 200
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['status'] == 'paid'


@pytest.mark.django_db
class TestOrderCreateAPI:
    """Tests for POST /v1/orders endpoint."""
    
    def test_create_order_with_edit_permission(self, tenant, user, editor_membership, customer):
        """Test that user with orders:edit can create orders."""
        from apps.rbac.services import RBACService
        
        client = APIClient()
        client.force_authenticate(user=user)
        
        order_data = {
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
        
        # Mock middleware
        def mock_process_request(request):
            request.tenant = tenant
            request.membership = editor_membership
            request.scopes = RBACService.resolve_scopes(editor_membership)
            return None
        
        with patch('apps.tenants.middleware.TenantContextMiddleware.process_request', side_effect=mock_process_request):
            response = client.post(
                '/v1/orders/',
                data=order_data,
                format='json',
                HTTP_X_TENANT_ID=str(tenant.id),
                HTTP_X_TENANT_API_KEY='test-key'
            )
        
        assert response.status_code == 201
        assert response.data['customer'] == str(customer.id)
        assert response.data['total'] == '110.00'
        assert response.data['status'] == 'draft'
    
    def test_create_order_without_permission(self, tenant, user, viewer_membership, customer):
        """Test that user without orders:edit cannot create orders."""
        from apps.rbac.services import RBACService
        
        client = APIClient()
        client.force_authenticate(user=user)
        
        order_data = {
            'customer': str(customer.id),
            'currency': 'USD',
            'subtotal': '100.00',
            'shipping': '10.00',
            'total': '110.00',
            'status': 'draft',
            'items': []
        }
        
        # Mock middleware
        def mock_process_request(request):
            request.tenant = tenant
            request.membership = viewer_membership
            request.scopes = RBACService.resolve_scopes(viewer_membership)
            return None
        
        with patch('apps.tenants.middleware.TenantContextMiddleware.process_request', side_effect=mock_process_request):
            response = client.post(
                '/v1/orders/',
                data=order_data,
                format='json',
                HTTP_X_TENANT_ID=str(tenant.id),
                HTTP_X_TENANT_API_KEY='test-key'
            )
        
        assert response.status_code == 403


@pytest.mark.django_db
class TestOrderDetailAPI:
    """Tests for GET /v1/orders/{id} endpoint."""
    
    def test_get_order_detail(self, tenant, user, viewer_membership, sample_order):
        """Test retrieving order details."""
        from apps.rbac.services import RBACService
        
        client = APIClient()
        client.force_authenticate(user=user)
        
        # Mock middleware
        def mock_process_request(request):
            request.tenant = tenant
            request.membership = viewer_membership
            request.scopes = RBACService.resolve_scopes(viewer_membership)
            return None
        
        with patch('apps.tenants.middleware.TenantContextMiddleware.process_request', side_effect=mock_process_request):
            response = client.get(
                f'/v1/orders/{sample_order.id}',
                HTTP_X_TENANT_ID=str(tenant.id),
                HTTP_X_TENANT_API_KEY='test-key'
            )
        
        assert response.status_code == 200
        assert response.data['id'] == str(sample_order.id)
        assert 'items' in response.data
        assert len(response.data['items']) == 1


@pytest.mark.django_db
class TestOrderUpdateAPI:
    """Tests for PUT /v1/orders/{id} endpoint."""
    
    def test_update_order_status(self, tenant, user, editor_membership, sample_order, mock_middleware):
        """Test updating order status."""
        from apps.rbac.services import RBACService
        
        client = APIClient()
        client.force_authenticate(user=user)
        
        with patch('apps.tenants.middleware.TenantContextMiddleware.process_view',
                   side_effect=mock_middleware(tenant, editor_membership, RBACService.resolve_scopes(editor_membership))):
            response = client.put(
                f'/v1/orders/{sample_order.id}',
                data={'status': 'paid', 'payment_ref': 'PAY123'},
                format='json',
                HTTP_X_TENANT_ID=str(tenant.id),
                HTTP_X_TENANT_API_KEY='test-key'
            )
        
        assert response.status_code == 200
        assert response.data['status'] == 'paid'
        assert response.data['payment_ref'] == 'PAY123'
        assert response.data['paid_at'] is not None
    
    @patch('apps.messaging.tasks.send_shipment_notification.delay')
    def test_invalid_status_transition(self, mock_celery_task, tenant, user, editor_membership, sample_order, mock_middleware):
        """Test that invalid status transitions are rejected."""
        from apps.rbac.services import RBACService
        
        # Set order to fulfilled (terminal state)
        sample_order.status = 'fulfilled'
        sample_order.save()
        
        client = APIClient()
        client.force_authenticate(user=user)
        
        with patch('apps.tenants.middleware.TenantContextMiddleware.process_view',
                   side_effect=mock_middleware(tenant, editor_membership, RBACService.resolve_scopes(editor_membership))):
            response = client.put(
                f'/v1/orders/{sample_order.id}',
                data={'status': 'paid'},
                format='json',
                HTTP_X_TENANT_ID=str(tenant.id),
                HTTP_X_TENANT_API_KEY='test-key'
            )
        
        assert response.status_code == 400
        assert 'status' in response.data
