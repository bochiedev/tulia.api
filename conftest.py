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
