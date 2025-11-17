"""
Tests for ContextBuilderService.

Tests context assembly from multiple sources including conversation history,
knowledge base, catalog data, and customer history.
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

from apps.bot.services.context_builder_service import (
    ContextBuilderService,
    AgentContext,
    CatalogContext,
    CustomerHistory,
    create_context_builder_service
)
from apps.bot.models import KnowledgeEntry, ConversationContext
from apps.messaging.models import Message, Conversation
from apps.catalog.models import Product
from apps.services.models import Service
from apps.orders.models import Order
from apps.tenants.models import Tenant, Customer


@pytest.fixture
def tenant(db):
    """Create test tenant."""
    return Tenant.objects.create(
        name="Test Business",
        slug="test-business",
        status="active"
    )


@pytest.fixture
def customer(db, tenant):
    """Create test customer."""
    return Customer.objects.create(
        tenant=tenant,
        phone_e164="+1234567890",
        name="Test Customer"
    )


@pytest.fixture
def conversation(db, tenant, customer):
    """Create test conversation."""
    return Conversation.objects.create(
        tenant=tenant,
        customer=customer,
        status="active"
    )


@pytest.fixture
def messages(db, conversation):
    """Create test messages."""
    return [
        Message.objects.create(
            conversation=conversation,
            direction='in',
            text="Hello, I'm looking for a blue shirt"
        ),
        Message.objects.create(
            conversation=conversation,
            direction='out',
            text="I can help you with that! We have several blue shirts available."
        ),
        Message.objects.create(
            conversation=conversation,
            direction='in',
            text="What sizes do you have?"
        ),
    ]


@pytest.fixture
def products(db, tenant):
    """Create test products."""
    return [
        Product.objects.create(
            tenant=tenant,
            title="Blue Shirt",
            description="Comfortable cotton shirt",
            price=Decimal('29.99'),
            stock=10,
            is_active=True
        ),
        Product.objects.create(
            tenant=tenant,
            title="Red Shirt",
            description="Stylish red shirt",
            price=Decimal('34.99'),
            stock=5,
            is_active=True
        ),
    ]


@pytest.fixture
def services(db, tenant):
    """Create test services."""
    return [
        Service.objects.create(
            tenant=tenant,
            title="Haircut",
            description="Professional haircut",
            is_active=True
        ),
        Service.objects.create(
            tenant=tenant,
            title="Hair Coloring",
            description="Professional hair coloring",
            is_active=True
        ),
    ]


@pytest.fixture
def knowledge_entries(db, tenant):
    """Create test knowledge entries."""
    return [
        KnowledgeEntry.objects.create(
            tenant=tenant,
            entry_type='faq',
            title="Shipping Policy",
            content="We offer free shipping on orders over $50",
            is_active=True
        ),
        KnowledgeEntry.objects.create(
            tenant=tenant,
            entry_type='policy',
            title="Return Policy",
            content="Returns accepted within 30 days",
            is_active=True
        ),
    ]


@pytest.fixture
def context_builder():
    """Create ContextBuilderService instance."""
    return ContextBuilderService()


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test."""
    cache.clear()
    yield
    cache.clear()


class TestContextBuilderInitialization:
    """Test ContextBuilderService initialization."""
    
    def test_initialization_default(self):
        """Test default initialization."""
        service = ContextBuilderService()
        
        assert service.knowledge_service is not None
        assert service.fuzzy_matcher is not None
        assert service.catalog_cache is not None
    
    def test_initialization_with_dependencies(self):
        """Test initialization with custom dependencies."""
        mock_knowledge = Mock()
        mock_fuzzy = Mock()
        mock_cache = Mock()
        
        service = ContextBuilderService(
            knowledge_service=mock_knowledge,
            fuzzy_matcher=mock_fuzzy,
            catalog_cache=mock_cache
        )
        
        assert service.knowledge_service == mock_knowledge
        assert service.fuzzy_matcher == mock_fuzzy
        assert service.catalog_cache == mock_cache
    
    def test_factory_function(self):
        """Test factory function."""
        service = create_context_builder_service()
        
        assert isinstance(service, ContextBuilderService)


