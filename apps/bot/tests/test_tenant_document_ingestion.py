"""
Tests for tenant document ingestion service.
"""
import pytest
from io import BytesIO
from unittest.mock import Mock, patch

from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.tenants.models import Tenant
from apps.bot.models_tenant_documents import TenantDocument, TenantDocumentChunk
from apps.bot.services.tenant_document_ingestion_service import TenantDocumentIngestionService


@pytest.mark.django_db
class TestTenantDocumentIngestionService:
    """Test tenant document ingestion service."""
    
    def setup_method(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            whatsapp_number="+1234567890"
        )
    
    @patch('apps.bot.services.tenant_document_ingestion_service.PineconeVectorStore')
    @patch('apps.bot.services.tenant_document_ingestion_service.EmbeddingService')
    def test_ingest_text_document(self, mock_embedding_service, mock_vector_store):
        """Test ingesting a text document."""
        # Mock embedding service
        mock_embedding_instance = Mock()
        mock_embedding_instance.model = 'text-embedding-3-small'
        mock_embedding_instance.embed_batch.return_value = [
            {
                'embedding': [0.1] * 1536,
                'tokens': 100,
                'cost': 0.0001
            }
        ]
        mock_embedding_service.create_for_tenant.return_value = mock_embedding_instance
        
        # Mock vector store
        mock_vector_instance = Mock()
        mock_vector_instance.upsert.return_value = {'upserted_count': 1}
        mock_vector_store.create_from_settings.return_value = mock_vector_instance
        
        # Create service
        service = TenantDocumentIngestionService.create_for_tenant(self.tenant)
        
        # Create test file
        test_content = "This is a test document with some content for testing."
        test_file = BytesIO(test_content.encode('utf-8'))
        
        # Ingest document
        document = service.ingest_document(
            file=test_file,
            filename="test.txt",
            title="Test Document",
            description="A test document"
        )
        
        # Verify document was created
        assert document.tenant == self.tenant
        assert document.title == "Test Document"
        assert document.document_type == "txt"
        assert document.status == "completed"
        assert document.vector_namespace == f"tenant_{self.tenant.id}"
        
        # Verify chunks were created
        chunks = TenantDocumentChunk.objects.filter(document=document)
        assert chunks.count() > 0
        
        # Verify vector store was called
        mock_vector_instance.upsert.assert_called_once()
    
    @patch('apps.bot.services.tenant_document_ingestion_service.PineconeVectorStore')
    @patch('apps.bot.services.tenant_document_ingestion_service.EmbeddingService')
    def test_search_documents(self, mock_embedding_service, mock_vector_store):
        """Test searching documents."""
        # Mock embedding service
        mock_embedding_instance = Mock()
        mock_embedding_instance.embed_text.return_value = {
            'embedding': [0.1] * 1536,
            'tokens': 10,
            'cost': 0.00001
        }
        mock_embedding_service.create_for_tenant.return_value = mock_embedding_instance
        
        # Mock vector store search results
        mock_vector_instance = Mock()
        mock_search_result = Mock()
        mock_search_result.id = "test_vector_id"
        mock_search_result.score = 0.85
        mock_search_result.metadata = {"test": "metadata"}
        mock_vector_instance.search.return_value = [mock_search_result]
        mock_vector_store.create_from_settings.return_value = mock_vector_instance
        
        # Create test document and chunk
        document = TenantDocument.objects.create(
            tenant=self.tenant,
            title="Test Document",
            document_type="txt",
            file_path="test.txt",
            file_size=100,
            file_hash="testhash",
            status="completed"
        )
        
        chunk = TenantDocumentChunk.objects.create(
            document=document,
            chunk_index=0,
            content="This is test content for searching.",
            token_count=10,
            vector_id="test_vector_id"
        )
        
        # Create service and search
        service = TenantDocumentIngestionService.create_for_tenant(self.tenant)
        results = service.search_documents(
            query="test content",
            top_k=5,
            min_score=0.7
        )
        
        # Verify results
        assert len(results) == 1
        result = results[0]
        assert result["document_id"] == str(document.id)
        assert result["document_title"] == "Test Document"
        assert result["content"] == "This is test content for searching."
        assert result["score"] == 0.85
        
        # Verify vector store was called with correct parameters
        mock_vector_instance.search.assert_called_once()
        call_args = mock_vector_instance.search.call_args
        assert call_args[1]["namespace"] == f"tenant_{self.tenant.id}"
        assert call_args[1]["filter_dict"]["tenant_id"] == str(self.tenant.id)
    
    def test_tenant_isolation(self):
        """Test that tenant isolation is enforced."""
        # Create two tenants
        tenant1 = self.tenant
        tenant2 = Tenant.objects.create(
            name="Test Tenant 2",
            slug="test-tenant-2",
            whatsapp_number="+1234567891"  # Different number to avoid unique constraint
        )
        
        # Create documents for each tenant
        doc1 = TenantDocument.objects.create(
            tenant=tenant1,
            title="Tenant 1 Document",
            document_type="txt",
            file_path="doc1.txt",
            file_size=100,
            file_hash="hash1",
            status="completed"
        )
        
        doc2 = TenantDocument.objects.create(
            tenant=tenant2,
            title="Tenant 2 Document", 
            document_type="txt",
            file_path="doc2.txt",
            file_size=100,
            file_hash="hash2",
            status="completed"
        )
        
        # Verify tenant 1 can only see their documents
        tenant1_docs = TenantDocument.objects.for_tenant(tenant1)
        assert tenant1_docs.count() == 1
        assert tenant1_docs.first().id == doc1.id
        
        # Verify tenant 2 can only see their documents
        tenant2_docs = TenantDocument.objects.for_tenant(tenant2)
        assert tenant2_docs.count() == 1
        assert tenant2_docs.first().id == doc2.id
    
    def test_vector_namespace_generation(self):
        """Test that vector namespaces are correctly generated."""
        document = TenantDocument.objects.create(
            tenant=self.tenant,
            title="Test Document",
            document_type="txt",
            file_path="test.txt",
            file_size=100,
            file_hash="testhash"
        )
        
        # Verify namespace is set correctly
        assert document.vector_namespace == f"tenant_{self.tenant.id}"
    
    def test_file_deduplication(self):
        """Test that duplicate files are detected."""
        # Create first document
        doc1 = TenantDocument.objects.create(
            tenant=self.tenant,
            title="Original Document",
            document_type="txt",
            file_path="doc1.txt",
            file_size=100,
            file_hash="samehash",
            status="completed"
        )
        
        # Try to create duplicate (same hash)
        with pytest.raises(Exception):  # Should raise integrity error
            TenantDocument.objects.create(
                tenant=self.tenant,
                title="Duplicate Document",
                document_type="txt", 
                file_path="doc2.txt",
                file_size=100,
                file_hash="samehash",  # Same hash
                status="completed"
            )
    
    def test_document_soft_delete(self):
        """Test document soft delete functionality."""
        document = TenantDocument.objects.create(
            tenant=self.tenant,
            title="Test Document",
            document_type="txt",
            file_path="test.txt",
            file_size=100,
            file_hash="testhash",
            status="completed"
        )
        
        # Verify document is active
        assert document.is_active is True
        active_docs = TenantDocument.objects.for_tenant(self.tenant)
        assert active_docs.count() == 1
        
        # Soft delete
        document.soft_delete()
        
        # Verify document is marked inactive
        document.refresh_from_db()
        assert document.is_active is False
        
        # Verify it's excluded from tenant queries
        active_docs = TenantDocument.objects.for_tenant(self.tenant)
        assert active_docs.count() == 0