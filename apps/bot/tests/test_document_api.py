"""
Tests for RAG document management API endpoints.
"""
import pytest
import io
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from apps.tenants.models import Tenant
from apps.rbac.models import User, TenantUser, Role, Permission
from apps.bot.models import Document, DocumentChunk


@pytest.fixture
def tenant():
    """Create a test tenant."""
    return Tenant.objects.create(
        name="Test Tenant",
        slug="test-tenant"
    )


@pytest.fixture
def user():
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123"
    )


@pytest.fixture
def tenant_user_with_scope(tenant, user):
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
    
    # Create role with permission
    role = Role.objects.create(
        tenant=tenant,
        name='Integration Manager',
        is_system=False
    )
    role.permissions.add(permission)
    
    # Create tenant user with role
    tenant_user = TenantUser.objects.create(
        tenant=tenant,
        user=user
    )
    tenant_user.roles.add(role)
    
    return tenant_user


@pytest.fixture
def tenant_user_without_scope(tenant, user):
    """Create tenant user WITHOUT integrations:manage scope."""
    return TenantUser.objects.create(
        tenant=tenant,
        user=user
    )


@pytest.fixture
def api_client():
    """Create API client."""
    return APIClient()


@pytest.fixture
def sample_pdf_file():
    """Create a sample PDF file for testing."""
    content = b'%PDF-1.4\n%Test PDF content\n%%EOF'
    return SimpleUploadedFile(
        "test_document.pdf",
        content,
        content_type="application/pdf"
    )


@pytest.fixture
def sample_txt_file():
    """Create a sample text file for testing."""
    content = b'This is a test document for RAG processing.'
    return SimpleUploadedFile(
        "test_document.txt",
        content,
        content_type="text/plain"
    )


@pytest.fixture
def sample_document(tenant):
    """Create a sample document."""
    return Document.objects.create(
        tenant=tenant,
        file_name="test.pdf",
        file_type="pdf",
        file_size=1024,
        status="completed",
        chunk_count=5,
        total_tokens=500
    )