class TestBuildContext:
    """Test main build_context method."""
    
    def test_build_context_basic(
        self,
        context_builder,
        conversation,
        messages,
        tenant
    ):
        """Test basic context building."""
        context = context_builder.build_context(
            conversation=conversation,
            message=messages[0],
            tenant=tenant
        )
        
        assert isinstance(context, AgentContext)
        assert context.conversation == conversation
        assert context.current_message == messages[0]
        assert context.context is not None
        assert isinstance(context.catalog_context, CatalogContext)
        assert isinstance(context.customer_history, CustomerHistory)
    
    def test_build_context_with_history(
        self,
        context_builder,
        conversation,
        messages,
        tenant
    ):
        """Test context building includes conversation history."""
        context = context_builder.build_context(
            conversation=conversation,
            message=messages[-1],
            tenant=tenant
        )
        
        assert len(context.conversation_history) > 0
        assert messages[0] in context.conversation_history
    
    def test_build_context_estimates_size(
        self,
        context_builder,
        conversation,
        messages,
        tenant
    ):
        """Test context size estimation."""
        context = context_builder.build_context(
            conversation=conversation,
            message=messages[0],
            tenant=tenant
        )
        
        assert context.context_size_tokens > 0
    
    def test_build_context_with_max_tokens(
        self,
        context_builder,
        conversation,
        messages,
        tenant
    ):
        """Test context truncation with max_tokens."""
        # Build large context
        for i in range(30):
            Message.objects.create(
                conversation=conversation,
                direction='in',
                text=f"This is message number {i} with some content"
            )
        
        context = context_builder.build_context(
            conversation=conversation,
            message=messages[0],
            tenant=tenant,
            max_tokens=100
        )
        
        assert context.truncated is True
        assert context.context_size_tokens <= 100


class TestConversationHistory:
    """Test conversation history retrieval."""
    
    def test_get_conversation_history_basic(
        self,
        context_builder,
        conversation,
        messages
    ):
        """Test basic history retrieval."""
        history = context_builder.get_conversation_history(conversation)
        
        assert len(history) == len(messages)
        assert all(isinstance(msg, Message) for msg in history)
        # Should be in chronological order
        assert history[0].created_at <= history[-1].created_at
    
    def test_get_conversation_history_limit(
        self,
        context_builder,
        conversation
    ):
        """Test history retrieval with limit."""
        # Create many messages
        for i in range(30):
            Message.objects.create(
                conversation=conversation,
                direction='in',
                text=f"Message {i}"
            )
        
        history = context_builder.get_conversation_history(
            conversation,
            max_messages=10
        )
        
        assert len(history) == 10
        # Should get most recent messages
        all_messages = Message.objects.filter(
            conversation=conversation
        ).order_by('-created_at')[:10]
        assert set(msg.id for msg in history) == set(msg.id for msg in all_messages)
    
    def test_get_conversation_history_with_summary(
        self,
        context_builder,
        conversation
    ):
        """Test history retrieval uses summary for old messages."""
        # Create many messages
        for i in range(30):
            Message.objects.create(
                conversation=conversation,
                direction='in',
                text=f"Message {i}"
            )
        
        # Create context with summary
        ConversationContext.objects.create(
            conversation=conversation,
            conversation_summary="Customer was asking about products"
        )
        
        history = context_builder.get_conversation_history(
            conversation,
            max_messages=10,
            use_summary=True
        )
        
        # Should return only recent messages when summary exists
        assert len(history) == 10


class TestKnowledgeRetrieval:
    """Test knowledge base retrieval."""
    
    def test_get_relevant_knowledge(
        self,
        context_builder,
        tenant,
        knowledge_entries
    ):
        """Test knowledge retrieval."""
        with patch.object(
            context_builder.knowledge_service,
            'search',
            return_value=[(knowledge_entries[0], 0.9)]
        ):
            results = context_builder.get_relevant_knowledge(
                query="What is your shipping policy?",
                tenant=tenant
            )
            
            assert len(results) > 0
            assert isinstance(results[0], tuple)
            entry, score = results[0]
            assert isinstance(entry, KnowledgeEntry)
            assert isinstance(score, float)
    
    def test_get_relevant_knowledge_with_types(
        self,
        context_builder,
        tenant
    ):
        """Test knowledge retrieval with entry type filter."""
        with patch.object(
            context_builder.knowledge_service,
            'search',
            return_value=[]
        ) as mock_search:
            context_builder.get_relevant_knowledge(
                query="test",
                tenant=tenant,
                entry_types=['faq', 'policy']
            )
            
            mock_search.assert_called_once()
            call_args = mock_search.call_args[1]
            assert call_args['entry_types'] == ['faq', 'policy']
    
    def test_get_relevant_knowledge_error_handling(
        self,
        context_builder,
        tenant
    ):
        """Test knowledge retrieval handles errors gracefully."""
        with patch.object(
            context_builder.knowledge_service,
            'search',
            side_effect=Exception("Search failed")
        ):
            results = context_builder.get_relevant_knowledge(
                query="test",
                tenant=tenant
            )
            
            # Should return empty list on error
            assert results == []


