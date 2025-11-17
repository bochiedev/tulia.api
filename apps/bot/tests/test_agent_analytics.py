"""
Tests for agent analytics endpoints.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from django.urls import reverse
from rest_framework import status
from apps.bot.models import AgentInteraction
from apps.messaging.models import Conversation, Message


@pytest.mark.django_db
class TestAgentAnalyticsEndpoints:
    """Test agent analytics API endpoints."""
    
    def test_conversation_statistics_empty(self, api_client, tenant, tenant_user):
        """Test conversation statistics with no data."""
        url = reverse('bot:analytics-conversations')
        
        response = api_client.get(
            url,
            headers={
                'X-TENANT-ID': str(tenant.id),
                'X-TENANT-API-KEY': 'test-key'
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['total_interactions'] == 0
        assert data['total_conversations'] == 0
        assert data['average_confidence'] == 0.0
    
    def test_conversation_statistics_with_data(
        self, api_client, tenant, tenant_user, customer, conversation
    ):
        """Test conversation statistics with interaction data."""
        # Create test interactions
        message = Message.objects.create(
            conversation=conversation,
            direction='in',
            text='Test message',
            from_number=customer.phone_e164,
            to_number=tenant.settings.twilio_phone_number
        )
        
        AgentInteraction.objects.create(
            conversation=conversation,
            customer_message='Test message',
            detected_intents=[{'name': 'test_intent', 'confidence': 0.9}],
            model_used='gpt-4o',
            context_size=1000,
            processing_time_ms=500,
            agent_response='Test response',
            confidence_score=0.85,
            handoff_triggered=False,
            message_type='text',
            token_usage={'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150},
            estimated_cost=Decimal('0.001')
        )
        
        url = reverse('bot:analytics-conversations')
        
        response = api_client.get(
            url,
            headers={
                'X-TENANT-ID': str(tenant.id),
                'X-TENANT-API-KEY': 'test-key'
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['total_interactions'] == 1
        assert data['total_conversations'] == 1
        assert data['average_confidence'] == 0.85
        assert data['message_type_distribution']['text'] == 1
    
    def test_handoff_analytics(self, api_client, tenant, tenant_user, customer, conversation):
        """Test handoff analytics endpoint."""
        # Create interaction with handoff
        AgentInteraction.objects.create(
            conversation=conversation,
            customer_message='I need to speak to a human',
            detected_intents=[],
            model_used='gpt-4o',
            context_size=500,
            processing_time_ms=300,
            agent_response='Let me connect you with an agent',
            confidence_score=0.95,
            handoff_triggered=True,
            handoff_reason='customer_requested_human',
            message_type='text',
            token_usage={'total_tokens': 100},
            estimated_cost=Decimal('0.0005')
        )
        
        url = reverse('bot:analytics-handoffs')
        
        response = api_client.get(
            url,
            headers={
                'X-TENANT-ID': str(tenant.id),
                'X-TENANT-API-KEY': 'test-key'
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['total_handoffs'] == 1
        assert data['handoff_rate'] > 0
        assert 'customer_requested_human' in data['handoff_reasons']
    
    def test_cost_analytics(self, api_client, tenant, tenant_user, customer, conversation):
        """Test cost analytics endpoint."""
        # Create interactions with different models
        AgentInteraction.objects.create(
            conversation=conversation,
            customer_message='Test 1',
            detected_intents=[],
            model_used='gpt-4o',
            context_size=1000,
            processing_time_ms=500,
            agent_response='Response 1',
            confidence_score=0.8,
            message_type='text',
            token_usage={'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150},
            estimated_cost=Decimal('0.002')
        )
        
        AgentInteraction.objects.create(
            conversation=conversation,
            customer_message='Test 2',
            detected_intents=[],
            model_used='gpt-4o-mini',
            context_size=500,
            processing_time_ms=300,
            agent_response='Response 2',
            confidence_score=0.75,
            message_type='text',
            token_usage={'prompt_tokens': 50, 'completion_tokens': 25, 'total_tokens': 75},
            estimated_cost=Decimal('0.0005')
        )
        
        url = reverse('bot:analytics-costs')
        
        response = api_client.get(
            url,
            headers={
                'X-TENANT-ID': str(tenant.id),
                'X-TENANT-API-KEY': 'test-key'
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['total_tokens'] == 225
        assert float(data['total_cost']) == 0.0025
        assert 'gpt-4o' in data['cost_by_model']
        assert 'gpt-4o-mini' in data['cost_by_model']
    
    def test_topics_analytics(self, api_client, tenant, tenant_user, customer, conversation):
        """Test topics analytics endpoint."""
        # Create interactions with different intents
        AgentInteraction.objects.create(
            conversation=conversation,
            customer_message='Show me products',
            detected_intents=[{'name': 'browse_products', 'confidence': 0.9}],
            model_used='gpt-4o',
            context_size=500,
            processing_time_ms=400,
            agent_response='Here are our products',
            confidence_score=0.9,
            message_type='text',
            token_usage={'total_tokens': 100},
            estimated_cost=Decimal('0.001')
        )
        
        AgentInteraction.objects.create(
            conversation=conversation,
            customer_message='I want to book an appointment',
            detected_intents=[{'name': 'book_appointment', 'confidence': 0.85}],
            model_used='gpt-4o',
            context_size=600,
            processing_time_ms=450,
            agent_response='Let me help you book',
            confidence_score=0.85,
            message_type='text',
            token_usage={'total_tokens': 120},
            estimated_cost=Decimal('0.0012')
        )
        
        url = reverse('bot:analytics-topics')
        
        response = api_client.get(
            url,
            headers={
                'X-TENANT-ID': str(tenant.id),
                'X-TENANT-API-KEY': 'test-key'
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['total_unique_intents'] == 2
        assert len(data['common_intents']) == 2
        
        # Check intent structure
        intent = data['common_intents'][0]
        assert 'intent' in intent
        assert 'count' in intent
        assert 'percentage' in intent
    
    def test_analytics_requires_scope(self, api_client, tenant, tenant_user_no_scopes):
        """Test that analytics endpoints require analytics:view scope."""
        endpoints = [
            'bot:analytics-conversations',
            'bot:analytics-handoffs',
            'bot:analytics-costs',
            'bot:analytics-topics',
        ]
        
        for endpoint_name in endpoints:
            url = reverse(endpoint_name)
            
            response = api_client.get(
                url,
                headers={
                    'X-TENANT-ID': str(tenant.id),
                    'X-TENANT-API-KEY': 'test-key-no-scopes'
                }
            )
            
            assert response.status_code == status.HTTP_403_FORBIDDEN, \
                f"Endpoint {endpoint_name} should require analytics:view scope"
    
    def test_date_range_filtering(self, api_client, tenant, tenant_user, customer, conversation):
        """Test date range filtering in analytics."""
        # Create interaction from yesterday
        yesterday = datetime.now() - timedelta(days=1)
        interaction = AgentInteraction.objects.create(
            conversation=conversation,
            customer_message='Test',
            detected_intents=[],
            model_used='gpt-4o',
            context_size=500,
            processing_time_ms=300,
            agent_response='Response',
            confidence_score=0.8,
            message_type='text',
            token_usage={'total_tokens': 100},
            estimated_cost=Decimal('0.001')
        )
        interaction.created_at = yesterday
        interaction.save()
        
        url = reverse('bot:analytics-conversations')
        
        # Query for today only (should return 0)
        today = datetime.now().date()
        response = api_client.get(
            url,
            {
                'start_date': today.isoformat(),
                'end_date': today.isoformat()
            },
            headers={
                'X-TENANT-ID': str(tenant.id),
                'X-TENANT-API-KEY': 'test-key'
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['total_interactions'] == 0
        
        # Query for yesterday (should return 1)
        yesterday_date = yesterday.date()
        response = api_client.get(
            url,
            {
                'start_date': yesterday_date.isoformat(),
                'end_date': yesterday_date.isoformat()
            },
            headers={
                'X-TENANT-ID': str(tenant.id),
                'X-TENANT-API-KEY': 'test-key'
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['total_interactions'] == 1
