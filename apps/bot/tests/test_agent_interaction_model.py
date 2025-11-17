"""
Tests for AgentInteraction model.
"""
import pytest
from decimal import Decimal
from apps.bot.models import AgentInteraction
from apps.messaging.models import Conversation
from apps.tenants.models import Tenant, Customer


@pytest.fixture
def tenant(db):
    """Create a test tenant."""
    return Tenant.objects.create(
        name="Test Tenant",
        slug="test-tenant"
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
        status='active'
    )


@pytest.mark.django_db
class TestAgentInteractionModel:
    """Test AgentInteraction model."""
    
    def test_create_agent_interaction(self, conversation):
        """Test creating an agent interaction."""
        interaction = AgentInteraction.objects.create(
            conversation=conversation,
            customer_message="Hello, I need help",
            detected_intents=[{'name': 'greeting', 'confidence': 0.95}],
            model_used='gpt-4o',
            context_size=1000,
            processing_time_ms=500,
            agent_response="Hello! How can I help you today?",
            confidence_score=0.9,
            handoff_triggered=False,
            message_type='text',
            token_usage={'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150},
            estimated_cost=Decimal('0.002')
        )
        
        assert interaction.id is not None
        assert interaction.conversation == conversation
        assert interaction.customer_message == "Hello, I need help"
        assert interaction.model_used == 'gpt-4o'
        assert interaction.confidence_score == 0.9
        assert interaction.handoff_triggered is False
        assert interaction.message_type == 'text'
    
    def test_is_high_confidence(self, conversation):
        """Test is_high_confidence method."""
        interaction = AgentInteraction.objects.create(
            conversation=conversation,
            customer_message="Test",
            model_used='gpt-4o',
            agent_response="Response",
            confidence_score=0.85
        )
        
        assert interaction.is_high_confidence(threshold=0.7) is True
        assert interaction.is_high_confidence(threshold=0.9) is False
    
    def test_is_low_confidence(self, conversation):
        """Test is_low_confidence method."""
        interaction = AgentInteraction.objects.create(
            conversation=conversation,
            customer_message="Test",
            model_used='gpt-4o',
            agent_response="Response",
            confidence_score=0.6
        )
        
        assert interaction.is_low_confidence(threshold=0.7) is True
        assert interaction.is_low_confidence(threshold=0.5) is False
    
    def test_get_total_tokens(self, conversation):
        """Test get_total_tokens method."""
        interaction = AgentInteraction.objects.create(
            conversation=conversation,
            customer_message="Test",
            model_used='gpt-4o',
            agent_response="Response",
            confidence_score=0.8,
            token_usage={'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150}
        )
        
        assert interaction.get_total_tokens() == 150
    
    def test_get_prompt_tokens(self, conversation):
        """Test get_prompt_tokens method."""
        interaction = AgentInteraction.objects.create(
            conversation=conversation,
            customer_message="Test",
            model_used='gpt-4o',
            agent_response="Response",
            confidence_score=0.8,
            token_usage={'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150}
        )
        
        assert interaction.get_prompt_tokens() == 100
    
    def test_get_completion_tokens(self, conversation):
        """Test get_completion_tokens method."""
        interaction = AgentInteraction.objects.create(
            conversation=conversation,
            customer_message="Test",
            model_used='gpt-4o',
            agent_response="Response",
            confidence_score=0.8,
            token_usage={'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150}
        )
        
        assert interaction.get_completion_tokens() == 50
    
    def test_get_cost_per_token(self, conversation):
        """Test get_cost_per_token method."""
        interaction = AgentInteraction.objects.create(
            conversation=conversation,
            customer_message="Test",
            model_used='gpt-4o',
            agent_response="Response",
            confidence_score=0.8,
            token_usage={'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150},
            estimated_cost=Decimal('0.003')
        )
        
        cost_per_token = interaction.get_cost_per_token()
        assert cost_per_token == pytest.approx(0.00002, rel=1e-6)
    
    def test_get_intent_names(self, conversation):
        """Test get_intent_names method."""
        interaction = AgentInteraction.objects.create(
            conversation=conversation,
            customer_message="Test",
            model_used='gpt-4o',
            agent_response="Response",
            confidence_score=0.8,
            detected_intents=[
                {'name': 'greeting', 'confidence': 0.9},
                {'name': 'product_inquiry', 'confidence': 0.8}
            ]
        )
        
        intent_names = interaction.get_intent_names()
        assert intent_names == ['greeting', 'product_inquiry']
    
    def test_get_primary_intent(self, conversation):
        """Test get_primary_intent method."""
        interaction = AgentInteraction.objects.create(
            conversation=conversation,
            customer_message="Test",
            model_used='gpt-4o',
            agent_response="Response",
            confidence_score=0.8,
            detected_intents=[
                {'name': 'greeting', 'confidence': 0.9},
                {'name': 'product_inquiry', 'confidence': 0.8}
            ]
        )
        
        primary_intent = interaction.get_primary_intent()
        assert primary_intent == {'name': 'greeting', 'confidence': 0.9}
    
    def test_handoff_tracking(self, conversation):
        """Test handoff tracking fields."""
        interaction = AgentInteraction.objects.create(
            conversation=conversation,
            customer_message="I need to speak to a human",
            model_used='gpt-4o',
            agent_response="Let me connect you with an agent",
            confidence_score=0.95,
            handoff_triggered=True,
            handoff_reason='customer_requested_human'
        )
        
        assert interaction.handoff_triggered is True
        assert interaction.handoff_reason == 'customer_requested_human'


@pytest.mark.django_db
class TestAgentInteractionManager:
    """Test AgentInteraction custom manager."""
    
    def test_for_tenant(self, tenant, conversation):
        """Test for_tenant query method."""
        # Create interaction
        AgentInteraction.objects.create(
            conversation=conversation,
            customer_message="Test",
            model_used='gpt-4o',
            agent_response="Response",
            confidence_score=0.8
        )
        
        # Query by tenant
        interactions = AgentInteraction.objects.for_tenant(tenant)
        assert interactions.count() == 1
    
    def test_for_conversation(self, conversation):
        """Test for_conversation query method."""
        # Create multiple interactions
        AgentInteraction.objects.create(
            conversation=conversation,
            customer_message="Test 1",
            model_used='gpt-4o',
            agent_response="Response 1",
            confidence_score=0.8
        )
        AgentInteraction.objects.create(
            conversation=conversation,
            customer_message="Test 2",
            model_used='gpt-4o',
            agent_response="Response 2",
            confidence_score=0.9
        )
        
        # Query by conversation
        interactions = AgentInteraction.objects.for_conversation(conversation)
        assert interactions.count() == 2
    
    def test_by_model(self, tenant, conversation):
        """Test by_model query method."""
        # Create interactions with different models
        AgentInteraction.objects.create(
            conversation=conversation,
            customer_message="Test 1",
            model_used='gpt-4o',
            agent_response="Response 1",
            confidence_score=0.8
        )
        AgentInteraction.objects.create(
            conversation=conversation,
            customer_message="Test 2",
            model_used='gpt-4o-mini',
            agent_response="Response 2",
            confidence_score=0.9
        )
        
        # Query by model
        gpt4_interactions = AgentInteraction.objects.by_model(tenant, 'gpt-4o')
        assert gpt4_interactions.count() == 1
        
        mini_interactions = AgentInteraction.objects.by_model(tenant, 'gpt-4o-mini')
        assert mini_interactions.count() == 1
    
    def test_with_handoff(self, tenant, conversation):
        """Test with_handoff query method."""
        # Create interaction with handoff
        AgentInteraction.objects.create(
            conversation=conversation,
            customer_message="Test",
            model_used='gpt-4o',
            agent_response="Response",
            confidence_score=0.8,
            handoff_triggered=True
        )
        
        # Create interaction without handoff
        AgentInteraction.objects.create(
            conversation=conversation,
            customer_message="Test 2",
            model_used='gpt-4o',
            agent_response="Response 2",
            confidence_score=0.9,
            handoff_triggered=False
        )
        
        # Query handoffs
        handoffs = AgentInteraction.objects.with_handoff(tenant)
        assert handoffs.count() == 1
    
    def test_high_confidence(self, tenant, conversation):
        """Test high_confidence query method."""
        # Create interactions with different confidence scores
        AgentInteraction.objects.create(
            conversation=conversation,
            customer_message="Test 1",
            model_used='gpt-4o',
            agent_response="Response 1",
            confidence_score=0.85
        )
        AgentInteraction.objects.create(
            conversation=conversation,
            customer_message="Test 2",
            model_used='gpt-4o',
            agent_response="Response 2",
            confidence_score=0.6
        )
        
        # Query high confidence
        high_conf = AgentInteraction.objects.high_confidence(tenant, threshold=0.7)
        assert high_conf.count() == 1
    
    def test_low_confidence(self, tenant, conversation):
        """Test low_confidence query method."""
        # Create interactions with different confidence scores
        AgentInteraction.objects.create(
            conversation=conversation,
            customer_message="Test 1",
            model_used='gpt-4o',
            agent_response="Response 1",
            confidence_score=0.85
        )
        AgentInteraction.objects.create(
            conversation=conversation,
            customer_message="Test 2",
            model_used='gpt-4o',
            agent_response="Response 2",
            confidence_score=0.6
        )
        
        # Query low confidence
        low_conf = AgentInteraction.objects.low_confidence(tenant, threshold=0.7)
        assert low_conf.count() == 1
