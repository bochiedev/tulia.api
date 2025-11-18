"""
Tests for RAG infrastructure components.
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

from apps.bot.models import Document, DocumentChunk
from apps.bot.services.embedding_service import EmbeddingService
from apps.bot.services.vector_store import PineconeVectorStore, VectorSearchResult
from apps.bot.services.document_store_service import DocumentStoreService


@pytest.mark.django_db
class TestEmbeddingService:
    """Tests for EmbeddingService."""
    
    def test_embed_text_success(self):
        """Test successful text embedding."""
        service = EmbeddingService(api_key='test-key')
        
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1, 0.2, 0.3])]
        mock_response.usage = Mock(total_tokens=10)
        
        with patch.object(service.client.embeddings, 'create', return_value=mock_response):
            result = service.embed_text("test text", use_cache=False)
        
        assert result['embedding'] == [0.1, 0.2, 0.3]
        assert result['tokens'] == 10
        assert result['cost'] > 0
        assert result['model'] == 'text-embedding-3-small'
    
    def test_embed_text_empty_raises_error(self):
        """Test that empty text raises ValueError."""
        service = EmbeddingService(api_key='test-key')
        
        with pytest.raises(ValueError, match="Text cannot be empty"):
            service.embed_text("")
    
    def test_embed_batch_success(self):
        """Test successful batch embedding."""
        service = EmbeddingService(api_key='test-key')
        
        mock_response = Mock()
        mock_response.data = [
            Mock(embedding=[0.1, 0.2]),
            Mock(embedding=[0.3, 0.4])
        ]
        mock_response.usage = Mock(total_tokens=20)
        
        with patch.object(service.client.embeddings, 'create', return_value=mock_response):
            results = service.embed_batch(["text1", "text2"], use_cache=False)
        
        assert len(results) == 2
        assert results[0]['embedding'] == [0.1, 0.2]
        assert results[1]['embedding'] == [0.3, 0.4]
    
    def test_embed_batch_exceeds_max_size(self):
        """Test that batch size limit is enforced."""
        service = EmbeddingService(api_key='test-key')
        
        texts = ["text"] * 101  # Exceeds MAX_BATCH_SIZE of 100
        
        with pytest.raises(ValueError, match="exceeds maximum"):
            service.embed_batch(texts)
    
    def test_calculate_cost(self):
        """Test cost calculation."""
        service = EmbeddingService(api_key='test-key')
        
        # 1000 tokens should cost $0.00002 for text-embedding-3-small
        cost = service._calculate_cost(1000)
        expected = Decimal('0.00002') * Decimal('1000') / Decimal('1000000')
        
        assert cost == expected


@pytest.mark.django_db
class TestVectorStore:
    """Tests for VectorStore implementations."""
    
    def test_pinecone_upsert(self):
        """Test upserting vectors to Pinecone."""
        with patch('apps.bot.services.vector_store.Pinecone') as mock_pc:
            mock_index = Mock()
            mock_index.upsert.return_value = Mock(upserted_count=2)
            mock_pc.return_value.Index.return_value = mock_index
            mock_pc.return_value.list_indexes.return_value = [Mock(name='test-index')]
            
            store = PineconeVectorStore(
                api_key='test-key',
                index_name='test-index'
            )
            
            vectors = [
                {'id': 'vec1', 'values': [0.1, 0.2], 'metadata': {'test': 'data'}},
                {'id': 'vec2', 'values': [0.3, 0.4], 'metadata': {'test': 'data'}}
            ]
            
            result = store.upsert(vectors, namespace='tenant_123')
            
            assert result['upserted_count'] == 2
            mock_index.upsert.assert_called_once()
    
    def test_pinecone_search(self):
        """Test searching vectors in Pinecone."""
        with patch('apps.bot.services.vector_store.Pinecone') as mock_pc:
            mock_index = Mock()
            mock_match1 = Mock(id='vec1', score=0.95, metadata={'key': 'value1'})
            mock_match2 = Mock(id='vec2', score=0.85, metadata={'key': 'value2'})
            mock_index.query.return_value = Mock(matches=[mock_match1, mock_match2])
            mock_pc.return_value.Index.return_value = mock_index
            mock_pc.return_value.list_indexes.return_value = [Mock(name='test-index')]
            
            store = PineconeVectorStore(
                api_key='test-key',
                index_name='test-index'
            )
            
            results = store.search(
                query_vector=[0.1, 0.2],
                top_k=2,
                namespace='tenant_123'
            )
            
            assert len(results) == 2
            assert results[0].id == 'vec1'
            assert results[0].score == 0.95
            assert results[1].id == 'vec2'
    
    def test_pinecone_delete(self):
        """Test deleting vectors from Pinecone."""
        with patch('apps.bot.services.vector_store.Pinecone') as mock_pc:
            mock_index = Mock()
            mock_pc.return_value.Index.return_value = mock_index
            mock_pc.return_value.list_indexes.return_value = [Mock(name='test-index')]
            
            store = PineconeVectorStore(
                api_key='test-key',
                index_name='test-index'
            )
            
            result = store.delete(
                ids=['vec1', 'vec2'],
                namespace='tenant_123'
            )
            
            assert result['deleted_count'] == 2
            mock_index.delete.assert_called_once()


@pytest.mark.django_db
class TestDocumentStoreService:
    """Tests for DocumentStoreService."""
    
    def test_upload_document_success(self, tenant):
        """Test successful document upload."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        file = SimpleUploadedFile(
            "test.pdf",
            b"test content",
            content_type="application/pdf"
        )
        
        with patch('apps.bot.services.document_store_service.default_storage') as mock_storage:
            mock_storage.save.return_value = 'documents/tenant_123/test.pdf'
            
            service = DocumentStoreService(tenant)
            document = service.upload_document(
                file=file,
                file_name='test.pdf',
                uploaded_by='user@example.com'
            )
        
        assert document.tenant == tenant
        assert document.file_name == 'test.pdf'
        assert document.file_type == 'pdf'
        assert document.status == 'pending'
    
    def test_upload_document_invalid_type(self, tenant):
        """Test that invalid file type raises error."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        file = SimpleUploadedFile(
            "test.exe",
            b"test content",
            content_type="application/x-msdownload"
        )
        
        service = DocumentStoreService(tenant)
        
        with pytest.raises(ValueError, match="not allowed"):
            service.upload_document(
                file=file,
                file_name='test.exe'
            )
    
    def test_search_documents(self, tenant):
        """Test document search."""
        # Create test document and chunk
        document = Document.objects.create(
            tenant=tenant,
            file_name='test.pdf',
            file_type='pdf',
            file_path='test/path.pdf',
            file_size=1000,
            status='completed'
        )
        
        chunk = DocumentChunk.objects.create(
            document=document,
            tenant=tenant,
            chunk_index=0,
            content='Test content about products',
            token_count=10,
            vector_id='vec_123'
        )
        
        with patch.object(EmbeddingService, 'embed_text') as mock_embed:
            mock_embed.return_value = {
                'embedding': [0.1, 0.2, 0.3],
                'tokens': 5,
                'cost': Decimal('0.0001')
            }
            
            with patch.object(PineconeVectorStore, 'search') as mock_search:
                mock_search.return_value = [
                    VectorSearchResult(
                        id='vec_123',
                        score=0.95,
                        metadata={'tenant_id': str(tenant.id)}
                    )
                ]
                
                service = DocumentStoreService(tenant)
                results = service.search_documents('test query')
        
        assert len(results) == 1
        assert results[0]['document_name'] == 'test.pdf'
        assert results[0]['content'] == 'Test content about products'
        assert results[0]['score'] == 0.95
    
    def test_delete_document(self, tenant):
        """Test document deletion."""
        document = Document.objects.create(
            tenant=tenant,
            file_name='test.pdf',
            file_type='pdf',
            file_path='test/path.pdf',
            file_size=1000,
            status='completed'
        )
        
        chunk = DocumentChunk.objects.create(
            document=document,
            tenant=tenant,
            chunk_index=0,
            content='Test content',
            token_count=10,
            vector_id='vec_123'
        )
        
        with patch.object(PineconeVectorStore, 'delete') as mock_delete:
            with patch('apps.bot.services.document_store_service.default_storage') as mock_storage:
                mock_storage.exists.return_value = True
                
                service = DocumentStoreService(tenant)
                result = service.delete_document(str(document.id))
        
        assert result is True
        assert not Document.objects.filter(id=document.id, deleted_at__isnull=True).exists()
    
    def test_get_document_status(self, tenant):
        """Test getting document status."""
        document = Document.objects.create(
            tenant=tenant,
            file_name='test.pdf',
            file_type='pdf',
            file_path='test/path.pdf',
            file_size=1000,
            status='processing',
            processing_progress=50,
            chunk_count=10,
            total_tokens=500
        )
        
        service = DocumentStoreService(tenant)
        status = service.get_document_status(str(document.id))
        
        assert status['file_name'] == 'test.pdf'
        assert status['status'] == 'processing'
        assert status['progress'] == 50
        assert status['chunk_count'] == 10
        assert status['total_tokens'] == 500
