"""
Tests for multi-provider LLM support and feedback collection system.

Tests Tasks 38-39 implementations.
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from django.utils import timezone
from unittest.mock import Mock, patch, MagicMock

from apps.bot.services.llm.provider_router import ProviderRouter, RoutingDecision
from apps.bot.services.llm.failover_manager import ProviderFailoverManager
from apps.bot.models_provider_tracking import ProviderUsage, ProviderDailySummary
from apps.bot.models_feedback import InteractionFeedback, HumanCorrection


@pytest.mark.django_db
class TestProviderRouter:
    """Test smart provider routing logic."""
    
    def test_simple_query_routes_to_gemini_flash(self):
        """Test that simple queries route to Gemini Flash."""
        router = ProviderRouter()
        
        messages = [
            {'role': 'user', 'content': 'Hi'}
        ]
        
        decision = router.route(messages)
        
        assert decision.provider == 'gemini'
        assert decision.model == 'gemini-1.5-flash'
        assert decision.complexity_score < 0.3
    
    def test_complex_query_routes_to_o1(self):
        """Test that complex queries route to O1."""
        router = ProviderRouter()
        
        messages = [
            {'role': 'user', 'content': 
             'Analyze the following complex algorithm and explain its time complexity, '
             'space complexity, and provide a detailed proof of correctness. '
             'Compare it with alternative approaches and recommend optimizations.'}
        ]
        
        decision = router.route(messages)
        
        assert decision.provider == 'openai'
        assert decision.model == 'o1-preview'
        assert decision.complexity_score > 0.7
    
    def test_large_context_routes_to_gemini_pro(self):
        """Test that large context routes to Gemini Pro."""
        router = ProviderRouter()
        
        # Create large context
        large_message = 'x' * 500000  # ~125K tokens
        messages = [
            {'role': 'user', 'content': large_message}
        ]
        
        decision = router.route(messages, context_size=125000)
        
        assert decision.provider == 'gemini'
        assert decision.model == 'gemini-1.5-pro'
    
    def test_default_routing(self):
        """Test default routing for medium complexity."""
        router = ProviderRouter()
        
        messages = [
            {'role': 'user', 'content': 'What are the benefits of using Django?'}
        ]
        
        decision = router.route(messages)
        
        assert decision.provider == 'openai'
        assert decision.model == 'gpt-4o'
        assert 0.3 <= decision.complexity_score <= 0.7
    
    def test_complexity_calculation(self):
        """Test complexity score calculation."""
        router = ProviderRouter()
        
        # Simple message
        simple = [{'role': 'user', 'content': 'Hello'}]
        simple_score = router.calculate_complexity(simple)
        assert simple_score < 0.3
        
        # Complex message with keywords
        complex_msg = [
            {'role': 'user', 'content': 
             'Analyze and compare these algorithms, explain the reasoning, '
             'and provide a comprehensive technical evaluation.'}
        ]
        complex_score = router.calculate_complexity(complex_msg)
        assert complex_score > 0.5
    
    def test_preferred_provider_override(self):
        """Test that preferred provider overrides routing."""
        router = ProviderRouter()
        
        messages = [{'role': 'user', 'content': 'Hi'}]
        
        decision = router.route(
            messages,
            preferred_provider='openai',
            preferred_model='gpt-4o-mini'
        )
        
        assert decision.provider == 'openai'
        assert decision.model == 'gpt-4o-mini'


@pytest.mark.django_db
class TestProviderFailover:
    """Test provider failover mechanism."""
    
    def test_failover_manager_initialization(self):
        """Test failover manager initialization."""
        manager = ProviderFailoverManager()
        
        assert len(manager.fallback_order) > 0
        assert manager.timeout == 30
        assert manager.provider_stats == {}
    
    def test_provider_health_tracking(self):
        """Test provider health tracking."""
        manager = ProviderFailoverManager()
        
        # Record successes
        for _ in range(10):
            manager._record_success('openai')
        
        # Record failures
        for _ in range(2):
            manager._record_failure('openai')
        
        # Check health
        assert manager._is_provider_healthy('openai')
        
        # Record more failures
        for _ in range(10):
            manager._record_failure('gemini')
        
        # Should be unhealthy
        assert not manager._is_provider_healthy('gemini')
    
    def test_health_stats_retrieval(self):
        """Test getting provider health stats."""
        manager = ProviderFailoverManager()
        
        manager._record_success('openai')
        manager._record_success('openai')
        manager._record_failure('openai')
        
        health = manager.get_provider_health()
        
        assert 'openai' in health
        assert health['openai']['total_calls'] == 3
        assert health['openai']['success_count'] == 2
        assert health['openai']['failure_count'] == 1
        assert health['openai']['success_rate'] == pytest.approx(0.666, rel=0.01)
    
    def test_reset_provider_stats(self):
        """Test resetting provider stats."""
        manager = ProviderFailoverManager()
        
        manager._record_success('openai')
        manager._record_failure('openai')
        
        manager.reset_provider_stats('openai')
        
        stats = manager.provider_stats.get('openai', {})
        assert stats.get('success', 0) == 0
        assert stats.get('failure', 0) == 0


@pytest.mark.django_db
class TestProviderTracking:
    """Test provider usage tracking models."""
    
    def test_provider_usage_creation(self, tenant, conversation):
        """Test creating provider usage record."""
        from apps.bot.models import AgentInteraction
        
        interaction = AgentInteraction.objects.create(
            tenant=tenant,
            conversation=conversation,
            customer_message='Test',
            agent_response='Response',
            model_used='gpt-4o',
            confidence_score=0.9
        )
        
        usage = ProviderUsage.objects.create(
            tenant=tenant,
            conversation=conversation,
            agent_interaction=interaction,
            provider='openai',
            model='gpt-4o',
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            estimated_cost=Decimal('0.001'),
            latency_ms=500,
            success=True,
            routing_reason='Default routing',
            complexity_score=0.5
        )
        
        assert usage.provider == 'openai'
        assert usage.total_tokens == 150
        assert usage.success is True
    
    def test_provider_daily_summary_properties(self, tenant):
        """Test daily summary calculated properties."""
        summary = ProviderDailySummary.objects.create(
            tenant=tenant,
            date=date.today(),
            provider='openai',
            model='gpt-4o',
            total_calls=100,
            successful_calls=90,
            failed_calls=10,
            total_cost=Decimal('1.50')
        )
        
        assert summary.success_rate == 0.9
        assert summary.failure_rate == 0.1
        assert summary.avg_cost_per_call == Decimal('0.015')


@pytest.mark.django_db
class TestFeedbackModels:
    """Test feedback collection models."""
    
    def test_interaction_feedback_creation(self, tenant, conversation, customer):
        """Test creating interaction feedback."""
        from apps.bot.models import AgentInteraction
        
        interaction = AgentInteraction.objects.create(
            tenant=tenant,
            conversation=conversation,
            customer_message='Test',
            agent_response='Response',
            model_used='gpt-4o',
            confidence_score=0.9
        )
        
        feedback = InteractionFeedback.objects.create(
            tenant=tenant,
            agent_interaction=interaction,
            conversation=conversation,
            customer=customer,
            rating='helpful',
            feedback_text='Great response!',
            user_continued=True,
            completed_action=True,
            response_time_seconds=15
        )
        
        assert feedback.rating == 'helpful'
        assert feedback.user_continued is True
        assert feedback.completed_action is True
    
    def test_implicit_satisfaction_score(self, tenant, conversation, customer):
        """Test implicit satisfaction score calculation."""
        from apps.bot.models import AgentInteraction
        
        interaction = AgentInteraction.objects.create(
            tenant=tenant,
            conversation=conversation,
            customer_message='Test',
            agent_response='Response',
            model_used='gpt-4o',
            confidence_score=0.9
        )
        
        # Positive signals
        feedback = InteractionFeedback.objects.create(
            tenant=tenant,
            agent_interaction=interaction,
            conversation=conversation,
            customer=customer,
            rating='helpful',
            user_continued=True,
            completed_action=True,
            response_time_seconds=20
        )
        
        score = feedback.implicit_satisfaction_score
        assert score > 0.5  # Should be high
        
        # Negative signals
        feedback2 = InteractionFeedback.objects.create(
            tenant=tenant,
            agent_interaction=interaction,
            conversation=conversation,
            customer=customer,
            rating='not_helpful',
            requested_human=True,
            response_time_seconds=120
        )
        
        score2 = feedback2.implicit_satisfaction_score
        assert score2 < 0.5  # Should be low
    
    def test_human_correction_creation(self, tenant, conversation, user):
        """Test creating human correction."""
        from apps.bot.models import AgentInteraction
        
        interaction = AgentInteraction.objects.create(
            tenant=tenant,
            conversation=conversation,
            customer_message='What is your return policy?',
            agent_response='I don\'t know.',
            model_used='gpt-4o',
            confidence_score=0.3
        )
        
        correction = HumanCorrection.objects.create(
            tenant=tenant,
            agent_interaction=interaction,
            conversation=conversation,
            bot_response='I don\'t know.',
            human_response='Our return policy allows returns within 30 days...',
            correction_reason='Bot lacked knowledge about return policy',
            correction_category='missing_information',
            corrected_by=user
        )
        
        assert correction.correction_category == 'missing_information'
        assert correction.approved_for_training is False
        
        # Approve for training
        correction.approved_for_training = True
        correction.approved_by = user
        correction.approved_at = timezone.now()
        correction.quality_score = 4.5
        correction.save()
        
        assert correction.approved_for_training is True
        assert correction.quality_score == 4.5


@pytest.mark.django_db
class TestFeedbackAPI:
    """Test feedback API endpoints."""
    
    def test_submit_feedback(self, api_client, tenant, conversation, customer):
        """Test submitting feedback via API."""
        from apps.bot.models import AgentInteraction
        
        interaction = AgentInteraction.objects.create(
            tenant=tenant,
            conversation=conversation,
            customer_message='Test',
            agent_response='Response',
            model_used='gpt-4o',
            confidence_score=0.9
        )
        
        response = api_client.post(
            '/v1/bot/feedback/submit/',
            {
                'agent_interaction_id': interaction.id,
                'rating': 'helpful',
                'feedback_text': 'Very helpful!'
            },
            format='json'
        )
        
        assert response.status_code == 201
        assert InteractionFeedback.objects.filter(
            agent_interaction=interaction
        ).exists()
    
    def test_feedback_analytics(self, authenticated_api_client, tenant, conversation, customer):
        """Test feedback analytics endpoint."""
        from apps.bot.models import AgentInteraction
        
        # Create some feedback
        for i in range(10):
            interaction = AgentInteraction.objects.create(
                tenant=tenant,
                conversation=conversation,
                customer_message=f'Test {i}',
                agent_response=f'Response {i}',
                model_used='gpt-4o',
                confidence_score=0.9
            )
            
            InteractionFeedback.objects.create(
                tenant=tenant,
                agent_interaction=interaction,
                conversation=conversation,
                customer=customer,
                rating='helpful' if i < 8 else 'not_helpful',
                user_continued=True
            )
        
        response = authenticated_api_client.get(
            '/v1/bot/feedback/analytics/',
            HTTP_X_TENANT_ID=str(tenant.id),
            HTTP_X_TENANT_API_KEY='test-key'
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['total_feedback'] == 10
        assert data['helpful_count'] == 8
        assert data['not_helpful_count'] == 2
        assert data['helpful_rate'] == 0.8


# Fixtures
@pytest.fixture
def tenant(db):
    """Create test tenant."""
    from apps.tenants.models import Tenant
    return Tenant.objects.create(name='Test Tenant')


@pytest.fixture
def user(db):
    """Create test user."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def customer(db, tenant):
    """Create test customer."""
    from apps.messaging.models import Customer
    return Customer.objects.create(
        tenant=tenant,
        phone_e164='+1234567890',
        name='Test Customer'
    )


@pytest.fixture
def conversation(db, tenant, customer):
    """Create test conversation."""
    from apps.messaging.models import Conversation
    return Conversation.objects.create(
        tenant=tenant,
        customer=customer,
        status='active'
    )


@pytest.fixture
def api_client():
    """Create API client."""
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def authenticated_api_client(api_client, user, tenant):
    """Create authenticated API client."""
    api_client.force_authenticate(user=user)
    return api_client
