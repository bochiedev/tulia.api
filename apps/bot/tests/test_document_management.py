"""
Tests for document management (Task 31).
"""
import pytest
import os
from io import BytesIO
from unittest.mock import Mock, patch, MagicMock
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status

from apps.bot.models import Document, DocumentChunk
from apps.bot.services.text_extraction_service import TextExtractionService
from apps.bot.services.chunking_service import ChunkingService


@pytest.mark.django_db
class TestDocumentUploadAPI:
    """Tests for document upload API endpoint."""
    
    def test_upload_pdf_success(self, tenant, api_client_with_tenant):
        """Test successful PDF upload."""
        client = api_client_with_tenant
        
        # Create test PDF file
        pdf_content = b"%PDF-1.4\nTest PDF content"
        file = SimpleUploadedFile(
            "test.pdf",
            pdf_content,
            content_type="application/pdf"
        )
        
        with patch('apps.bot.views.document_views.process_document') as mock_task:
            mock_task.delay.return_value = Mock(id='task-123')
            
            response = client.post(
                '/v1/bot/documents/upload',
                {'file': file},
                format='multipart'
            )
        
        assert response.status_code == status.HTTP_201_CREATED
        assert 'id' in response.data
        assert response.data['file_name'] == 'test.pdf'
        assert response.data['file_type'] == 'pdf'
        assert response.data['status'] == 'pending'
        
        # Verify document created
        document = Document.objects.get(id=response.data['id'])
        assert document.tenant == tenant
        assert document.file_name == 'test.pdf'
        
        # Verify task was triggered
        mock_task.delay.assert_called_once()
    
    def test_upload_txt_success(self, tenant, api_client_with_tenant):
        """Test successful TXT upload."""
        client = api_client_with_tenant
        
        file = SimpleUploadedFile(
            "test.txt",
            b"Test text content",
            content_type="text/plain"
        )
        
        with patch('apps.bot.views.document_views.process_document') as mock_task:
            response = client.post(
                '/v1/bot/documents/upload',
                {'file': file},
                format='multipart'
            )
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['file_type'] == 'txt'
    
    def test_upload_invalid_file_type(self, api_client_with_tenant):
        """Test upload with invalid file type."""
        client = api_client_with_tenant
        
        file = SimpleUploadedFile(
            "test.exe",
            b"Invalid content",
            content_type="application/x-msdownload"
        )
        
        response = client.post(
            '/v1/bot/documents/upload',
            {'file': file},
            format='multipart'
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'not allowed' in str(response.data).lower()
    
    def test_upload_file_too_large(self, api_client_with_tenant):
        """Test upload with file exceeding size limit."""
        client = api_client_with_tenant
        
        # Create file larger than 10MB
        large_content = b"x" * (11 * 1024 * 1024)
        file = SimpleUploadedFile(
            "large.pdf",
            large_content,
            content_type="application/pdf"
        )
        
        response = client.post(
            '/v1/bot/documents/upload',
            {'file': file},
            format='multipart'
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'exceeds maximum' in str(response.data).lower()
    
    def test_upload_requires_scope(self, tenant, api_client):
        """Test that upload requires integrations:manage scope."""
        # Client without proper scope
        response = api_client.post(
            '/v1/bot/documents/upload',
            {},
            format='multipart'
        )
        
        # Should return 401 or 403
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


@pytest.mark.django_db
class TestDocumentListAPI:
    """Tests for document list API endpoint."""
    
    def test_list_documents(self, tenant, api_client_with_tenant):
        """Test listing documents."""
        client = api_client_with_tenant
        
        # Create test documents
        doc1 = Document.objects.create(
            tenant=tenant,
            file_name='doc1.pdf',
            file_type='pdf',
            file_path='test/doc1.pdf',
            file_size=1000,
            status='completed'
        )
        doc2 = Document.objects.create(
            tenant=tenant,
            file_name='doc2.txt',
            file_type='txt',
            file_path='test/doc2.txt',
            file_size=500,
            status='processing'
        )
        
        response = client.get('/v1/bot/documents/')
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 2
    
    def test_filter_by_status(self, tenant, api_client_with_tenant):
        """Test filtering documents by status."""
        client = api_client_with_tenant
        
        Document.objects.create(
            tenant=tenant,
            file_name='completed.pdf',
            file_type='pdf',
            file_path='test/completed.pdf',
            file_size=1000,
            status='completed'
        )
        Document.objects.create(
            tenant=tenant,
            file_name='processing.pdf',
            file_type='pdf',
            file_path='test/processing.pdf',
            file_size=1000,
            status='processing'
        )
        
        response = client.get('/v1/bot/documents/?status=completed')
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['status'] == 'completed'
    
    def test_search_by_filename(self, tenant, api_client_with_tenant):
        """Test searching documents by filename."""
        client = api_client_with_tenant
        
        Document.objects.create(
            tenant=tenant,
            file_name='business_faq.pdf',
            file_type='pdf',
            file_path='test/business_faq.pdf',
            file_size=1000,
            status='completed'
        )
        Document.objects.create(
            tenant=tenant,
            file_name='product_guide.pdf',
            file_type='pdf',
            file_path='test/product_guide.pdf',
            file_size=1000,
            status='completed'
        )
        
        response = client.get('/v1/bot/documents/?search=business')
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert 'business' in response.data['results'][0]['file_name'].lower()
    
    def test_tenant_isolation(self, tenant, other_tenant, api_client_with_tenant):
        """Test that documents are isolated by tenant."""
        client = api_client_with_tenant
        
        # Create document for current tenant
        Document.objects.create(
            tenant=tenant,
            file_name='my_doc.pdf',
            file_type='pdf',
            file_path='test/my_doc.pdf',
            file_size=1000,
            status='completed'
        )
        
        # Create document for other tenant
        Document.objects.create(
            tenant=other_tenant,
            file_name='other_doc.pdf',
            file_type='pdf',
            file_path='test/other_doc.pdf',
            file_size=1000,
            status='completed'
        )
        
        response = client.get('/v1/bot/documents/')
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['file_name'] == 'my_doc.pdf'


@pytest.mark.django_db
class TestDocumentDetailAPI:
    """Tests for document detail API endpoint."""
    
    def test_get_document_detail(self, tenant, api_client_with_tenant):
        """Test getting document details."""
        client = api_client_with_tenant
        
        document = Document.objects.create(
            tenant=tenant,
            file_name='test.pdf',
            file_type='pdf',
            file_path='test/test.pdf',
            file_size=1000,
            status='completed',
            chunk_count=10,
            total_tokens=500
        )
        
        response = client.get(f'/v1/bot/documents/{document.id}')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == str(document.id)
        assert response.data['file_name'] == 'test.pdf'
        assert response.data['chunk_count'] == 10
        assert response.data['total_tokens'] == 500
    
    def test_get_nonexistent_document(self, api_client_with_tenant):
        """Test getting non-existent document."""
        client = api_client_with_tenant
        
        import uuid
        fake_id = uuid.uuid4()
        
        response = client.get(f'/v1/bot/documents/{fake_id}')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestDocumentDeleteAPI:
    """Tests for document delete API endpoint."""
    
    def test_delete_document(self, tenant, api_client_with_tenant):
        """Test deleting a document."""
        client = api_client_with_tenant
        
        document = Document.objects.create(
            tenant=tenant,
            file_name='test.pdf',
            file_type='pdf',
            file_path='test/test.pdf',
            file_size=1000,
            status='completed'
        )
        
        with patch('apps.bot.services.document_store_service.PineconeVectorStore'):
            with patch('apps.bot.services.document_store_service.default_storage'):
                response = client.delete(f'/v1/bot/documents/{document.id}/delete')
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify soft delete
        document.refresh_from_db()
        assert document.deleted_at is not None


@pytest.mark.django_db
class TestTextExtractionService:
    """Tests for text extraction service."""
    
    def test_extract_from_text_file(self, tmp_path):
        """Test extracting text from text file."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("This is test content.\nWith multiple lines.")
        
        result = TextExtractionService.extract_from_text(str(test_file))
        
        assert 'text' in result
        assert 'This is test content' in result['text']
        assert 'metadata' in result
        assert result['metadata']['extraction_method'] == 'text'
    
    def test_extract_from_empty_file(self, tmp_path):
        """Test extracting from empty file raises error."""
        test_file = tmp_path / "empty.txt"
        test_file.write_text("")
        
        with pytest.raises(ValueError, match="empty"):
            TextExtractionService.extract_from_text(str(test_file))


@pytest.mark.django_db
class TestChunkingService:
    """Tests for chunking service."""
    
    def test_chunk_text(self):
        """Test chunking text."""
        service = ChunkingService(chunk_size=100, chunk_overlap=20)
        
        text = "This is a test. " * 50  # Create long text
        
        chunks = service.chunk_text(text)
        
        assert len(chunks) > 1
        assert all('content' in chunk for chunk in chunks)
        assert all('token_count' in chunk for chunk in chunks)
        assert all('metadata' in chunk for chunk in chunks)
    
    def test_chunk_preserves_metadata(self):
        """Test that chunking preserves metadata."""
        service = ChunkingService(chunk_size=100, chunk_overlap=20)
        
        text = "Test content. " * 50
        metadata = {'page_number': 5, 'section': 'Introduction'}
        
        chunks = service.chunk_text(text, metadata=metadata)
        
        assert all(chunk['metadata']['page_number'] == 5 for chunk in chunks)
        assert all(chunk['metadata']['section'] == 'Introduction' for chunk in chunks)
    
    def test_chunk_pages(self):
        """Test chunking pages."""
        service = ChunkingService(chunk_size=100, chunk_overlap=20)
        
        pages = [
            {'page_number': 1, 'text': 'Page 1 content. ' * 30},
            {'page_number': 2, 'text': 'Page 2 content. ' * 30},
        ]
        
        chunks = service.chunk_pages(pages)
        
        assert len(chunks) > 0
        # Verify page numbers are preserved
        page_numbers = [chunk['metadata'].get('page_number') for chunk in chunks]
        assert 1 in page_numbers
        assert 2 in page_numbers
    
    def test_empty_text_returns_empty_list(self):
        """Test that empty text returns empty list."""
        service = ChunkingService()
        
        chunks = service.chunk_text("")
        
        assert chunks == []


@pytest.mark.django_db
class TestDocumentProcessingTask:
    """Tests for document processing Celery task."""
    
    def test_process_document_success(self, tenant):
        """Test successful document processing."""
        # Create test document
        document = Document.objects.create(
            tenant=tenant,
            file_name='test.txt',
            file_type='txt',
            file_path='test/test.txt',
            file_size=100,
            status='pending'
        )
        
        # Mock all external dependencies
        with patch('apps.bot.tasks.default_storage.path') as mock_path:
            with patch('apps.bot.tasks.TextExtractionService.extract') as mock_extract:
                with patch('apps.bot.tasks.EmbeddingService.create_for_tenant') as mock_embed_service:
                    with patch('apps.bot.tasks.PineconeVectorStore.create_from_settings') as mock_vector:
                        # Setup mocks
                        mock_path.return_value = '/fake/path/test.txt'
                        mock_extract.return_value = {
                            'text': 'Test content',
                            'pages': [{'page_number': 1, 'text': 'Test content'}],
                            'metadata': {}
                        }
                        
                        mock_embed_instance = Mock()
                        mock_embed_instance.embed_batch.return_value = [
                            {'embedding': [0.1] * 1536, 'tokens': 10, 'cost': 0.0001, 'model': 'test'}
                        ]
                        mock_embed_service.return_value = mock_embed_instance
                        
                        mock_vector_instance = Mock()
                        mock_vector_instance.upsert.return_value = {'upserted_count': 1}
                        mock_vector.return_value = mock_vector_instance
                        
                        # Run task
                        from apps.bot.tasks import process_document
                        result = process_document(str(document.id))
        
        assert result['status'] == 'success'
        
        # Verify document updated
        document.refresh_from_db()
        assert document.status == 'completed'
        assert document.processing_progress == 100
        assert document.chunk_count > 0
        assert document.processed_at is not None
