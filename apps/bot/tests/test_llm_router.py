"""
Tests for LLM Router service.
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from django.utils import timezone

from apps.bot.services.llm_router import LLMRouter
from apps.bot.services.intent_detection_engine import Intent
from apps.bot.services.llm.base import LLMResponse
from apps.bot.models import AgentConfiguration
from apps.bot.models_sales_orchestration import LLMUsageLog


@pytest.fixture
def tenant(db):
    """Create a test tenant."""
    from apps.tenants.models import Tenant
    return Tenant.objects.create(
        name="Test Business",
        slug="test-business",
        whatsapp_number="+254712345678"
    )


@pytest.fixture
def agent_config(tenant):
    """Create agent configuration."""
    return AgentConfiguration.objects.create(
        tenant=tenant,
        monthly_llm_budget_usd=Decimal('10.00'),
        llm_budget_exceeded_action='fallback'
    )


@pytest.fixture
def mock_llm_response():
    """Create a mock LLM response."""
    return LLMResponse(
        content='{"intent": "BROWSE_PRODUCTS", "confidence": 0.85, "slots": {}}',
        model='gpt-4o-mini',
        provider='openai',
        input_tokens=50,
        output_tokens=20,
        total_tokens=70,
        estimated_cost=Decimal('0.00001'),
        finish_reason='stop',
        metadata={}
    )



@pytest.mark.django_db
class TestLLMRouter:
    """Test LLM Router functionality."""
    
    def test_router_initialization(self, tenant, agent_config):
        """Test router initializes correctly."""
        router = LLMRouter(tenant)
        
        assert router.tenant == tenant
        assert router.config == agent_config
        assert router._provider_cache == {}
    
    @patch('apps.bot.services.llm_router.LLMProviderFactory.create_from_tenant_settings')
    def test_model_selection(self, mock_factory, tenant, agent_config):
        """Test model selection logic."""
        router = LLMRouter(tenant)
        
        # Test intent classification task
        provider_name, model_name = router._select_model('intent_classification')
        assert provider_name == 'openai'
        assert model_name == 'gpt-4o-mini'
        
        # Test slot extraction task
        provider_name, model_name = router._select_model('slot_extraction')
        assert provider_name == 'openai'
        assert model_name == 'gpt-4o-mini'
        
        # Test RAG answer task
        provider_name, model_name = router._select_model('rag_answer')
        assert provider_name == 'openai'
        assert model_name == 'gpt-4o-mini'
    
    @patch('apps.bot.services.llm_router.LLMProviderFactory.create_from_tenant_settings')
    def test_budget_check_within_limit(self, mock_factory, tenant, agent_config):
        """Test budget check when within limit."""
        router = LLMRouter(tenant)
        
        # No usage yet, should be within budget
        assert router._check_budget() is True
    
    @patch('apps.bot.services.llm_router.LLMProviderFactory.create_from_tenant_settings')
    def test_budget_check_exceeded(self, mock_factory, tenant, agent_config):
        """Test budget check when exceeded."""
        # Create usage that exceeds budget
        now = timezone.now()
        LLMUsageLog.objects.create(
            tenant=tenant,
            model_name='gpt-4o-mini',
            task_type='intent_classification',
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            estimated_cost_usd=Decimal('15.00')  # Exceeds $10 budget
        )
        
        router = LLMRouter(tenant)
        assert router._check_budget() is False

    
    @patch('apps.bot.services.llm_router.LLMProviderFactory.create_from_tenant_settings')
    def test_classify_intent_success(self, mock_factory, tenant, agent_config, mock_llm_response):
        """Test successful intent classification."""
        # Mock provider
        mock_provider = Mock()
        mock_provider.generate.return_value = mock_llm_response
        mock_factory.return_value = mock_provider
        
        router = LLMRouter(tenant)
        
        result = router.classify_intent(
            text="What do you sell?",
            context={'current_flow': '', 'awaiting_response': False}
        )
        
        assert result['intent'] == 'BROWSE_PRODUCTS'
        assert result['confidence'] == 0.85
        assert 'slots' in result
        
        # Verify LLM was called
        mock_provider.generate.assert_called_once()
        
        # Verify usage was logged
        assert LLMUsageLog.objects.filter(tenant=tenant).count() == 1
        log = LLMUsageLog.objects.first()
        assert log.task_type == 'intent_classification'
        assert log.model_name == 'gpt-4o-mini'
    
    @patch('apps.bot.services.llm_router.LLMProviderFactory.create_from_tenant_settings')
    def test_classify_intent_budget_exceeded(self, mock_factory, tenant, agent_config):
        """Test intent classification when budget exceeded."""
        # Create usage that exceeds budget
        LLMUsageLog.objects.create(
            tenant=tenant,
            model_name='gpt-4o-mini',
            task_type='intent_classification',
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            estimated_cost_usd=Decimal('15.00')
        )
        
        router = LLMRouter(tenant)
        
        result = router.classify_intent(
            text="What do you sell?",
            context={'current_flow': '', 'awaiting_response': False}
        )
        
        assert result['intent'] == Intent.UNKNOWN.value
        assert result['confidence'] == 0.0
        assert result['budget_exceeded'] is True
        
        # Verify LLM was NOT called
        mock_factory.assert_not_called()
    
    @patch('apps.bot.services.llm_router.LLMProviderFactory.create_from_tenant_settings')
    def test_extract_slots_success(self, mock_factory, tenant, agent_config):
        """Test successful slot extraction."""
        # Mock provider with slot extraction response
        mock_provider = Mock()
        mock_response = LLMResponse(
            content='{"category": "shoes", "budget": 5000}',
            model='gpt-4o-mini',
            provider='openai',
            input_tokens=40,
            output_tokens=15,
            total_tokens=55,
            estimated_cost=Decimal('0.000008'),
            finish_reason='stop',
            metadata={}
        )
        mock_provider.generate.return_value = mock_response
        mock_factory.return_value = mock_provider
        
        router = LLMRouter(tenant)
        
        slots = router.extract_slots(
            text="I want shoes under 5000",
            intent=Intent.BROWSE_PRODUCTS,
            context={}
        )
        
        assert slots['category'] == 'shoes'
        assert slots['budget'] == 5000
        
        # Verify usage was logged
        assert LLMUsageLog.objects.filter(
            tenant=tenant,
            task_type='slot_extraction'
        ).count() == 1

    
    @patch('apps.bot.services.llm_router.LLMProviderFactory.create_from_tenant_settings')
    def test_generate_rag_answer_success(self, mock_factory, tenant, agent_config):
        """Test successful RAG answer generation."""
        # Mock provider with RAG response
        mock_provider = Mock()
        mock_response = LLMResponse(
            content='Our return policy allows returns within 14 days of purchase.',
            model='gpt-4o-mini',
            provider='openai',
            input_tokens=100,
            output_tokens=30,
            total_tokens=130,
            estimated_cost=Decimal('0.000025'),
            finish_reason='stop',
            metadata={}
        )
        mock_provider.generate.return_value = mock_response
        mock_factory.return_value = mock_provider
        
        router = LLMRouter(tenant)
        
        chunks = [
            {'text': 'We accept returns within 14 days of purchase.'},
            {'text': 'Items must be in original condition with tags.'}
        ]
        
        answer = router.generate_rag_answer(
            question="What is your return policy?",
            chunks=chunks,
            language=['en']
        )
        
        assert 'return policy' in answer.lower()
        assert '14 days' in answer.lower()
        
        # Verify usage was logged
        assert LLMUsageLog.objects.filter(
            tenant=tenant,
            task_type='rag_answer'
        ).count() == 1
    
    @patch('apps.bot.services.llm_router.LLMProviderFactory.create_from_tenant_settings')
    def test_usage_logging(self, mock_factory, tenant, agent_config, mock_llm_response):
        """Test that LLM usage is properly logged."""
        mock_provider = Mock()
        mock_provider.generate.return_value = mock_llm_response
        mock_factory.return_value = mock_provider
        
        router = LLMRouter(tenant)
        
        # Make a call
        router.classify_intent(
            text="Show me products",
            context={}
        )
        
        # Verify log was created
        logs = LLMUsageLog.objects.filter(tenant=tenant)
        assert logs.count() == 1
        
        log = logs.first()
        assert log.tenant == tenant
        assert log.model_name == 'gpt-4o-mini'
        assert log.task_type == 'intent_classification'
        assert log.input_tokens == 50
        assert log.output_tokens == 20
        assert log.total_tokens == 70
        assert log.estimated_cost_usd == Decimal('0.00001')
        assert log.prompt_template == 'intent_classification'
        assert len(log.response_preview) > 0