@pytest.mark.django_db
class TestDocumentUploadView:
    """Tests for document upload endpoint."""
    
    def test_upload_requires_scope(self, api_client, tenant, tenant_user_without_scope, sample_pdf_file):
        """Test that upload requires integrations:manage scope."""
        api_client.force_authenticate(user=tenant_user_without_scope.user)
        
        response = api_client.post(
            '/v1/bot/documents/upload',
            {'file': sample_pdf_file},
            format='multipart',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        # Should return 401 or 403 (401 if middleware not set up, 403 if no scope)
        assert response.status_code in [401, 403]
    
    def test_upload_pdf_success(self, api_client, tenant, tenant_user_with_scope, sample_pdf_file):
        """Test successful PDF upload."""
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        response = api_client.post(
            '/v1/bot/documents/upload',
            {'file': sample_pdf_file},
            format='multipart',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 201
        assert 'id' in response.data
        assert response.data['file_name'] == 'test_document.pdf'
        assert response.data['file_type'] == 'pdf'
        assert response.data['status'] == 'pending'
        
        # Verify document created in database
        document = Document.objects.get(id=response.data['id'])
        assert document.tenant == tenant
        assert document.file_name == 'test_document.pdf'
    
    def test_upload_txt_success(self, api_client, tenant, tenant_user_with_scope, sample_txt_file):
        """Test successful TXT upload."""
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        response = api_client.post(
            '/v1/bot/documents/upload',
            {'file': sample_txt_file},
            format='multipart',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 201
        assert response.data['file_type'] == 'txt'
    
    def test_upload_invalid_file_type(self, api_client, tenant, tenant_user_with_scope):
        """Test upload with invalid file type."""
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        invalid_file = SimpleUploadedFile(
            "test.docx",
            b'Invalid content',
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        
        response = api_client.post(
            '/v1/bot/documents/upload',
            {'file': invalid_file},
            format='multipart',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 400
        assert 'file' in response.data
    
    def test_upload_file_too_large(self, api_client, tenant, tenant_user_with_scope):
        """Test upload with file exceeding size limit."""
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        # Create a file larger than 10MB
        large_content = b'x' * (11 * 1024 * 1024)  # 11MB
        large_file = SimpleUploadedFile(
            "large.pdf",
            large_content,
            content_type="application/pdf"
        )
        
        response = api_client.post(
            '/v1/bot/documents/upload',
            {'file': large_file},
            format='multipart',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 400
        assert 'file' in response.data
    
    def test_upload_missing_file(self, api_client, tenant, tenant_user_with_scope):
        """Test upload without file."""
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        response = api_client.post(
            '/v1/bot/documents/upload',
            {},
            format='multipart',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 400
        assert 'file' in response.data


@pytest.mark.django_db
class TestDocumentListView:
    """Tests for document list endpoint."""
    
    def test_list_requires_scope(self, api_client, tenant, tenant_user_without_scope):
        """Test that list requires integrations:manage scope."""
        api_client.force_authenticate(user=tenant_user_without_scope.user)
        
        response = api_client.get(
            '/v1/bot/documents/',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code in [401, 403]
    
    def test_list_success(self, api_client, tenant, tenant_user_with_scope, sample_document):
        """Test successful document list."""
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        response = api_client.get(
            '/v1/bot/documents/',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 200
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['id'] == str(sample_document.id)
    
    def test_list_tenant_isolation(self, api_client, tenant, tenant_user_with_scope):
        """Test that users only see their tenant's documents."""
        # Create document for another tenant
        other_tenant = Tenant.objects.create(name="Other Tenant", slug="other")
        Document.objects.create(
            tenant=other_tenant,
            file_name="other.pdf",
            file_type="pdf",
            file_size=1024,
            status="completed"
        )
        
        # Create document for current tenant
        Document.objects.create(
            tenant=tenant,
            file_name="mine.pdf",
            file_type="pdf",
            file_size=1024,
            status="completed"
        )
        
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        response = api_client.get(
            '/v1/bot/documents/',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 200
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['file_name'] == 'mine.pdf'
    
    def test_list_filter_by_status(self, api_client, tenant, tenant_user_with_scope):
        """Test filtering documents by status."""
        Document.objects.create(
            tenant=tenant,
            file_name="pending.pdf",
            file_type="pdf",
            file_size=1024,
            status="pending"
        )
        Document.objects.create(
            tenant=tenant,
            file_name="completed.pdf",
            file_type="pdf",
            file_size=1024,
            status="completed"
        )
        
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        response = api_client.get(
            '/v1/bot/documents/?status=completed',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 200
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['status'] == 'completed'
    
    def test_list_search_by_name(self, api_client, tenant, tenant_user_with_scope):
        """Test searching documents by file name."""
        Document.objects.create(
            tenant=tenant,
            file_name="product_catalog.pdf",
            file_type="pdf",
            file_size=1024,
            status="completed"
        )
        Document.objects.create(
            tenant=tenant,
            file_name="business_faq.pdf",
            file_type="pdf",
            file_size=1024,
            status="completed"
        )
        
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        response = api_client.get(
            '/v1/bot/documents/?search=catalog',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 200
        assert len(response.data['results']) == 1
        assert 'catalog' in response.data['results'][0]['file_name']


@pytest.mark.django_db
class TestDocumentDetailView:
    """Tests for document detail endpoint."""
    
    def test_detail_requires_scope(self, api_client, tenant, tenant_user_without_scope, sample_document):
        """Test that detail requires integrations:manage scope."""
        api_client.force_authenticate(user=tenant_user_without_scope.user)
        
        response = api_client.get(
            f'/v1/bot/documents/{sample_document.id}',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code in [401, 403]
    
    def test_detail_success(self, api_client, tenant, tenant_user_with_scope, sample_document):
        """Test successful document detail retrieval."""
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        response = api_client.get(
            f'/v1/bot/documents/{sample_document.id}',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 200
        assert response.data['id'] == str(sample_document.id)
        assert response.data['file_name'] == sample_document.file_name
    
    def test_detail_not_found(self, api_client, tenant, tenant_user_with_scope):
        """Test detail with non-existent document."""
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        import uuid
        fake_id = uuid.uuid4()
        
        response = api_client.get(
            f'/v1/bot/documents/{fake_id}',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 404
    
    def test_detail_tenant_isolation(self, api_client, tenant, tenant_user_with_scope):
        """Test that users cannot access other tenant's documents."""
        # Create document for another tenant
        other_tenant = Tenant.objects.create(name="Other Tenant", slug="other")
        other_document = Document.objects.create(
            tenant=other_tenant,
            file_name="other.pdf",
            file_type="pdf",
            file_size=1024,
            status="completed"
        )
        
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        response = api_client.get(
            f'/v1/bot/documents/{other_document.id}',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 404


@pytest.mark.django_db
class TestDocumentDeleteView:
    """Tests for document delete endpoint."""
    
    def test_delete_requires_scope(self, api_client, tenant, tenant_user_without_scope, sample_document):
        """Test that delete requires integrations:manage scope."""
        api_client.force_authenticate(user=tenant_user_without_scope.user)
        
        response = api_client.delete(
            f'/v1/bot/documents/{sample_document.id}',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code in [401, 403]
    
    def test_delete_success(self, api_client, tenant, tenant_user_with_scope, sample_document):
        """Test successful document deletion."""
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        response = api_client.delete(
            f'/v1/bot/documents/{sample_document.id}',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 204
        
        # Verify document deleted
        assert not Document.objects.filter(id=sample_document.id).exists()
    
    def test_delete_tenant_isolation(self, api_client, tenant, tenant_user_with_scope):
        """Test that users cannot delete other tenant's documents."""
        # Create document for another tenant
        other_tenant = Tenant.objects.create(name="Other Tenant", slug="other")
        other_document = Document.objects.create(
            tenant=other_tenant,
            file_name="other.pdf",
            file_type="pdf",
            file_size=1024,
            status="completed"
        )
        
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        response = api_client.delete(
            f'/v1/bot/documents/{other_document.id}',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 404
        
        # Verify document still exists
        assert Document.objects.filter(id=other_document.id).exists()


@pytest.mark.django_db
class TestDocumentStatusView:
    """Tests for document status endpoint."""
    
    def test_status_requires_scope(self, api_client, tenant, tenant_user_without_scope, sample_document):
        """Test that status requires integrations:manage scope."""
        api_client.force_authenticate(user=tenant_user_without_scope.user)
        
        response = api_client.get(
            f'/v1/bot/documents/{sample_document.id}/status',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code in [401, 403]
    
    def test_status_success(self, api_client, tenant, tenant_user_with_scope, sample_document):
        """Test successful status retrieval."""
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        response = api_client.get(
            f'/v1/bot/documents/{sample_document.id}/status',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 200
        assert response.data['id'] == str(sample_document.id)
        assert response.data['status'] == 'completed'
        assert 'progress_percentage' in response.data


@pytest.mark.django_db
class TestDocumentChunkListView:
    """Tests for document chunks list endpoint."""
    
    def test_chunks_requires_scope(self, api_client, tenant, tenant_user_without_scope, sample_document):
        """Test that chunks list requires integrations:manage scope."""
        api_client.force_authenticate(user=tenant_user_without_scope.user)
        
        response = api_client.get(
            f'/v1/bot/documents/{sample_document.id}/chunks',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code in [401, 403]
    
    def test_chunks_success(self, api_client, tenant, tenant_user_with_scope, sample_document):
        """Test successful chunks list retrieval."""
        # Create chunks
        DocumentChunk.objects.create(
            tenant=tenant,
            document=sample_document,
            chunk_index=0,
            content="First chunk content",
            token_count=10
        )
        DocumentChunk.objects.create(
            tenant=tenant,
            document=sample_document,
            chunk_index=1,
            content="Second chunk content",
            token_count=10
        )
        
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        response = api_client.get(
            f'/v1/bot/documents/{sample_document.id}/chunks',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 200
        assert len(response.data['results']) == 2
        assert response.data['results'][0]['chunk_index'] == 0
        assert response.data['results'][1]['chunk_index'] == 1
    
    def test_chunks_tenant_isolation(self, api_client, tenant, tenant_user_with_scope, sample_document):
        """Test that users only see chunks from their tenant's documents."""
        # Create chunk for current tenant
        DocumentChunk.objects.create(
            tenant=tenant,
            document=sample_document,
            chunk_index=0,
            content="My chunk",
            token_count=10
        )
        
        # Create chunk for another tenant
        other_tenant = Tenant.objects.create(name="Other Tenant", slug="other")
        other_document = Document.objects.create(
            tenant=other_tenant,
            file_name="other.pdf",
            file_type="pdf",
            file_size=1024,
            status="completed"
        )
        DocumentChunk.objects.create(
            tenant=other_tenant,
            document=other_document,
            chunk_index=0,
            content="Other chunk",
            token_count=10
        )
        
        api_client.force_authenticate(user=tenant_user_with_scope.user)
        
        response = api_client.get(
            f'/v1/bot/documents/{sample_document.id}/chunks',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        assert response.status_code == 200
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['content'] == 'My chunk'
