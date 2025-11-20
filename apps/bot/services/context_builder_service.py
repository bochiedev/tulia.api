"""
Context Builder Service for assembling AI agent context.

Orchestrates context assembly from multiple sources including conversation history,
knowledge base, catalog data, and customer history for comprehensive AI agent context.
"""
import logging
from typing import List, Optional, Dict, Any, NamedTuple
from dataclasses import dataclass, field
from django.core.cache import cache
from django.db.models import Q, Prefetch
from django.utils import timezone

from apps.messaging.models import Message, Conversation
from apps.bot.models import KnowledgeEntry, ConversationContext
from apps.catalog.models import Product
from apps.services.models import Service
from apps.orders.models import Order
from apps.services.models import Appointment
from apps.bot.services.knowledge_base_service import KnowledgeBaseService
from apps.bot.services.fuzzy_matcher_service import FuzzyMatcherService
from apps.bot.services.catalog_cache_service import CatalogCacheService

logger = logging.getLogger(__name__)


@dataclass
class CatalogContext:
    """Container for catalog context data."""
    products: List[Product] = field(default_factory=list)
    services: List[Service] = field(default_factory=list)
    total_products: int = 0
    total_services: int = 0


@dataclass
class CustomerHistory:
    """Container for customer history data."""
    orders: List[Order] = field(default_factory=list)
    appointments: List[Appointment] = field(default_factory=list)
    total_orders: int = 0
    total_appointments: int = 0
    total_spent: float = 0.0


