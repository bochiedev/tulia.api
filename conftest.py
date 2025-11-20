"""
Pytest configuration and fixtures.
"""
import pytest
from django.conf import settings
import django
from django.core.management import call_command


def pytest_configure(config):
    """Configure Django settings for tests."""
    settings.DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'ATOMIC_REQUESTS': False,
    }
    django.setup()


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    """Set up test database with migrations."""
    with django_db_blocker.unblock():
        call_command('migrate', '--run-syncdb', verbosity=0)


@pytest.fixture
def api_client():
    """Return DRF API client."""
    from rest_framework.test import APIClient
    return APIClient()



@pytest.fixture
def tenant(db):
    """Create a test tenant."""
    from apps.tenants.models import Tenant
    return Tenant.objects.create(
        name='Test Tenant',
        slug='test-tenant',
        status='active'
    )


@pytest.fixture
def customer(db, tenant):
    """Create a test customer."""
    from apps.tenants.models import Customer
    return Customer.objects.create(
        tenant=tenant,
        phone_e164='+254712345678',
        name='Test Customer'
    )


@pytest.fixture
def product(db, tenant):
    """Create a test product."""
    from apps.catalog.models import Product
    from decimal import Decimal
    return Product.objects.create(
        tenant=tenant,
        title='Test Product',
        description='A test product',
        price=Decimal('99.99'),
        currency='USD',
        is_active=True
    )


@pytest.fixture
def other_tenant(db):
    """Create another test tenant for isolation tests."""
    from apps.tenants.models import Tenant
    return Tenant.objects.create(
        name='Other Tenant',
        slug='other-tenant',
        is_active=True
    )


@pytest.fixture
def api_client_with_tenant(api_client, tenant):
    """Return API client with tenant context."""
    from unittest.mock import Mock
    
    # Mock request with tenant
    def make_request(*args, **kwargs):
        response = api_client.generic(*args, **kwargs)
        return response
    
    # Add tenant to client
    api_client.tenant = tenant
    
    # Mock the request to include tenant
    original_generic = api_client.generic
    
    def generic_with_tenant(method, path, data='', content_type='application/octet-stream', **extra):
        # Add tenant to extra kwargs
        if not extra.get('HTTP_X_TENANT_ID'):
            extra['HTTP_X_TENANT_ID'] = str(tenant.id)
        return original_generic(method, path, data, content_type, **extra)
    
    api_client.generic = generic_with_tenant
    
    # Also patch the request object
    from unittest.mock import patch
    with patch('apps.core.permissions.HasTenantScopes.has_permission', return_value=True):
        yield api_client


@pytest.fixture
def tenant_user(db, tenant):
    """Create a test tenant user with analytics:view scope."""
    from django.contrib.auth import get_user_model
    from apps.rbac.models import TenantUser, Permission
    
    User = get_user_model()
    user = User.objects.create_user(
        email='test@example.com',
        password='testpass123'
    )
    
    tenant_user = TenantUser.objects.create(
        tenant=tenant,
        user=user,
        is_active=True
    )
    
    # Grant analytics:view permission
    permission, _ = Permission.objects.get_or_create(
        code='analytics:view',
        defaults={
            'label': 'View Analytics',
            'description': 'Can view analytics',
            'category': 'analytics'
        }
    )
    
    from apps.rbac.models import UserPermission
    UserPermission.objects.create(
        tenant_user=tenant_user,
        permission=permission,
        granted=True
    )
    
    return tenant_user


@pytest.fixture
def tenant_user_no_scopes(db, tenant):
    """Create a test tenant user with no scopes."""
    from django.contrib.auth import get_user_model
    from apps.rbac.models import TenantUser
    
    User = get_user_model()
    user = User.objects.create_user(
        email='test_no_scopes@example.com',
        password='testpass123'
    )
    
    tenant_user = TenantUser.objects.create(
        tenant=tenant,
        user=user,
        is_active=True
    )
    
    return tenant_user


@pytest.fixture
def conversation(db, tenant, customer):
    """Create a test conversation."""
    from apps.messaging.models import Conversation
    
    return Conversation.objects.create(
        tenant=tenant,
        customer=customer,
        channel='whatsapp',
        status='active'
    )
