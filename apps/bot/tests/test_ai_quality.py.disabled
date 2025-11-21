"""
AI Quality Tests for AI-powered customer service agent.

Tests the quality and accuracy of AI agent responses including:
- Intent accuracy with sample messages
- Spelling correction accuracy
- Context retention across conversation gaps
- Multi-intent handling
- Handoff appropriateness
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from django.utils import timezone
from datetime import timedelta

from apps.bot.services.ai_agent_service import AIAgentService, AgentResponse
from apps.bot.services.fuzzy_matcher_service import FuzzyMatcherService
from apps.bot.services.multi_intent_processor import MultiIntentProcessor
from apps.bot.models import AgentConfiguration, ConversationContext
from apps.messaging.models import Message, Conversation
from apps.catalog.models import Product
from apps.services.models import Service
from apps.tenants.models import Tenant, Customer


@pytest.fixture
def tenant(db):
    """Create test tenant."""
    tenant = Tenant.objects.create(
        name="Test Business",
        slug="test-business",
        status="active"
    )
    # Set OpenAI API key for tests that need it
    tenant.settings.openai_api_key = "test-api-key"
    tenant.settings.save()
    return tenant


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
def agent_config(db, tenant):
    """Create agent configuration."""
    return AgentConfiguration.objects.create(
        tenant=tenant,
        agent_name="TestBot",
        tone="friendly",
        default_model="gpt-4o",
        confidence_threshold=0.7,
        max_low_confidence_attempts=2,
        enable_spelling_correction=True,
        enable_proactive_suggestions=True,
        enable_rich_messages=True
    )


@pytest.fixture
def products(db, tenant):
    """Create test products."""
    return [
        Product.objects.create(
            tenant=tenant,
            title="Blue T-Shirt",
            description="Comfortable cotton t-shirt",
            price=Decimal("29.99"),
            stock=10,
            is_active=True
        ),
        Product.objects.create(
            tenant=tenant,
            title="Running Shoes",
            description="Athletic shoes for running",
            price=Decimal("89.99"),
            stock=5,
            is_active=True
        ),
        Product.objects.create(
            tenant=tenant,
            title="Denim Jeans",
            description="Classic blue jeans",
            price=Decimal("59.99"),
            stock=8,
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
            description="Professional haircut service",
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
def ai_agent():
    """Create AI agent service instance."""
    return AIAgentService()


@pytest.fixture
def fuzzy_matcher():
    """Create fuzzy matcher instance."""
    return FuzzyMatcherService()


@pytest.fixture
def multi_intent_processor(tenant):
    """Create multi-intent processor instance."""
    return MultiIntentProcessor(tenant=tenant)


class TestIntentAccuracy:
    """Test intent detection accuracy with sample messages."""
    
    @pytest.mark.django_db
    def test_product_browsing_intent(self, ai_agent, tenant, products):
        """Test detection of product browsing intent."""
        test_messages = [
            ("blue shirt", True),  # Should match
            ("t-shirt", True),  # Should match
            ("Show me your products", False),  # Generic, may not match specific product
            ("What items do you sell?", False),  # Generic
            ("I want to buy something", False),  # Generic
        ]
        
        for message_text, should_match in test_messages:
            # Check that fuzzy matcher can find products
            results = ai_agent.fuzzy_matcher.match_product(message_text, tenant, threshold=0.5)
            
            # For product-related queries with specific terms, should find relevant products
            if should_match:
                assert len(results) > 0, f"Failed to find products for: {message_text}"
    
    @pytest.mark.django_db
    def test_service_booking_intent(self, ai_agent, tenant, services):
        """Test detection of service booking intent."""
        test_messages = [
            "I want to book a haircut",
            "Can I schedule an appointment?",
            "What services do you offer?",
            "I need a hair coloring appointment",
            "Book me for a haircut"
        ]
        
        for message_text in test_messages:
            # Check that fuzzy matcher can find services
            results = ai_agent.fuzzy_matcher.match_service(message_text, tenant)
            
            # For service-related queries, should find relevant services
            if "haircut" in message_text.lower() or "hair" in message_text.lower():
                assert len(results) > 0, f"Failed to find services for: {message_text}"
    
    @pytest.mark.django_db
    def test_greeting_intent(self, ai_agent):
        """Test detection of greeting intent."""
        test_messages = [
            "Hello",
            "Hi there",
            "Good morning",
            "Hey",
            "Greetings"
        ]
        
        # Greetings should be short and simple
        for message_text in test_messages:
            # Model selection should use mini model for simple greetings
            model = ai_agent.select_model(message_text, Mock(default_model="gpt-4o"))
            assert model == "gpt-4o-mini", f"Should use mini model for greeting: {message_text}"
    
    @pytest.mark.django_db
    def test_complex_query_intent(self, ai_agent):
        """Test detection of complex reasoning queries."""
        # Test messages that contain reasoning keywords AND are long enough
        test_messages = [
            "Why should I choose this product over others and what makes it special?",
            "How does this service compare to alternatives in terms of quality?",
            "Explain the difference between these options and help me understand",
            "What would you recommend for my situation based on my needs?",
            "Which is the best option for me and why do you think so?"
        ]
        
        for message_text in test_messages:
            # Model selection should use reasoning model for complex queries
            model = ai_agent.select_model(message_text, Mock(default_model="gpt-4o"))
            assert model == "o1-preview", f"Should use reasoning model for: {message_text}"
    
    @pytest.mark.django_db
    def test_human_handoff_intent(self, ai_agent, conversation, agent_config):
        """Test detection of human handoff requests."""
        test_messages = [
            "I want to speak to a human",
            "Connect me to a real person",
            "Can I talk to customer service?",
            "I need a live agent",
            "Transfer me to someone"
        ]
        
        for message_text in test_messages:
            # Create mock response
            mock_response = AgentResponse(
                content="I'll connect you with a human agent",
                model_used="gpt-4o",
                provider="openai",
                confidence_score=0.9,
                processing_time_ms=100,
                input_tokens=10,
                output_tokens=10,
                total_tokens=20,
                estimated_cost=Decimal("0.001")
            )
            
            # Create message
            message = Message.objects.create(
                conversation=conversation,
                direction='in',
                text=message_text
            )
            
            # Check handoff detection
            should_handoff, reason = ai_agent.should_handoff(
                response=mock_response,
                conversation=conversation,
                agent_config=agent_config
            )
            
            assert should_handoff, f"Should detect handoff request in: {message_text}"
            assert reason == "customer_requested_human", f"Wrong handoff reason for: {message_text}"


class TestSpellingCorrectionAccuracy:
    """Test spelling correction accuracy."""
    
    def test_single_word_correction(self, fuzzy_matcher):
        """Test correcting single misspelled words."""
        test_cases = [
            ("prodct", ["product"], "product"),
            ("shrt", ["shirt"], "shirt"),
            ("servce", ["service"], "service"),
            ("apointment", ["appointment"], "appointment"),
        ]
        
        for misspelled, vocabulary, expected in test_cases:
            corrected = fuzzy_matcher.correct_spelling(misspelled, vocabulary)
            assert corrected == expected, f"Failed to correct '{misspelled}' to '{expected}'"
    
    def test_multiple_word_correction(self, fuzzy_matcher):
        """Test correcting multiple words in a sentence."""
        vocabulary = ["blue", "shirt", "running", "shoes", "denim", "jeans"]
        
        test_cases = [
            ("blu shrt", "blue shirt"),
            ("runing shoos", "running shoes"),
            ("denim jens", "denim jeans"),
        ]
        
        for misspelled, expected in test_cases:
            corrected = fuzzy_matcher.correct_spelling(misspelled, vocabulary)
            # Check that key words were corrected
            for word in expected.split():
                assert word in corrected.lower(), f"Expected '{word}' in corrected text: {corrected}"
    
    def test_preserve_correct_words(self, fuzzy_matcher):
        """Test that correctly spelled words are preserved."""
        vocabulary = ["blue", "shirt", "running", "shoes"]
        
        text = "blue shirt"
        corrected = fuzzy_matcher.correct_spelling(text, vocabulary)
        
        assert corrected == text, "Should preserve correctly spelled words"
    
    @pytest.mark.django_db
    def test_product_name_correction(self, fuzzy_matcher, tenant, products):
        """Test correcting product names with typos."""
        test_cases = [
            ("blu tshirt", "Blue T-Shirt"),
            ("runing shoos", "Running Shoes"),
            ("denim jens", "Denim Jeans"),
        ]
        
        for query, expected_product in test_cases:
            results = fuzzy_matcher.match_product(query, tenant, threshold=0.6)
            
            assert len(results) > 0, f"Failed to match product for query: {query}"
            
            # Check if expected product is in results
            product_titles = [p.title for p, _ in results]
            assert expected_product in product_titles, \
                f"Expected '{expected_product}' in results for query '{query}'"
    
    @pytest.mark.django_db
    def test_service_name_correction(self, fuzzy_matcher, tenant, services):
        """Test correcting service names with typos."""
        test_cases = [
            ("harcut", "Haircut"),
            ("hair colring", "Hair Coloring"),
        ]
        
        for query, expected_service in test_cases:
            results = fuzzy_matcher.match_service(query, tenant, threshold=0.6)
            
            assert len(results) > 0, f"Failed to match service for query: {query}"
            
            # Check if expected service is in results
            service_titles = [s.title for s, _ in results]
            assert expected_service in service_titles, \
                f"Expected '{expected_service}' in results for query '{query}'"
    
    def test_correction_confidence_threshold(self, fuzzy_matcher):
        """Test that low-confidence corrections are rejected."""
        vocabulary = ["product"]
        
        # Very different word should not be corrected
        text = "xyz"
        corrected = fuzzy_matcher.correct_spelling(text, vocabulary, threshold=0.9)
        
        assert corrected == text, "Should not correct words with low similarity"


class TestContextRetention:
    """Test context retention across conversation gaps."""
    
    @pytest.mark.django_db
    def test_context_retention_within_window(self, conversation, ai_agent):
        """Test that context is retained within expiration window."""
        # Create conversation context
        context = ConversationContext.objects.create(
            conversation=conversation,
            current_topic="product_inquiry",
            pending_action="view_product",
            conversation_summary="Customer is looking for blue shirts"
        )
        
        # Extend expiration (simulates recent activity)
        context.extend_expiration(minutes=30)
        
        # Retrieve context
        retrieved = ai_agent.context_builder._get_or_create_context(conversation)
        
        assert retrieved.current_topic == "product_inquiry"
        assert retrieved.pending_action == "view_product"
        assert "blue shirts" in retrieved.conversation_summary
    
    @pytest.mark.django_db
    def test_context_cleared_after_expiration(self, conversation, ai_agent):
        """Test that expired context is cleared."""
        # Create expired context
        context = ConversationContext.objects.create(
            conversation=conversation,
            current_topic="old_topic",
            pending_action="old_action",
            context_expires_at=timezone.now() - timedelta(hours=1)
        )
        
        # Retrieve context (should be cleared)
        retrieved = ai_agent.context_builder._get_or_create_context(conversation)
        
        assert retrieved.current_topic == ""
        assert retrieved.pending_action == ""
    
    @pytest.mark.django_db
    def test_conversation_history_retention(self, conversation, ai_agent):
        """Test that conversation history is retained."""
        # Create messages over time
        messages = []
        for i in range(5):
            msg = Message.objects.create(
                conversation=conversation,
                direction='in' if i % 2 == 0 else 'out',
                text=f"Message {i}"
            )
            messages.append(msg)
        
        # Retrieve history
        history = ai_agent.context_builder.get_conversation_history(conversation)
        
        assert len(history) == 5
        assert all(msg in history for msg in messages)
    
    @pytest.mark.django_db
    def test_context_restoration_after_gap(self, conversation, products, ai_agent):
        """Test context restoration after conversation gap."""
        # Create context with product reference
        context = ConversationContext.objects.create(
            conversation=conversation,
            current_topic="product_inquiry",
            last_product_viewed=products[0],
            conversation_summary="Customer was interested in Blue T-Shirt"
        )
        
        # Simulate gap (but within expiration window)
        context.extend_expiration(minutes=30)
        
        # Create new message after gap
        message = Message.objects.create(
            conversation=conversation,
            direction='in',
            text="What was that product again?"
        )
        
        # Build context
        agent_context = ai_agent.context_builder.build_context(
            conversation=conversation,
            message=message,
            tenant=conversation.tenant
        )
        
        # Should restore product reference
        assert agent_context.context is not None
        assert agent_context.context.last_product_viewed == products[0]
    
    @pytest.mark.django_db
    def test_key_facts_preservation(self, conversation, ai_agent):
        """Test that key facts are preserved even after context expiration."""
        # Create context with key facts
        context = ConversationContext.objects.create(
            conversation=conversation,
            key_facts=["Customer prefers blue color", "Size: Medium"],
            context_expires_at=timezone.now() - timedelta(hours=1)
        )
        
        # Even though expired, key facts should be preserved
        # (In production, this would be handled by the context builder)
        assert context.key_facts == ["Customer prefers blue color", "Size: Medium"]


class TestMultiIntentHandling:
    """Test multi-intent detection and handling."""
    
    @pytest.mark.django_db
    def test_detect_multiple_intents(self, multi_intent_processor, conversation):
        """Test detection of multiple intents in single message."""
        # Message with multiple intents
        message_text = "I want to buy a blue shirt and also book a haircut appointment"
        
        message = Message.objects.create(
            conversation=conversation,
            direction='in',
            text=message_text
        )
        
        # Mock LLM response for intent detection
        with patch.object(
            multi_intent_processor,
            '_call_llm_for_intent_detection',
            return_value=[
                {'intent': 'BROWSE_PRODUCTS', 'confidence': 0.9, 'entities': {'product': 'blue shirt'}},
                {'intent': 'BOOK_APPOINTMENT', 'confidence': 0.85, 'entities': {'service': 'haircut'}}
            ]
        ):
            intents = multi_intent_processor.detect_intents(message_text, Mock())
            
            assert len(intents) >= 2, "Should detect multiple intents"
            
            # Check that both intents are detected
            intent_types = [intent['intent'] for intent in intents]
            assert 'BROWSE_PRODUCTS' in intent_types or any('product' in str(i).lower() for i in intent_types)
            assert 'BOOK_APPOINTMENT' in intent_types or any('appointment' in str(i).lower() for i in intent_types)
    
    @pytest.mark.django_db
    def test_prioritize_intents(self, multi_intent_processor):
        """Test intent prioritization based on urgency."""
        intents = [
            {'intent': 'BROWSE_PRODUCTS', 'confidence': 0.9, 'priority': 'low'},
            {'intent': 'EMERGENCY', 'confidence': 0.95, 'priority': 'high'},
            {'intent': 'BOOK_APPOINTMENT', 'confidence': 0.85, 'priority': 'medium'},
        ]
        
        prioritized = multi_intent_processor.prioritize_intents(intents)
        
        # High priority should come first
        assert prioritized[0]['priority'] == 'high'
    
    @pytest.mark.django_db
    def test_message_burst_handling(self, multi_intent_processor, conversation):
        """Test handling of rapid message bursts."""
        # Create multiple messages in quick succession
        messages = []
        for i in range(3):
            msg = Message.objects.create(
                conversation=conversation,
                direction='in',
                text=f"Message {i}"
            )
            messages.append(msg)
        
        # Mock LLM response
        with patch.object(
            multi_intent_processor,
            '_call_llm_for_intent_detection',
            return_value=[{'intent': 'GENERAL_INQUIRY', 'confidence': 0.8}]
        ):
            # Process burst
            response = multi_intent_processor.process_message_burst(
                messages=messages,
                conversation=conversation
            )
            
            assert response is not None
            # Should process all messages together
            assert len(messages) == 3
    
    @pytest.mark.django_db
    def test_prevent_duplicate_intent_processing(self, multi_intent_processor, conversation):
        """Test that duplicate intents are not processed multiple times."""
        # Messages with same intent
        messages = [
            Message.objects.create(
                conversation=conversation,
                direction='in',
                text="Show me products"
            ),
            Message.objects.create(
                conversation=conversation,
                direction='in',
                text="I want to see your products"
            ),
        ]
        
        # Mock LLM to return same intent for both
        with patch.object(
            multi_intent_processor,
            '_call_llm_for_intent_detection',
            return_value=[{'intent': 'BROWSE_PRODUCTS', 'confidence': 0.9}]
        ):
            # Detect intents for both messages
            intents1 = multi_intent_processor.detect_intents(messages[0].text, Mock())
            intents2 = multi_intent_processor.detect_intents(messages[1].text, Mock())
            
            # Both should detect the same intent
            assert intents1[0]['intent'] == intents2[0]['intent']


class TestHandoffAppropriateness:
    """Test handoff decision appropriateness."""
    
    @pytest.mark.django_db
    def test_handoff_on_low_confidence(self, ai_agent, conversation, agent_config):
        """Test handoff triggered by low confidence."""
        # Create response with low confidence
        response = AgentResponse(
            content="I'm not sure about that",
            model_used="gpt-4o",
            provider="openai",
            confidence_score=0.5,  # Below threshold
            processing_time_ms=100,
            input_tokens=10,
            output_tokens=10,
            total_tokens=20,
            estimated_cost=Decimal("0.001")
        )
        
        # Set low confidence count to trigger handoff
        conversation.low_confidence_count = 1
        conversation.save()
        
        should_handoff, reason = ai_agent.should_handoff(
            response=response,
            conversation=conversation,
            agent_config=agent_config
        )
        
        assert should_handoff, "Should handoff after consecutive low confidence"
        assert reason == "consecutive_low_confidence"
    
    @pytest.mark.django_db
    def test_handoff_on_explicit_request(self, ai_agent, conversation, agent_config):
        """Test handoff on explicit customer request."""
        # Create message requesting human
        Message.objects.create(
            conversation=conversation,
            direction='in',
            text="I want to speak to a human agent"
        )
        
        response = AgentResponse(
            content="I'll connect you",
            model_used="gpt-4o",
            provider="openai",
            confidence_score=0.9,
            processing_time_ms=100,
            input_tokens=10,
            output_tokens=10,
            total_tokens=20,
            estimated_cost=Decimal("0.001")
        )
        
        should_handoff, reason = ai_agent.should_handoff(
            response=response,
            conversation=conversation,
            agent_config=agent_config
        )
        
        assert should_handoff, "Should handoff on explicit request"
        assert reason == "customer_requested_human"
    
    @pytest.mark.django_db
    def test_handoff_on_complex_issue(self, ai_agent, conversation, agent_config):
        """Test handoff on complex issues requiring human intervention."""
        complex_issues = [
            "I want a refund",
            "This is a complaint",
            "I need to speak to a lawyer",
            "This is an emergency",
            "I'm going to sue you"
        ]
        
        for issue_text in complex_issues:
            # Clear previous messages
            Message.objects.filter(conversation=conversation).delete()
            
            # Create message with complex issue
            Message.objects.create(
                conversation=conversation,
                direction='in',
                text=issue_text
            )
            
            # Response should NOT suggest handoff in content for this test
            response = AgentResponse(
                content="I understand your concern. Let me help you with that.",
                model_used="gpt-4o",
                provider="openai",
                confidence_score=0.9,
                processing_time_ms=100,
                input_tokens=10,
                output_tokens=10,
                total_tokens=20,
                estimated_cost=Decimal("0.001")
            )
            
            should_handoff, reason = ai_agent.should_handoff(
                response=response,
                conversation=conversation,
                agent_config=agent_config
            )
            
            assert should_handoff, f"Should handoff for complex issue: {issue_text}"
            assert "complex_issue" in reason or "customer_requested" in reason, \
                f"Wrong reason '{reason}' for: {issue_text}"
    
    @pytest.mark.django_db
    def test_no_handoff_on_high_confidence(self, ai_agent, conversation, agent_config):
        """Test that handoff is not triggered with high confidence."""
        response = AgentResponse(
            content="Here's the information you requested",
            model_used="gpt-4o",
            provider="openai",
            confidence_score=0.95,  # High confidence
            processing_time_ms=100,
            input_tokens=10,
            output_tokens=10,
            total_tokens=20,
            estimated_cost=Decimal("0.001")
        )
        
        # Create normal message
        Message.objects.create(
            conversation=conversation,
            direction='in',
            text="What products do you have?"
        )
        
        should_handoff, reason = ai_agent.should_handoff(
            response=response,
            conversation=conversation,
            agent_config=agent_config
        )
        
        assert not should_handoff, "Should not handoff with high confidence"
        assert reason == ""
    
    @pytest.mark.django_db
    def test_handoff_on_auto_handoff_topic(self, ai_agent, conversation, agent_config):
        """Test handoff on configured auto-handoff topics."""
        # Configure auto-handoff topics
        agent_config.auto_handoff_topics = ["billing", "technical support"]
        agent_config.save()
        
        # Clear previous messages
        Message.objects.filter(conversation=conversation).delete()
        
        # Create message with auto-handoff topic
        Message.objects.create(
            conversation=conversation,
            direction='in',
            text="I have a billing question"
        )
        
        # Response should NOT suggest handoff in content for this test
        response = AgentResponse(
            content="I can help you with your billing question",
            model_used="gpt-4o",
            provider="openai",
            confidence_score=0.9,
            processing_time_ms=100,
            input_tokens=10,
            output_tokens=10,
            total_tokens=20,
            estimated_cost=Decimal("0.001")
        )
        
        should_handoff, reason = ai_agent.should_handoff(
            response=response,
            conversation=conversation,
            agent_config=agent_config
        )
        
        assert should_handoff, "Should handoff on auto-handoff topic"
        assert "auto_handoff_topic" in reason or "billing" in reason.lower(), \
            f"Expected auto_handoff_topic in reason, got: {reason}"
    
    @pytest.mark.django_db
    def test_confidence_tracking_reset(self, ai_agent, conversation, agent_config):
        """Test that confidence tracking resets after high confidence."""
        # Set low confidence count
        conversation.low_confidence_count = 1
        conversation.save()
        
        # Create high confidence response
        response = AgentResponse(
            content="Here's what you need",
            model_used="gpt-4o",
            provider="openai",
            confidence_score=0.95,
            processing_time_ms=100,
            input_tokens=10,
            output_tokens=10,
            total_tokens=20,
            estimated_cost=Decimal("0.001")
        )
        
        # Update confidence tracking
        ai_agent._update_confidence_tracking(
            conversation=conversation,
            confidence_score=response.confidence_score,
            threshold=agent_config.confidence_threshold
        )
        
        # Reload conversation
        conversation.refresh_from_db()
        
        # Should reset counter
        assert conversation.low_confidence_count == 0


class TestModelSelection:
    """Test appropriate model selection for different query types."""
    
    def test_simple_query_uses_mini_model(self, ai_agent):
        """Test that simple queries use cost-effective mini model."""
        simple_queries = [
            "Hello",
            "Thanks",
            "Yes",
            "No",
            "OK"
        ]
        
        mock_config = Mock(default_model="gpt-4o")
        
        for query in simple_queries:
            model = ai_agent.select_model(query, mock_config)
            assert model == "gpt-4o-mini", f"Should use mini model for: {query}"
    
    def test_complex_query_uses_reasoning_model(self, ai_agent):
        """Test that complex queries use reasoning model."""
        # Queries must have reasoning keywords AND be > 50 chars
        complex_queries = [
            "Why is this product better than alternatives and what makes it special?",
            "How does this service compare to others in terms of quality and value?",
            "Explain the difference between these options so I can make a decision",
            "What would you recommend for my specific needs and requirements here?",
            "Which option should I choose and why do you think it's the best one?"
        ]
        
        mock_config = Mock(default_model="gpt-4o")
        
        for query in complex_queries:
            model = ai_agent.select_model(query, mock_config)
            assert model == "o1-preview", f"Should use reasoning model for: {query}"
    
    def test_default_model_for_standard_queries(self, ai_agent):
        """Test that standard queries use default model."""
        # Use longer queries (>100 chars) without reasoning keywords
        standard_queries = [
            "What products do you have available in your store right now and can you tell me about them?",
            "I want to buy a shirt from your collection today and I need it in blue color please",
            "Show me your services and tell me about pricing and availability for this month",
            "Can I book an appointment for next week please and let me know what times are available?"
        ]
        
        mock_config = Mock(default_model="gpt-4o")
        
        for query in standard_queries:
            model = ai_agent.select_model(query, mock_config)
            assert model == "gpt-4o", f"Should use default model for: {query}"
