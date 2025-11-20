"""
Smart Product Discovery Service for proactive product suggestions.

Implements immediate product visibility without requiring category narrowing,
with fuzzy matching and contextual recommendations.

**Feature: conversational-commerce-ux-enhancement**
**Requirements: 2.1, 2.2, 2.3, 2.4, 2.5**
"""
import logging
from typing import List, Optional, Dict, Any
from django.db.models import Q, Count, F
from decimal import Decimal

from apps.catalog.models import Product
from apps.services.models import Service
from apps.bot.services.catalog_cache_service import CatalogCacheService
from apps.bot.services.fuzzy_matcher_service import FuzzyMatcherService

logger = logging.getLogger(__name__)


class SmartProductDiscoveryService:
    """
    Service for smart product discovery with immediate suggestions.
    
    Provides proactive product suggestions without requiring category narrowing,
    enabling customers to see products immediately when they ask "what do you have".
    
    Features:
    - Immediate product display (no narrowing required)
    - Fuzzy matching for product queries
    - Contextual recommendations based on conversation
    - Integration with catalog cache for performance
    - Popularity-based ranking
    
    TENANT SCOPING: All operations are tenant-scoped.
    """
    
    DEFAULT_SUGGESTION_LIMIT = 5
    MAX_SUGGESTION_LIMIT = 10
    
    def __init__(
        self,
        catalog_cache: Optional[CatalogCacheService] = None,
        fuzzy_matcher: Optional[FuzzyMatcherService] = None
    ):
        """
        Initialize Smart Product Discovery Service.
        
        Args:
            catalog_cache: Optional CatalogCacheService instance
            fuzzy_matcher: Optional FuzzyMatcherService instance
        """
        self.catalog_cache = catalog_cache or CatalogCacheService()
        self.fuzzy_matcher = fuzzy_matcher or FuzzyMatcherService()
    
    def get_immediate_suggestions(
        self,
        tenant,
        query: Optional[str] = None,
        context: Optional[Any] = None,
        limit: int = DEFAULT_SUGGESTION_LIMIT
    ) -> Dict[str, Any]:
        """
        Get immediate product/service suggestions without narrowing.
        
        Shows products immediately when customer asks "what do you have" or
        similar queries, without requiring category selection first.
        
        **Validates: Requirements 2.1, 2.2, 2.3**
        
        Args:
            tenant: Tenant instance
            query: Optional search query from customer
            context: Optional AgentContext for contextual recommendations
            limit: Maximum number of suggestions (default: 5)
            
        Returns:
            Dictionary with:
                - products: List of Product instances
                - services: List of Service instances
                - reasoning: Why these suggestions were chosen
                - priority: 'high', 'medium', or 'low'
                - total_available: Total products/services available
        """
        limit = min(limit, self.MAX_SUGGESTION_LIMIT)
        
        logger.info(
            f"Getting immediate suggestions for tenant {tenant.id}, "
            f"query='{query}', limit={limit}"
        )
        
        # Get all active products and services from cache
        all_products = self.catalog_cache.get_products(tenant, active_only=True)
        all_services = self.catalog_cache.get_services(tenant, active_only=True)
        
        # If no query, show popular/featured items
        if not query or len(query.strip()) < 2:
            return self._get_default_suggestions(
                all_products=all_products,
                all_services=all_services,
                limit=limit,
                context=context
            )
        
        # If query provided, use fuzzy matching and filtering
        return self._get_query_based_suggestions(
            all_products=all_products,
            all_services=all_services,
            query=query,
            limit=limit,
            context=context
        )
    
    def get_contextual_recommendations(
        self,
        tenant,
        customer,
        conversation_context,
        limit: int = DEFAULT_SUGGESTION_LIMIT
    ) -> List:
        """
        Get contextual recommendations based on conversation history.
        
        Analyzes conversation context to provide relevant product/service
        recommendations based on what the customer has discussed.
        
        **Validates: Requirements 2.3, 2.4**
        
        Args:
            tenant: Tenant instance
            customer: Customer instance
            conversation_context: ConversationContext instance
            limit: Maximum number of recommendations
            
        Returns:
            List of Product or Service instances
        """
        logger.info(
            f"Getting contextual recommendations for customer {customer.id}, "
            f"tenant {tenant.id}"
        )
        
        recommendations = []
        
        # Extract topics from conversation summary
        topics = self._extract_topics_from_context(conversation_context)
        
        if not topics:
            logger.debug("No topics found in conversation context")
            return recommendations
        
        # Get products matching topics
        products = self.catalog_cache.get_products(tenant, active_only=True)
        
        for product in products:
            relevance_score = self._calculate_relevance_score(product, topics)
            if relevance_score > 0.3:  # Threshold for relevance
                recommendations.append((product, relevance_score))
        
        # Sort by relevance score
        recommendations.sort(key=lambda x: x[1], reverse=True)
        
        # Return top recommendations
        return [item[0] for item in recommendations[:limit]]
    
    def search_products(
        self,
        tenant,
        query: str,
        limit: int = DEFAULT_SUGGESTION_LIMIT,
        fuzzy: bool = True
    ) -> List[Product]:
        """
        Search products with fuzzy matching support.
        
        Optimized with select_related for better query performance.
        
        **Validates: Requirements 2.2, 2.5**
        
        Args:
            tenant: Tenant instance
            query: Search query
            limit: Maximum number of results
            fuzzy: Whether to use fuzzy matching (default: True)
            
        Returns:
            List of matching Product instances
        """
        if not query or len(query.strip()) < 2:
            return []
        
        query = query.strip().lower()
        
        # Get all products from cache (already optimized with select_related)
        all_products = self.catalog_cache.get_products(tenant, active_only=True)
        
        if not fuzzy:
            # Exact matching only
            return [
                p for p in all_products
                if query in p.title.lower() or query in (p.description or '').lower()
            ][:limit]
        
        # Fuzzy matching
        matches = []
        
        for product in all_products:
            # Calculate similarity score using Levenshtein similarity
            title_score = FuzzyMatcherService._levenshtein_similarity(
                query,
                product.title.lower()
            )
            
            desc_score = 0.0
            if product.description:
                desc_score = FuzzyMatcherService._levenshtein_similarity(
                    query,
                    product.description.lower()
                )
            
            # Use best score
            best_score = max(title_score, desc_score * 0.8)  # Weight description lower
            
            if best_score > 0.5:  # Threshold for fuzzy match
                matches.append((product, best_score))
        
        # Sort by score
        matches.sort(key=lambda x: x[1], reverse=True)
        
        return [item[0] for item in matches[:limit]]
    
    def search_services(
        self,
        tenant,
        query: str,
        limit: int = DEFAULT_SUGGESTION_LIMIT,
        fuzzy: bool = True
    ) -> List[Service]:
        """
        Search services with fuzzy matching support.
        
        **Validates: Requirements 2.2, 2.5**
        
        Args:
            tenant: Tenant instance
            query: Search query
            limit: Maximum number of results
            fuzzy: Whether to use fuzzy matching (default: True)
            
        Returns:
            List of matching Service instances
        """
        if not query or len(query.strip()) < 2:
            return []
        
        query = query.strip().lower()
        
        # Get all services from cache
        all_services = self.catalog_cache.get_services(tenant, active_only=True)
        
        if not fuzzy:
            # Exact matching only
            return [
                s for s in all_services
                if query in s.title.lower() or query in (s.description or '').lower()
            ][:limit]
        
        # Fuzzy matching
        matches = []
        
        for service in all_services:
            # Calculate similarity score using Levenshtein similarity
            title_score = FuzzyMatcherService._levenshtein_similarity(
                query,
                service.title.lower()
            )
            
            desc_score = 0.0
            if service.description:
                desc_score = FuzzyMatcherService._levenshtein_similarity(
                    query,
                    service.description.lower()
                )
            
            # Use best score
            best_score = max(title_score, desc_score * 0.8)
            
            if best_score > 0.5:
                matches.append((service, best_score))
        
        # Sort by score
        matches.sort(key=lambda x: x[1], reverse=True)
        
        return [item[0] for item in matches[:limit]]
    
    # Private helper methods
    
    def _get_default_suggestions(
        self,
        all_products: List[Product],
        all_services: List[Service],
        limit: int,
        context: Optional[Any]
    ) -> Dict[str, Any]:
        """Get default suggestions when no query provided."""
        # Prioritize in-stock products
        in_stock_products = [p for p in all_products if p.is_in_stock]
        
        # If we have in-stock products, show those first
        if in_stock_products:
            suggested_products = in_stock_products[:limit]
            reasoning = "Showing available products from our catalog"
            priority = 'high'
        else:
            # Show any products
            suggested_products = all_products[:limit]
            reasoning = "Showing products from our catalog"
            priority = 'medium'
        
        # Also suggest services if available
        suggested_services = all_services[:limit]
        
        return {
            'products': suggested_products,
            'services': suggested_services,
            'reasoning': reasoning,
            'priority': priority,
            'total_available': {
                'products': len(all_products),
                'services': len(all_services)
            }
        }
    
    def _get_query_based_suggestions(
        self,
        all_products: List[Product],
        all_services: List[Service],
        query: str,
        limit: int,
        context: Optional[Any]
    ) -> Dict[str, Any]:
        """Get suggestions based on search query."""
        query_lower = query.lower()
        
        # Check if query is asking for products or services specifically
        is_product_query = any(word in query_lower for word in [
            'product', 'item', 'buy', 'purchase', 'sell', 'price'
        ])
        
        is_service_query = any(word in query_lower for word in [
            'service', 'appointment', 'book', 'schedule', 'available'
        ])
        
        # Search products
        matching_products = self.search_products(
            tenant=all_products[0].tenant if all_products else None,
            query=query,
            limit=limit,
            fuzzy=True
        ) if all_products else []
        
        # Search services
        matching_services = self.search_services(
            tenant=all_services[0].tenant if all_services else None,
            query=query,
            limit=limit,
            fuzzy=True
        ) if all_services else []
        
        # Determine priority and reasoning
        if matching_products or matching_services:
            if is_product_query and matching_products:
                priority = 'high'
                reasoning = f"Found {len(matching_products)} products matching '{query}'"
            elif is_service_query and matching_services:
                priority = 'high'
                reasoning = f"Found {len(matching_services)} services matching '{query}'"
            else:
                priority = 'medium'
                reasoning = f"Found items matching '{query}'"
        else:
            # No matches, show popular items instead
            priority = 'low'
            reasoning = f"No exact matches for '{query}', showing popular items"
            matching_products = all_products[:limit]
            matching_services = all_services[:limit]
        
        return {
            'products': matching_products,
            'services': matching_services,
            'reasoning': reasoning,
            'priority': priority,
            'query': query,
            'total_available': {
                'products': len(all_products),
                'services': len(all_services)
            }
        }
    
    def _extract_topics_from_context(
        self,
        conversation_context
    ) -> List[str]:
        """Extract topics from conversation context."""
        topics = []
        
        if not conversation_context:
            return topics
        
        # Extract from conversation summary
        if conversation_context.conversation_summary:
            summary_lower = conversation_context.conversation_summary.lower()
            
            # Simple keyword extraction (can be enhanced with NLP)
            keywords = [
                'phone', 'laptop', 'computer', 'tablet', 'watch',
                'clothing', 'shoes', 'accessories',
                'food', 'drink', 'beverage',
                'book', 'magazine', 'media',
                'furniture', 'home', 'decor',
                'electronics', 'appliance',
                'beauty', 'cosmetics', 'skincare',
                'sports', 'fitness', 'exercise',
                'toy', 'game', 'entertainment'
            ]
            
            for keyword in keywords:
                if keyword in summary_lower:
                    topics.append(keyword)
        
        # Extract from key facts
        if hasattr(conversation_context, 'key_facts') and conversation_context.key_facts:
            for fact in conversation_context.key_facts:
                if isinstance(fact, str):
                    topics.extend(fact.lower().split())
        
        return list(set(topics))  # Remove duplicates
    
    def _calculate_relevance_score(
        self,
        product: Product,
        topics: List[str]
    ) -> float:
        """Calculate relevance score for a product given topics."""
        if not topics:
            return 0.0
        
        score = 0.0
        product_text = f"{product.title} {product.description or ''}".lower()
        
        for topic in topics:
            if topic in product_text:
                score += 1.0
        
        # Normalize by number of topics
        return score / len(topics)


def create_discovery_service() -> SmartProductDiscoveryService:
    """
    Factory function to create SmartProductDiscoveryService instance.
    
    Returns:
        SmartProductDiscoveryService instance
    """
    return SmartProductDiscoveryService()
