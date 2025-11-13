"""
Tests for API key management endpoints.

Tests:
- List API keys (masked)
- Generate new API key
- Revoke API key
- RBAC enforcement (users:manage scope required)
"""
import pytest
import hashlib
from django.urls import reverse
from rest_framework.test import APIClient
from apps.rbac.models import User, TenantUser, Role, Permission, RolePermission, TenantUserRole
from apps.tenants.models import Tenant


@pytest.fixture
def tenant(db):
    """Create a test tenant."""
    return Tenant.objects.create(
        name='Test Tenant',
        slug='test-tenant',
        whatsapp_number='+1234567890',
        status='active'
    )


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email='test@example.com',
        password='testpass123',
        first_name='Test',
        last_name='User'
    )


@pytest.fixture
def tenant_user_with_scope(db, tenant, user):
    """Create tenant user with users:manage scope."""
    # Create tenant user
    tenant_user = TenantUser.objects.create(
        tenant=tenant,
        user=user,
        is_active=True,
        invite_status='accepted'
    )
    
    # Create permission
    permission = Permission.objects.create(
        code='users:manage',
        label='Manage Users',
        category='users'
    )
    
    # Create or get role with permission
    role, _ = Role.objects.get_or_create(
        tenant=tenant,
        name='Admin',
        defaults={'is_system': True}
    )
    
    RolePermission.objects.create(
        role=role,
        permission=permission
    )
    
    # Assign role to user
    TenantUserRole.objects.create(
        tenant_user=tenant_user,
        role=role
    )
    
    return tenant_user


@pytest.fixture
def tenant_user_without_scope(db, tenant):
    """Create tenant user without users:manage scope."""
    user = User.objects.create_user(
        email='noscope@example.com',
        password='testpass123'
    )
    
    tenant_user = TenantUser.objects.create(
        tenant=tenant,
        user=user,
        is_active=True,
        invite_status='accepted'
    )
    
    return tenant_user


@pytest.fixture
def api_client():
    """Create API client."""
    return APIClient()


@pytest.mark.django_db
class TestAPIKeysList:
    """Tests for GET /v1/settings/api-keys"""
    
    def test_list_api_keys_empty(self, api_client, tenant, tenant_user_with_scope):
        """Test listing API keys (tenant may have initial key from signal)."""
        # Manually call view since we need to inject tenant context
        from apps.tenants.views_api_keys import api_keys_view
        from rest_framework.test import APIRequestFactory
        
        # Clear any existing API keys for this test
        tenant.api_keys = []
        tenant.save()
        
        factory = APIRequestFactory()
        request = factory.get('/v1/settings/api-keys')
        request.tenant = tenant
        request.user = tenant_user_with_scope.user
        request.scopes = {'users:manage'}
        
        response = api_keys_view(request)
        
        assert response.status_code == 200
        assert response.data['total'] == 0
        assert response.data['api_keys'] == []
    
    def test_list_api_keys_with_existing(self, api_client, tenant, tenant_user_with_scope):
        """Test listing API keys when some exist."""
        # Add some API keys to tenant
        tenant.api_keys = [
            {
                'id': 'key1',
                'key_hash': 'hash1',
                'key_preview': 'abcd1234',
                'name': 'Production Key',
                'created_at': '2024-01-01T00:00:00Z',
                'created_by_email': 'admin@example.com',
                'last_used_at': None
            },
            {
                'id': 'key2',
                'key_hash': 'hash2',
                'key_preview': 'efgh5678',
                'name': 'Development Key',
                'created_at': '2024-01-02T00:00:00Z',
                'created_by_email': 'dev@example.com',
                'last_used_at': '2024-01-03T00:00:00Z'
            }
        ]
        tenant.save()
        
        # Make request
        from apps.tenants.views_api_keys import api_keys_view
        from rest_framework.test import APIRequestFactory
        
        factory = APIRequestFactory()
        request = factory.get('/v1/settings/api-keys')
        request.tenant = tenant
        request.user = tenant_user_with_scope.user
        request.scopes = {'users:manage'}
        
        response = api_keys_view(request)
        
        assert response.status_code == 200
        assert response.data['total'] == 2
        assert len(response.data['api_keys']) == 2
        
        # Verify masked data
        key1 = response.data['api_keys'][0]
        assert key1['id'] == 'key1'
        assert key1['name'] == 'Production Key'
        assert key1['key_preview'] == 'abcd1234'
        assert 'key_hash' not in key1  # Hash should not be exposed
    
    def test_list_api_keys_requires_scope(self, api_client, tenant, tenant_user_without_scope):
        """Test that listing API keys requires users:manage scope."""
        from apps.tenants.views_api_keys import api_keys_view
        from rest_framework.test import APIRequestFactory
        
        factory = APIRequestFactory()
        request = factory.get('/v1/settings/api-keys')
        request.tenant = tenant
        request.user = tenant_user_without_scope.user
        request.scopes = set()  # No scopes
        
        response = api_keys_view(request)
        
        assert response.status_code == 403
        assert 'users:manage' in response.data['detail']


