"""
RBAC tests for catalog API endpoints.

Verifies that catalog endpoints enforce scope requirements and create audit logs.
"""
import pytest
import json
from decimal import Decimal
from django.test import RequestFactory
from rest_framework.test import force_authenticate, APIRequestFactory

from apps.tenants.models import Tenant, SubscriptionTier
from apps.catalog.models import Product
from apps.catalog.views import ProductListView, ProductDetailView
from apps.rbac.models import User, TenantUser, Permission, Role, RolePermission, TenantUserRole, AuditLog


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
        subscription_waived=True  # Bypass subscription checks for tests
    )


@pytest.fixture
def user(db):
    """Create a user."""
    return User.objects.create_user(
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def catalog_view_permission(db):
    """Create catalog:view permission."""
    return Permission.objects.get_or_create(
        code='catalog:view',
        defaults={
            'label': 'View Catalog',
            'description': 'View products and services',
            'category': 'catalog'
        }
    )[0]


@pytest.fixture
def catalog_edit_permission(db):
    """Create catalog:edit permission."""
    return Permission.objects.get_or_create(
        code='catalog:edit',
        defaults={
            'label': 'Edit Catalog',
            'description': 'Create, update, and delete products and services',
            'category': 'catalog'
        }
    )[0]


@pytest.fixture
def viewer_role(db, tenant, catalog_view_permission):
    """Create a viewer role with catalog:view permission."""
    role = Role.objects.create(
        tenant=tenant,
        name='Viewer',
        description='Can view catalog',
        is_system=False
    )
    RolePermission.objects.create(
        role=role,
        permission=catalog_view_permission
    )
    return role


@pytest.fixture
def editor_role(db, tenant, catalog_view_permission, catalog_edit_permission):
    """Create an editor role with catalog:view and catalog:edit permissions."""
    role = Role.objects.create(
        tenant=tenant,
        name='Editor',
        description='Can view and edit catalog',
        is_system=False
    )
    RolePermission.objects.create(role=role, permission=catalog_view_permission)
    RolePermission.objects.create(role=role, permission=catalog_edit_permission)
    return role


@pytest.fixture
def tenant_user_viewer(db, user, tenant, viewer_role):
    """Create a tenant user with viewer role."""
    tenant_user = TenantUser.objects.create(
        user=user,
        tenant=tenant,
        invite_status='accepted'
    )
    TenantUserRole.objects.create(
        tenant_user=tenant_user,
        role=viewer_role
    )
    return tenant_user


@pytest.fixture
def tenant_user_editor(db, user, tenant, editor_role):
    """Create a tenant user with editor role."""
    tenant_user = TenantUser.objects.create(
        user=user,
        tenant=tenant,
        invite_status='accepted'
    )
    TenantUserRole.objects.create(
        tenant_user=tenant_user,
        role=editor_role
    )
    return tenant_user


@pytest.fixture
def product(db, tenant):
    """Create a test product."""
    return Product.objects.create(
        tenant=tenant,
        title='Test Product',
        description='Test description',
        price=Decimal('99.99'),
        currency='USD',
        is_active=True
    )


@pytest.fixture
def request_factory():
    """Create an API request factory."""
    return APIRequestFactory()


@pytest.mark.django_db
class TestCatalogViewPermissions:
    """Test catalog view endpoint permissions."""
    
    def test_list_products_requires_catalog_view(self, request_factory, tenant, user, tenant_user_viewer):
        """GET /v1/products requires catalog:view scope."""
        # Create request with scopes
        request = request_factory.get('/v1/products')
        force_authenticate(request, user=user)
        request.tenant = tenant
        request.membership = tenant_user_viewer
        request.scopes = {'catalog:view'}
        
        # Should succeed with catalog:view scope
        view = ProductListView.as_view()
        response = view(request)
        assert response.status_code == 200
    
    def test_list_products_denied_without_scope(self, request_factory, tenant, user):
        """GET /v1/products denied without catalog:view scope."""
        # Create request without scopes
        request = request_factory.get('/v1/products')
        force_authenticate(request, user=user)
        request.tenant = tenant
        request.scopes = set()
        
        # Should fail without catalog:view scope
        view = ProductListView.as_view()
        response = view(request)
        assert response.status_code == 403
    
    def test_get_product_requires_catalog_view(self, request_factory, tenant, user, tenant_user_viewer, product):
        """GET /v1/products/{id} requires catalog:view scope."""
        # Create request with scopes
        request = request_factory.get(f'/v1/products/{product.id}')
        force_authenticate(request, user=user)
        request.tenant = tenant
        request.membership = tenant_user_viewer
        request.scopes = {'catalog:view'}
        
        # Should succeed with catalog:view scope
        view = ProductDetailView.as_view()
        response = view(request, product_id=str(product.id))
        assert response.status_code == 200
    
    def test_get_product_denied_without_scope(self, request_factory, tenant, user, product):
        """GET /v1/products/{id} denied without catalog:view scope."""
        # Create request without scopes
        request = request_factory.get(f'/v1/products/{product.id}')
        force_authenticate(request, user=user)
        request.tenant = tenant
        request.scopes = set()
        
        # Should fail without catalog:view scope
        view = ProductDetailView.as_view()
        response = view(request, product_id=str(product.id))
        assert response.status_code == 403


@pytest.mark.django_db
class TestCatalogEditPermissions:
    """Test catalog edit endpoint permissions."""
    
    def test_create_product_requires_catalog_edit(self, request_factory, tenant, user, tenant_user_editor):
        """POST /v1/products requires catalog:edit scope."""
        # Create request with scopes
        request = request_factory.post('/v1/products', {
            'title': 'New Product',
            'price': '49.99',
            'currency': 'USD'
        }, format='json')
        force_authenticate(request, user=user)
        request.tenant = tenant
        request.membership = tenant_user_editor
        request.scopes = {'catalog:view', 'catalog:edit'}
        
        # Should succeed with catalog:edit scope
        view = ProductListView.as_view()
        response = view(request)
        assert response.status_code == 201
    
    def test_create_product_denied_without_scope(self, request_factory, tenant, user, tenant_user_viewer):
        """POST /v1/products denied without catalog:edit scope."""
        # Create request with only catalog:view scope
        request = request_factory.post('/v1/products', {
            'title': 'New Product',
            'price': '49.99',
            'currency': 'USD'
        }, format='json')
        force_authenticate(request, user=user)
        request.tenant = tenant
        request.membership = tenant_user_viewer
        request.scopes = {'catalog:view'}  # Missing catalog:edit
        
        # Should fail without catalog:edit scope
        view = ProductListView.as_view()
        response = view(request)
        assert response.status_code == 403
    
    def test_update_product_requires_catalog_edit(self, request_factory, tenant, user, tenant_user_editor, product):
        """PUT /v1/products/{id} requires catalog:edit scope."""
        # Create request with scopes
        request = request_factory.put(f'/v1/products/{product.id}', {
            'title': 'Updated Product'
        }, format='json')
        force_authenticate(request, user=user)
        request.tenant = tenant
        request.membership = tenant_user_editor
        request.scopes = {'catalog:view', 'catalog:edit'}
        
        # Should succeed with catalog:edit scope
        view = ProductDetailView.as_view()
        response = view(request, product_id=str(product.id))
        assert response.status_code == 200
    
    def test_update_product_denied_without_scope(self, request_factory, tenant, user, tenant_user_viewer, product):
        """PUT /v1/products/{id} denied without catalog:edit scope."""
        # Create request with only catalog:view scope
        request = request_factory.put(f'/v1/products/{product.id}', {
            'title': 'Updated Product'
        }, format='json')
        force_authenticate(request, user=user)
        request.tenant = tenant
        request.membership = tenant_user_viewer
        request.scopes = {'catalog:view'}  # Missing catalog:edit
        
        # Should fail without catalog:edit scope
        view = ProductDetailView.as_view()
        response = view(request, product_id=str(product.id))
        assert response.status_code == 403
    
    def test_delete_product_requires_catalog_edit(self, request_factory, tenant, user, tenant_user_editor, product):
        """DELETE /v1/products/{id} requires catalog:edit scope."""
        # Create request with scopes
        request = request_factory.delete(f'/v1/products/{product.id}')
        force_authenticate(request, user=user)
        request.tenant = tenant
        request.membership = tenant_user_editor
        request.scopes = {'catalog:view', 'catalog:edit'}
        
        # Should succeed with catalog:edit scope
        view = ProductDetailView.as_view()
        response = view(request, product_id=str(product.id))
        assert response.status_code == 204
    
    def test_delete_product_denied_without_scope(self, request_factory, tenant, user, tenant_user_viewer, product):
        """DELETE /v1/products/{id} denied without catalog:edit scope."""
        # Create request with only catalog:view scope
        request = request_factory.delete(f'/v1/products/{product.id}')
        force_authenticate(request, user=user)
        request.tenant = tenant
        request.membership = tenant_user_viewer
        request.scopes = {'catalog:view'}  # Missing catalog:edit
        
        # Should fail without catalog:edit scope
        view = ProductDetailView.as_view()
        response = view(request, product_id=str(product.id))
        assert response.status_code == 403


@pytest.mark.django_db
class TestCatalogAuditLogs:
    """Test audit log creation for catalog operations."""
    
    def test_create_product_creates_audit_log(self, request_factory, tenant, user, tenant_user_editor):
        """Creating a product creates an audit log entry."""
        # Clear existing audit logs
        AuditLog.objects.all().delete()
        
        # Create request
        request = request_factory.post('/v1/products', {
            'title': 'Audited Product',
            'price': '29.99',
            'currency': 'USD'
        }, format='json')
        force_authenticate(request, user=user)
        request.tenant = tenant
        request.membership = tenant_user_editor
        request.scopes = {'catalog:view', 'catalog:edit'}
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        
        # Create product
        view = ProductListView.as_view()
        response = view(request)
        assert response.status_code == 201
        
        # Verify audit log was created
        audit_logs = AuditLog.objects.filter(action='product_created')
        assert audit_logs.count() == 1
        
        log = audit_logs.first()
        assert log.user == user
        assert log.tenant == tenant
        assert log.target_type == 'Product'
        assert log.metadata['title'] == 'Audited Product'
    
    def test_update_product_creates_audit_log(self, request_factory, tenant, user, tenant_user_editor, product):
        """Updating a product creates an audit log entry with diff."""
        # Clear existing audit logs
        AuditLog.objects.all().delete()
        
        # Create request
        request = request_factory.put(f'/v1/products/{product.id}', {
            'title': 'Updated Title'
        }, format='json')
        force_authenticate(request, user=user)
        request.tenant = tenant
        request.membership = tenant_user_editor
        request.scopes = {'catalog:view', 'catalog:edit'}
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        
        # Update product
        view = ProductDetailView.as_view()
        response = view(request, product_id=str(product.id))
        assert response.status_code == 200
        
        # Verify audit log was created
        audit_logs = AuditLog.objects.filter(action='product_updated')
        assert audit_logs.count() == 1
        
        log = audit_logs.first()
        assert log.user == user
        assert log.tenant == tenant
        assert log.target_type == 'Product'
        assert log.target_id == product.id
        assert 'before' in log.diff
        assert 'after' in log.diff
        assert log.diff['before']['title'] == 'Test Product'
        assert log.diff['after']['title'] == 'Updated Title'
    
    def test_delete_product_creates_audit_log(self, request_factory, tenant, user, tenant_user_editor, product):
        """Deleting a product creates an audit log entry."""
        # Clear existing audit logs
        AuditLog.objects.all().delete()
        
        product_id = product.id
        product_title = product.title
        
        # Create request
        request = request_factory.delete(f'/v1/products/{product_id}')
        force_authenticate(request, user=user)
        request.tenant = tenant
        request.membership = tenant_user_editor
        request.scopes = {'catalog:view', 'catalog:edit'}
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        
        # Delete product
        view = ProductDetailView.as_view()
        response = view(request, product_id=str(product_id))
        assert response.status_code == 204
        
        # Verify audit log was created
        audit_logs = AuditLog.objects.filter(action='product_deleted')
        assert audit_logs.count() == 1
        
        log = audit_logs.first()
        assert log.user == user
        assert log.tenant == tenant
        assert log.target_type == 'Product'
        assert log.target_id == product_id
        assert log.metadata['title'] == product_title
