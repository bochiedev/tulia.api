"""
Tests for AgentInteraction API endpoints.

Tests RBAC enforcement, tenant isolation, filtering, and statistics.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bot.models import AgentInteraction
from apps.messaging.models import Conversation, Message
from apps.tenants.models import Tenant, Customer
from apps.rbac.models import User, TenantUser, Role, Permission, RolePermission


@pytest.fixture
def tenant_a(db):
    """Create tenant A for testing."""
    return Tenant.objects.create(
        name="Tenant A",
        slug="tenant-a",
        status="active"
    )


@pytest.fixture
def tenant_b(db):
    """Create tenant B for testing."""
    return Tenant.objects.create(
        name="Tenant B",
        slug="tenant-b",
        status="active"
    )


@pytest.fixture
def user_a(db):
    """Create user for tenant A."""
    return User.objects.create(
        email="user_a@example.com",
        is_active=True
    )


@pytest.fixture
def user_b(db):
    """Create user for tenant B."""
    return User.objects.create(
        email="user_b@example.com",
        is_active=True
    )


@pytest.fixture
def analytics_permission(db):
    """Create analytics:view permission."""
    return Permission.objects.get_or_create(
        code="analytics:view",
        defaults={
            'label': "View Analytics",
            'description': "View analytics and reports",
            'category': "analytics"
        }
    )[0]


@pytest.fixture
def analyst_role_a(db, tenant_a, analytics_permission):
    """Create Analyst role for tenant A with analytics:view permission."""
    role = Role.objects.create(
        tenant=tenant_a,
        name="Analyst",
        description="Can view analytics",
        is_system=False
    )
    RolePermission.objects.create(
        role=role,
        permission=analytics_permission
    )
    return role


@pytest.fixture
def tenant_user_a(db, tenant_a, user_a, analyst_role_a):
    """Create tenant user A with analytics:view scope."""
    tenant_user = TenantUser.objects.create(
        tenant=tenant_a,
        user=user_a,
        invite_status="accepted"
    )
    tenant_user.roles.add(analyst_role_a)
    return tenant_user


@pytest.fixture
def tenant_user_b_no_scope(db, tenant_b, user_b):
    """Create tenant user B without analytics:view scope."""
    return TenantUser.objects.create(
        tenant=tenant_b,
        user=user_b,
        invite_status="accepted"
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
def conversation_a(db, tenant_a, customer_a):
    """Create conversation for tenant A."""
    return Conversation.objects.create(
        tenant=tenant_a,
        customer=customer_a,
        status="active"
    )


@pytest.fixture
def agent_interaction_a(db, conversation_a):
    """Create agent interaction for tenant A."""
    return AgentInteraction.objects.create(
        conversation=conversation_a,
        customer_message="What are your business hours?",
        detected_intents=[
            {"name": "business_hours", "confidence": 0.95}
        ],
        model_used="gpt-4o",
        context_size=500,
        processing_time_ms=1200,
        agent_response="We are open Monday-Friday 9am-5pm EST.",
        confidence_score=0.95,
        handoff_triggered=False,
        message_type="text",
        token_usage={
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150
        },
        estimated_cost=Decimal("0.000450")
    )


@pytest.fixture
def agent_interaction_low_confidence(db, conversation_a):
    """Create low confidence agent interaction for tenant A."""
    return AgentInteraction.objects.create(
        conversation=conversation_a,
        customer_message="I need help with something complex",
        detected_intents=[
            {"name": "general_inquiry", "confidence": 0.45}
        ],
        model_used="gpt-4o",
        context_size=300,
        processing_time_ms=1500,
        agent_response="I'm not sure I understand. Let me connect you with a human agent.",
        confidence_score=0.45,
        handoff_triggered=True,
        handoff_reason="low_confidence",
        message_type="text",
        token_usage={
            "prompt_tokens": 80,
            "completion_tokens": 40,
            "total_tokens": 120
        },
        estimated_cost=Decimal("0.000360")
    )


@pytest.fixture
def api_client():
    """Create API client."""
    return APIClient()


@pytest.mark.django_db
class TestAgentInteractionListView:
    """Tests for AgentInteractionListView."""
    
    def test_list_requires_analytics_view_scope(
        self, api_client, tenant_b, user_b, tenant_user_b_no_scope
    ):
        """Test that listing interactions requires analytics:view scope."""
        # User without analytics:view scope
        api_client.force_authenticate(user=user_b)
        
        response = api_client.get(
            '/v1/bot/interactions',
            HTTP_X_TENANT_ID=str(tenant_b.id)
        )
        
        assert response.status_code == 403
    
    def test_list_interactions_success(
        self, api_client, tenant_a, user_a, tenant_user_a, agent_interaction_a
    ):
        """Test successful listing of agent interactions."""
        api_client.force_authenticate(user=user_a)
        
        response = api_client.get(
            '/v1/bot/interactions',
            HTTP_X_TENANT_ID=str(tenant_a.id)
        )
        
        assert response.status_code == 200
        assert 'results' in response.data
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['id'] == str(agent_interaction_a.id)
    
    def test_list_interactions_tenant_isolation(
        self, api_client, tenant_a, tenant_b, user_a, tenant_user_a,
        agent_interaction_a, customer_a
    ):
        """Test that users can only see interactions from their tenant."""
        # Create interaction for tenant B
        customer_b = Customer.objects.create(
            tenant=tenant_b,
            phone_e164="+9876543210",
            name="Customer B"
        )
        conversation_b = Conversation.objects.create(
            tenant=tenant_b,
            customer=customer_b,
            status="active"
        )
        AgentInteraction.objects.create(
            conversation=conversation_b,
            customer_message="Test message",
            model_used="gpt-4o",
            agent_response="Test response",
            confidence_score=0.8,
            token_usage={"total_tokens": 100},
            estimated_cost=Decimal("0.000300")
        )
        
        # User A should only see tenant A's interaction
        api_client.force_authenticate(user=user_a)
        
        response = api_client.get(
            '/v1/bot/interactions',
            HTTP_X_TENANT_ID=str(tenant_a.id)
        )
        
        assert response.status_code == 200
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['id'] == str(agent_interaction_a.id)
    
    def test_filter_by_model(
        self, api_client, tenant_a, user_a, tenant_user_a,
        conversation_a, agent_interaction_a
    ):
        """Test filtering interactions by model."""
        # Create interaction with different model
        AgentInteraction.objects.create(
            conversation=conversation_a,
            customer_message="Another message",
            model_used="o1-preview",
            agent_response="Another response",
            confidence_score=0.9,
            token_usage={"total_tokens": 200},
            estimated_cost=Decimal("0.000600")
        )
        
        api_client.force_authenticate(user=user_a)
        
        response = api_client.get(
            '/v1/bot/interactions?model_used=gpt-4o',
            HTTP_X_TENANT_ID=str(tenant_a.id)
        )
        
        assert response.status_code == 200
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['model_used'] == 'gpt-4o'
    
    def test_filter_by_handoff_triggered(
        self, api_client, tenant_a, user_a, tenant_user_a,
        agent_interaction_a, agent_interaction_low_confidence
    ):
        """Test filtering interactions by handoff status."""
        api_client.force_authenticate(user=user_a)
        
        # Filter for handoffs
        response = api_client.get(
            '/v1/bot/interactions?handoff_triggered=true',
            HTTP_X_TENANT_ID=str(tenant_a.id)
        )
        
        assert response.status_code == 200
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['handoff_triggered'] is True
    
    def test_filter_by_confidence_range(
        self, api_client, tenant_a, user_a, tenant_user_a,
        agent_interaction_a, agent_interaction_low_confidence
    ):
        """Test filtering interactions by confidence score range."""
        api_client.force_authenticate(user=user_a)
        
        # Filter for high confidence
        response = api_client.get(
            '/v1/bot/interactions?min_confidence=0.7',
            HTTP_X_TENANT_ID=str(tenant_a.id)
        )
        
        assert response.status_code == 200
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['confidence_score'] >= 0.7
    
    def test_filter_by_date_range(
        self, api_client, tenant_a, user_a, tenant_user_a,
        agent_interaction_a
    ):
        """Test filtering interactions by date range."""
        api_client.force_authenticate(user=user_a)
        
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        
        response = api_client.get(
            f'/v1/bot/interactions?start_date={yesterday.isoformat()}&end_date={today.isoformat()}',
            HTTP_X_TENANT_ID=str(tenant_a.id)
        )
        
        assert response.status_code == 200
        assert len(response.data['results']) == 1


@pytest.mark.django_db
class TestAgentInteractionDetailView:
    """Tests for AgentInteractionDetailView."""
    
    def test_detail_requires_analytics_view_scope(
        self, api_client, tenant_b, user_b, tenant_user_b_no_scope,
        conversation_a, agent_interaction_a
    ):
        """Test that viewing interaction details requires analytics:view scope."""
        api_client.force_authenticate(user=user_b)
        
        response = api_client.get(
            f'/v1/bot/interactions/{agent_interaction_a.id}',
            HTTP_X_TENANT_ID=str(tenant_b.id)
        )
        
        assert response.status_code == 403
    
    def test_get_interaction_detail_success(
        self, api_client, tenant_a, user_a, tenant_user_a, agent_interaction_a
    ):
        """Test successful retrieval of interaction details."""
        api_client.force_authenticate(user=user_a)
        
        response = api_client.get(
            f'/v1/bot/interactions/{agent_interaction_a.id}',
            HTTP_X_TENANT_ID=str(tenant_a.id)
        )
        
        assert response.status_code == 200
        assert response.data['id'] == str(agent_interaction_a.id)
        assert response.data['customer_message'] == agent_interaction_a.customer_message
        assert response.data['agent_response'] == agent_interaction_a.agent_response
        assert 'total_tokens' in response.data
        assert 'intent_names' in response.data
    
    def test_get_interaction_detail_tenant_isolation(
        self, api_client, tenant_a, tenant_b, user_a, tenant_user_a,
        customer_a, conversation_a
    ):
        """Test that users cannot access interactions from other tenants."""
        # Create interaction for tenant B
        customer_b = Customer.objects.create(
            tenant=tenant_b,
            phone_e164="+9876543210",
            name="Customer B"
        )
        conversation_b = Conversation.objects.create(
            tenant=tenant_b,
            customer=customer_b,
            status="active"
        )
        interaction_b = AgentInteraction.objects.create(
            conversation=conversation_b,
            customer_message="Test message",
            model_used="gpt-4o",
            agent_response="Test response",
            confidence_score=0.8,
            token_usage={"total_tokens": 100},
            estimated_cost=Decimal("0.000300")
        )
        
        # User A tries to access tenant B's interaction
        api_client.force_authenticate(user=user_a)
        
        response = api_client.get(
            f'/v1/bot/interactions/{interaction_b.id}',
            HTTP_X_TENANT_ID=str(tenant_a.id)
        )
        
        assert response.status_code == 404
    
    def test_get_nonexistent_interaction(
        self, api_client, tenant_a, user_a, tenant_user_a
    ):
        """Test getting a nonexistent interaction returns 404."""
        api_client.force_authenticate(user=user_a)
        
        import uuid
        fake_id = uuid.uuid4()
        
        response = api_client.get(
            f'/v1/bot/interactions/{fake_id}',
            HTTP_X_TENANT_ID=str(tenant_a.id)
        )
        
        assert response.status_code == 404


@pytest.mark.django_db
class TestAgentInteractionStatsView:
    """Tests for AgentInteractionStatsView."""
    
    def test_stats_requires_analytics_view_scope(
        self, api_client, tenant_b, user_b, tenant_user_b_no_scope
    ):
        """Test that viewing stats requires analytics:view scope."""
        api_client.force_authenticate(user=user_b)
        
        response = api_client.get(
            '/v1/bot/interactions/stats',
            HTTP_X_TENANT_ID=str(tenant_b.id)
        )
        
        assert response.status_code == 403
    
    def test_get_stats_success(
        self, api_client, tenant_a, user_a, tenant_user_a,
        agent_interaction_a, agent_interaction_low_confidence
    ):
        """Test successful retrieval of interaction statistics."""
        api_client.force_authenticate(user=user_a)
        
        response = api_client.get(
            '/v1/bot/interactions/stats',
            HTTP_X_TENANT_ID=str(tenant_a.id)
        )
        
        assert response.status_code == 200
        assert response.data['total_interactions'] == 2
        assert 'total_cost' in response.data
        assert 'avg_confidence' in response.data
        assert response.data['handoff_count'] == 1
        assert 'handoff_rate' in response.data
        assert 'interactions_by_model' in response.data
        assert 'cost_by_model' in response.data
        assert 'high_confidence_count' in response.data
        assert 'low_confidence_count' in response.data
    
    def test_stats_tenant_isolation(
        self, api_client, tenant_a, tenant_b, user_a, tenant_user_a,
        agent_interaction_a
    ):
        """Test that stats only include data from the user's tenant."""
        # Create interaction for tenant B
        customer_b = Customer.objects.create(
            tenant=tenant_b,
            phone_e164="+9876543210",
            name="Customer B"
        )
        conversation_b = Conversation.objects.create(
            tenant=tenant_b,
            customer=customer_b,
            status="active"
        )
        AgentInteraction.objects.create(
            conversation=conversation_b,
            customer_message="Test message",
            model_used="gpt-4o",
            agent_response="Test response",
            confidence_score=0.8,
            token_usage={"total_tokens": 100},
            estimated_cost=Decimal("0.000300")
        )
        
        # User A should only see tenant A's stats
        api_client.force_authenticate(user=user_a)
        
        response = api_client.get(
            '/v1/bot/interactions/stats',
            HTTP_X_TENANT_ID=str(tenant_a.id)
        )
        
        assert response.status_code == 200
        assert response.data['total_interactions'] == 1
    
    def test_stats_with_date_range(
        self, api_client, tenant_a, user_a, tenant_user_a, agent_interaction_a
    ):
        """Test stats with custom date range."""
        api_client.force_authenticate(user=user_a)
        
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        
        response = api_client.get(
            f'/v1/bot/interactions/stats?start_date={yesterday.isoformat()}&end_date={today.isoformat()}',
            HTTP_X_TENANT_ID=str(tenant_a.id)
        )
        
        assert response.status_code == 200
        assert response.data['total_interactions'] == 1
    
    def test_stats_empty_result(
        self, api_client, tenant_a, user_a, tenant_user_a
    ):
        """Test stats with no interactions returns zero values."""
        api_client.force_authenticate(user=user_a)
        
        response = api_client.get(
            '/v1/bot/interactions/stats',
            HTTP_X_TENANT_ID=str(tenant_a.id)
        )
        
        assert response.status_code == 200
        assert response.data['total_interactions'] == 0
        assert response.data['total_cost'] == '0.000000'
        assert response.data['avg_confidence'] == 0.0
        assert response.data['handoff_count'] == 0
