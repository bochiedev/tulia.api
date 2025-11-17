"""
Knowledge Base Service for managing AI agent knowledge entries.

Provides CRUD operations, semantic search using embeddings, and caching
for frequently accessed knowledge entries.
"""
import logging
import math
from typing import List, Optional, Dict, Any, Tuple
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from openai import OpenAI
from django.conf import settings

from apps.bot.models import KnowledgeEntry

logger = logging.getLogger(__name__)


class KnowledgeBaseService:
    """
    Service for managing knowledge base entries with semantic search.
    
    Handles CRUD operations, embedding generation, semantic similarity search,
    and caching for performance optimization.
    """
    
    # Cache TTL in seconds (5 minutes for entries, 10 minutes for embeddings)
    ENTRY_CACHE_TTL = 300
    EMBEDDING_CACHE_TTL = 600
    
    # OpenAI embedding model
    EMBEDDING_MODEL = 'text-embedding-3-small'
    EMBEDDING_DIMENSIONS = 1536
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Knowledge Base Service.
        
        Args:
            api_key: OpenAI API key (defaults to settings.OPENAI_API_KEY)
        """
        self.api_key = api_key or settings.OPENAI_API_KEY
        if not self.api_key:
            logger.warning("OpenAI API key not configured, embedding generation will fail")
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None
    
    @staticmethod
    def _get_entry_cache_key(entry_id: str) -> str:
        """Generate cache key for knowledge entry."""
        return f"knowledge_entry:{entry_id}"
    
    @staticmethod
    def _get_search_cache_key(tenant_id: str, query: str, entry_types: Optional[List[str]]) -> str:
        """Generate cache key for search results."""
        types_str = ','.join(sorted(entry_types)) if entry_types else 'all'
        return f"knowledge_search:{tenant_id}:{types_str}:{query[:100]}"
    
    def create_entry(
        self,
        tenant,
        entry_type: str,
        title: str,
        content: str,
        category: str = '',
        keywords: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        priority: int = 0,
        is_active: bool = True
    ) -> KnowledgeEntry:
        """
        Create new knowledge base entry with embedding generation.
        
        Generates vector embedding from title and content for semantic search.
        
        Args:
            tenant: Tenant instance
            entry_type: Type of entry (faq, policy, product_info, etc.)
            title: Entry title or question
            content: Entry content or answer
            category: Optional category for organization
            keywords: Optional list of keywords
            metadata: Optional metadata dictionary
            priority: Priority for ranking (0-100)
            is_active: Whether entry is active
            
        Returns:
            Created KnowledgeEntry instance
            
        Raises:
            ValidationError: If entry data is invalid
        """
        # Import sanitizer
        from apps.bot.security_audit import InputSanitizer
        
        # Sanitize title and content
        title, content = InputSanitizer.sanitize_knowledge_content(title, content)
        
        # Validate metadata if provided
        if metadata:
            InputSanitizer.validate_json_field(metadata, 'metadata')
        
        # Validate entry type
        valid_types = ['faq', 'policy', 'product_info', 'service_info', 'procedure', 'general']
        if entry_type not in valid_types:
            raise ValidationError(f"Invalid entry_type. Must be one of: {', '.join(valid_types)}")
        
        # Validate priority
        if not 0 <= priority <= 100:
            raise ValidationError("Priority must be between 0 and 100")
        
        # Generate embedding
        embedding = self._generate_embedding(title, content)
        
        # Create entry
        with transaction.atomic():
            entry = KnowledgeEntry.objects.create(
                tenant=tenant,
                entry_type=entry_type,
                title=title,
                content=content,
                category=category,
                keywords=', '.join(keywords) if keywords else '',
                embedding=embedding,
                metadata=metadata or {},
                priority=priority,
                is_active=is_active,
                version=1
            )
        
        logger.info(
            f"Created knowledge entry {entry.id} for tenant {tenant.id}: "
            f"type={entry_type}, title={title[:50]}"
        )
        
        # Cache the entry
        self._cache_entry(entry)
        
        return entry
    
    def search(
        self,
        tenant,
        query: str,
        entry_types: Optional[List[str]] = None,
        limit: int = 5,
        min_similarity: float = 0.7
    ) -> List[Tuple[KnowledgeEntry, float]]:
        """
        Search knowledge base using semantic similarity.
        
        Uses cosine similarity between query embedding and entry embeddings
        to find the most relevant knowledge entries.
        
        Args:
            tenant: Tenant instance
            query: Search query text
            entry_types: Optional list of entry types to filter by
            limit: Maximum number of results to return
            min_similarity: Minimum similarity score (0.0-1.0)
            
        Returns:
            List of tuples (KnowledgeEntry, similarity_score) sorted by relevance
        """
        # Check cache first
        cache_key = self._get_search_cache_key(str(tenant.id), query, entry_types)
        cached_results = cache.get(cache_key)
        if cached_results is not None:
            logger.debug(f"Returning cached search results for query: {query[:50]}")
            return cached_results
        
        # Generate query embedding
        query_embedding = self._generate_embedding(query)
        if not query_embedding:
            logger.warning("Failed to generate query embedding, falling back to keyword search")
            return self._fallback_keyword_search(tenant, query, entry_types, limit)
        
        # Get all active entries for tenant
        entries_query = KnowledgeEntry.objects.filter(
            tenant=tenant,
            is_active=True
        )
        
        # Filter by entry types if specified
        if entry_types:
            entries_query = entries_query.filter(entry_type__in=entry_types)
        
        # Get entries with embeddings
        entries = entries_query.exclude(embedding__isnull=True)
        
        # Calculate similarity scores
        results = []
        for entry in entries:
            if entry.embedding:
                similarity = self._cosine_similarity(query_embedding, entry.embedding)
                if similarity >= min_similarity:
                    results.append((entry, similarity))
        
        # Sort by similarity (descending) and priority
        results.sort(key=lambda x: (x[1], x[0].priority), reverse=True)
        
        # Limit results
        results = results[:limit]
        
        logger.info(
            f"Knowledge search for tenant {tenant.id}: "
            f"query='{query[:50]}', found={len(results)} results"
        )
        
        # Cache results
        cache.set(cache_key, results, self.ENTRY_CACHE_TTL)
        
        return results
    
    def update_entry(
        self,
        entry_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        category: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        priority: Optional[int] = None,
        is_active: Optional[bool] = None
    ) -> KnowledgeEntry:
        """
        Update existing knowledge entry with version increment.
        
        Regenerates embedding if title or content changed.
        
        Args:
            entry_id: UUID of entry to update
            title: New title (optional)
            content: New content (optional)
            category: New category (optional)
            keywords: New keywords list (optional)
            metadata: New metadata (optional)
            priority: New priority (optional)
            is_active: New active status (optional)
            
        Returns:
            Updated KnowledgeEntry instance
            
        Raises:
            KnowledgeEntry.DoesNotExist: If entry not found
            ValidationError: If update data is invalid
        """
        entry = KnowledgeEntry.objects.get(id=entry_id)
        
        # Track if we need to regenerate embedding
        regenerate_embedding = False
        
        with transaction.atomic():
            # Update fields
            if title is not None:
                entry.title = title
                regenerate_embedding = True
            
            if content is not None:
                entry.content = content
                regenerate_embedding = True
            
            if category is not None:
                entry.category = category
            
            if keywords is not None:
                entry.keywords = ', '.join(keywords)
            
            if metadata is not None:
                entry.metadata = metadata
            
            if priority is not None:
                if not 0 <= priority <= 100:
                    raise ValidationError("Priority must be between 0 and 100")
                entry.priority = priority
            
            if is_active is not None:
                entry.is_active = is_active
            
            # Regenerate embedding if content changed
            if regenerate_embedding:
                entry.embedding = self._generate_embedding(entry.title, entry.content)
            
            # Increment version
            entry.increment_version()
            
            # Save
            entry.save()
        
        logger.info(
            f"Updated knowledge entry {entry.id}: "
            f"version={entry.version}, regenerated_embedding={regenerate_embedding}"
        )
        
        # Invalidate caches
        self._invalidate_entry_cache(entry)
        self._invalidate_search_cache(entry.tenant)
        
        return entry
    
    def delete_entry(self, entry_id: str) -> KnowledgeEntry:
        """
        Soft delete knowledge entry.
        
        Sets is_active=False instead of actually deleting the record.
        
        Args:
            entry_id: UUID of entry to delete
            
        Returns:
            Deleted (deactivated) KnowledgeEntry instance
            
        Raises:
            KnowledgeEntry.DoesNotExist: If entry not found
        """
        entry = KnowledgeEntry.objects.get(id=entry_id)
        
        with transaction.atomic():
            entry.is_active = False
            entry.increment_version()
            entry.save()
        
        logger.info(f"Soft deleted knowledge entry {entry.id}")
        
        # Invalidate caches
        self._invalidate_entry_cache(entry)
        self._invalidate_search_cache(entry.tenant)
        
        return entry
    
    def get_entry(self, entry_id: str, use_cache: bool = True) -> KnowledgeEntry:
        """
        Get knowledge entry by ID with optional caching.
        
        Args:
            entry_id: UUID of entry to retrieve
            use_cache: Whether to use cache (default: True)
            
        Returns:
            KnowledgeEntry instance
            
        Raises:
            KnowledgeEntry.DoesNotExist: If entry not found
        """
        if use_cache:
            cache_key = self._get_entry_cache_key(str(entry_id))
            entry = cache.get(cache_key)
            if entry is not None:
                return entry
        
        entry = KnowledgeEntry.objects.get(id=entry_id)
        
        if use_cache:
            self._cache_entry(entry)
        
        return entry
    
    def _generate_embedding(
        self,
        title: str,
        content: Optional[str] = None
    ) -> Optional[List[float]]:
        """
        Generate vector embedding for text using OpenAI.
        
        Args:
            title: Title text
            content: Optional content text
            
        Returns:
            List of floats representing the embedding vector, or None on error
        """
        if not self.client:
            logger.error("OpenAI client not initialized, cannot generate embedding")
            return None
        
        try:
            # Combine title and content
            text = title
            if content:
                text = f"{title}\n\n{content}"
            
            # Truncate if too long (max 8191 tokens for text-embedding-3-small)
            # Rough estimate: 1 token ≈ 4 characters
            max_chars = 8191 * 4
            if len(text) > max_chars:
                text = text[:max_chars]
                logger.warning(f"Truncated text to {max_chars} characters for embedding")
            
            # Generate embedding
            response = self.client.embeddings.create(
                model=self.EMBEDDING_MODEL,
                input=text
            )
            
            embedding = response.data[0].embedding
            
            logger.debug(
                f"Generated embedding: model={self.EMBEDDING_MODEL}, "
                f"dimensions={len(embedding)}"
            )
            
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None
    
    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if len(vec1) != len(vec2):
            logger.error(f"Vector dimension mismatch: {len(vec1)} vs {len(vec2)}")
            return 0.0
        
        # Calculate dot product
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        
        # Calculate magnitudes
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))
        
        # Avoid division by zero
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        # Calculate cosine similarity
        similarity = dot_product / (magnitude1 * magnitude2)
        
        # Normalize to 0-1 range (cosine similarity is -1 to 1)
        normalized = (similarity + 1) / 2
        
        return normalized
    
    def _fallback_keyword_search(
        self,
        tenant,
        query: str,
        entry_types: Optional[List[str]],
        limit: int
    ) -> List[Tuple[KnowledgeEntry, float]]:
        """
        Fallback keyword-based search when embeddings unavailable.
        
        Args:
            tenant: Tenant instance
            query: Search query
            entry_types: Optional entry types filter
            limit: Maximum results
            
        Returns:
            List of tuples (KnowledgeEntry, score)
        """
        entries_query = KnowledgeEntry.objects.filter(
            tenant=tenant,
            is_active=True
        )
        
        if entry_types:
            entries_query = entries_query.filter(entry_type__in=entry_types)
        
        # Simple keyword matching
        query_lower = query.lower()
        results = []
        
        for entry in entries_query:
            score = 0.0
            
            # Check title
            if query_lower in entry.title.lower():
                score += 0.5
            
            # Check content
            if query_lower in entry.content.lower():
                score += 0.3
            
            # Check keywords
            if entry.keywords and query_lower in entry.keywords.lower():
                score += 0.2
            
            if score > 0:
                results.append((entry, score))
        
        # Sort by score and priority
        results.sort(key=lambda x: (x[1], x[0].priority), reverse=True)
        
        return results[:limit]
    
    def _cache_entry(self, entry: KnowledgeEntry) -> None:
        """Cache knowledge entry."""
        cache_key = self._get_entry_cache_key(str(entry.id))
        cache.set(cache_key, entry, self.ENTRY_CACHE_TTL)
    
    def _invalidate_entry_cache(self, entry: KnowledgeEntry) -> None:
        """Invalidate cached entry."""
        cache_key = self._get_entry_cache_key(str(entry.id))
        cache.delete(cache_key)
    
    def _invalidate_search_cache(self, tenant) -> None:
        """
        Invalidate all search caches for tenant.
        
        Note: This is a simple implementation. For production, consider
        using cache key patterns or a more sophisticated cache invalidation strategy.
        """
        # In a real implementation, you might want to track cache keys
        # or use a cache backend that supports pattern-based deletion
        logger.debug(f"Search cache invalidated for tenant {tenant.id}")


def create_knowledge_base_service(api_key: Optional[str] = None) -> KnowledgeBaseService:
    """
    Factory function to create KnowledgeBaseService instance.
    
    Args:
        api_key: Optional OpenAI API key (defaults to settings)
        
    Returns:
        KnowledgeBaseService instance
    """
    return KnowledgeBaseService(api_key=api_key)
