"""
Fuzzy Matcher Service for intelligent product and service matching.

Provides fuzzy string matching, spelling correction, and semantic similarity
for matching customer queries to catalog items even with typos, abbreviations,
or informal names.
"""
import logging
import re
from typing import List, Optional, Tuple, Dict, Any
from difflib import SequenceMatcher
from django.core.cache import cache

from apps.catalog.models import Product
from apps.services.models import Service

logger = logging.getLogger(__name__)


class FuzzyMatcherService:
    """
    Service for intelligent fuzzy matching and spelling correction.
    
    Provides methods to match customer queries to products and services
    using Levenshtein distance, semantic similarity, and vocabulary-based
    spelling correction. Handles abbreviations, informal names, and typos.
    """
    
    # Cache TTL in seconds (5 minutes)
    CACHE_TTL = 300
    
    # Default similarity thresholds
    DEFAULT_THRESHOLD = 0.7
    HIGH_CONFIDENCE_THRESHOLD = 0.85
    LOW_CONFIDENCE_THRESHOLD = 0.6
    
    # Common abbreviations and informal names mapping
    COMMON_ABBREVIATIONS = {
        'tshirt': 't-shirt',
        't shirt': 't-shirt',
        'tee': 't-shirt',
        'hoodie': 'hooded sweatshirt',
        'sweater': 'sweatshirt',
        'pants': 'trousers',
        'jeans': 'denim pants',
        'sneakers': 'athletic shoes',
        'trainers': 'athletic shoes',
        'runners': 'running shoes',
    }
    
    def __init__(self, openai_client=None):
        """
        Initialize Fuzzy Matcher Service.
        
        Args:
            openai_client: Optional OpenAI client for semantic similarity
        """
        self.openai_client = openai_client
    
    @staticmethod
    def _get_cache_key(prefix: str, tenant_id: str, query: str) -> str:
        """Generate cache key for fuzzy match results."""
        return f"fuzzy_match:{prefix}:{tenant_id}:{query[:100].lower()}"
    
    def match_product(
        self,
        query: str,
        tenant,
        threshold: float = DEFAULT_THRESHOLD,
        limit: int = 5,
        use_semantic: bool = True
    ) -> List[Tuple[Product, float]]:
        """
        Match query to products using fuzzy matching and semantic similarity.
        
        Combines multiple matching strategies:
        1. Exact match (case-insensitive)
        2. Levenshtein distance (string similarity)
        3. Semantic similarity (if OpenAI client available)
        4. Abbreviation expansion
        
        Args:
            query: Customer query text
            tenant: Tenant instance
            threshold: Minimum similarity score (0.0-1.0)
            limit: Maximum number of results
            use_semantic: Whether to use semantic similarity
            
        Returns:
            List of tuples (Product, confidence_score) sorted by relevance
        """
        # Check cache first
        cache_key = self._get_cache_key('product', str(tenant.id), query)
        cached_results = cache.get(cache_key)
        if cached_results is not None:
            logger.debug(f"Returning cached product match for query: {query[:50]}")
            return cached_results
        
        # Normalize query
        normalized_query = self._normalize_text(query)
        
        # Expand abbreviations
        expanded_query = self._expand_abbreviations(normalized_query)
        
        # Get all active products for tenant
        products = Product.objects.filter(
            tenant=tenant,
            is_active=True
        ).select_related('tenant')
        
        # Calculate similarity scores
        results = []
        for product in products:
            # Calculate string similarity
            string_score = self._calculate_string_similarity(
                expanded_query,
                product.title,
                product.description
            )
            
            # Use string score as base
            confidence = string_score
            
            # Boost for exact matches
            if normalized_query.lower() in product.title.lower():
                confidence = max(confidence, 0.95)
            
            # Add to results if above threshold
            if confidence >= threshold:
                results.append((product, confidence))
        
        # Sort by confidence (descending)
        results.sort(key=lambda x: x[1], reverse=True)
        
        # Limit results
        results = results[:limit]
        
        logger.info(
            f"Product fuzzy match for tenant {tenant.id}: "
            f"query='{query[:50]}', found={len(results)} matches"
        )
        
        # Cache results
        cache.set(cache_key, results, self.CACHE_TTL)
        
        return results
    
    def match_service(
        self,
        query: str,
        tenant,
        threshold: float = DEFAULT_THRESHOLD,
        limit: int = 5,
        use_semantic: bool = True
    ) -> List[Tuple[Service, float]]:
        """
        Match query to services using fuzzy matching and semantic similarity.
        
        Uses same approach as match_product but for services.
        
        Args:
            query: Customer query text
            tenant: Tenant instance
            threshold: Minimum similarity score (0.0-1.0)
            limit: Maximum number of results
            use_semantic: Whether to use semantic similarity
            
        Returns:
            List of tuples (Service, confidence_score) sorted by relevance
        """
        # Check cache first
        cache_key = self._get_cache_key('service', str(tenant.id), query)
        cached_results = cache.get(cache_key)
        if cached_results is not None:
            logger.debug(f"Returning cached service match for query: {query[:50]}")
            return cached_results
        
        # Normalize query
        normalized_query = self._normalize_text(query)
        
        # Expand abbreviations
        expanded_query = self._expand_abbreviations(normalized_query)
        
        # Get all active services for tenant
        services = Service.objects.filter(
            tenant=tenant,
            is_active=True
        ).select_related('tenant')
        
        # Calculate similarity scores
        results = []
        for service in services:
            # Calculate string similarity
            string_score = self._calculate_string_similarity(
                expanded_query,
                service.title,
                service.description
            )
            
            # Use string score as base
            confidence = string_score
            
            # Boost for exact matches
            if normalized_query.lower() in service.title.lower():
                confidence = max(confidence, 0.95)
            
            # Add to results if above threshold
            if confidence >= threshold:
                results.append((service, confidence))
        
        # Sort by confidence (descending)
        results.sort(key=lambda x: x[1], reverse=True)
        
        # Limit results
        results = results[:limit]
        
        logger.info(
            f"Service fuzzy match for tenant {tenant.id}: "
            f"query='{query[:50]}', found={len(results)} matches"
        )
        
        # Cache results
        cache.set(cache_key, results, self.CACHE_TTL)
        
        return results
    
    def correct_spelling(
        self,
        text: str,
        vocabulary: List[str],
        threshold: float = 0.75
    ) -> str:
        """
        Correct spelling using vocabulary-based correction.
        
        Finds the closest match in the vocabulary for each word that
        doesn't match exactly. Uses Levenshtein distance for similarity.
        
        Args:
            text: Text to correct
            vocabulary: List of correct words/phrases
            threshold: Minimum similarity for correction
            
        Returns:
            Corrected text
        """
        # Normalize text
        normalized = self._normalize_text(text)
        
        # Split into words
        words = normalized.split()
        
        # Correct each word
        corrected_words = []
        for word in words:
            # Check if word exists in vocabulary (case-insensitive)
            if any(word.lower() == v.lower() for v in vocabulary):
                corrected_words.append(word)
                continue
            
            # Find best match in vocabulary
            best_match = None
            best_score = 0.0
            
            for vocab_word in vocabulary:
                score = self._levenshtein_similarity(word.lower(), vocab_word.lower())
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = vocab_word
            
            # Use best match if found, otherwise keep original
            if best_match:
                corrected_words.append(best_match)
                logger.debug(f"Corrected '{word}' to '{best_match}' (score: {best_score:.2f})")
            else:
                corrected_words.append(word)
        
        return ' '.join(corrected_words)
    
    def get_confidence_level(self, score: float) -> str:
        """
        Get confidence level description from score.
        
        Args:
            score: Confidence score (0.0-1.0)
            
        Returns:
            Confidence level: 'high', 'medium', or 'low'
        """
        if score >= self.HIGH_CONFIDENCE_THRESHOLD:
            return 'high'
        elif score >= self.LOW_CONFIDENCE_THRESHOLD:
            return 'medium'
        else:
            return 'low'
    
    def should_confirm_correction(self, score: float) -> bool:
        """
        Determine if correction should be confirmed with customer.
        
        Args:
            score: Confidence score (0.0-1.0)
            
        Returns:
            True if confirmation needed, False otherwise
        """
        return score < self.HIGH_CONFIDENCE_THRESHOLD
    
    @staticmethod
    def _normalize_text(text: str) -> str:
        """
        Normalize text for matching.
        
        - Convert to lowercase
        - Remove extra whitespace
        - Remove special characters (keep alphanumeric and spaces)
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text
        """
        # Convert to lowercase
        text = text.lower()
        
        # Remove special characters except spaces and hyphens
        text = re.sub(r'[^a-z0-9\s\-]', '', text)
        
        # Replace multiple spaces with single space
        text = re.sub(r'\s+', ' ', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def _expand_abbreviations(self, text: str) -> str:
        """
        Expand common abbreviations and informal names.
        
        Args:
            text: Text to expand
            
        Returns:
            Text with abbreviations expanded
        """
        expanded = text
        
        for abbrev, full in self.COMMON_ABBREVIATIONS.items():
            # Replace whole word matches only
            pattern = r'\b' + re.escape(abbrev) + r'\b'
            expanded = re.sub(pattern, full, expanded, flags=re.IGNORECASE)
        
        return expanded
    
    def _calculate_string_similarity(
        self,
        query: str,
        title: str,
        description: Optional[str] = None
    ) -> float:
        """
        Calculate string similarity using Levenshtein distance.
        
        Compares query against title and description, returning the
        highest similarity score.
        
        Args:
            query: Query text
            title: Item title
            description: Optional item description
            
        Returns:
            Similarity score (0.0-1.0)
        """
        # Normalize inputs
        query_norm = self._normalize_text(query)
        title_norm = self._normalize_text(title)
        
        # Calculate title similarity
        title_score = self._levenshtein_similarity(query_norm, title_norm)
        
        # Check for substring matches (boost score)
        if query_norm in title_norm or title_norm in query_norm:
            title_score = max(title_score, 0.85)
        
        # Calculate description similarity if available
        desc_score = 0.0
        if description:
            desc_norm = self._normalize_text(description)
            desc_score = self._levenshtein_similarity(query_norm, desc_norm)
            
            # Check for substring matches
            if query_norm in desc_norm:
                desc_score = max(desc_score, 0.75)
        
        # Return highest score (title weighted more than description)
        return max(title_score, desc_score * 0.8)
    
    @staticmethod
    def _levenshtein_similarity(s1: str, s2: str) -> float:
        """
        Calculate Levenshtein similarity between two strings.
        
        Uses Python's SequenceMatcher for efficient similarity calculation.
        Returns a score between 0.0 (completely different) and 1.0 (identical).
        
        Args:
            s1: First string
            s2: Second string
            
        Returns:
            Similarity score (0.0-1.0)
        """
        if not s1 or not s2:
            return 0.0
        
        # Use SequenceMatcher for similarity ratio
        matcher = SequenceMatcher(None, s1, s2)
        return matcher.ratio()
    
    def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for semantic similarity.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector or None if unavailable
        """
        if not self.openai_client:
            return None
        
        try:
            response = self.openai_client.embeddings.create(
                model='text-embedding-3-small',
                input=text
            )
            return response.data[0].embedding
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
            Similarity score (0.0-1.0)
        """
        if len(vec1) != len(vec2):
            return 0.0
        
        import math
        
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
        
        # Normalize to 0-1 range
        return (similarity + 1) / 2


def create_fuzzy_matcher_service(openai_client=None) -> FuzzyMatcherService:
    """
    Factory function to create FuzzyMatcherService instance.
    
    Args:
        openai_client: Optional OpenAI client for semantic similarity
        
    Returns:
        FuzzyMatcherService instance
    """
    return FuzzyMatcherService(openai_client=openai_client)
