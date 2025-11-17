"""
Tests for Knowledge Base API endpoints.
"""
import pytest
import json
from unittest.mock import patch, MagicMock
from rest_framework.test import APIClient
from django.urls import reverse

from apps.bot.models import KnowledgeEntry
from apps.tenants.models import Tenant
from apps.rbac.models import TenantUser, Role, Permission, RolePermission
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def tenant(db):
    """Create a test tenant."""
    return Tenant.objects.create(
        name="Test Tenant",
        slug="test-tenant",
        whatsapp_number="+1234567890"
    )


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123"
    )


@pytest.fixture
def tenant_user_with_scope(tenant, user, db):
    """Create tenant user with integrations:manage scope."""
    # Create permission
    permission = Permission.objects.get_or_create(
        code='integrations:manage',
        defaults={
            'label': 'Manage Integrations',
            'description': 'Manage integrations',
            'category': 'integrations'
        }
    )[0]
    
    # Create or get role
    role, _ = Role.objects.get_or_create(
        tenant=tenant,
        name='Admin',
        defaults={'description': 'Admin role'}
    )
    
    # Assign permission to role
    RolePermission.objects.create(
        role=role,
        permission=permission
    )
    
    # Create tenant user
    tenant_user = TenantUser.objects.create(
        tenant=tenant,
        user=user
    )
    tenant_user.roles.add(role)
    
    return tenant_user


@pytest.fixture
def tenant_user_without_scope(tenant, user, db):
    """Create tenant user without integrations:manage scope."""
    return TenantUser.objects.create(
        tenant=tenant,
        user=user
    )


@pytest.fixture
def api_client():
    """Create API client."""
    return APIClient()


@pytest.fixture
def mock_openai_embeddings():
    """Mock OpenAI embeddings for testing."""
    with patch('openai.OpenAI') as mock_openai:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai.return_value = mock_client
        yield mock_client


