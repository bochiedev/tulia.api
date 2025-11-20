"""
Tests for RAG integration into AI Agent Service.

Verifies that RAG retrieval, context synthesis, and attribution
are properly integrated into the agent workflow.
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from django.utils import timezone

from apps.bot.services.ai_agent_service import AIAgentService, AgentResponse
from apps.bot.models import AgentConfiguration
from apps.messaging.models import Message, Conversation
from apps.tenants.models import Tenant, Customer


@pytest.fixture
def tenant(db):
    """Create test tenant."""
    return Tenant.objects.create(
        name="Test Tenant",
        slug="test-tenant"
    )


@pytest.fixture
def customer(db, tenant):
    """Create test customer."""
    return Customer.objects.create(
        tenant=tenant,
        phone_e164="+254712345678",
        name="Test Customer"
    )


@pytest.fixture
def conversation(db, tenant, customer):
    """Create test conversation."""
    return Conversation.objects.create(
        tenant=tenant,
        customer=customer,
        channel='whatsapp',
        status='active'
    )


@pytest.fixture
def message(db, conversation):
    """Create test message."""
    return Message.objects.create(
        conversation=conversation,
        direction='in',
        message_type='customer_inbound',
        text="Tell me about your return policy"
    )


@pytest.fixture
def agent_config(db, tenant):
    """Create agent configuration with RAG enabled."""
    return AgentConfiguration.objects.create(
        tenant=tenant,
        agent_name="TestBot",
        enable_document_retrieval=True,
        enable_database_retrieval=True,
        enable_internet_enrichment=True,
        enable_source_attribution=True,
        max_document_results=3,
        max_database_results=5,
        max_internet_results=2,
        agent_can_do="Answer questions about products, services, and policies",
        agent_cannot_do="Process payments or access external systems"
    )


@pytest.mark.django_db
class TestRAGIntegration:
    """Test RAG integration into AI agent."""
    
    def test_should_use_rag_when_enabled(self, agent_config):
        """Test that RAG is used when enabled in config."""
        service = AIAgentService()
        
        # Should use RAG when any source is enabled
        assert service._should_use_rag(agent_config) is True
        
        # Should not use RAG when all sources disabled
        agent_config.enable_document_retrieval = False
        agent_config.enable_database_retrieval = False
        agent_config.enable_internet_enrichment = False
        assert service._should_use_rag(agent_config) is False
    
    @patch('apps.bot.services.ai_agent_service.RAGRetrieverService')
    @patch('apps.bot.services.ai_agent_service.ContextSynthesizer')
    @patch('apps.bot.services.ai_agent_service.AttributionHandler')
    def test_retrieve_rag_context(
        self,
        mock_attribution_handler,
        mock_synthesizer,
        mock_retriever,
        tenant,
        conversation,
        agent_config
    ):
        """Test RAG context retrieval."""
        # Setup mocks
        mock_retriever_instance = Mock()
        mock_retriever.create_for_tenant.return_value = mock_retriever_instance
        
        mock_retriever_instance.retrieve.return_value = {
            'document_results': [
                {'content': 'Return policy: 30 days', 'source': 'FAQ.pdf', 'score': 0.9}
            ],
            'database_results': [
                {'content': 'Product: Widget', 'score': 0.8}
            ],
            'internet_results': [],
            'retrieval_time_ms': 150
        }
        
        mock_synthesizer_instance = Mock()
        mock_synthesizer.return_value = mock_synthesizer_instance
        mock_synthesizer_instance.synthesize.return_value = {
            'synthesized_text': 'Our return policy allows returns within 30 days.',
            'sources': [
                {'type': 'document', 'name': 'FAQ.pdf', 'section': 'Returns'}
            ],
            'confidence': 0.9
        }
        
        # Create service and retrieve context
        service = AIAgentService()
        
        from apps.bot.services.context_builder_service import AgentContext
        context = AgentContext(
            conversation=conversation,
            current_message=Mock(text="What is your return policy?"),
            conversation_history=[],
            relevant_knowledge=[],
            catalog_context=Mock(products=[], services=[]),
            customer_history={},
            context=None,
            context_size_tokens=100,
            truncated=False,
            metadata={}
        )
        
        rag_context = service.retrieve_rag_context(
            query="What is your return policy?",
            conversation=conversation,
            context=context,
            agent_config=agent_config,
            tenant=tenant
        )
        
        # Verify retrieval was called
        mock_retriever.create_for_tenant.assert_called_once_with(tenant)
        mock_retriever_instance.retrieve.assert_called_once()
        
        # Verify context was synthesized
        mock_synthesizer_instance.synthesize.assert_called_once()
        
        # Verify returned context structure
        assert rag_context is not None
        assert 'document_results' in rag_context
        assert 'database_results' in rag_context
        assert 'synthesized_text' in rag_context
        assert 'sources' in rag_context
        assert len(rag_context['document_results']) == 1
        assert rag_context['synthesized_text'] == 'Our return policy allows returns within 30 days.'
    
    def test_build_rag_context_section(self, tenant):
        """Test building RAG context section for prompt."""
        service = AIAgentService()
        
        rag_context = {
            'synthesized_text': 'Our return policy allows returns within 30 days.',
            'document_results': [
                {'content': 'Return policy: 30 days', 'source': 'FAQ.pdf'}
            ],
            'database_results': [
                {'content': 'Product: Widget - $19.99'}
            ],
            'internet_results': [
                {'content': 'Industry standard return period is 30 days', 'source': 'RetailGuide.com'}
            ]
        }
        
        section = service._build_rag_context_section(rag_context)
        
        # Verify section structure
        assert '## Retrieved Information' in section
        assert '### Relevant Context:' in section
        assert 'Our return policy allows returns within 30 days.' in section
        assert '### From Business Documents:' in section
        assert 'Return policy: 30 days' in section
        assert '### From Our Catalog:' in section
        assert 'Product: Widget' in section
        assert '### Additional Information:' in section
        assert 'Industry standard' in section
        assert '**Instructions:**' in section
    
    @patch('apps.bot.services.ai_agent_service.AttributionHandler')
    def test_add_attribution_to_response(self, mock_attribution_handler, agent_config):
        """Test adding source attribution to response."""
        # Setup mock
        mock_handler_instance = Mock()
        mock_attribution_handler.return_value = mock_handler_instance
        mock_handler_instance.add_attribution.return_value = (
            "Our return policy allows returns within 30 days. [Source: FAQ.pdf]"
        )
        
        # Create service and response
        service = AIAgentService()
        service.attribution_handler = mock_handler_instance
        
        response = AgentResponse(
            content="Our return policy allows returns within 30 days.",
            model_used="gpt-4o",
            provider="openai",
            confidence_score=0.9,
            processing_time_ms=500,
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            estimated_cost=Decimal('0.001')
        )
        
        rag_context = {
            'sources': [
                {'type': 'document', 'name': 'FAQ.pdf', 'section': 'Returns'}
            ]
        }
        
        # Add attribution
        attributed_response = service.add_attribution_to_response(
            response=response,
            rag_context=rag_context,
            agent_config=agent_config
        )
        
        # Verify attribution was added
        mock_handler_instance.add_attribution.assert_called_once()
        assert '[Source: FAQ.pdf]' in attributed_response.content
        assert attributed_response.metadata['attribution_added'] is True
        assert attributed_response.metadata['source_count'] == 1
    
    def test_attribution_disabled(self, agent_config):
        """Test that attribution is skipped when disabled."""
        agent_config.enable_source_attribution = False
        
        service = AIAgentService()
        
        response = AgentResponse(
            content="Our return policy allows returns within 30 days.",
            model_used="gpt-4o",
            provider="openai",
            confidence_score=0.9,
            processing_time_ms=500,
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            estimated_cost=Decimal('0.001')
        )
        
        rag_context = {
            'sources': [
                {'type': 'document', 'name': 'FAQ.pdf'}
            ]
        }
        
        # Add attribution (should be skipped)
        attributed_response = service.add_attribution_to_response(
            response=response,
            rag_context=rag_context,
            agent_config=agent_config
        )
        
        # Verify attribution was NOT added
        assert attributed_response.content == "Our return policy allows returns within 30 days."
        assert 'attribution_added' not in attributed_response.metadata
    
    @patch('apps.bot.services.ai_agent_service.RAGRetrieverService')
    @patch('apps.bot.services.ai_agent_service.ContextBuilderService')
    @patch('apps.bot.services.ai_agent_service.LLMProviderFactory')
    @patch('apps.bot.services.ai_agent_service.ProviderRouter')
    @patch('apps.bot.services.ai_agent_service.ProviderFailoverManager')
    def test_process_message_with_rag(
        self,
        mock_failover,
        mock_router,
        mock_llm_factory,
        mock_context_builder,
        mock_retriever,
        tenant,
        conversation,
        message,
        agent_config
    ):
        """Test full message processing with RAG integration."""
        # Setup mocks
        from apps.bot.services.llm.base import LLMResponse
        from apps.bot.services.llm.provider_router import RoutingDecision
        from apps.bot.services.context_builder_service import AgentContext
        
        # Mock context builder
        mock_context_instance = Mock()
        mock_context_builder.return_value = mock_context_instance
        
        mock_context = AgentContext(
            conversation=conversation,
            current_message=message,
            conversation_history=[],
            relevant_knowledge=[],
            catalog_context=Mock(products=[], services=[]),
            customer_history={},
            context=None,
            context_size_tokens=100,
            truncated=False,
            metadata={}
        )
        mock_context_instance.build_context.return_value = mock_context
        
        # Mock RAG retriever
        mock_retriever_instance = Mock()
        mock_retriever.create_for_tenant.return_value = mock_retriever_instance
        mock_retriever_instance.retrieve.return_value = {
            'document_results': [
                {'content': 'Return policy: 30 days', 'source': 'FAQ.pdf', 'score': 0.9}
            ],
            'database_results': [],
            'internet_results': [],
            'retrieval_time_ms': 150
        }
        
        # Mock router
        mock_router_instance = Mock()
        mock_router.return_value = mock_router_instance
        mock_router_instance.route.return_value = RoutingDecision(
            provider='openai',
            model='gpt-4o',
            reason='Default model',
            estimated_cost_per_1k_tokens=0.00625,
            complexity_score=0.5
        )
        
        # Mock failover manager
        mock_failover_instance = Mock()
        mock_failover.return_value = mock_failover_instance
        
        llm_response = LLMResponse(
            content="Our return policy allows returns within 30 days of purchase.",
            model="gpt-4o",
            provider="openai",
            finish_reason="stop",
            input_tokens=200,
            output_tokens=50,
            total_tokens=250,
            estimated_cost=Decimal('0.002'),
            metadata={}
        )
        mock_failover_instance.execute_with_failover.return_value = (
            llm_response, 'openai', 'gpt-4o'
        )
        
        # Create service with mocked dependencies
        service = AIAgentService(
            context_builder=mock_context_instance,
            provider_router=mock_router_instance,
            failover_manager=mock_failover_instance
        )
        
        # Process message
        with patch.object(service, 'generate_suggestions', return_value={}):
            with patch.object(service, 'should_handoff', return_value=(False, '')):
                with patch.object(service, '_update_conversation_context'):
                    with patch.object(service, 'enhance_response_with_rich_message', side_effect=lambda response, **kwargs: response):
                        with patch.object(service, 'track_interaction', return_value=None):
                            response = service.process_message(
                                message=message,
                                conversation=conversation,
                                tenant=tenant
                            )
        
        # Verify RAG was used
        mock_retriever.create_for_tenant.assert_called_once_with(tenant)
        mock_retriever_instance.retrieve.assert_called_once()
        
        # Verify response was generated
        assert response is not None
        assert response.content is not None
        assert 'return policy' in response.content.lower()
        assert response.model_used == 'gpt-4o'
        assert response.provider == 'openai'


@pytest.mark.django_db
class TestRAGPromptIntegration:
    """Test RAG integration into prompts."""
    
    def test_rag_context_in_user_prompt(self, tenant, conversation, message):
        """Test that RAG context is included in user prompt."""
        from apps.bot.services.context_builder_service import AgentContext
        
        service = AIAgentService()
        
        context = AgentContext(
            conversation=conversation,
            current_message=message,
            conversation_history=[],
            relevant_knowledge=[],
            catalog_context=Mock(products=[], services=[]),
            customer_history={},
            context=None,
            context_size_tokens=100,
            truncated=False,
            metadata={
                'rag_context': {
                    'synthesized_text': 'Return policy: 30 days',
                    'document_results': [
                        {'content': 'Return policy details', 'source': 'FAQ.pdf'}
                    ],
                    'database_results': [],
                    'internet_results': []
                }
            }
        )
        
        # Build user prompt
        with patch('apps.bot.services.ai_agent_service.PromptTemplateManager.build_complete_user_prompt', return_value="Base prompt"):
            prompt = service._build_user_prompt(context, suggestions=None)
        
        # Verify RAG context is included
        assert '## Retrieved Information' in prompt
        assert 'Return policy: 30 days' in prompt
    
    def test_agent_can_do_cannot_do_in_system_prompt(self, tenant, agent_config):
        """Test that agent_can_do and agent_cannot_do are in system prompt."""
        from apps.bot.services.agent_config_service import AgentConfigurationService
        
        base_prompt = "You are an AI assistant."
        
        enhanced_prompt = AgentConfigurationService.apply_persona(
            base_prompt=base_prompt,
            config=agent_config
        )
        
        # Verify agent_can_do and agent_cannot_do are included
        assert '## What You CAN Do' in enhanced_prompt
        assert 'Answer questions about products, services, and policies' in enhanced_prompt
        assert '## What You CANNOT Do' in enhanced_prompt
        assert 'Process payments or access external systems' in enhanced_prompt
