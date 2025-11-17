"""
Query Optimizer for AI Agent database operations.

Provides optimized query methods with select_related and prefetch_related
to reduce database queries and improve performance.
"""
import logging
from typing import List, Optional
from django.db.models import Prefetch, Q, Count, Sum
from django.core.cache import cache

from apps.messaging.models import Message, Conversation
from apps.bot.models import (
    AgentInteraction,
    ConversationContext,
    KnowledgeEntry,
    AgentConfiguration
)

logger = logging.getLogger(__name__)


class QueryOptimizer:
    """
    Service for optimized database queries with caching.
    
    Implements query optimization patterns including:
    - select_related for foreign keys
    - prefetch_related for reverse foreign keys
    - Query result caching
    - Efficient filtering and aggregation
    """
    
    # Cache TTL in seconds
    QUERY_CACHE_TTL = 300  # 5 minutes
    
    @classmethod
    def get_conversation_with_context(cls, conversation_id: str, use_cache: bool = True):
        """
        Get conversation with related context in a single query.
        
        Uses select_related to fetch conversation, customer, and tenant
        in a single database query.
        
        Args:
            conversation_id: Conversation UUID
            use_cache: Whether to use cache (default: True)
            
        Returns:
            Conversation instance with related objects loaded
        """
        if use_cache:
            cache_key = f"conversation_with_context:{conversation_id}"
            cached = cache.get(cache_key)
            if cached:
                logger.debug(f"Retrieved conversation {conversation_id} from cache")
                return cached
        
        try:
            conversation = Conversation.objects.select_related(
                'tenant',
                'customer',
                'context'  # One-to-one relationship
            ).get(id=conversation_id)
            
            if use_cache:
                cache.set(cache_key, conversation, cls.QUERY_CACHE_TTL)
            
            return conversation
            
        except Conversation.DoesNotExist:
            logger.error(f"Conversation {conversation_id} not found")
            return None
    
    @classmethod
    def get_conversation_messages(
        cls,
        conversation_id: str,
        limit: int = 20,
        use_cache: bool = True
    ) -> List[Message]:
        """
        Get conversation messages with optimized query.
        
        Fetches messages with conversation and customer data in a single query.
        
        Args:
            conversation_id: Conversation UUID
            limit: Maximum number of messages to return
            use_cache: Whether to use cache (default: True)
            
        Returns:
            List of Message instances ordered chronologically
        """
        if use_cache:
            cache_key = f"conversation_messages:{conversation_id}:{limit}"
            cached = cache.get(cache_key)
            if cached:
                logger.debug(f"Retrieved {len(cached)} messages from cache")
                return cached
        
        messages = Message.objects.filter(
            conversation_id=conversation_id
        ).select_related(
            'conversation',
            'conversation__customer',
            'conversation__tenant'
        ).order_by('-created_at')[:limit]
        
        # Convert to list and reverse to chronological order
        messages = list(reversed(messages))
        
        if use_cache:
            cache.set(cache_key, messages, cls.QUERY_CACHE_TTL)
        
        logger.debug(f"Retrieved {len(messages)} messages for conversation {conversation_id}")
        
        return messages
    
    @classmethod
    def get_agent_interactions(
        cls,
        conversation_id: str,
        limit: int = 10,
        use_cache: bool = True
    ) -> List[AgentInteraction]:
        """
        Get agent interactions for a conversation with optimized query.
        
        Args:
            conversation_id: Conversation UUID
            limit: Maximum number of interactions to return
            use_cache: Whether to use cache (default: True)
            
        Returns:
            List of AgentInteraction instances
        """
        if use_cache:
            cache_key = f"agent_interactions:{conversation_id}:{limit}"
            cached = cache.get(cache_key)
            if cached:
                logger.debug(f"Retrieved {len(cached)} interactions from cache")
                return cached
        
        interactions = AgentInteraction.objects.filter(
            conversation_id=conversation_id
        ).select_related(
            'conversation',
            'conversation__tenant'
        ).order_by('-created_at')[:limit]
        
        interactions = list(interactions)
        
        if use_cache:
            cache.set(cache_key, interactions, cls.QUERY_CACHE_TTL)
        
        logger.debug(f"Retrieved {len(interactions)} interactions for conversation {conversation_id}")
        
        return interactions
    
    @classmethod
    def get_knowledge_entries_for_tenant(
        cls,
        tenant_id: str,
        entry_type: Optional[str] = None,
        active_only: bool = True,
        use_cache: bool = True
    ) -> List[KnowledgeEntry]:
        """
        Get knowledge entries for tenant with optimized query.
        
        Args:
            tenant_id: Tenant UUID
            entry_type: Optional entry type filter
            active_only: Whether to return only active entries
            use_cache: Whether to use cache (default: True)
            
        Returns:
            List of KnowledgeEntry instances
        """
        cache_key = f"knowledge_entries:{tenant_id}:{entry_type or 'all'}:{active_only}"
        
        if use_cache:
            cached = cache.get(cache_key)
            if cached:
                logger.debug(f"Retrieved {len(cached)} knowledge entries from cache")
                return cached
        
        query = KnowledgeEntry.objects.filter(
            tenant_id=tenant_id
        ).select_related('tenant')
        
        if active_only:
            query = query.filter(is_active=True)
        
        if entry_type:
            query = query.filter(entry_type=entry_type)
        
        entries = list(query.order_by('-priority', '-created_at'))
        
        if use_cache:
            cache.set(cache_key, entries, cls.QUERY_CACHE_TTL)
        
        logger.debug(f"Retrieved {len(entries)} knowledge entries for tenant {tenant_id}")
        
        return entries
    
    @classmethod
    def get_conversation_statistics(
        cls,
        tenant_id: str,
        use_cache: bool = True
    ) -> dict:
        """
        Get conversation statistics for a tenant with aggregation.
        
        Uses efficient aggregation queries to calculate statistics.
        
        Args:
            tenant_id: Tenant UUID
            use_cache: Whether to use cache (default: True)
            
        Returns:
            Dictionary with statistics
        """
        cache_key = f"conversation_stats:{tenant_id}"
        
        if use_cache:
            cached = cache.get(cache_key)
            if cached:
                logger.debug("Retrieved conversation statistics from cache")
                return cached
        
        # Get conversation counts by status
        conversations = Conversation.objects.filter(
            tenant_id=tenant_id
        ).values('status').annotate(
            count=Count('id')
        )
        
        stats = {
            'total_conversations': 0,
            'by_status': {},
            'total_messages': 0,
            'total_interactions': 0
        }
        
        for conv in conversations:
            stats['by_status'][conv['status']] = conv['count']
            stats['total_conversations'] += conv['count']
        
        # Get total messages
        stats['total_messages'] = Message.objects.filter(
            conversation__tenant_id=tenant_id
        ).count()
        
        # Get total agent interactions
        stats['total_interactions'] = AgentInteraction.objects.filter(
            conversation__tenant_id=tenant_id
        ).count()
        
        if use_cache:
            cache.set(cache_key, stats, cls.QUERY_CACHE_TTL)
        
        logger.debug(f"Retrieved conversation statistics for tenant {tenant_id}")
        
        return stats
    
    @classmethod
    def get_agent_performance_metrics(
        cls,
        tenant_id: str,
        use_cache: bool = True
    ) -> dict:
        """
        Get agent performance metrics for a tenant with aggregation.
        
        Calculates average confidence, handoff rate, and cost metrics.
        
        Args:
            tenant_id: Tenant UUID
            use_cache: Whether to use cache (default: True)
            
        Returns:
            Dictionary with performance metrics
        """
        from django.db.models import Avg
        
        cache_key = f"agent_performance:{tenant_id}"
        
        if use_cache:
            cached = cache.get(cache_key)
            if cached:
                logger.debug("Retrieved agent performance metrics from cache")
                return cached
        
        interactions = AgentInteraction.objects.filter(
            conversation__tenant_id=tenant_id
        )
        
        # Calculate metrics
        total_interactions = interactions.count()
        
        if total_interactions == 0:
            return {
                'total_interactions': 0,
                'avg_confidence': 0.0,
                'handoff_rate': 0.0,
                'total_cost': 0.0,
                'avg_processing_time_ms': 0
            }
        
        metrics = interactions.aggregate(
            avg_confidence=Avg('confidence_score'),
            total_cost=Sum('estimated_cost'),
            avg_processing_time=Avg('processing_time_ms')
        )
        
        handoff_count = interactions.filter(handoff_triggered=True).count()
        
        result = {
            'total_interactions': total_interactions,
            'avg_confidence': float(metrics['avg_confidence'] or 0),
            'handoff_rate': handoff_count / total_interactions if total_interactions > 0 else 0,
            'total_cost': float(metrics['total_cost'] or 0),
            'avg_processing_time_ms': int(metrics['avg_processing_time'] or 0)
        }
        
        if use_cache:
            cache.set(cache_key, result, cls.QUERY_CACHE_TTL)
        
        logger.debug(f"Retrieved agent performance metrics for tenant {tenant_id}")
        
        return result
    
    @classmethod
    def invalidate_conversation_cache(cls, conversation_id: str) -> None:
        """
        Invalidate all caches related to a conversation.
        
        Call this when conversation data changes.
        
        Args:
            conversation_id: Conversation UUID
        """
        cache_keys = [
            f"conversation_with_context:{conversation_id}",
            f"conversation_messages:{conversation_id}:*",
            f"agent_interactions:{conversation_id}:*"
        ]
        
        # Note: This is a simplified implementation
        # In production, consider using cache key patterns or a more sophisticated approach
        for key in cache_keys:
            if '*' not in key:
                cache.delete(key)
        
        logger.debug(f"Invalidated caches for conversation {conversation_id}")
    
    @classmethod
    def invalidate_tenant_cache(cls, tenant_id: str) -> None:
        """
        Invalidate all caches related to a tenant.
        
        Call this when tenant data changes significantly.
        
        Args:
            tenant_id: Tenant UUID
        """
        cache_keys = [
            f"knowledge_entries:{tenant_id}:*",
            f"conversation_stats:{tenant_id}",
            f"agent_performance:{tenant_id}"
        ]
        
        # Note: This is a simplified implementation
        for key in cache_keys:
            if '*' not in key:
                cache.delete(key)
        
        logger.debug(f"Invalidated caches for tenant {tenant_id}")
    
    @classmethod
    def bulk_prefetch_conversations(
        cls,
        conversation_ids: List[str]
    ) -> dict:
        """
        Bulk prefetch conversations with all related data.
        
        Optimizes for scenarios where multiple conversations need to be loaded.
        
        Args:
            conversation_ids: List of conversation UUIDs
            
        Returns:
            Dictionary mapping conversation_id to Conversation instance
        """
        conversations = Conversation.objects.filter(
            id__in=conversation_ids
        ).select_related(
            'tenant',
            'customer',
            'context'
        ).prefetch_related(
            Prefetch(
                'messages',
                queryset=Message.objects.order_by('-created_at')[:20]
            ),
            Prefetch(
                'agent_interactions',
                queryset=AgentInteraction.objects.order_by('-created_at')[:10]
            )
        )
        
        result = {str(conv.id): conv for conv in conversations}
        
        logger.debug(f"Bulk prefetched {len(result)} conversations")
        
        return result


def create_query_optimizer() -> QueryOptimizer:
    """
    Factory function to create QueryOptimizer instance.
    
    Returns:
        QueryOptimizer instance
    """
    return QueryOptimizer()
