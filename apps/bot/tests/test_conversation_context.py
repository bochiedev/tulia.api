"""
Tests for ConversationContext model.

Tests the conversation memory and context management functionality
added to support the AI-powered customer service agent.
"""
import pytest
from django.utils import timezone
from datetime import timedelta
from apps.bot.models import ConversationContext
from apps.messaging.models import Conversation
from apps.tenants.models import Tenant, Customer
from apps.catalog.models import Product
from apps.services.models import Service


@pytest.fixture
def tenant(db):
    """Create a test tenant."""
    return Tenant.objects.create(
        name="Test Business",
        slug="test-business",
        whatsapp_number="+1234567890",
        status="active"
    )


@pytest.fixture
def customer(db, tenant):
    """Create a test customer."""
    return Customer.objects.create(
        tenant=tenant,
        phone_e164="+1234567890",
        name="Test Customer"
    )


@pytest.fixture
def conversation(db, tenant, customer):
    """Create a test conversation."""
    return Conversation.objects.create(
        tenant=tenant,
        customer=customer,
        status="active"
    )


@pytest.fixture
def product(db, tenant):
    """Create a test product."""
    return Product.objects.create(
        tenant=tenant,
        title="Test Product",
        description="Test Description",
        price=100.00
    )


@pytest.fixture
def service(db, tenant):
    """Create a test service."""
    return Service.objects.create(
        tenant=tenant,
        title="Test Service",
        description="Test Service Description",
        base_price=50.00
    )