@pytest.mark.django_db
class TestKnowledgeEntryListAPI:
    """Test knowledge entry list endpoint."""
    
    def test_list_requires_scope(self, api_client, tenant, tenant_user_without_scope):
        """Test that list endpoint requires integrations:manage scope."""
        api_client.force_authenticate(user=tenant_user_without_scope.user)
        
        response = api_client.get(
            '/v1/bot/knowledge/',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        # Should return 401 or 403 (401 if middleware not set up, 403 if no scope)
        assert response.status_code in [401, 403]
    
    def test_list_with_scope(self, api_client, tenant, tenant_user_with_scope, mock_openai_embeddings):
        """Test that list endpoint works with proper scope."""
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        # Create test entries
        KnowledgeEntry.objects.create(
            tenant=tenant,
            entry_type='faq',
            title='Test FAQ',
            content='Test content',
            is_active=True
        )
        
        response = api_client.get(
            '/v1/bot/knowledge/',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 200
        assert 'results' in response.data
        assert len(response.data['results']) == 1
    
    def test_list_filters_by_tenant(self, api_client, tenant, tenant_user_with_scope, db, mock_openai_embeddings):
        """Test that list only returns entries for authenticated tenant."""
        # Create another tenant
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            whatsapp_number="+0987654321"
        )
        
        # Create entries for both tenants
        KnowledgeEntry.objects.create(
            tenant=tenant,
            entry_type='faq',
            title='Tenant 1 Entry',
            content='Content 1',
            is_active=True
        )
        
        KnowledgeEntry.objects.create(
            tenant=other_tenant,
            entry_type='faq',
            title='Tenant 2 Entry',
            content='Content 2',
            is_active=True
        )
        
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        response = api_client.get(
            '/v1/bot/knowledge/',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 200
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['title'] == 'Tenant 1 Entry'
    
    def test_list_filters_by_entry_type(self, api_client, tenant, tenant_user_with_scope, mock_openai_embeddings):
        """Test filtering by entry_type."""
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        # Create entries of different types
        KnowledgeEntry.objects.create(
            tenant=tenant,
            entry_type='faq',
            title='FAQ Entry',
            content='FAQ content',
            is_active=True
        )
        
        KnowledgeEntry.objects.create(
            tenant=tenant,
            entry_type='policy',
            title='Policy Entry',
            content='Policy content',
            is_active=True
        )
        
        response = api_client.get(
            '/v1/bot/knowledge/?entry_type=faq',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 200
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['entry_type'] == 'faq'


@pytest.mark.django_db
class TestKnowledgeEntryCreateAPI:
    """Test knowledge entry create endpoint."""
    
    def test_create_requires_scope(self, api_client, tenant, tenant_user_without_scope):
        """Test that create endpoint requires integrations:manage scope."""
        api_client.force_authenticate(user=tenant_user_without_scope.user)
        
        response = api_client.post(
            '/v1/bot/knowledge/',
            data={
                'entry_type': 'faq',
                'title': 'Test',
                'content': 'Test content'
            },
            format='json',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        # Should return 401 or 403 (401 if middleware not set up, 403 if no scope)
        assert response.status_code in [401, 403]
    
    def test_create_with_scope(self, api_client, tenant, tenant_user_with_scope, mock_openai_embeddings):
        """Test creating knowledge entry with proper scope."""
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        response = api_client.post(
            '/v1/bot/knowledge/',
            data={
                'entry_type': 'faq',
                'title': 'What are your hours?',
                'content': 'We are open Monday-Friday 9am-5pm',
                'category': 'general',
                'keywords_list': ['hours', 'schedule'],
                'priority': 80
            },
            format='json',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 201
        assert response.data['title'] == 'What are your hours?'
        assert response.data['entry_type'] == 'faq'
        assert response.data['priority'] == 80
        assert 'embedding' in response.data
    
    def test_create_validates_entry_type(self, api_client, tenant, tenant_user_with_scope):
        """Test that invalid entry_type is rejected."""
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        response = api_client.post(
            '/v1/bot/knowledge/',
            data={
                'entry_type': 'invalid_type',
                'title': 'Test',
                'content': 'Test content'
            },
            format='json',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 400


@pytest.mark.django_db
class TestKnowledgeEntrySearchAPI:
    """Test knowledge entry search endpoint."""
    
    def test_search_requires_scope(self, api_client, tenant, tenant_user_without_scope):
        """Test that search endpoint requires integrations:manage scope."""
        api_client.force_authenticate(user=tenant_user_without_scope.user)
        
        response = api_client.get(
            '/v1/bot/knowledge/search/?q=test',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        # Should return 401 or 403 (401 if middleware not set up, 403 if no scope)
        assert response.status_code in [401, 403]
    
    def test_search_requires_query(self, api_client, tenant, tenant_user_with_scope):
        """Test that search requires query parameter."""
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        response = api_client.get(
            '/v1/bot/knowledge/search/',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 400
        assert 'error' in response.data
    
    def test_search_with_query(self, api_client, tenant, tenant_user_with_scope, mock_openai_embeddings):
        """Test search with query parameter."""
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        # Create test entry
        KnowledgeEntry.objects.create(
            tenant=tenant,
            entry_type='faq',
            title='What are your hours?',
            content='We are open Monday-Friday 9am-5pm',
            embedding=[0.1] * 1536,
            is_active=True
        )
        
        response = api_client.get(
            '/v1/bot/knowledge/search/?q=hours&min_similarity=0.0',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 200
        assert isinstance(response.data, list)


@pytest.mark.django_db
class TestKnowledgeEntryBulkImportAPI:
    """Test knowledge entry bulk import endpoint."""
    
    def test_bulk_import_requires_scope(self, api_client, tenant, tenant_user_without_scope):
        """Test that bulk import requires integrations:manage scope."""
        api_client.force_authenticate(user=tenant_user_without_scope.user)
        
        response = api_client.post(
            '/v1/bot/knowledge/bulk_import/',
            data={'entries': []},
            format='json',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        # Should return 401 or 403 (401 if middleware not set up, 403 if no scope)
        assert response.status_code in [401, 403]
    
    def test_bulk_import_with_scope(self, api_client, tenant, tenant_user_with_scope, mock_openai_embeddings):
        """Test bulk import with proper scope."""
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        response = api_client.post(
            '/v1/bot/knowledge/bulk_import/',
            data={
                'entries': [
                    {
                        'entry_type': 'faq',
                        'title': 'Question 1',
                        'content': 'Answer 1',
                        'priority': 50
                    },
                    {
                        'entry_type': 'policy',
                        'title': 'Policy 1',
                        'content': 'Policy details',
                        'priority': 80
                    }
                ]
            },
            format='json',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 201
        assert response.data['success_count'] == 2
        assert response.data['error_count'] == 0
        assert len(response.data['created_ids']) == 2
    
    def test_bulk_import_validates_entries(self, api_client, tenant, tenant_user_with_scope):
        """Test that bulk import validates each entry."""
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        response = api_client.post(
            '/v1/bot/knowledge/bulk_import/',
            data={
                'entries': [
                    {
                        'entry_type': 'invalid_type',
                        'title': 'Test',
                        'content': 'Test content'
                    }
                ]
            },
            format='json',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 400


@pytest.mark.django_db
class TestKnowledgeEntryUpdateAPI:
    """Test knowledge entry update endpoint."""
    
    def test_update_requires_scope(self, api_client, tenant, tenant_user_without_scope, mock_openai_embeddings):
        """Test that update endpoint requires integrations:manage scope."""
        # Create entry
        entry = KnowledgeEntry.objects.create(
            tenant=tenant,
            entry_type='faq',
            title='Test',
            content='Test content',
            is_active=True
        )
        
        api_client.force_authenticate(user=tenant_user_without_scope.user)
        
        response = api_client.patch(
            f'/v1/bot/knowledge/{entry.id}/',
            data={'title': 'Updated'},
            format='json',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 403
    
    def test_update_with_scope(self, api_client, tenant, tenant_user_with_scope, mock_openai_embeddings):
        """Test updating knowledge entry with proper scope."""
        # Create entry
        entry = KnowledgeEntry.objects.create(
            tenant=tenant,
            entry_type='faq',
            title='Original Title',
            content='Original content',
            is_active=True
        )
        
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        response = api_client.patch(
            f'/v1/bot/knowledge/{entry.id}/',
            data={'title': 'Updated Title'},
            format='json',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 200
        assert response.data['title'] == 'Updated Title'
        assert response.data['version'] == 2  # Version should increment


@pytest.mark.django_db
class TestKnowledgeEntryDeleteAPI:
    """Test knowledge entry delete endpoint."""
    
    def test_delete_requires_scope(self, api_client, tenant, tenant_user_without_scope, mock_openai_embeddings):
        """Test that delete endpoint requires integrations:manage scope."""
        # Create entry
        entry = KnowledgeEntry.objects.create(
            tenant=tenant,
            entry_type='faq',
            title='Test',
            content='Test content',
            is_active=True
        )
        
        api_client.force_authenticate(user=tenant_user_without_scope.user)
        
        response = api_client.delete(
            f'/v1/bot/knowledge/{entry.id}/',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 403
    
    def test_delete_with_scope(self, api_client, tenant, tenant_user_with_scope, mock_openai_embeddings):
        """Test deleting knowledge entry with proper scope."""
        # Create entry
        entry = KnowledgeEntry.objects.create(
            tenant=tenant,
            entry_type='faq',
            title='Test',
            content='Test content',
            is_active=True
        )
        
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        response = api_client.delete(
            f'/v1/bot/knowledge/{entry.id}/',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 204
        
        # Entry should still exist but be inactive
        entry.refresh_from_db()
        assert entry.is_active is False
