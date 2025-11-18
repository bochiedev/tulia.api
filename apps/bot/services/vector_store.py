"""
Vector store abstraction layer for RAG retrieval.
"""
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from pinecone import Pinecone, ServerlessSpec

logger = logging.getLogger(__name__)


@dataclass
class VectorSearchResult:
    """Result from vector search."""
    id: str
    score: float
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'score': self.score,
            'metadata': self.metadata
        }


class VectorStore(ABC):
    """
    Abstract base class for vector stores.
    """
    
    @abstractmethod
    def upsert(
        self,
        vectors: List[Dict[str, Any]],
        namespace: str = None
    ) -> Dict[str, Any]:
        """
        Insert or update vectors.
        
        Args:
            vectors: List of dicts with 'id', 'values', and 'metadata'
            namespace: Optional namespace for tenant isolation
        
        Returns:
            Dict with upsert statistics
        """
        pass
    
    @abstractmethod
    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filter_dict: Dict[str, Any] = None,
        namespace: str = None
    ) -> List[VectorSearchResult]:
        """
        Search for similar vectors.
        
        Args:
            query_vector: Query embedding
            top_k: Number of results to return
            filter_dict: Metadata filters
            namespace: Optional namespace for tenant isolation
        
        Returns:
            List of VectorSearchResult objects
        """
        pass
    
    @abstractmethod
    def delete(
        self,
        ids: List[str] = None,
        filter_dict: Dict[str, Any] = None,
        namespace: str = None
    ) -> Dict[str, Any]:
        """
        Delete vectors.
        
        Args:
            ids: List of vector IDs to delete
            filter_dict: Metadata filters for deletion
            namespace: Optional namespace for tenant isolation
        
        Returns:
            Dict with deletion statistics
        """
        pass


class PineconeVectorStore(VectorStore):
    """
    Pinecone implementation of vector store.
    """
    
    def __init__(
        self,
        api_key: str,
        index_name: str,
        dimension: int = 1536,  # text-embedding-3-small dimension
        metric: str = 'cosine',
        cloud: str = 'aws',
        region: str = 'us-east-1'
    ):
        """
        Initialize Pinecone vector store.
        
        Args:
            api_key: Pinecone API key
            index_name: Name of the index
            dimension: Vector dimension
            metric: Distance metric (cosine, euclidean, dotproduct)
            cloud: Cloud provider
            region: Cloud region
        """
        self.pc = Pinecone(api_key=api_key)
        self.index_name = index_name
        self.dimension = dimension
        self.metric = metric
        self.cloud = cloud
        self.region = region
        
        # Create index if it doesn't exist
        self._ensure_index_exists()
        
        # Get index
        self.index = self.pc.Index(index_name)
    
    def _ensure_index_exists(self):
        """Create index if it doesn't exist."""
        try:
            existing_indexes = [idx.name for idx in self.pc.list_indexes()]
            
            if self.index_name not in existing_indexes:
                logger.info(f"Creating Pinecone index: {self.index_name}")
                
                self.pc.create_index(
                    name=self.index_name,
                    dimension=self.dimension,
                    metric=self.metric,
                    spec=ServerlessSpec(
                        cloud=self.cloud,
                        region=self.region
                    )
                )
                
                logger.info(f"Index {self.index_name} created successfully")
            else:
                logger.debug(f"Index {self.index_name} already exists")
                
        except Exception as e:
            logger.error(f"Error ensuring index exists: {e}")
            raise
    
    def upsert(
        self,
        vectors: List[Dict[str, Any]],
        namespace: str = None
    ) -> Dict[str, Any]:
        """
        Insert or update vectors in Pinecone.
        
        Args:
            vectors: List of dicts with 'id', 'values', and 'metadata'
            namespace: Tenant namespace for isolation
        
        Returns:
            Dict with upsert statistics
        """
        if not vectors:
            return {'upserted_count': 0}
        
        try:
            # Validate vector format
            for vec in vectors:
                if 'id' not in vec or 'values' not in vec:
                    raise ValueError("Each vector must have 'id' and 'values'")
            
            # Upsert to Pinecone
            response = self.index.upsert(
                vectors=vectors,
                namespace=namespace or ''
            )
            
            logger.info(
                f"Upserted {response.upserted_count} vectors to "
                f"namespace '{namespace or 'default'}'"
            )
            
            return {
                'upserted_count': response.upserted_count
            }
            
        except Exception as e:
            logger.error(f"Error upserting vectors: {e}")
            raise
    
    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filter_dict: Dict[str, Any] = None,
        namespace: str = None
    ) -> List[VectorSearchResult]:
        """
        Search for similar vectors in Pinecone.
        
        Args:
            query_vector: Query embedding
            top_k: Number of results to return
            filter_dict: Metadata filters
            namespace: Tenant namespace for isolation
        
        Returns:
            List of VectorSearchResult objects
        """
        try:
            response = self.index.query(
                vector=query_vector,
                top_k=top_k,
                filter=filter_dict,
                namespace=namespace or '',
                include_metadata=True
            )
            
            results = [
                VectorSearchResult(
                    id=match.id,
                    score=match.score,
                    metadata=match.metadata or {}
                )
                for match in response.matches
            ]
            
            logger.debug(
                f"Found {len(results)} results in "
                f"namespace '{namespace or 'default'}'"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching vectors: {e}")
            raise
    
    def delete(
        self,
        ids: List[str] = None,
        filter_dict: Dict[str, Any] = None,
        namespace: str = None
    ) -> Dict[str, Any]:
        """
        Delete vectors from Pinecone.
        
        Args:
            ids: List of vector IDs to delete
            filter_dict: Metadata filters for deletion
            namespace: Tenant namespace for isolation
        
        Returns:
            Dict with deletion statistics
        """
        try:
            if ids:
                self.index.delete(
                    ids=ids,
                    namespace=namespace or ''
                )
                logger.info(
                    f"Deleted {len(ids)} vectors from "
                    f"namespace '{namespace or 'default'}'"
                )
                return {'deleted_count': len(ids)}
            
            elif filter_dict:
                self.index.delete(
                    filter=filter_dict,
                    namespace=namespace or ''
                )
                logger.info(
                    f"Deleted vectors matching filter from "
                    f"namespace '{namespace or 'default'}'"
                )
                return {'deleted_count': 'unknown'}
            
            else:
                raise ValueError("Must provide either ids or filter_dict")
                
        except Exception as e:
            logger.error(f"Error deleting vectors: {e}")
            raise
    
    @classmethod
    def create_from_settings(cls) -> 'PineconeVectorStore':
        """
        Create Pinecone vector store from Django settings.
        
        Returns:
            PineconeVectorStore instance
        """
        from django.conf import settings
        
        api_key = getattr(settings, 'PINECONE_API_KEY', None)
        if not api_key:
            raise ValueError("PINECONE_API_KEY not configured in settings")
        
        index_name = getattr(settings, 'PINECONE_INDEX_NAME', 'wabotiq-rag')
        dimension = getattr(settings, 'PINECONE_DIMENSION', 1536)
        metric = getattr(settings, 'PINECONE_METRIC', 'cosine')
        cloud = getattr(settings, 'PINECONE_CLOUD', 'aws')
        region = getattr(settings, 'PINECONE_REGION', 'us-east-1')
        
        return cls(
            api_key=api_key,
            index_name=index_name,
            dimension=dimension,
            metric=metric,
            cloud=cloud,
            region=region
        )
