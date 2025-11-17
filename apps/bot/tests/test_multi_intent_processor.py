"""
Tests for MultiIntentProcessor service.

Tests multi-intent detection, message burst handling, intent prioritization,
and structured response generation.
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from django.utils import timezone
from datetime import timedelta

from apps.bot.services.multi_intent_processor import (
    MultiIntentProcessor,
    Intent,
    MessageBurst,
    MultiIntentProcessorError,
    create_multi_intent_processor
)
from apps.messaging.models import Message, Conversation, MessageQueue
from apps.tenants.models import Tenant, Customer
from apps.bot.models import AgentConfiguration
from apps.bot.services.context_builder_service import AgentContext


@pytest.fixture
def tenant(db):
    """Create test tenant."""
    tenant = Tenant.objects.create(
        name="Test Business",
        slug="test-business",
        status="active"
    )
    # Create tenant settings with API key
    tenant.settings.openai_api_key = "test-key"
    tenant.settings.llm_provider = "openai"
    tenant.settings.save()
    return tenant


@pytest.fixture
def agent_config(db, tenant):
    """Create test agent configuration."""
    return AgentConfiguration.objects.create(
        tenant=tenant,
        agent_name="TestBot",
        default_model="gpt-4o",
        enable_proactive_suggestions=True
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
            text="I want to book a haircut"
        ),
        Message.objects.create(
            conversation=conversation,
            direction='in',
            text="And also check the price of your shampoo"
        ),
    ]


@pytest.fixture
def mock_llm_provider():
    """Create mock LLM provider."""
    provider = Mock()
    provider.generate = Mock()
    return provider


@pytest.fixture
def processor(tenant, agent_config, mock_llm_provider):
    """Create MultiIntentProcessor with mocked LLM."""
    with patch('apps.bot.services.multi_intent_processor.LLMProviderFactory') as mock_factory:
        mock_factory_instance = Mock()
        mock_factory_instance.create_from_tenant_settings.return_value = mock_llm_provider
        mock_factory.return_value = mock_factory_instance
        
        processor = MultiIntentProcessor(tenant=tenant)
        processor.llm_provider = mock_llm_provider
        return processor


class TestIntentDataClass:
    """Test Intent data class."""
    
    def test_intent_creation(self):
        """Test creating Intent."""
        intent = Intent(
            name="BOOK_APPOINTMENT",
            confidence=0.9,
            slots={"service": "haircut"},
            priority=80,
            category="transactional",
            reasoning="Customer explicitly requested booking"
        )
        
        assert intent.name == "BOOK_APPOINTMENT"
        assert intent.confidence == 0.9
        assert intent.slots == {"service": "haircut"}
        assert intent.priority == 80
        assert intent.category == "transactional"
    
    def test_intent_to_dict(self):
        """Test converting Intent to dictionary."""
        intent = Intent(
            name="PRICE_CHECK",
            confidence=0.85,
            slots={"product": "shampoo"}
        )
        
        data = intent.to_dict()
        
        assert data['name'] == "PRICE_CHECK"
        assert data['confidence'] == 0.85
        assert data['slots'] == {"product": "shampoo"}


class TestMessageBurstDataClass:
    """Test MessageBurst data class."""
    
    def test_message_burst_creation(self, messages, conversation):
        """Test creating MessageBurst."""
        burst = MessageBurst(
            messages=messages,
            conversation=conversation,
            combined_text="Message 1\nMessage 2"
        )
        
        assert len(burst.messages) == 2
        assert burst.conversation == conversation
        assert burst.combined_text == "Message 1\nMessage 2"
    
    def test_get_message_ids(self, messages, conversation):
        """Test getting message IDs."""
        burst = MessageBurst(
            messages=messages,
            conversation=conversation,
            combined_text="test"
        )
        
        ids = burst.get_message_ids()
        
        assert len(ids) == 2
        assert all(isinstance(id, str) for id in ids)
    
    def test_get_message_count(self, messages, conversation):
        """Test getting message count."""
        burst = MessageBurst(
            messages=messages,
            conversation=conversation,
            combined_text="test"
        )
        
        assert burst.get_message_count() == 2


class TestProcessorInitialization:
    """Test MultiIntentProcessor initialization."""
    
    def test_initialization_basic(self, tenant, agent_config):
        """Test basic initialization."""
        with patch('apps.bot.services.multi_intent_processor.LLMProviderFactory'):
            processor = MultiIntentProcessor(tenant=tenant)
            
            assert processor.tenant == tenant
            assert processor.model is not None
            assert processor.context_builder is not None
    
    def test_initialization_with_model(self, tenant):
        """Test initialization with custom model."""
        with patch('apps.bot.services.multi_intent_processor.LLMProviderFactory'):
            processor = MultiIntentProcessor(
                tenant=tenant,
                model="gpt-4o-mini"
            )
            
            assert processor.model == "gpt-4o-mini"
    
    def test_factory_function(self, tenant):
        """Test factory function."""
        with patch('apps.bot.services.multi_intent_processor.LLMProviderFactory'):
            processor = create_multi_intent_processor(tenant)
            
            assert isinstance(processor, MultiIntentProcessor)


class TestIntentDetection:
    """Test intent detection functionality."""
    
    def test_detect_intents_single(self, processor, mock_llm_provider):
        """Test detecting single intent."""
        # Mock LLM response
        mock_response = Mock()
        mock_response.content = json.dumps({
            "intents": [
                {
                    "intent": "BOOK_APPOINTMENT",
                    "confidence": 0.9,
                    "slots": {"service": "haircut"},
                    "reasoning": "Customer wants to book"
                }
            ]
        })
        mock_llm_provider.generate.return_value = mock_response
        
        intents = processor.detect_intents("I want to book a haircut")
        
        assert len(intents) == 1
        assert intents[0].name == "BOOK_APPOINTMENT"
        assert intents[0].confidence == 0.9
        assert intents[0].slots == {"service": "haircut"}
    
    def test_detect_intents_multiple(self, processor, mock_llm_provider):
        """Test detecting multiple intents."""
        # Mock LLM response with multiple intents
        mock_response = Mock()
        mock_response.content = json.dumps({
            "intents": [
                {
                    "intent": "BOOK_APPOINTMENT",
                    "confidence": 0.9,
                    "slots": {"service": "haircut"},
                    "reasoning": "Booking request"
                },
                {
                    "intent": "PRICE_CHECK",
                    "confidence": 0.85,
                    "slots": {"product": "shampoo"},
                    "reasoning": "Price inquiry"
                }
            ]
        })
        mock_llm_provider.generate.return_value = mock_response
        
        intents = processor.detect_intents(
            "I want to book a haircut and check the price of shampoo"
        )
        
        assert len(intents) == 2
        assert intents[0].name == "BOOK_APPOINTMENT"
        assert intents[1].name == "PRICE_CHECK"
    
    def test_detect_intents_with_context(self, processor, mock_llm_provider):
        """Test intent detection with conversation context."""
        # Create mock context
        mock_context = Mock(spec=AgentContext)
        mock_context.conversation_history = []
        
        mock_response = Mock()
        mock_response.content = json.dumps({
            "intents": [{"intent": "GREETING", "confidence": 0.95, "slots": {}, "reasoning": ""}]
        })
        mock_llm_provider.generate.return_value = mock_response
        
        intents = processor.detect_intents("Hello", context=mock_context)
        
        assert len(intents) > 0
        # Should have called LLM with context
        mock_llm_provider.generate.assert_called_once()
    
    def test_detect_intents_error_handling(self, processor, mock_llm_provider):
        """Test error handling in intent detection."""
        # Mock LLM to raise error
        mock_llm_provider.generate.side_effect = Exception("API Error")
        
        with pytest.raises(MultiIntentProcessorError):
            processor.detect_intents("test message")
    
    def test_detect_intents_invalid_json(self, processor, mock_llm_provider):
        """Test handling of invalid JSON response."""
        # Mock LLM response with invalid JSON
        mock_response = Mock()
        mock_response.content = "This is not JSON"
        mock_llm_provider.generate.return_value = mock_response
        
        intents = processor.detect_intents("test")
        
        # Should return empty list for invalid JSON
        assert intents == []
    
    def test_detect_intents_json_in_markdown(self, processor, mock_llm_provider):
        """Test extracting JSON from markdown code blocks."""
        # Mock LLM response with JSON in markdown
        mock_response = Mock()
        mock_response.content = """
        Here's the result:
        ```json
        {
            "intents": [
                {"intent": "GREETING", "confidence": 0.9, "slots": {}, "reasoning": ""}
            ]
        }
        ```
        """
        mock_llm_provider.generate.return_value = mock_response
        
        intents = processor.detect_intents("Hello")
        
        assert len(intents) == 1
        assert intents[0].name == "GREETING"


class TestIntentPrioritization:
    """Test intent prioritization."""
    
    def test_prioritize_intents_by_category(self, processor):
        """Test prioritization by category."""
        intents = [
            Intent(name="BROWSE_PRODUCTS", confidence=0.9, category="browsing"),
            Intent(name="HUMAN_HANDOFF", confidence=0.8, category="urgent"),
            Intent(name="PRICE_CHECK", confidence=0.85, category="informational")
        ]
        
        prioritized = processor.prioritize_intents(intents)
        
        # Urgent should come first
        assert prioritized[0].name == "HUMAN_HANDOFF"
        assert prioritized[0].category == "urgent"
    
    def test_prioritize_intents_by_confidence(self, processor):
        """Test prioritization by confidence within same category."""
        intents = [
            Intent(name="PRODUCT_DETAILS", confidence=0.7, category="informational"),
            Intent(name="PRICE_CHECK", confidence=0.9, category="informational")
        ]
        
        prioritized = processor.prioritize_intents(intents)
        
        # Higher confidence should come first within same category
        assert prioritized[0].confidence > prioritized[1].confidence
    
    def test_prioritize_intents_assigns_priority(self, processor):
        """Test that prioritization assigns priority scores."""
        intents = [
            Intent(name="GREETING", confidence=0.9, category="browsing")
        ]
        
        prioritized = processor.prioritize_intents(intents)
        
        # Should have priority assigned
        assert prioritized[0].priority > 0


class TestMessageBurstProcessing:
    """Test message burst processing."""
    
    def test_process_message_burst_basic(
        self,
        processor,
        conversation,
        messages,
        mock_llm_provider
    ):
        """Test basic message burst processing."""
        # Create queued messages
        for msg in messages:
            MessageQueue.objects.create(
                conversation=conversation,
                message=msg,
                status='queued',
                queue_position=0,
                queued_at=timezone.now() - timedelta(seconds=10)
            )
        
        # Mock LLM responses
        intent_response = Mock()
        intent_response.content = json.dumps({
            "intents": [
                {"intent": "BOOK_APPOINTMENT", "confidence": 0.9, "slots": {}, "reasoning": ""}
            ]
        })
        
        response_response = Mock()
        response_response.content = "I can help you book a haircut!"
        
        mock_llm_provider.generate.side_effect = [intent_response, response_response]
        
        result = processor.process_message_burst(conversation, delay_seconds=5)
        
        assert result is not None
        assert 'response' in result
        assert 'intents_addressed' in result
        assert 'message_count' in result
        assert result['message_count'] == 2
    
    def test_process_message_burst_no_messages(self, processor, conversation):
        """Test burst processing with no ready messages."""
        result = processor.process_message_burst(conversation)
        
        # Should return None when no messages ready
        assert result is None
    
    def test_process_message_burst_marks_processed(
        self,
        processor,
        conversation,
        messages,
        mock_llm_provider
    ):
        """Test that processed messages are marked."""
        # Create queued messages
        queued = []
        for msg in messages:
            qm = MessageQueue.objects.create(
                conversation=conversation,
                message=msg,
                status='queued',
                queue_position=0,
                queued_at=timezone.now() - timedelta(seconds=10)
            )
            queued.append(qm)
        
        # Mock LLM responses
        mock_llm_provider.generate.return_value = Mock(
            content=json.dumps({"intents": []})
        )
        
        processor.process_message_burst(conversation, delay_seconds=5)
        
        # Check messages are marked as processed
        for qm in queued:
            qm.refresh_from_db()
            assert qm.status == 'processed'
    
    def test_process_message_burst_error_handling(
        self,
        processor,
        conversation,
        messages,
        mock_llm_provider
    ):
        """Test error handling in burst processing."""
        # Create queued messages
        for msg in messages:
            MessageQueue.objects.create(
                conversation=conversation,
                message=msg,
                status='queued',
                queue_position=0,
                queued_at=timezone.now() - timedelta(seconds=10)
            )
        
        # Mock LLM to raise error
        mock_llm_provider.generate.side_effect = Exception("API Error")
        
        with pytest.raises(MultiIntentProcessorError):
            processor.process_message_burst(conversation, delay_seconds=5)
        
        # Messages should be marked as failed
        failed = MessageQueue.objects.filter(
            conversation=conversation,
            status='failed'
        )
        assert failed.exists()


class TestStructuredResponseGeneration:
    """Test structured response generation."""
    
    def test_generate_structured_response(
        self,
        processor,
        conversation,
        messages,
        mock_llm_provider
    ):
        """Test generating structured response."""
        burst = MessageBurst(
            messages=messages,
            conversation=conversation,
            combined_text="I want to book a haircut and check prices"
        )
        
        intents = [
            Intent(name="BOOK_APPOINTMENT", confidence=0.9, category="transactional"),
            Intent(name="PRICE_CHECK", confidence=0.85, category="informational")
        ]
        
        mock_context = Mock(spec=AgentContext)
        mock_context.knowledge_entries = []
        mock_context.products = []
        mock_context.services = []
        
        mock_response = Mock()
        mock_response.content = "I can help you with both! Let me address each..."
        mock_llm_provider.generate.return_value = mock_response
        
        response = processor.generate_structured_response(
            burst=burst,
            intents=intents,
            context=mock_context
        )
        
        assert isinstance(response, str)
        assert len(response) > 0
        # Should have called LLM
        mock_llm_provider.generate.assert_called_once()
    
    def test_generate_structured_response_error(
        self,
        processor,
        conversation,
        messages,
        mock_llm_provider
    ):
        """Test error handling in response generation."""
        burst = MessageBurst(
            messages=messages,
            conversation=conversation,
            combined_text="test"
        )
        
        mock_llm_provider.generate.side_effect = Exception("API Error")
        
        with pytest.raises(MultiIntentProcessorError):
            processor.generate_structured_response(
                burst=burst,
                intents=[],
                context=Mock()
            )


class TestIntentCategorization:
    """Test intent categorization."""
    
    def test_get_intent_category_urgent(self, processor):
        """Test urgent intent categorization."""
        category = processor._get_intent_category("HUMAN_HANDOFF")
        assert category == "urgent"
    
    def test_get_intent_category_transactional(self, processor):
        """Test transactional intent categorization."""
        category = processor._get_intent_category("BOOK_APPOINTMENT")
        assert category == "transactional"
    
    def test_get_intent_category_informational(self, processor):
        """Test informational intent categorization."""
        category = processor._get_intent_category("PRICE_CHECK")
        assert category == "informational"
    
    def test_get_intent_category_browsing(self, processor):
        """Test browsing intent categorization."""
        category = processor._get_intent_category("BROWSE_PRODUCTS")
        assert category == "browsing"
    
    def test_get_intent_category_unknown(self, processor):
        """Test unknown intent defaults to support."""
        category = processor._get_intent_category("UNKNOWN_INTENT")
        assert category == "support"


class TestPromptBuilding:
    """Test prompt building methods."""
    
    def test_build_multi_intent_system_prompt(self, processor):
        """Test multi-intent system prompt building."""
        prompt = processor._build_multi_intent_system_prompt()
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "intents" in prompt.lower()
        assert "json" in prompt.lower()
    
    def test_build_multi_intent_user_prompt(self, processor):
        """Test multi-intent user prompt building."""
        prompt = processor._build_multi_intent_user_prompt(
            "I want to book a haircut",
            context=None
        )
        
        assert isinstance(prompt, str)
        assert "book a haircut" in prompt
    
    def test_build_multi_intent_user_prompt_with_context(self, processor):
        """Test user prompt includes context."""
        mock_context = Mock(spec=AgentContext)
        mock_msg = Mock()
        mock_msg.direction = 'in'
        mock_msg.text = "Previous message"
        mock_context.conversation_history = [mock_msg]
        
        prompt = processor._build_multi_intent_user_prompt(
            "Current message",
            context=mock_context
        )
        
        assert "Previous message" in prompt
        assert "Current message" in prompt
    
    def test_build_response_generation_system_prompt(self, processor):
        """Test response generation system prompt."""
        prompt = processor._build_response_generation_system_prompt()
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "response" in prompt.lower()
    
    def test_build_response_generation_user_prompt(
        self,
        processor,
        conversation,
        messages
    ):
        """Test response generation user prompt."""
        burst = MessageBurst(
            messages=messages,
            conversation=conversation,
            combined_text="test"
        )
        
        intents = [
            Intent(name="GREETING", confidence=0.9, category="browsing")
        ]
        
        mock_context = Mock(spec=AgentContext)
        mock_context.knowledge_entries = []
        mock_context.products = []
        mock_context.services = []
        
        prompt = processor._build_response_generation_user_prompt(
            burst=burst,
            intents=intents,
            context=mock_context
        )
        
        assert isinstance(prompt, str)
        assert "GREETING" in prompt


class TestJSONParsing:
    """Test JSON response parsing."""
    
    def test_parse_multi_intent_response_valid_json(self, processor):
        """Test parsing valid JSON."""
        response = '{"intents": [{"intent": "GREETING", "confidence": 0.9}]}'
        
        result = processor._parse_multi_intent_response(response)
        
        assert 'intents' in result
        assert len(result['intents']) == 1
    
    def test_parse_multi_intent_response_markdown(self, processor):
        """Test parsing JSON from markdown."""
        response = """
        ```json
        {"intents": [{"intent": "GREETING", "confidence": 0.9}]}
        ```
        """
        
        result = processor._parse_multi_intent_response(response)
        
        assert 'intents' in result
    
    def test_parse_multi_intent_response_invalid(self, processor):
        """Test parsing invalid response."""
        response = "This is not JSON at all"
        
        result = processor._parse_multi_intent_response(response)
        
        # Should return empty intents
        assert result == {'intents': []}
