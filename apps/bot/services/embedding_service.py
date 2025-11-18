"""
Embedding service for generating text embeddings using OpenAI.
"""
import hashlib
import logging
from typing import List, Dict, Any
from decimal import Decimal

from django.core.cache import cache
from openai import OpenAI

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Service for generating text embeddings with caching and batch support.
    """
    
    # Model pricing per 1M tokens
    MODEL_PRICING = {
        'text-embedding-3-small': Decimal('0.00002'),  # $0.02 per 1M tokens
        'text-embedding-3-large': Decimal('0.00013'),  # $0.13 per 1M tokens
    }
    
    DEFAULT_MODEL = 'text-embedding-3-small'
    CACHE_TTL = 300  # 5 minutes for query embeddings
    MAX_BATCH_SIZE = 100
    
    def __init__(self, api_key: str, model: str = None):
        """
        Initialize embedding service.
        
        Args:
            api_key: OpenAI API key
            model: Embedding model to use (default: text-embedding-3-small)
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model or self.DEFAULT_MODEL
    
    def embed_text(
        self,
        text: str,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            use_cache: Whether to use cache for this embedding
        
        Returns:
            Dict with 'embedding', 'tokens', and 'cost'
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        # Check cache
        if use_cache:
            cache_key = self._get_cache_key(text)
            cached = cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for embedding: {text[:50]}")
                return cached
        
        # Generate embedding
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text
            )
            
            embedding = response.data[0].embedding
            tokens = response.usage.total_tokens
            cost = self._calculate_cost(tokens)
            
            result = {
                'embedding': embedding,
                'tokens': tokens,
                'cost': cost,
                'model': self.model
            }
            
            # Cache result
            if use_cache:
                cache.set(cache_key, result, self.CACHE_TTL)
            
            logger.info(
                f"Generated embedding: {tokens} tokens, "
                f"${cost:.6f} cost"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    def embed_batch(
        self,
        texts: List[str],
        use_cache: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Generate embeddings for multiple texts in batch.
        
        Args:
            texts: List of texts to embed
            use_cache: Whether to use cache (usually False for batch)
        
        Returns:
            List of dicts with 'embedding', 'tokens', and 'cost'
        """
        if not texts:
            return []
        
        if len(texts) > self.MAX_BATCH_SIZE:
            raise ValueError(
                f"Batch size {len(texts)} exceeds maximum {self.MAX_BATCH_SIZE}"
            )
        
        # Filter empty texts
        valid_texts = [t for t in texts if t and t.strip()]
        if not valid_texts:
            raise ValueError("No valid texts to embed")
        
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=valid_texts
            )
            
            total_tokens = response.usage.total_tokens
            total_cost = self._calculate_cost(total_tokens)
            
            results = []
            for i, data in enumerate(response.data):
                results.append({
                    'embedding': data.embedding,
                    'tokens': total_tokens // len(valid_texts),  # Approximate
                    'cost': total_cost / len(valid_texts),  # Approximate
                    'model': self.model,
                    'text': valid_texts[i]
                })
            
            logger.info(
                f"Generated {len(results)} embeddings: "
                f"{total_tokens} tokens, ${total_cost:.6f} cost"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            raise
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        return f"embedding:{self.model}:{text_hash}"
    
    def _calculate_cost(self, tokens: int) -> Decimal:
        """Calculate cost for given token count."""
        price_per_token = self.MODEL_PRICING.get(
            self.model,
            self.MODEL_PRICING[self.DEFAULT_MODEL]
        )
        return (Decimal(tokens) / Decimal(1_000_000)) * price_per_token
    
    @classmethod
    def create_for_tenant(cls, tenant) -> 'EmbeddingService':
        """
        Create embedding service for a tenant.
        
        Args:
            tenant: Tenant instance
        
        Returns:
            EmbeddingService instance
        """
        from django.conf import settings
        
        # Get API key from tenant settings or fall back to global
        api_key = tenant.settings.openai_api_key
        if not api_key:
            api_key = settings.OPENAI_API_KEY
        
        if not api_key:
            raise ValueError("OpenAI API key not configured")
        
        # Get embedding model from agent configuration
        model = cls.DEFAULT_MODEL
        try:
            config = tenant.agent_configuration
            if config and config.embedding_model:
                model = config.embedding_model
        except Exception:
            pass
        
        return cls(api_key=api_key, model=model)
