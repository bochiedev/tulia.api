"""
Integration tests for AI-powered customer service agent.

Tests end-to-end message flow, knowledge base search accuracy,
conversation memory retention, multi-tenant isolation, and rich message delivery.

Requirements: All (comprehensive integration testing)
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from django.utils import timezone
from datetime import timedelta

from apps.tenants.models import Tenant, Customer, SubscriptionTier
from apps.messaging.models import Conversation, Message
from apps.catalog.models import Product
from apps.services.models import Service
from apps.orders.models import Order
from apps.bot.models import (
    AgentConfiguration,
    KnowledgeEntry,
    ConversationContext,
    AgentInteraction
)


@pytest.fixture
def subscription_tier(db):
    """Create subscription tier."""
    return SubscriptionTier.objects.create(
        name='Test Tier',
        monthly_price=29.00,
        yearly_price=278.00
    )


@pytest.fixture
def tenant_a(db, subscription_tier):
    """Create first test tenant."""
    return Tenant.objects.create(
        name="Tenant A",
        slug="tenant-a",
        whatsapp_number="+1111111111",
        status="active",
        subscription_tier=subscription_tier
    )


@pytest.fixture
def tenant_b(db, subscription_tier):
    """Create second test tenant."""
    return Tenant.objects.create(
        name="Tenant B",
        slug="tenant-b",
        whatsapp_number="+2222222222",
        status="active",
        subscription_tier=subscription_tier
    )


@pytest.fixture
def customer_a(db, tenant_a):
    """Create customer for tenant A."""
    return Customer.objects.create(
        tenant=tenant_a,
        phone_e164="+1234567890",
        name="Customer A"
    )


@pytest.fixture
def customer_b(db, tenant_b):
    """Create customer for tenant B."""
    return Customer.objects.create(
        tenant=tenant_b,
        phone_e164="+0987654321",
        name="Customer B"
    )


@pytest.fixture
def conversation_a(db, tenant_a, customer_a):
    """Create conversation for tenant A."""
    return Conversation.objects.create(
        tenant=tenant_a,
        customer=customer_a,
        status="bot",
        channel="whatsapp"
    )


@pytest.fixture
def conversation_b(db, tenant_b, customer_b):
    """Create conversation for tenant B."""
    return Conversation.objects.create(
        tenant=tenant_b,
        customer=customer_b,
        status="bot",
        channel="whatsapp"
    )


@pytest.mark.django_db
class TestKnowledgeBaseSearchAccuracy:
    """Test knowledge base search accuracy and relevance."""
    
    def test_semantic_search_finds_relevant_entries(self, tenant_a):
        """Test that semantic search finds relevant knowledge entries."""
        from apps.bot.services.knowledge_base_service import KnowledgeBaseService
        
        # Mock OpenAI client
        with patch('apps.bot.services.knowledge_base_service.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
            mock_client.embeddings.create.return_value = mock_response
            mock_openai.return_value = mock_client
            
            kb_service = KnowledgeBaseService(api_key='test-key')
            
            # Create knowledge entries
            shipping_entry = kb_service.create_entry(
                tenant=tenant_a,
                entry_type='faq',
                title='Shipping Information',
                content='We ship worldwide in 3-5 business days.',
                keywords=['shipping', 'delivery']
            )
            
            # Search for shipping-related query
            results = kb_service.search(
                tenant=tenant_a,
                query='How long does delivery take?',
                limit=5,
                min_similarity=0.0
            )
            
            # Should find shipping entry
            assert len(results) > 0
            entry_ids = [entry.id for entry, score in results]
            assert shipping_entry.id in entry_ids


@pytest.mark.django_db
class TestConversationMemoryRetention:
    """Test conversation memory retention across messages."""
    
    def test_conversation_history_is_retained(self, tenant_a, customer_a, conversation_a):
        """Test that conversation history is maintained."""
        # Create multiple messages
        messages = []
        for i in range(5):
            msg = Message.objects.create(
                conversation=conversation_a,
                direction='in' if i % 2 == 0 else 'out',
                message_type='customer_inbound' if i % 2 == 0 else 'bot_response',
                text=f"Message {i}"
            )
            messages.append(msg)
        
        # Build context
        from apps.bot.services.context_builder_service import ContextBuilderService
        
        context_builder = ContextBuilderService()
        context = context_builder.build_context(
            conversation=conversation_a,
            message=messages[-1],
            tenant=tenant_a
        )
        
        # Verify history is included
        assert len(context.conversation_history) > 0
        assert messages[0] in context.conversation_history


@pytest.mark.django_db
class TestMultiTenantIsolation:
    """Test strict multi-tenant data isolation."""
    
    def test_knowledge_base_isolation(self, tenant_a, tenant_b):
        """Test that knowledge base entries are isolated by tenant."""
        from apps.bot.services.knowledge_base_service import KnowledgeBaseService
        
        # Mock OpenAI client
        with patch('apps.bot.services.knowledge_base_service.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
            mock_client.embeddings.create.return_value = mock_response
            mock_openai.return_value = mock_client
            
            kb_service = KnowledgeBaseService(api_key='test-key')
            
            # Create entries for each tenant
            entry_a = kb_service.create_entry(
                tenant=tenant_a,
                entry_type='faq',
                title='Tenant A FAQ',
                content='Tenant A specific information'
            )
            
            entry_b = kb_service.create_entry(
                tenant=tenant_b,
                entry_type='faq',
                title='Tenant B FAQ',
                content='Tenant B specific information'
            )
            
            # Search for Tenant A should only return Tenant A entries
            results_a = kb_service.search(
                tenant=tenant_a,
                query='FAQ',
                min_similarity=0.0
            )
            
            entry_ids_a = [entry.id for entry, score in results_a]
            assert entry_a.id in entry_ids_a
            assert entry_b.id not in entry_ids_a


@pytest.mark.django_db
class TestRichMessageDelivery:
    """Test rich WhatsApp message delivery."""
    
    def test_product_card_generation(self, tenant_a):
        """Test generating product card with image and buttons."""
        from apps.bot.services.rich_message_builder import RichMessageBuilder
        
        # Create product
        product = Product.objects.create(
            tenant=tenant_a,
            title="Blue Shirt",
            description="Comfortable cotton shirt",
            price=Decimal('29.99'),
            is_active=True
        )
        
        # Build product card
        builder = RichMessageBuilder()
        rich_message = builder.build_product_card(
            product=product,
            actions=['buy', 'details']
        )
        
        # Verify message structure
        assert rich_message is not None
        assert rich_message.message_type in ['button', 'list']
        assert 'Blue Shirt' in rich_message.body


@pytest.mark.django_db
class TestEndToEndFlow:
    """Test end-to-end message processing flow."""
    
    def test_context_building_integration(self, tenant_a, customer_a, conversation_a):
        """Test that context builder integrates all data sources."""
        # Create test data
        product = Product.objects.create(
            tenant=tenant_a,
            title="Test Product",
            price=Decimal('10.00'),
            is_active=True
        )
        
        order = Order.objects.create(
            tenant=tenant_a,
            customer=customer_a,
            status='paid',
            currency='USD',
            subtotal=Decimal('100.00'),
            total=Decimal('100.00')
        )
        
        message = Message.objects.create(
            conversation=conversation_a,
            direction='in',
            message_type='customer_inbound',
            text="What products do you have?"
        )
        
        # Build context
        from apps.bot.services.context_builder_service import ContextBuilderService
        
        context_builder = ContextBuilderService()
        context = context_builder.build_context(
            conversation=conversation_a,
            message=message,
            tenant=tenant_a
        )
        
        # Verify all components are present
        assert context.conversation is not None
        assert context.current_message is not None
        assert context.customer_history is not None
        assert context.customer_history.total_orders > 0