class TestCatalogContext:
    """Test catalog context retrieval."""
    
    def test_get_catalog_context_all(
        self,
        context_builder,
        tenant,
        products,
        services
    ):
        """Test getting all catalog items."""
        with patch.object(
            context_builder.catalog_cache,
            'get_products',
            return_value=products
        ), patch.object(
            context_builder.catalog_cache,
            'get_services',
            return_value=services
        ):
            catalog = context_builder.get_catalog_context(tenant)
            
            assert isinstance(catalog, CatalogContext)
            assert len(catalog.products) > 0
            assert len(catalog.services) > 0
            assert catalog.total_products == len(products)
            assert catalog.total_services == len(services)
    
    def test_get_catalog_context_with_query(
        self,
        context_builder,
        tenant,
        products
    ):
        """Test catalog retrieval with search query."""
        catalog = context_builder.get_catalog_context(
            tenant,
            query="blue"
        )
        
        assert isinstance(catalog, CatalogContext)
        # Should find blue shirt
        assert any('Blue' in p.title for p in catalog.products)
    
    def test_get_catalog_context_fuzzy_matching(
        self,
        context_builder,
        tenant,
        products
    ):
        """Test catalog uses fuzzy matching for poor exact matches."""
        with patch.object(
            context_builder.fuzzy_matcher,
            'match_product',
            return_value=[(products[0], 0.8)]
        ) as mock_fuzzy:
            catalog = context_builder.get_catalog_context(
                tenant,
                query="blu shrt"  # Typo
            )
            
            # Should call fuzzy matcher
            mock_fuzzy.assert_called()
    
    def test_get_catalog_context_caching(
        self,
        context_builder,
        tenant,
        products
    ):
        """Test catalog context is cached."""
        with patch.object(
            context_builder.catalog_cache,
            'get_products',
            return_value=products
        ) as mock_get:
            # First call
            catalog1 = context_builder.get_catalog_context(tenant)
            
            # Second call should use cache
            catalog2 = context_builder.get_catalog_context(tenant)
            
            # Should only call once (first time)
            assert mock_get.call_count == 1


class TestCustomerHistory:
    """Test customer history retrieval."""
    
    def test_get_customer_history(
        self,
        context_builder,
        customer,
        tenant
    ):
        """Test customer history retrieval."""
        # Create orders
        Order.objects.create(
            tenant=tenant,
            customer=customer,
            status='completed',
            total_amount=Decimal('100.00')
        )
        Order.objects.create(
            tenant=tenant,
            customer=customer,
            status='paid',
            total_amount=Decimal('50.00')
        )
        
        history = context_builder.get_customer_history(customer, tenant)
        
        assert isinstance(history, CustomerHistory)
        assert len(history.orders) > 0
        assert history.total_orders == 2
        assert history.total_spent == 150.0
    
    def test_get_customer_history_limit(
        self,
        context_builder,
        customer,
        tenant
    ):
        """Test customer history respects limit."""
        # Create many orders
        for i in range(10):
            Order.objects.create(
                tenant=tenant,
                customer=customer,
                status='completed',
                total_amount=Decimal('10.00')
            )
        
        history = context_builder.get_customer_history(
            customer,
            tenant,
            max_items=3
        )
        
        assert len(history.orders) == 3
        assert history.total_orders == 10
    
    def test_get_customer_history_caching(
        self,
        context_builder,
        customer,
        tenant
    ):
        """Test customer history is cached."""
        # First call
        history1 = context_builder.get_customer_history(customer, tenant)
        
        # Second call should use cache
        with patch('apps.orders.models.Order.objects.filter') as mock_filter:
            history2 = context_builder.get_customer_history(customer, tenant)
            
            # Should not query database
            mock_filter.assert_not_called()


