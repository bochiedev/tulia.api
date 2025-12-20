"""
Tenant document ingestion service for LangGraph RAG implementation.

This service handles the ingestion of PDF, DOCX, and text files with
strict tenant isolation and vector embedding generation.
"""
import os
import hashlib
import logging
from typing import List, Dict, Any, Optional, BinaryIO
from io import BytesIO

from django.conf import settings
from django.core.files.storage import default_storage
from django.utils import timezone

# Document processing imports
try:
    import PyPDF2
    from docx import Document as DocxDocument
except ImportError:
    PyPDF2 = None
    DocxDocument = None

from apps.bot.models_tenant_documents import TenantDocument, TenantDocumentChunk
from apps.bot.services.embedding_service import EmbeddingService
from apps.bot.services.vector_store import PineconeVectorStore

logger = logging.getLogger(__name__)


class TenantDocumentIngestionService:
    """
    Service for ingesting tenant documents with vector embeddings.
    
    Supports PDF, DOCX, and text files with tenant-scoped processing
    and vector database storage.
    """
    
    # Supported file types
    SUPPORTED_EXTENSIONS = {
        'pdf': 'PDF Document',
        'docx': 'Word Document', 
        'txt': 'Text File',
    }
    
    # Chunking parameters
    DEFAULT_CHUNK_SIZE = 1000  # tokens
    DEFAULT_CHUNK_OVERLAP = 200  # tokens
    MAX_CHUNK_SIZE = 2000  # tokens
    
    def __init__(self, tenant):
        """
        Initialize document ingestion service for a tenant.
        
        Args:
            tenant: Tenant instance
        """
        self.tenant = tenant
        self.embedding_service = EmbeddingService.create_for_tenant(tenant)
        self.vector_store = PineconeVectorStore.create_from_settings()
        self.namespace = f"tenant_{tenant.id}"
    
    def ingest_document(
        self,
        file: BinaryIO,
        filename: str,
        document_type: str = None,
        title: str = None,
        description: str = None,
        tags: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> TenantDocument:
        """
        Ingest a document file with processing and vector embedding.
        
        Args:
            file: File object to ingest
            filename: Original filename
            document_type: Type of document (auto-detected if not provided)
            title: Document title (uses filename if not provided)
            description: Optional description
            tags: Optional tags for categorization
            metadata: Optional additional metadata
        
        Returns:
            TenantDocument instance
        
        Raises:
            ValueError: If file type is not supported or file is invalid
            Exception: If processing fails
        """
        # Validate file
        file_ext = self._get_file_extension(filename)
        if file_ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: {file_ext}. "
                f"Supported types: {list(self.SUPPORTED_EXTENSIONS.keys())}"
            )
        
        # Auto-detect document type if not provided
        if not document_type:
            document_type = file_ext
        
        # Calculate file hash for deduplication
        file_content = file.read()
        file.seek(0)  # Reset file pointer
        file_hash = hashlib.sha256(file_content).hexdigest()
        
        # Check for existing document with same hash
        existing_doc = TenantDocument.objects.filter(
            tenant=self.tenant,
            file_hash=file_hash,
            is_active=True
        ).first()
        
        if existing_doc:
            logger.info(f"Document already exists: {existing_doc.id}")
            return existing_doc
        
        # Store file
        file_path = self._store_file(file, filename, file_hash)
        
        # Create document record
        document = TenantDocument.objects.create(
            tenant=self.tenant,
            title=title or filename,
            document_type=document_type,
            description=description or '',
            file_path=file_path,
            file_size=len(file_content),
            file_hash=file_hash,
            embedding_model=self.embedding_service.model,
            tags=tags or [],
            metadata=metadata or {},
            status='pending'
        )
        
        logger.info(f"Created document record: {document.id} - {filename}")
        
        # Process document asynchronously (or synchronously for now)
        try:
            self._process_document(document, file_content)
        except Exception as e:
            document.mark_processing_failed(str(e))
            logger.error(f"Failed to process document {document.id}: {e}")
            raise
        
        return document
    
    def _process_document(self, document: TenantDocument, file_content: bytes):
        """
        Process document by extracting text, chunking, and creating embeddings.
        
        Args:
            document: TenantDocument instance
            file_content: Raw file content bytes
        """
        document.mark_processing_started()
        
        try:
            # Extract text from document
            text_content = self._extract_text(document, file_content)
            document.update_progress(25)
            
            # Split into chunks
            chunks = self._create_chunks(text_content)
            document.update_progress(50)
            
            # Generate embeddings and store in vector database
            self._process_chunks(document, chunks)
            document.update_progress(90)
            
            # Mark as completed
            document.mark_processing_completed(
                chunk_count=len(chunks),
                total_tokens=sum(chunk['token_count'] for chunk in chunks)
            )
            
            logger.info(
                f"Successfully processed document {document.id}: "
                f"{len(chunks)} chunks, {document.total_tokens} tokens"
            )
            
        except Exception as e:
            document.mark_processing_failed(str(e))
            logger.error(f"Error processing document {document.id}: {e}")
            raise
    
    def _extract_text(self, document: TenantDocument, file_content: bytes) -> str:
        """
        Extract text content from document based on file type.
        
        Args:
            document: TenantDocument instance
            file_content: Raw file content bytes
        
        Returns:
            Extracted text content
        """
        file_ext = document.get_file_extension()
        
        if file_ext == 'txt':
            return self._extract_text_from_txt(file_content)
        elif file_ext == 'pdf':
            return self._extract_text_from_pdf(file_content)
        elif file_ext == 'docx':
            return self._extract_text_from_docx(file_content)
        else:
            raise ValueError(f"Unsupported file type for text extraction: {file_ext}")
    
    def _extract_text_from_txt(self, file_content: bytes) -> str:
        """Extract text from plain text file."""
        try:
            # Try UTF-8 first, then fallback to other encodings
            for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
                try:
                    return file_content.decode(encoding)
                except UnicodeDecodeError:
                    continue
            
            # If all encodings fail, use UTF-8 with error handling
            return file_content.decode('utf-8', errors='replace')
            
        except Exception as e:
            raise ValueError(f"Failed to extract text from TXT file: {e}")
    
    def _extract_text_from_pdf(self, file_content: bytes) -> str:
        """Extract text from PDF file."""
        if not PyPDF2:
            raise ValueError("PyPDF2 not installed. Cannot process PDF files.")
        
        try:
            pdf_file = BytesIO(file_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text_parts = []
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text.strip():
                        text_parts.append(f"[Page {page_num + 1}]\n{page_text}")
                except Exception as e:
                    logger.warning(f"Failed to extract text from page {page_num + 1}: {e}")
                    continue
            
            if not text_parts:
                raise ValueError("No text content found in PDF")
            
            return '\n\n'.join(text_parts)
            
        except Exception as e:
            raise ValueError(f"Failed to extract text from PDF file: {e}")
    
    def _extract_text_from_docx(self, file_content: bytes) -> str:
        """Extract text from DOCX file."""
        if not DocxDocument:
            raise ValueError("python-docx not installed. Cannot process DOCX files.")
        
        try:
            docx_file = BytesIO(file_content)
            doc = DocxDocument(docx_file)
            
            text_parts = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_parts.append(paragraph.text)
            
            if not text_parts:
                raise ValueError("No text content found in DOCX")
            
            return '\n\n'.join(text_parts)
            
        except Exception as e:
            raise ValueError(f"Failed to extract text from DOCX file: {e}")
    
    def _create_chunks(self, text: str) -> List[Dict[str, Any]]:
        """
        Split text into chunks for processing.
        
        Args:
            text: Full text content
        
        Returns:
            List of chunk dictionaries with content and metadata
        """
        # Simple chunking by character count (can be enhanced with proper tokenization)
        chunk_size_chars = self.DEFAULT_CHUNK_SIZE * 4  # Rough estimate: 1 token ≈ 4 chars
        overlap_chars = self.DEFAULT_CHUNK_OVERLAP * 4
        
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(text):
            # Calculate end position
            end = start + chunk_size_chars
            
            # If this is not the last chunk, try to break at a sentence or paragraph
            if end < len(text):
                # Look for sentence endings within the last 200 characters
                search_start = max(start + chunk_size_chars - 200, start)
                sentence_end = -1
                
                for i in range(end, search_start, -1):
                    if text[i:i+1] in '.!?\n':
                        # Check if this looks like a real sentence ending
                        if i + 1 < len(text) and (text[i+1].isspace() or text[i+1].isupper()):
                            sentence_end = i + 1
                            break
                
                if sentence_end > 0:
                    end = sentence_end
            
            # Extract chunk content
            chunk_content = text[start:end].strip()
            
            if chunk_content:
                # Estimate token count (rough approximation)
                token_count = len(chunk_content.split())
                
                chunks.append({
                    'chunk_index': chunk_index,
                    'content': chunk_content,
                    'token_count': token_count,
                    'start_char': start,
                    'end_char': end,
                })
                
                chunk_index += 1
            
            # Move start position with overlap
            start = max(end - overlap_chars, start + 1)
            
            # Prevent infinite loop
            if start >= len(text):
                break
        
        logger.info(f"Created {len(chunks)} chunks from {len(text)} characters")
        return chunks
    
    def _process_chunks(self, document: TenantDocument, chunks: List[Dict[str, Any]]):
        """
        Process chunks by generating embeddings and storing in vector database.
        
        Args:
            document: TenantDocument instance
            chunks: List of chunk dictionaries
        """
        if not chunks:
            return
        
        # Prepare texts for batch embedding
        chunk_texts = [chunk['content'] for chunk in chunks]
        
        # Generate embeddings in batches
        batch_size = 20  # Process in smaller batches to avoid API limits
        chunk_records = []
        vector_records = []
        
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_texts = chunk_texts[i:i + batch_size]
            
            # Generate embeddings for batch
            embedding_results = self.embedding_service.embed_batch(batch_texts)
            
            # Create chunk records and vector data
            for j, (chunk, embedding_result) in enumerate(zip(batch_chunks, embedding_results)):
                chunk_index = chunk['chunk_index']
                
                # Create chunk record
                chunk_record = TenantDocumentChunk(
                    document=document,
                    chunk_index=chunk_index,
                    content=chunk['content'],
                    token_count=chunk['token_count'],
                    embedding_model=self.embedding_service.model,
                    metadata={
                        'start_char': chunk['start_char'],
                        'end_char': chunk['end_char'],
                    }
                )
                chunk_records.append(chunk_record)
                
                # Prepare vector data for Pinecone
                vector_data = {
                    'id': chunk_record.vector_id,
                    'values': embedding_result['embedding'],
                    'metadata': {
                        'tenant_id': str(document.tenant_id),
                        'document_id': str(document.id),
                        'chunk_index': chunk_index,
                        'document_type': document.document_type,
                        'document_title': document.title,
                        'content_preview': chunk['content'][:200],
                        'token_count': chunk['token_count'],
                    }
                }
                vector_records.append(vector_data)
        
        # Bulk create chunk records
        TenantDocumentChunk.objects.bulk_create(chunk_records)
        
        # Store vectors in Pinecone
        if vector_records:
            self.vector_store.upsert(
                vectors=vector_records,
                namespace=self.namespace
            )
        
        logger.info(
            f"Processed {len(chunk_records)} chunks for document {document.id}"
        )
    
    def _store_file(self, file: BinaryIO, filename: str, file_hash: str) -> str:
        """
        Store file in tenant-scoped directory.
        
        Args:
            file: File object
            filename: Original filename
            file_hash: File hash for unique naming
        
        Returns:
            Stored file path
        """
        # Create tenant-scoped file path
        file_path = os.path.join(
            'tenant_documents',
            f"tenant_{self.tenant.id}",
            f"{file_hash}_{filename}"
        )
        
        # Store file
        stored_path = default_storage.save(file_path, file)
        
        logger.info(f"Stored file: {stored_path}")
        return stored_path
    
    def _get_file_extension(self, filename: str) -> str:
        """Get file extension from filename."""
        return os.path.splitext(filename)[1].lower().lstrip('.')
    
    def delete_document(self, document_id: str) -> bool:
        """
        Delete a document and clean up associated data.
        
        Args:
            document_id: Document ID to delete
        
        Returns:
            True if deleted successfully
        """
        try:
            document = TenantDocument.objects.get(
                id=document_id,
                tenant=self.tenant
            )
            
            # Get all chunk vector IDs
            vector_ids = list(
                document.chunks.values_list('vector_id', flat=True)
            )
            
            # Delete vectors from Pinecone
            if vector_ids:
                self.vector_store.delete(
                    ids=vector_ids,
                    namespace=self.namespace
                )
            
            # Delete file from storage
            if document.file_path and default_storage.exists(document.file_path):
                default_storage.delete(document.file_path)
            
            # Soft delete document (cascades to chunks)
            document.soft_delete()
            
            logger.info(f"Deleted document: {document_id}")
            return True
            
        except TenantDocument.DoesNotExist:
            logger.error(f"Document not found: {document_id}")
            return False
        except Exception as e:
            logger.error(f"Error deleting document {document_id}: {e}")
            raise
    
    def search_documents(
        self,
        query: str,
        top_k: int = 5,
        document_types: List[str] = None,
        min_score: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search documents using semantic similarity.
        
        Args:
            query: Search query
            top_k: Number of results to return
            document_types: Optional filter by document types
            min_score: Minimum similarity score
        
        Returns:
            List of search results with chunks and metadata
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        # Generate query embedding
        embedding_result = self.embedding_service.embed_text(query, use_cache=True)
        query_vector = embedding_result['embedding']
        
        # Build filter for tenant isolation
        filter_dict = {'tenant_id': str(self.tenant.id)}
        if document_types:
            filter_dict['document_type'] = {'$in': document_types}
        
        # Search vector store
        vector_results = self.vector_store.search(
            query_vector=query_vector,
            top_k=top_k * 2,  # Get more results to filter by score
            filter_dict=filter_dict,
            namespace=self.namespace
        )
        
        # Filter by minimum score and retrieve chunk details
        results = []
        for vec_result in vector_results:
            if vec_result.score >= min_score:
                try:
                    chunk = TenantDocumentChunk.objects.select_related('document').get(
                        vector_id=vec_result.id
                    )
                    
                    results.append({
                        'chunk_id': str(chunk.id),
                        'document_id': str(chunk.document.id),
                        'document_title': chunk.document.title,
                        'document_type': chunk.document.document_type,
                        'content': chunk.content,
                        'chunk_index': chunk.chunk_index,
                        'score': vec_result.score,
                        'metadata': vec_result.metadata,
                        'page_number': chunk.page_number,
                        'section_title': chunk.section_title,
                    })
                except TenantDocumentChunk.DoesNotExist:
                    logger.warning(f"Chunk not found for vector_id: {vec_result.id}")
                    continue
        
        # Limit to requested top_k
        results = results[:top_k]
        
        logger.info(
            f"Document search for tenant {self.tenant.id}: "
            f"'{query[:50]}' - Found {len(results)} results"
        )
        
        return results
    
    @classmethod
    def create_for_tenant(cls, tenant) -> 'TenantDocumentIngestionService':
        """
        Create document ingestion service for a tenant.
        
        Args:
            tenant: Tenant instance
        
        Returns:
            TenantDocumentIngestionService instance
        """
        return cls(tenant)