"""
Text chunking service for document processing.
"""
import logging
from typing import List, Dict, Any
from langchain.text_splitter import RecursiveCharacterTextSplitter
import tiktoken
from django.conf import settings

logger = logging.getLogger(__name__)


class ChunkingService:
    """
    Service for chunking text into smaller pieces for embedding.
    """
    
    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
        encoding_name: str = 'cl100k_base'
    ):
        """
        Initialize chunking service.
        
        Args:
            chunk_size: Target chunk size in tokens
            chunk_overlap: Overlap between chunks in tokens
            encoding_name: Tokenizer encoding name
        """
        self.chunk_size = chunk_size or settings.RAG_CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.RAG_CHUNK_OVERLAP
        self.encoding = tiktoken.get_encoding(encoding_name)
        
        # Create text splitter
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=self._count_tokens,
            separators=[
                "\n\n",  # Paragraph breaks
                "\n",    # Line breaks
                ". ",    # Sentences
                "! ",
                "? ",
                "; ",
                ", ",
                " ",     # Words
                "",      # Characters
            ]
        )
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoding.encode(text))
    
    def chunk_text(
        self,
        text: str,
        metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Chunk text into smaller pieces.
        
        Args:
            text: Text to chunk
            metadata: Optional metadata to include with chunks
        
        Returns:
            List of chunk dicts with 'content', 'token_count', and 'metadata'
        """
        if not text or not text.strip():
            return []
        
        # Split text
        chunks = self.splitter.split_text(text)
        
        # Create chunk objects
        result = []
        for i, chunk_text in enumerate(chunks):
            token_count = self._count_tokens(chunk_text)
            
            chunk_metadata = {
                'chunk_index': i,
                'total_chunks': len(chunks),
            }
            
            # Add provided metadata
            if metadata:
                chunk_metadata.update(metadata)
            
            result.append({
                'content': chunk_text,
                'token_count': token_count,
                'metadata': chunk_metadata
            })
        
        logger.info(
            f"Chunked text into {len(result)} chunks "
            f"(avg {sum(c['token_count'] for c in result) // len(result)} tokens/chunk)"
        )
        
        return result
    
    def chunk_pages(
        self,
        pages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Chunk text from pages, preserving page metadata.
        
        Args:
            pages: List of page dicts with 'page_number' and 'text'
        
        Returns:
            List of chunk dicts with page metadata
        """
        all_chunks = []
        
        for page in pages:
            page_number = page.get('page_number')
            page_text = page.get('text', '')
            
            if not page_text.strip():
                continue
            
            # Chunk page text
            chunks = self.chunk_text(
                page_text,
                metadata={'page_number': page_number}
            )
            
            all_chunks.extend(chunks)
        
        # Re-index chunks globally
        for i, chunk in enumerate(all_chunks):
            chunk['metadata']['chunk_index'] = i
            chunk['metadata']['total_chunks'] = len(all_chunks)
        
        logger.info(
            f"Chunked {len(pages)} pages into {len(all_chunks)} chunks"
        )
        
        return all_chunks
    
    @classmethod
    def create_default(cls) -> 'ChunkingService':
        """Create chunking service with default settings."""
        return cls(
            chunk_size=settings.RAG_CHUNK_SIZE,
            chunk_overlap=settings.RAG_CHUNK_OVERLAP
        )