class TestContextManagement:
    """Test conversation context management."""
    
    def test_get_or_create_context_new(
        self,
        context_builder,
        conversation
    ):
        """Test creating new conversation context."""
        context = context_builder._get_or_create_context(conversation)
        
        assert isinstance(context, ConversationContext)
        assert context.conversation == conversation
        assert context.context_expires_at is not None
    
    def test_get_or_create_context_existing(
        self,
        context_builder,
        conversation
    ):
        """Test retrieving existing context."""
        # Create context
        existing = ConversationContext.objects.create(
            conversation=conversation,
            current_topic="test"
        )
        
        context = context_builder._get_or_create_context(conversation)
        
        assert context.id == existing.id
        assert context.current_topic == "test"
    
    def test_get_or_create_context_expired(
        self,
        context_builder,
        conversation
    ):
        """Test expired context is cleared."""
        # Create expired context
        existing = ConversationContext.objects.create(
            conversation=conversation,
            current_topic="old_topic",
            context_expires_at=timezone.now() - timedelta(hours=1)
        )
        
        context = context_builder._get_or_create_context(conversation)
        
        # Should clear expired context
        assert context.current_topic == ""


class TestTokenEstimation:
    """Test token estimation and truncation."""
    
    def test_estimate_context_size(
        self,
        context_builder,
        conversation,
        messages,
        tenant
    ):
        """Test context size estimation."""
        context = AgentContext(
            conversation=conversation,
            current_message=messages[0],
            conversation_history=messages
        )
        
        tokens = context_builder._estimate_context_size(context)
        
        assert tokens > 0
        # Should be roughly text length / 4
        total_text = sum(len(msg.text) for msg in messages)
        expected_tokens = total_text // context_builder.CHARS_PER_TOKEN
        assert abs(tokens - expected_tokens) < 10
    
    def test_truncate_context(
        self,
        context_builder,
        conversation,
        messages,
        tenant,
        products
    ):
        """Test context truncation."""
        # Create large context
        context = AgentContext(
            conversation=conversation,
            current_message=messages[0],
            conversation_history=messages * 10,  # Many messages
            catalog_context=CatalogContext(products=products * 10)
        )
        
        context.context_size_tokens = 10000
        
        truncated = context_builder._truncate_context(context, max_tokens=500)
        
        assert truncated.context_size_tokens < 10000
        # Should keep recent messages
        assert len(truncated.conversation_history) <= 5
        # Should reduce catalog items
        assert len(truncated.catalog_context.products) <= 5


class TestAgentContextDataClass:
    """Test AgentContext data class."""
    
    def test_agent_context_creation(self, conversation, messages):
        """Test creating AgentContext."""
        context = AgentContext(
            conversation=conversation,
            current_message=messages[0]
        )
        
        assert context.conversation == conversation
        assert context.current_message == messages[0]
        assert context.conversation_history == []
        assert context.context is None
    
    def test_agent_context_to_dict(self, conversation, messages):
        """Test converting AgentContext to dictionary."""
        context = AgentContext(
            conversation=conversation,
            current_message=messages[0],
            conversation_history=messages,
            context_size_tokens=100
        )
        
        data = context.to_dict()
        
        assert 'conversation_id' in data
        assert 'customer_id' in data
        assert 'current_message' in data
        assert data['history_count'] == len(messages)
        assert data['context_size_tokens'] == 100


class TestCatalogContextDataClass:
    """Test CatalogContext data class."""
    
    def test_catalog_context_creation(self, products, services):
        """Test creating CatalogContext."""
        catalog = CatalogContext(
            products=products,
            services=services,
            total_products=len(products),
            total_services=len(services)
        )
        
        assert len(catalog.products) == len(products)
        assert len(catalog.services) == len(services)
        assert catalog.total_products == len(products)
        assert catalog.total_services == len(services)


class TestCustomerHistoryDataClass:
    """Test CustomerHistory data class."""
    
    def test_customer_history_creation(self):
        """Test creating CustomerHistory."""
        history = CustomerHistory(
            total_orders=5,
            total_appointments=3,
            total_spent=250.0
        )
        
        assert history.total_orders == 5
        assert history.total_appointments == 3
        assert history.total_spent == 250.0
        assert history.orders == []
        assert history.appointments == []