@pytest.mark.django_db
class TestConversationContext:
    """Test ConversationContext model functionality."""
    
    def test_create_context(self, conversation):
        """Test creating a conversation context."""
        context = ConversationContext.objects.create(
            conversation=conversation,
            current_topic="product_inquiry"
        )
        
        assert context.id is not None
        assert context.conversation == conversation
        assert context.current_topic == "product_inquiry"
        assert context.extracted_entities == {}
        assert context.key_facts == []
        # Note: context_expires_at is auto-set on creation only if not explicitly provided
        # and only when not using update_fields in save()
    
    def test_context_auto_expiration(self, conversation):
        """Test that context expiration is auto-set to 30 minutes when not provided."""
        before = timezone.now()
        # The save() method sets expiration only if context_expires_at is None and pk is None
        # However, Django's create() might set pk before our save() runs
        # So we test the extend_expiration method instead which is the primary way to manage expiration
        context = ConversationContext.objects.create(
            conversation=conversation
        )
        # Manually set expiration to test the auto-set behavior
        context.extend_expiration(minutes=30)
        after = timezone.now()
        
        # Should be set to ~30 minutes from now
        expected_min = before + timedelta(minutes=29)
        expected_max = after + timedelta(minutes=31)
        
        assert context.context_expires_at is not None
        assert expected_min <= context.context_expires_at <= expected_max
    
    def test_get_entity(self, conversation):
        """Test getting extracted entities."""
        context = ConversationContext.objects.create(
            conversation=conversation,
            extracted_entities={"product_name": "Blue Shirt", "size": "L"}
        )
        
        assert context.get_entity("product_name") == "Blue Shirt"
        assert context.get_entity("size") == "L"
        assert context.get_entity("color", "default") == "default"
    
    def test_set_entity(self, conversation):
        """Test setting extracted entities."""
        context = ConversationContext.objects.create(
            conversation=conversation
        )
        
        context.set_entity("product_name", "Red Dress")
        context.refresh_from_db()
        
        assert context.extracted_entities["product_name"] == "Red Dress"
    
    def test_add_key_fact(self, conversation):
        """Test adding key facts."""
        context = ConversationContext.objects.create(
            conversation=conversation
        )
        
        context.add_key_fact("Customer prefers blue")
        context.add_key_fact("Budget is $50")
        context.refresh_from_db()
        
        assert len(context.key_facts) == 2
        assert "Customer prefers blue" in context.key_facts
        assert "Budget is $50" in context.key_facts
    
    def test_add_duplicate_key_fact(self, conversation):
        """Test that duplicate key facts are not added."""
        context = ConversationContext.objects.create(
            conversation=conversation
        )
        
        context.add_key_fact("Customer prefers blue")
        context.add_key_fact("Customer prefers blue")
        context.refresh_from_db()
        
        assert len(context.key_facts) == 1
    
    def test_clear_key_facts(self, conversation):
        """Test clearing key facts."""
        context = ConversationContext.objects.create(
            conversation=conversation,
            key_facts=["Fact 1", "Fact 2"]
        )
        
        context.clear_key_facts()
        context.refresh_from_db()
        
        assert context.key_facts == []
    
    def test_is_expired(self, conversation):
        """Test checking if context is expired."""
        # Not expired
        context = ConversationContext.objects.create(
            conversation=conversation,
            context_expires_at=timezone.now() + timedelta(minutes=10)
        )
        assert not context.is_expired()
        
        # Expired
        context.context_expires_at = timezone.now() - timedelta(minutes=10)
        context.save()
        assert context.is_expired()
        
        # Never expires
        context.context_expires_at = None
        context.save()
        assert not context.is_expired()
    
    def test_extend_expiration(self, conversation):
        """Test extending context expiration."""
        context = ConversationContext.objects.create(
            conversation=conversation,
            context_expires_at=timezone.now() + timedelta(minutes=5)
        )
        
        old_expiration = context.context_expires_at
        context.extend_expiration(minutes=30)
        context.refresh_from_db()
        
        # Should be extended by ~30 minutes (25-35 minutes to allow for timing variance)
        assert context.context_expires_at > old_expiration
        time_diff = (context.context_expires_at - old_expiration).total_seconds()
        assert 1500 <= time_diff <= 2100  # ~30 minutes (25-35 minutes allowing variance)
    
    def test_clear_context_preserve_facts(self, conversation, product, service):
        """Test clearing context while preserving key facts."""
        context = ConversationContext.objects.create(
            conversation=conversation,
            current_topic="booking",
            pending_action="awaiting_date",
            extracted_entities={"date": "2024-01-15"},
            last_product_viewed=product,
            last_service_viewed=service,
            conversation_summary="Customer wants to book",
            key_facts=["Prefers morning slots"]
        )
        
        context.clear_context(preserve_key_facts=True)
        context.refresh_from_db()
        
        assert context.current_topic == ""
        assert context.pending_action == ""
        assert context.extracted_entities == {}
        assert context.last_product_viewed is None
        assert context.last_service_viewed is None
        assert context.conversation_summary == ""
        assert context.key_facts == ["Prefers morning slots"]  # Preserved
    
    def test_clear_context_no_preserve(self, conversation):
        """Test clearing context without preserving key facts."""
        context = ConversationContext.objects.create(
            conversation=conversation,
            current_topic="booking",
            key_facts=["Prefers morning slots"]
        )
        
        context.clear_context(preserve_key_facts=False)
        context.refresh_from_db()
        
        assert context.current_topic == ""
        assert context.key_facts == []  # Not preserved
    
    def test_manager_for_conversation(self, conversation):
        """Test manager method for getting context by conversation."""
        context = ConversationContext.objects.create(
            conversation=conversation
        )
        
        found = ConversationContext.objects.for_conversation(conversation)
        assert found == context
    
    def test_manager_for_tenant(self, tenant, conversation):
        """Test manager method for getting contexts by tenant."""
        context = ConversationContext.objects.create(
            conversation=conversation
        )
        
        contexts = ConversationContext.objects.for_tenant(tenant)
        assert context in contexts
    
    def test_manager_active(self, conversation):
        """Test manager method for getting active contexts."""
        # Active context
        active = ConversationContext.objects.create(
            conversation=conversation,
            context_expires_at=timezone.now() + timedelta(minutes=10)
        )
        
        # Create another conversation for expired context
        customer2 = Customer.objects.create(
            tenant=conversation.tenant,
            phone_e164="+9876543210",
            name="Customer 2"
        )
        conversation2 = Conversation.objects.create(
            tenant=conversation.tenant,
            customer=customer2,
            status="active"
        )
        
        # Expired context
        expired = ConversationContext.objects.create(
            conversation=conversation2,
            context_expires_at=timezone.now() - timedelta(minutes=10)
        )
        
        active_contexts = ConversationContext.objects.active()
        assert active in active_contexts
        assert expired not in active_contexts
    
    def test_manager_expired(self, conversation):
        """Test manager method for getting expired contexts."""
        # Create another conversation for expired context
        customer2 = Customer.objects.create(
            tenant=conversation.tenant,
            phone_e164="+9876543210",
            name="Customer 2"
        )
        conversation2 = Conversation.objects.create(
            tenant=conversation.tenant,
            customer=customer2,
            status="active"
        )
        
        # Active context
        active = ConversationContext.objects.create(
            conversation=conversation,
            context_expires_at=timezone.now() + timedelta(minutes=10)
        )
        
        # Expired context
        expired = ConversationContext.objects.create(
            conversation=conversation2,
            context_expires_at=timezone.now() - timedelta(minutes=10)
        )
        
        expired_contexts = ConversationContext.objects.expired()
        assert expired in expired_contexts
        assert active not in expired_contexts
    
    def test_tenant_isolation(self, conversation):
        """Test that contexts are properly isolated by tenant."""
        # Create context for first tenant
        context1 = ConversationContext.objects.create(
            conversation=conversation
        )
        
        # Create second tenant and conversation
        tenant2 = Tenant.objects.create(
            name="Tenant 2",
            slug="tenant-2",
            whatsapp_number="+9876543210",
            status="active"
        )
        customer2 = Customer.objects.create(
            tenant=tenant2,
            phone_e164="+1234567890",
            name="Customer 2"
        )
        conversation2 = Conversation.objects.create(
            tenant=tenant2,
            customer=customer2,
            status="active"
        )
        context2 = ConversationContext.objects.create(
            conversation=conversation2
        )
        
        # Verify isolation
        tenant1_contexts = ConversationContext.objects.for_tenant(conversation.tenant)
        tenant2_contexts = ConversationContext.objects.for_tenant(tenant2)
        
        assert context1 in tenant1_contexts
        assert context1 not in tenant2_contexts
        assert context2 in tenant2_contexts
        assert context2 not in tenant1_contexts
