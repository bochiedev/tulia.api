"""
Tests for IntentEvent tenant isolation.

Verifies that IntentEvent queries are properly scoped to tenants
and that cross-tenant data leakage is prevented.
"""
import pytest
from django.contrib.auth import get_user_model
from apps.tenants.models import Tenant, Customer
from apps.messaging.models import Conversation
from apps.bot.models import IntentEvent

User = get_user_model()


@pytest.mark.django_db
class TestIntentEventTenantIsolation:
    """Test suite for IntentEvent tenant isolation."""
    
    @pytest.fixture
    def tenant_a(self):
        """Create tenant A."""
        return Tenant.objects.create(
            name="Tenant A",
            slug="tenant-a",
            status="active",
            whatsapp_number="+1111111111"
        )
    
    @pytest.fixture
    def tenant_b(self):
        """Create tenant B."""
        return Tenant.objects.create(
            name="Tenant B",
            slug="tenant-b",
            status="active",
            whatsapp_number="+2222222222"
        )
    
    @pytest.fixture
    def customer_a(self, tenant_a):
        """Create customer for tenant A."""
        return Customer.objects.create(
            tenant=tenant_a,
            phone_e164="+1234567890",
            name="Customer A"
        )
    
    @pytest.fixture
    def customer_b(self, tenant_b):
        """Create customer for tenant B."""
        return Customer.objects.create(
            tenant=tenant_b,
            phone_e164="+1234567890",  # Same phone, different tenant
            name="Customer B"
        )
    
    @pytest.fixture
    def conversation_a(self, tenant_a, customer_a):
        """Create conversation for tenant A."""
        return Conversation.objects.create(
            tenant=tenant_a,
            customer=customer_a,
            status="open"
        )
    
    @pytest.fixture
    def conversation_b(self, tenant_b, customer_b):
        """Create conversation for tenant B."""
        return Conversation.objects.create(
            tenant=tenant_b,
            customer=customer_b,
            status="open"
        )
    
    def test_intent_event_auto_populates_tenant(self, tenant_a, conversation_a):
        """Test that IntentEvent auto-populates tenant from conversation."""
        intent_event = IntentEvent.objects.create(
            conversation=conversation_a,
            intent_name="BROWSE_PRODUCTS",
            confidence_score=0.95,
            model="gpt-4",
            message_text="Show me your products"
        )
        
        assert intent_event.tenant_id == tenant_a.id
        assert intent_event.tenant == tenant_a
    
    def test_intent_event_validates_tenant_consistency(self, tenant_a, tenant_b, conversation_a):
        """Test that IntentEvent validates tenant matches conversation tenant."""
        with pytest.raises(ValueError, match="must match Conversation tenant"):
            IntentEvent.objects.create(
                tenant=tenant_b,  # Wrong tenant
                conversation=conversation_a,  # Belongs to tenant_a
                intent_name="BROWSE_PRODUCTS",
                confidence_score=0.95,
                model="gpt-4",
                message_text="Show me your products"
            )
    
    def test_for_tenant_filters_correctly(self, tenant_a, tenant_b, conversation_a, conversation_b):
        """Test that for_tenant() returns only events for that tenant."""
        # Create intent events for both tenants
        intent_a = IntentEvent.objects.create(
            conversation=conversation_a,
            intent_name="BROWSE_PRODUCTS",
            confidence_score=0.95,
            model="gpt-4",
            message_text="Show me products"
        )
        
        intent_b = IntentEvent.objects.create(
            conversation=conversation_b,
            intent_name="BOOK_APPOINTMENT",
            confidence_score=0.88,
            model="gpt-4",
            message_text="Book appointment"
        )
        
        # Query for tenant A
        tenant_a_events = IntentEvent.objects.for_tenant(tenant_a)
        assert tenant_a_events.count() == 1
        assert intent_a in tenant_a_events
        assert intent_b not in tenant_a_events
        
        # Query for tenant B
        tenant_b_events = IntentEvent.objects.for_tenant(tenant_b)
        assert tenant_b_events.count() == 1
        assert intent_b in tenant_b_events
        assert intent_a not in tenant_b_events
    
    def test_by_intent_requires_tenant(self, tenant_a, tenant_b, conversation_a, conversation_b):
        """Test that by_intent() is scoped to tenant."""
        # Create same intent for both tenants
        IntentEvent.objects.create(
            conversation=conversation_a,
            intent_name="BROWSE_PRODUCTS",
            confidence_score=0.95,
            model="gpt-4",
            message_text="Show products"
        )
        
        IntentEvent.objects.create(
            conversation=conversation_b,
            intent_name="BROWSE_PRODUCTS",
            confidence_score=0.92,
            model="gpt-4",
            message_text="Show products"
        )
        
        # Query by intent for tenant A
        tenant_a_browse = IntentEvent.objects.by_intent(tenant_a, "BROWSE_PRODUCTS")
        assert tenant_a_browse.count() == 1
        assert tenant_a_browse.first().tenant == tenant_a
        
        # Query by intent for tenant B
        tenant_b_browse = IntentEvent.objects.by_intent(tenant_b, "BROWSE_PRODUCTS")
        assert tenant_b_browse.count() == 1
        assert tenant_b_browse.first().tenant == tenant_b
    
    def test_high_confidence_scoped_to_tenant(self, tenant_a, tenant_b, conversation_a, conversation_b):
        """Test that high_confidence() is scoped to tenant."""
        # Create high confidence for tenant A
        IntentEvent.objects.create(
            conversation=conversation_a,
            intent_name="BROWSE_PRODUCTS",
            confidence_score=0.95,
            model="gpt-4",
            message_text="Show products"
        )
        
        # Create low confidence for tenant A
        IntentEvent.objects.create(
            conversation=conversation_a,
            intent_name="UNCLEAR",
            confidence_score=0.45,
            model="gpt-4",
            message_text="Hmm"
        )
        
        # Create high confidence for tenant B
        IntentEvent.objects.create(
            conversation=conversation_b,
            intent_name="BOOK_APPOINTMENT",
            confidence_score=0.88,
            model="gpt-4",
            message_text="Book appointment"
        )
        
        # Query high confidence for tenant A
        tenant_a_high = IntentEvent.objects.high_confidence(tenant_a, threshold=0.7)
        assert tenant_a_high.count() == 1
        assert tenant_a_high.first().intent_name == "BROWSE_PRODUCTS"
        
        # Query high confidence for tenant B
        tenant_b_high = IntentEvent.objects.high_confidence(tenant_b, threshold=0.7)
        assert tenant_b_high.count() == 1
        assert tenant_b_high.first().intent_name == "BOOK_APPOINTMENT"
    
    def test_low_confidence_scoped_to_tenant(self, tenant_a, tenant_b, conversation_a, conversation_b):
        """Test that low_confidence() is scoped to tenant."""
        # Create low confidence for tenant A
        IntentEvent.objects.create(
            conversation=conversation_a,
            intent_name="UNCLEAR",
            confidence_score=0.45,
            model="gpt-4",
            message_text="Hmm"
        )
        
        # Create high confidence for tenant B
        IntentEvent.objects.create(
            conversation=conversation_b,
            intent_name="BOOK_APPOINTMENT",
            confidence_score=0.88,
            model="gpt-4",
            message_text="Book appointment"
        )
        
        # Query low confidence for tenant A
        tenant_a_low = IntentEvent.objects.low_confidence(tenant_a, threshold=0.7)
        assert tenant_a_low.count() == 1
        assert tenant_a_low.first().intent_name == "UNCLEAR"
        
        # Query low confidence for tenant B (should be empty)
        tenant_b_low = IntentEvent.objects.low_confidence(tenant_b, threshold=0.7)
        assert tenant_b_low.count() == 0
    
    def test_same_phone_different_tenants_separate_intent_events(
        self, tenant_a, tenant_b, customer_a, customer_b, conversation_a, conversation_b
    ):
        """Test that same phone number in different tenants creates separate intent events."""
        # Verify customers have same phone but different IDs
        assert customer_a.phone_e164 == customer_b.phone_e164
        assert customer_a.id != customer_b.id
        assert customer_a.tenant != customer_b.tenant
        
        # Create intent events for both
        intent_a = IntentEvent.objects.create(
            conversation=conversation_a,
            intent_name="BROWSE_PRODUCTS",
            confidence_score=0.95,
            model="gpt-4",
            message_text="Show products"
        )
        
        intent_b = IntentEvent.objects.create(
            conversation=conversation_b,
            intent_name="BOOK_APPOINTMENT",
            confidence_score=0.88,
            model="gpt-4",
            message_text="Book appointment"
        )
        
        # Verify they are separate records
        assert intent_a.id != intent_b.id
        assert intent_a.tenant != intent_b.tenant
        assert intent_a.conversation != intent_b.conversation
        
        # Verify tenant A cannot see tenant B's events
        tenant_a_events = IntentEvent.objects.for_tenant(tenant_a)
        assert intent_a in tenant_a_events
        assert intent_b not in tenant_a_events
        
        # Verify tenant B cannot see tenant A's events
        tenant_b_events = IntentEvent.objects.for_tenant(tenant_b)
        assert intent_b in tenant_b_events
        assert intent_a not in tenant_b_events
    
    def test_conversation_related_query_respects_tenant(self, tenant_a, tenant_b, conversation_a, conversation_b):
        """Test that querying via conversation relationship respects tenant boundaries."""
        # Create multiple intent events for conversation A
        IntentEvent.objects.create(
            conversation=conversation_a,
            intent_name="BROWSE_PRODUCTS",
            confidence_score=0.95,
            model="gpt-4",
            message_text="Show products"
        )
        
        IntentEvent.objects.create(
            conversation=conversation_a,
            intent_name="PRODUCT_DETAILS",
            confidence_score=0.92,
            model="gpt-4",
            message_text="Tell me about product X"
        )
        
        # Create intent event for conversation B
        IntentEvent.objects.create(
            conversation=conversation_b,
            intent_name="BOOK_APPOINTMENT",
            confidence_score=0.88,
            model="gpt-4",
            message_text="Book appointment"
        )
        
        # Query via conversation relationship
        conversation_a_events = conversation_a.intent_events.all()
        assert conversation_a_events.count() == 2
        assert all(event.tenant == tenant_a for event in conversation_a_events)
        
        conversation_b_events = conversation_b.intent_events.all()
        assert conversation_b_events.count() == 1
        assert all(event.tenant == tenant_b for event in conversation_b_events)