@pytest.mark.django_db
class TestAPIKeyGeneration:
    """Tests for POST /v1/settings/api-keys"""
    
    def test_generate_api_key_success(self, api_client, tenant, tenant_user_with_scope):
        """Test generating a new API key."""
        from apps.tenants.views_api_keys import api_keys_view
        from rest_framework.test import APIRequestFactory, force_authenticate
        
        # Clear existing keys
        tenant.api_keys = []
        tenant.save()
        
        factory = APIRequestFactory()
        # Create request with JSON data - format='json' enables request.data parsing
        request = factory.post(
            '/v1/settings/api-keys',
            data={'name': 'Test Key'},
            format='json'
        )
        
        # Attach tenant context (normally done by middleware)
        request.tenant = tenant
        request.user = tenant_user_with_scope.user
        request.scopes = {'users:manage'}
        
        # Force authentication for DRF
        force_authenticate(request, user=tenant_user_with_scope.user)
        
        response = api_keys_view(request)
        
        assert response.status_code == 201
        assert 'api_key' in response.data
        assert 'key_id' in response.data
        assert response.data['name'] == 'Test Key'
        assert 'warning' in response.data
        
        # Verify key was added to tenant
        tenant.refresh_from_db()
        assert len(tenant.api_keys) == 1
        assert tenant.api_keys[0]['name'] == 'Test Key'
        
        # Verify key hash is stored (not plain key)
        plain_key = response.data['api_key']
        expected_hash = hashlib.sha256(plain_key.encode()).hexdigest()
        assert tenant.api_keys[0]['key_hash'] == expected_hash
    
    def test_generate_api_key_without_name(self, api_client, tenant, tenant_user_with_scope):
        """Test that generating API key requires a name."""
        from apps.tenants.views_api_keys import api_keys_view
        from rest_framework.test import APIRequestFactory
        import json
        
        factory = APIRequestFactory()
        request = factory.post(
            '/v1/settings/api-keys',
            data=json.dumps({}),
            content_type='application/json'
        )
        request.tenant = tenant
        request.user = tenant_user_with_scope.user
        request.scopes = {'users:manage'}
        
        response = api_keys_view(request)
        
        assert response.status_code == 400
        # Serializer returns validation errors in 'name' field
        assert 'name' in response.data
        assert 'required' in str(response.data['name']).lower()
    
    def test_generate_api_key_requires_scope(self, api_client, tenant, tenant_user_without_scope):
        """Test that generating API key requires users:manage scope."""
        from apps.tenants.views_api_keys import api_keys_view
        from rest_framework.test import APIRequestFactory
        
        factory = APIRequestFactory()
        request = factory.post('/v1/settings/api-keys', {'name': 'Test Key'})
        request.tenant = tenant
        request.user = tenant_user_without_scope.user
        request.scopes = set()
        
        response = api_keys_view(request)
        
        assert response.status_code == 403


@pytest.mark.django_db
class TestAPIKeyRevocation:
    """Tests for DELETE /v1/settings/api-keys/{key_id}"""
    
    def test_revoke_api_key_success(self, api_client, tenant, tenant_user_with_scope):
        """Test revoking an API key."""
        # Add API key to tenant
        tenant.api_keys = [
            {
                'id': 'key-to-revoke',
                'key_hash': 'hash123',
                'key_preview': 'abcd1234',
                'name': 'Old Key',
                'created_at': '2024-01-01T00:00:00Z',
                'created_by_email': 'admin@example.com'
            }
        ]
        tenant.save()
        
        from apps.tenants.views_api_keys import api_key_revoke_view
        from rest_framework.test import APIRequestFactory
        
        factory = APIRequestFactory()
        request = factory.delete('/v1/settings/api-keys/key-to-revoke')
        request.tenant = tenant
        request.user = tenant_user_with_scope.user
        request.scopes = {'users:manage'}
        request.META = {}
        
        response = api_key_revoke_view(request, key_id='key-to-revoke')
        
        assert response.status_code == 200
        assert 'revoked successfully' in response.data['message']
        
        # Verify key was removed from tenant
        tenant.refresh_from_db()
        assert len(tenant.api_keys) == 0
    
    def test_revoke_nonexistent_key(self, api_client, tenant, tenant_user_with_scope):
        """Test revoking a key that doesn't exist."""
        from apps.tenants.views_api_keys import api_key_revoke_view
        from rest_framework.test import APIRequestFactory
        
        factory = APIRequestFactory()
        request = factory.delete('/v1/settings/api-keys/nonexistent')
        request.tenant = tenant
        request.user = tenant_user_with_scope.user
        request.scopes = {'users:manage'}
        
        response = api_key_revoke_view(request, key_id='nonexistent')
        
        assert response.status_code == 404
        assert 'not found' in response.data['error']
    
    def test_revoke_api_key_requires_scope(self, api_client, tenant, tenant_user_without_scope):
        """Test that revoking API key requires users:manage scope."""
        from apps.tenants.views_api_keys import api_key_revoke_view
        from rest_framework.test import APIRequestFactory
        
        factory = APIRequestFactory()
        request = factory.delete('/v1/settings/api-keys/some-key')
        request.tenant = tenant
        request.user = tenant_user_without_scope.user
        request.scopes = set()
        
        response = api_key_revoke_view(request, key_id='some-key')
        
        assert response.status_code == 403