@dataclass
class AgentContext:
    """
    Complete context for AI agent processing.
    
    Contains all information needed for the agent to generate
    contextually aware responses.
    """
    # Conversation data
    conversation: Conversation
    current_message: Message
    conversation_history: List[Message] = field(default_factory=list)
    
    # Context state
    context: Optional[ConversationContext] = None
    
    # Knowledge and catalog
    relevant_knowledge: List[tuple] = field(default_factory=list)  # List of (KnowledgeEntry, score)
    catalog_context: CatalogContext = field(default_factory=CatalogContext)
    
    # Customer data
    customer_history: CustomerHistory = field(default_factory=CustomerHistory)
    
    # Last viewed items (for quick reference)
    last_product_viewed: Optional[Any] = None
    last_service_viewed: Optional[Any] = None
    
    # Metadata
    context_size_tokens: int = 0
    truncated: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for serialization."""
        return {
            'conversation_id': str(self.conversation.id),
            'customer_id': str(self.conversation.customer.id),
            'current_message': self.current_message.text,
            'history_count': len(self.conversation_history),
            'knowledge_count': len(self.relevant_knowledge),
            'products_count': len(self.catalog_context.products),
            'services_count': len(self.catalog_context.services),
            'orders_count': len(self.customer_history.orders),
            'appointments_count': len(self.customer_history.appointments),
            'context_size_tokens': self.context_size_tokens,
            'truncated': self.truncated,
        }


class ContextBuilderService:
    """
    Service for building comprehensive AI agent context.
    
    Orchestrates context assembly from multiple sources with intelligent
    prioritization and truncation to fit within model context windows.
    """
    
    # Cache TTL in seconds
    CATALOG_CACHE_TTL = 60  # 1 minute for catalog data
    HISTORY_CACHE_TTL = 300  # 5 minutes for customer history
    
    # Context window management
    MAX_HISTORY_MESSAGES = 20  # Maximum conversation history messages
    MAX_KNOWLEDGE_ENTRIES = 5  # Maximum knowledge base entries
    MAX_CATALOG_ITEMS = 10  # Maximum catalog items per type
    MAX_HISTORY_ITEMS = 5  # Maximum orders/appointments
    
    # Token estimation (rough approximation: 1 token ≈ 4 characters)
    CHARS_PER_TOKEN = 4
    
    def __init__(
        self,
        knowledge_service: Optional[KnowledgeBaseService] = None,
        fuzzy_matcher: Optional[FuzzyMatcherService] = None,
        catalog_cache: Optional[CatalogCacheService] = None
    ):
        """
        Initialize Context Builder Service.
        
        Args:
            knowledge_service: Optional KnowledgeBaseService instance
            fuzzy_matcher: Optional FuzzyMatcherService instance
            catalog_cache: Optional CatalogCacheService instance
        """
        self.knowledge_service = knowledge_service or KnowledgeBaseService()
        self.fuzzy_matcher = fuzzy_matcher or FuzzyMatcherService()
        self.catalog_cache = catalog_cache or CatalogCacheService()
    
    def build_context(
        self,
        conversation: Conversation,
        message: Message,
        tenant,
        max_tokens: Optional[int] = None
    ) -> AgentContext:
        """
        Build comprehensive context for AI agent.
        
        Orchestrates all context sources and assembles them into a unified
        AgentContext object with intelligent prioritization.
        
        Args:
            conversation: Conversation instance
            message: Current message being processed
            tenant: Tenant instance
            max_tokens: Optional maximum context size in tokens
            
        Returns:
            AgentContext with all assembled context data
        """
        logger.info(
            f"Building context for conversation {conversation.id}, "
            f"message: '{message.text[:50]}...'"
        )
        
        # Initialize context
        context = AgentContext(
            conversation=conversation,
            current_message=message
        )
        
        # Get or create conversation context
        context.context = self._get_or_create_context(conversation)
        
        # Populate last viewed items from conversation context
        if context.context:
            context.last_product_viewed = context.context.last_product_viewed
            context.last_service_viewed = context.context.last_service_viewed
        
        # Build context from all sources
        context.conversation_history = self.get_conversation_history(
            conversation,
            max_messages=self.MAX_HISTORY_MESSAGES
        )
        
        context.relevant_knowledge = self.get_relevant_knowledge(
            message.text,
            tenant,
            limit=self.MAX_KNOWLEDGE_ENTRIES
        )
        
        context.catalog_context = self.get_catalog_context(
            tenant,
            query=message.text
        )
        
        context.customer_history = self.get_customer_history(
            conversation.customer,
            tenant
        )
        
        # Estimate context size
        context.context_size_tokens = self._estimate_context_size(context)
        
        # Apply truncation if needed
        if max_tokens and context.context_size_tokens > max_tokens:
            context = self._truncate_context(context, max_tokens)
            context.truncated = True
        
        logger.info(
            f"Context built: {context.context_size_tokens} tokens, "
            f"truncated={context.truncated}"
        )
        
        return context
    
    def get_conversation_history(
        self,
        conversation: Conversation,
        max_messages: int = 20,
        use_summary: bool = True
    ) -> List[Message]:
        """
        Retrieve conversation history with intelligent truncation.
        
        Returns recent messages prioritizing:
        1. Most recent messages (always included)
        2. Messages with high importance (customer questions, bot responses)
        3. Messages with extracted entities or actions
        
        If conversation has many messages and a summary exists, uses summary
        for older messages and returns only recent full messages.
        
        Args:
            conversation: Conversation instance
            max_messages: Maximum number of messages to return
            use_summary: Whether to use summary for old messages
            
        Returns:
            List of Message instances ordered chronologically
        """
        # Get total message count
        total_messages = Message.objects.filter(
            conversation=conversation
        ).count()
        
        # If we have a summary and many messages, use it
        if use_summary and total_messages > max_messages:
            try:
                context = ConversationContext.objects.get(conversation=conversation)
                if context.conversation_summary:
                    logger.debug(
                        f"Using summary for conversation {conversation.id}: "
                        f"{total_messages} total messages, returning {max_messages} recent"
                    )
                    # Return only recent messages, summary will be used separately
                    messages = Message.objects.filter(
                        conversation=conversation
                    ).order_by('-created_at')[:max_messages]
                    
                    return list(reversed(messages))
            except ConversationContext.DoesNotExist:
                pass
        
        # Get recent messages
        messages = Message.objects.filter(
            conversation=conversation
        ).order_by('-created_at')[:max_messages]
        
        # Convert to list and reverse to chronological order
        messages = list(reversed(messages))
        
        logger.debug(
            f"Retrieved {len(messages)} messages for conversation {conversation.id}"
        )
        
        return messages
    
    def get_relevant_knowledge(
        self,
        query: str,
        tenant,
        entry_types: Optional[List[str]] = None,
        limit: int = 5
    ) -> List[tuple]:
        """
        Retrieve relevant knowledge base entries using semantic search.
        
        Uses the KnowledgeBaseService to perform semantic similarity search
        and returns the most relevant entries.
        
        Args:
            query: Search query (typically the customer's message)
            tenant: Tenant instance
            entry_types: Optional list of entry types to filter
            limit: Maximum number of entries to return
            
        Returns:
            List of tuples (KnowledgeEntry, similarity_score)
        """
        try:
            results = self.knowledge_service.search(
                tenant=tenant,
                query=query,
                entry_types=entry_types,
                limit=limit,
                min_similarity=0.7
            )
            
            logger.debug(
                f"Found {len(results)} relevant knowledge entries for query: "
                f"'{query[:50]}...'"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to retrieve knowledge entries: {e}")
            return []
    
    def get_catalog_context(
        self,
        tenant,
        query: Optional[str] = None,
        max_items: int = 10
    ) -> CatalogContext:
        """
        Get product and service catalog context.
        
        Returns relevant catalog items, optionally filtered by query.
        Uses fuzzy matching when exact matches fail or return few results.
        Uses caching for performance.
        
        Args:
            tenant: Tenant instance
            query: Optional search query to filter items
            max_items: Maximum items per type
            
        Returns:
            CatalogContext with products and services
        """
        cache_key = f"catalog_context:{tenant.id}:{query or 'all'}:{max_items}"
        cached = cache.get(cache_key)
        if cached:
            logger.debug("Returning cached catalog context")
            return cached
        
        catalog = CatalogContext()
        
        try:
            if query:
                # Try exact matching first
                products_query = Product.objects.filter(
                    tenant=tenant,
                    is_active=True
                ).filter(
                    Q(title__icontains=query) |
                    Q(description__icontains=query)
                )
                
                services_query = Service.objects.filter(
                    tenant=tenant,
                    is_active=True
                ).filter(
                    Q(title__icontains=query) |
                    Q(description__icontains=query)
                )
                
                exact_products = list(products_query[:max_items])
                exact_services = list(services_query[:max_items])
                
                # If exact matching returns few results, use fuzzy matching
                if len(exact_products) < 3:
                    logger.debug(
                        f"Exact product match returned {len(exact_products)} results, "
                        f"trying fuzzy matching"
                    )
                    fuzzy_results = self.fuzzy_matcher.match_product(
                        query=query,
                        tenant=tenant,
                        threshold=0.6,  # Lower threshold for broader matches
                        limit=max_items
                    )
                    
                    # Combine exact and fuzzy results, removing duplicates
                    exact_ids = {p.id for p in exact_products}
                    for product, confidence in fuzzy_results:
                        if product.id not in exact_ids:
                            exact_products.append(product)
                            if len(exact_products) >= max_items:
                                break
                    
                    logger.info(
                        f"Fuzzy product matching added {len(exact_products) - len(exact_ids)} "
                        f"additional matches"
                    )
                
                if len(exact_services) < 3:
                    logger.debug(
                        f"Exact service match returned {len(exact_services)} results, "
                        f"trying fuzzy matching"
                    )
                    fuzzy_results = self.fuzzy_matcher.match_service(
                        query=query,
                        tenant=tenant,
                        threshold=0.6,  # Lower threshold for broader matches
                        limit=max_items
                    )
                    
                    # Combine exact and fuzzy results, removing duplicates
                    exact_ids = {s.id for s in exact_services}
                    for service, confidence in fuzzy_results:
                        if service.id not in exact_ids:
                            exact_services.append(service)
                            if len(exact_services) >= max_items:
                                break
                    
                    logger.info(
                        f"Fuzzy service matching added {len(exact_services) - len(exact_ids)} "
                        f"additional matches"
                    )
                
                catalog.products = exact_products
                catalog.services = exact_services
                catalog.total_products = len(exact_products)
                catalog.total_services = len(exact_services)
                
            else:
                # No query - return all active items using cache
                all_products = self.catalog_cache.get_products(tenant, active_only=True)
                all_services = self.catalog_cache.get_services(tenant, active_only=True)
                
                catalog.total_products = len(all_products)
                catalog.products = all_products[:max_items]
                
                catalog.total_services = len(all_services)
                catalog.services = all_services[:max_items]
            
            logger.debug(
                f"Catalog context: {len(catalog.products)} products, "
                f"{len(catalog.services)} services"
            )
            
            # Cache the result
            cache.set(cache_key, catalog, self.CATALOG_CACHE_TTL)
            
        except Exception as e:
            logger.error(f"Failed to retrieve catalog context: {e}")
        
        return catalog
    
    def get_customer_history(
        self,
        customer,
        tenant,
        max_items: int = 5
    ) -> CustomerHistory:
        """
        Get customer order and appointment history.
        
        Returns recent orders and appointments for personalization.
        Uses caching for performance.
        
        Args:
            customer: Customer instance
            tenant: Tenant instance
            max_items: Maximum items per type
            
        Returns:
            CustomerHistory with orders and appointments
        """
        cache_key = f"customer_history:{tenant.id}:{customer.id}:{max_items}"
        cached = cache.get(cache_key)
        if cached:
            logger.debug("Returning cached customer history")
            return cached
        
        history = CustomerHistory()
        
        try:
            # Get recent orders
            orders = Order.objects.filter(
                tenant=tenant,
                customer=customer
            ).order_by('-created_at')[:max_items]
            
            history.orders = list(orders)
            history.total_orders = Order.objects.filter(
                tenant=tenant,
                customer=customer
            ).count()
            
            # Calculate total spent
            from django.db.models import Sum
            total = Order.objects.filter(
                tenant=tenant,
                customer=customer,
                status__in=['completed', 'paid']
            ).aggregate(total=Sum('total'))
            history.total_spent = float(total['total'] or 0)
            
            # Get recent appointments
            appointments = Appointment.objects.filter(
                tenant=tenant,
                customer=customer
            ).order_by('-created_at')[:max_items]
            
            history.appointments = list(appointments)
            history.total_appointments = Appointment.objects.filter(
                tenant=tenant,
                customer=customer
            ).count()
            
            logger.debug(
                f"Customer history: {len(history.orders)} orders, "
                f"{len(history.appointments)} appointments, "
                f"total_spent=${history.total_spent:.2f}"
            )
            
            # Cache the result
            cache.set(cache_key, history, self.HISTORY_CACHE_TTL)
            
        except Exception as e:
            logger.error(f"Failed to retrieve customer history: {e}")
        
        return history
    
    def _get_or_create_context(
        self,
        conversation: Conversation
    ) -> ConversationContext:
        """
        Get or create conversation context.
        
        Args:
            conversation: Conversation instance
            
        Returns:
            ConversationContext instance
        """
        try:
            context = ConversationContext.objects.get(conversation=conversation)
            
            # Extend expiration on access
            if context.is_expired():
                logger.info(f"Context expired for conversation {conversation.id}, clearing")
                context.clear_context(preserve_key_facts=True)
            
            context.extend_expiration(minutes=30)
            
        except ConversationContext.DoesNotExist:
            context = ConversationContext.objects.create(
                conversation=conversation
            )
            # Refresh to get the context_expires_at set by save()
            context.refresh_from_db()
            logger.info(f"Created new context for conversation {conversation.id}")
        
        return context
    
    def _estimate_context_size(self, context: AgentContext) -> int:
        """
        Estimate context size in tokens.
        
        Rough approximation: 1 token ≈ 4 characters
        
        Args:
            context: AgentContext instance
            
        Returns:
            Estimated token count
        """
        total_chars = 0
        
        # Current message
        total_chars += len(context.current_message.text)
        
        # Conversation history
        for msg in context.conversation_history:
            total_chars += len(msg.text)
        
        # Knowledge entries
        for entry, _ in context.relevant_knowledge:
            total_chars += len(entry.title) + len(entry.content)
        
        # Catalog items
        for product in context.catalog_context.products:
            total_chars += len(product.title)
            if product.description:
                total_chars += len(product.description)
        
        for service in context.catalog_context.services:
            total_chars += len(service.title)
            if service.description:
                total_chars += len(service.description)
        
        # Context state
        if context.context:
            if context.context.conversation_summary:
                total_chars += len(context.context.conversation_summary)
            for fact in context.context.key_facts:
                total_chars += len(str(fact))
        
        # Convert to tokens
        tokens = total_chars // self.CHARS_PER_TOKEN
        
        return tokens
    
    def _truncate_context(
        self,
        context: AgentContext,
        max_tokens: int
    ) -> AgentContext:
        """
        Truncate context to fit within token limit.
        
        Priority order:
        1. Current message (always included)
        2. Recent conversation history (last 5 messages)
        3. Relevant knowledge entries
        4. Catalog context
        5. Older conversation history
        6. Customer history
        
        Args:
            context: AgentContext to truncate
            max_tokens: Maximum token limit
            
        Returns:
            Truncated AgentContext
        """
        logger.info(
            f"Truncating context from {context.context_size_tokens} to {max_tokens} tokens"
        )
        
        # Start with essential items
        current_tokens = len(context.current_message.text) // self.CHARS_PER_TOKEN
        
        # Keep last 5 messages
        if len(context.conversation_history) > 5:
            context.conversation_history = context.conversation_history[-5:]
            logger.debug("Truncated conversation history to last 5 messages")
        
        # Reduce knowledge entries if needed
        if len(context.relevant_knowledge) > 3:
            context.relevant_knowledge = context.relevant_knowledge[:3]
            logger.debug("Truncated knowledge entries to top 3")
        
        # Reduce catalog items if needed
        if len(context.catalog_context.products) > 5:
            context.catalog_context.products = context.catalog_context.products[:5]
            logger.debug("Truncated products to top 5")
        
        if len(context.catalog_context.services) > 5:
            context.catalog_context.services = context.catalog_context.services[:5]
            logger.debug("Truncated services to top 5")
        
        # Clear customer history if still too large
        if self._estimate_context_size(context) > max_tokens:
            context.customer_history = CustomerHistory()
            logger.debug("Cleared customer history to reduce context size")
        
        # Recalculate size
        context.context_size_tokens = self._estimate_context_size(context)
        
        return context


def create_context_builder_service(
    knowledge_service: Optional[KnowledgeBaseService] = None
) -> ContextBuilderService:
    """
    Factory function to create ContextBuilderService instance.
    
    Args:
        knowledge_service: Optional KnowledgeBaseService instance
        
    Returns:
        ContextBuilderService instance
    """
    return ContextBuilderService(knowledge_service=knowledge_service)
