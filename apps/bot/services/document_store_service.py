"""
Document store service for managing documents and semantic search.
"""
import os
import logging
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from django.conf import settings
from django.core.files.storage import default_storage
from django.utils import timezone

from apps.bot.models import Document, DocumentChunk
from apps.bot.services.embedding_service import EmbeddingService
from apps.bot.services.vector_store import PineconeVectorStore

logger = logging.getLogger(__name__)


class DocumentStoreService:
    """
    Service for managing documents and performing semantic search.
    """
    
    def __init__(self, tenant):
        """
        Initialize document store service.
        
        Args:
            tenant: Tenant instance
        """
        self.tenant = tenant
        self.embedding_service = EmbeddingService.create_for_tenant(tenant)
        self.vector_store = PineconeVectorStore.create_from_settings()
        self.namespace = f"tenant_{tenant.id}"
    
    def upload_document(
        self,
        file,
        file_name: str,
        uploaded_by: str = None
    ) -> Document:
        """
        Upload a document for processing.
        
        Args:
            file: File object
            file_name: Name of the file
            uploaded_by: User who uploaded the document
        
        Returns:
            Document instance
        """
        # Validate file type
        file_ext = os.path.splitext(file_name)[1].lower().lstrip('.')
        if file_ext not in settings.ALLOWED_DOCUMENT_TYPES:
            raise ValueError(
                f"File type '{file_ext}' not allowed. "
                f"Allowed types: {settings.ALLOWED_DOCUMENT_TYPES}"
            )
        
        # Validate file size
        file_size = file.size
        if file_size > settings.MAX_DOCUMENT_SIZE:
            raise ValueError(
                f"File size {file_size} exceeds maximum "
                f"{settings.MAX_DOCUMENT_SIZE} bytes"
            )
        
        # Generate unique file path
        file_hash = hashlib.md5(file.read()).hexdigest()
        file.seek(0)  # Reset file pointer
        
        file_path = os.path.join(
            'documents',
            f"tenant_{self.tenant.id}",
            f"{file_hash}_{file_name}"
        )
        
        # Save file
        saved_path = default_storage.save(file_path, file)
        
        # Create document record
        document = Document.objects.create(
            tenant=self.tenant,
            file_name=file_name,
            file_type=file_ext,
            file_path=saved_path,
            file_size=file_size,
            uploaded_by=uploaded_by,
            status='pending'
        )
        
        logger.info(
            f"Document uploaded: {document.id} - {file_name} "
            f"({file_size} bytes)"
        )
        
        return document
    
    def search_documents(
        self,
        query: str,
        top_k: int = None,
        document_ids: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search documents using semantic similarity.
        
        Args:
            query: Search query
            top_k: Number of results to return
            document_ids: Optional list of document IDs to search within
        
        Returns:
            List of search results with chunks and scores
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        top_k = top_k or settings.RAG_TOP_K_RESULTS
        
        # Generate query embedding
        embedding_result = self.embedding_service.embed_text(
            query,
            use_cache=True
        )
        query_vector = embedding_result['embedding']
        
        # Build filter
        filter_dict = {'tenant_id': str(self.tenant.id)}
        if document_ids:
            filter_dict['document_id'] = {'$in': [str(d) for d in document_ids]}
        
        # Search vector store
        vector_results = self.vector_store.search(
            query_vector=query_vector,
            top_k=top_k,
            filter_dict=filter_dict,
            namespace=self.namespace
        )
        
        # Retrieve chunks from database
        results = []
        for vec_result in vector_results:
            try:
                chunk = DocumentChunk.objects.select_related('document').get(
                    vector_id=vec_result.id
                )
                
                results.append({
                    'chunk_id': str(chunk.id),
                    'document_id': str(chunk.document.id),
                    'document_name': chunk.document.file_name,
                    'content': chunk.content,
                    'page_number': chunk.page_number,
                    'section': chunk.section,
                    'score': vec_result.score,
                    'metadata': vec_result.metadata
                })
            except DocumentChunk.DoesNotExist:
                logger.warning(f"Chunk not found for vector_id: {vec_result.id}")
                continue
        
        logger.info(
            f"Document search: '{query[:50]}' - "
            f"Found {len(results)} results"
        )
        
        return results
    
    def delete_document(self, document_id: str) -> bool:
        """
        Delete a document and its chunks.
        
        Args:
            document_id: Document ID
        
        Returns:
            True if deleted successfully
        """
        try:
            document = Document.objects.get(
                id=document_id,
                tenant=self.tenant
            )
            
            # Get all chunk vector IDs
            vector_ids = list(
                document.chunks.values_list('vector_id', flat=True)
            )
            
            # Delete from vector store
            if vector_ids:
                self.vector_store.delete(
                    ids=vector_ids,
                    namespace=self.namespace
                )
            
            # Delete file
            if document.file_path and default_storage.exists(document.file_path):
                default_storage.delete(document.file_path)
            
            # Soft delete document (will cascade to chunks)
            document.delete()
            
            logger.info(f"Document deleted: {document_id}")
            
            return True
            
        except Document.DoesNotExist:
            logger.error(f"Document not found: {document_id}")
            return False
        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            raise
    
    def get_document_status(self, document_id: str) -> Dict[str, Any]:
        """
        Get document processing status.
        
        Args:
            document_id: Document ID
        
        Returns:
            Dict with status information
        """
        try:
            document = Document.objects.get(
                id=document_id,
                tenant=self.tenant
            )
            
            return {
                'id': str(document.id),
                'file_name': document.file_name,
                'status': document.status,
                'progress': document.processing_progress,
                'chunk_count': document.chunk_count,
                'total_tokens': document.total_tokens,
                'error_message': document.error_message,
                'created_at': document.created_at.isoformat(),
                'processed_at': (
                    document.processed_at.isoformat()
                    if document.processed_at else None
                )
            }
            
        except Document.DoesNotExist:
            raise ValueError(f"Document not found: {document_id}")
    
    @classmethod
    def create_for_tenant(cls, tenant) -> 'DocumentStoreService':
        """
        Create document store service for a tenant.
        
        Args:
            tenant: Tenant instance
        
        Returns:
            DocumentStoreService instance
        """
        return cls(tenant)
