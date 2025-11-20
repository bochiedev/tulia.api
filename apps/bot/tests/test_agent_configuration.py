"""
Tests for AgentConfiguration model, service, and API endpoints.
"""
import pytest
from django.core.cache import cache
from django.core.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate
from apps.bot.models import AgentConfiguration
from apps.bot.services import AgentConfigurationService
from apps.bot.bot_views import AgentConfigurationView
from apps.tenants.models import Tenant
from apps.rbac.models import User, TenantUser, Role, Permission, RolePermission, TenantUserRole


@pytest.fixture
def tenant(db):
    """Create a test tenant."""
    return Tenant.objects.create(
        name="Test Tenant",
        slug="test-tenant"
    )


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123"
    )


@pytest.fixture
def tenant_user_with_scope(db, tenant, user):
    """Create a tenant user with integrations:manage scope."""
    # Create permission
    permission = Permission.objects.get_or_create(
        code='integrations:manage',
        defaults={
            'label': 'Manage Integrations',
            'description': 'Manage integration settings',
            'category': 'integrations'
        }
    )[0]
    
    # Create or get role
    role, _ = Role.objects.get_or_create(
        tenant=tenant,
        name='Admin',
        defaults={'description': 'Administrator role'}
    )
    
    # Assign permission to role (if not already assigned)
    RolePermission.objects.get_or_create(
        role=role,
        permission=permission
    )
    
    # Create tenant user
    tenant_user = TenantUser.objects.create(
        tenant=tenant,
        user=user,
        invite_status='accepted'
    )
    
    # Assign role to tenant user
    TenantUserRole.objects.create(
        tenant_user=tenant_user,
        role=role
    )
    
    return tenant_user


@pytest.fixture
def request_factory():
    """Create API request factory for unit testing views."""
    return APIRequestFactory()


@pytest.mark.django_db
class TestAgentConfigurationModel:
    """Test AgentConfiguration model."""
    
    def test_create_agent_configuration(self, tenant):
        """Test creating an agent configuration."""
        config = AgentConfiguration.objects.create(
            tenant=tenant,
            agent_name="TestBot",
            tone="friendly"
        )
        
        assert config.id is not None
        assert config.tenant == tenant
        assert config.agent_name == "TestBot"
        assert config.tone == "friendly"
        assert config.default_model == "gpt-4o"
        assert config.confidence_threshold == 0.7
    
    def test_one_to_one_relationship(self, tenant):
        """Test that tenant can only have one configuration."""
        AgentConfiguration.objects.create(tenant=tenant)
        
        # Attempting to create another should raise error
        with pytest.raises(Exception):
            AgentConfiguration.objects.create(tenant=tenant)
    
    def test_get_personality_trait(self, tenant):
        """Test getting personality trait."""
        config = AgentConfiguration.objects.create(
            tenant=tenant,
            personality_traits={'helpful': True, 'patient': True}
        )
        
        assert config.get_personality_trait('helpful') is True
        assert config.get_personality_trait('patient') is True
        assert config.get_personality_trait('nonexistent') is None
        assert config.get_personality_trait('nonexistent', 'default') == 'default'
    
    def test_has_behavioral_restriction(self, tenant):
        """Test checking behavioral restrictions."""
        config = AgentConfiguration.objects.create(
            tenant=tenant,
            behavioral_restrictions=['politics', 'medical advice']
        )
        
        assert config.has_behavioral_restriction('politics') is True
        assert config.has_behavioral_restriction('POLITICS') is True  # Case insensitive
        assert config.has_behavioral_restriction('medical advice') is True
        assert config.has_behavioral_restriction('sports') is False
    
    def test_should_auto_handoff(self, tenant):
        """Test checking auto handoff topics."""
        config = AgentConfiguration.objects.create(
            tenant=tenant,
            auto_handoff_topics=['refund', 'complaint']
        )
        
        assert config.should_auto_handoff('refund') is True
        assert config.should_auto_handoff('REFUND') is True  # Case insensitive
        assert config.should_auto_handoff('complaint') is True
        assert config.should_auto_handoff('question') is False
    
    def test_get_fallback_model(self, tenant):
        """Test getting fallback models."""
        config = AgentConfiguration.objects.create(
            tenant=tenant,
            fallback_models=['gpt-4o-mini', 'gpt-3.5-turbo']
        )
        
        assert config.get_fallback_model(0) == 'gpt-4o-mini'
        assert config.get_fallback_model(1) == 'gpt-3.5-turbo'
        assert config.get_fallback_model(2) is None


@pytest.mark.django_db
class TestAgentConfigurationService:
    """Test AgentConfigurationService."""
    
    def setup_method(self):
        """Clear cache before each test."""
        cache.clear()
    
    def test_get_configuration(self, tenant):
        """Test getting configuration."""
        # Create configuration
        config = AgentConfiguration.objects.create(
            tenant=tenant,
            agent_name="TestBot"
        )
        
        # Get configuration
        retrieved = AgentConfigurationService.get_configuration(tenant)
        
        assert retrieved.id == config.id
        assert retrieved.agent_name == "TestBot"
    
    def test_get_configuration_caching(self, tenant):
        """Test that configuration is cached."""
        config = AgentConfiguration.objects.create(tenant=tenant)
        
        # First call - should hit database
        config1 = AgentConfigurationService.get_configuration(tenant)
        
        # Second call - should hit cache
        config2 = AgentConfigurationService.get_configuration(tenant)
        
        assert config1.id == config2.id
    
    def test_get_or_create_configuration(self, tenant):
        """Test getting or creating configuration."""
        # Should create default configuration
        config = AgentConfigurationService.get_or_create_configuration(tenant)
        
        assert config.id is not None
        assert config.tenant == tenant
        assert config.agent_name == "Assistant"
    
    def test_update_configuration(self, tenant):
        """Test updating configuration."""
        # Create initial configuration
        AgentConfiguration.objects.create(tenant=tenant)
        
        # Update configuration
        updated = AgentConfigurationService.update_configuration(
            tenant,
            {
                'agent_name': 'NewBot',
                'tone': 'professional',
                'confidence_threshold': 0.8
            }
        )
        
        assert updated.agent_name == 'NewBot'
        assert updated.tone == 'professional'
        assert updated.confidence_threshold == 0.8
    
    def test_update_configuration_validation(self, tenant):
        """Test that update validates data."""
        AgentConfiguration.objects.create(tenant=tenant)
        
        # Invalid temperature
        with pytest.raises(ValidationError):
            AgentConfigurationService.update_configuration(
                tenant,
                {'temperature': 3.0}  # Out of range
            )
        
        # Invalid confidence threshold
        with pytest.raises(ValidationError):
            AgentConfigurationService.update_configuration(
                tenant,
                {'confidence_threshold': 1.5}  # Out of range
            )
    
    def test_apply_persona(self, tenant):
        """Test applying persona to prompt."""
        config = AgentConfiguration.objects.create(
            tenant=tenant,
            agent_name="Sarah",
            tone="friendly",
            personality_traits={'helpful': True, 'empathetic': True},
            behavioral_restrictions=['politics'],
            required_disclaimers=['I am an AI assistant'],
            max_response_length=300,
            confidence_threshold=0.75
        )
        
        base_prompt = "You are a customer service assistant."
        enhanced = AgentConfigurationService.apply_persona(base_prompt, config)
        
        assert "Sarah" in enhanced
        assert "friendly" in enhanced.lower()
        assert "helpful" in enhanced
        assert "empathetic" in enhanced
        assert "politics" in enhanced
        assert "I am an AI assistant" in enhanced
        assert "300" in enhanced
        assert "75%" in enhanced
    
    def test_get_default_configuration(self, tenant):
        """Test creating default configuration."""
        config = AgentConfigurationService.get_default_configuration(tenant)
        
        assert config.agent_name == "Assistant"
        assert config.tone == "friendly"
        assert config.default_model == "gpt-4o"
        assert config.enable_proactive_suggestions is True
        assert config.enable_spelling_correction is True
        assert config.enable_rich_messages is True


@pytest.mark.django_db
class TestAgentConfigurationAPI:
    """Test AgentConfiguration API endpoints."""
    
    def setup_method(self):
        """Clear cache before each test."""
        cache.clear()
    
    def test_get_agent_config_requires_scope(self, request_factory, tenant, user):
        """Test that GET requires integrations:manage scope."""
        # Create tenant user WITHOUT scope
        tenant_user = TenantUser.objects.create(
            tenant=tenant,
            user=user,
            invite_status='accepted'
        )
        
        # Create request without required scope
        request = request_factory.get('/v1/bot/agent-config')
        force_authenticate(request, user=user)
        request.tenant = tenant
        request.membership = tenant_user
        request.scopes = set()  # No scopes
        
        # Should return 403 without required scope
        view = AgentConfigurationView.as_view()
        response = view(request)
        assert response.status_code == 403
    
    def test_get_agent_config_with_scope(self, request_factory, tenant, user, tenant_user_with_scope):
        """Test GET with proper scope."""
        # Create request with required scope
        request = request_factory.get('/v1/bot/agent-config')
        force_authenticate(request, user=user)
        request.tenant = tenant
        request.membership = tenant_user_with_scope
        request.scopes = {'integrations:manage'}
        
        # Should succeed with proper scope
        view = AgentConfigurationView.as_view()
        response = view(request)
        
        assert response.status_code == 200
        assert 'agent_name' in response.data
        assert 'default_model' in response.data
    
    def test_update_agent_config_requires_scope(self, request_factory, tenant, user):
        """Test that PUT requires integrations:manage scope."""
        # Create tenant user WITHOUT scope
        tenant_user = TenantUser.objects.create(
            tenant=tenant,
            user=user,
            invite_status='accepted'
        )
        
        # Create request without required scope
        request = request_factory.put(
            '/v1/bot/agent-config',
            {'agent_name': 'NewBot'},
            format='json'
        )
        force_authenticate(request, user=user)
        request.tenant = tenant
        request.membership = tenant_user
        request.scopes = set()  # No scopes
        
        # Should return 403 without required scope
        view = AgentConfigurationView.as_view()
        response = view(request)
        assert response.status_code == 403
    
    def test_update_agent_config_with_scope(self, request_factory, tenant, user, tenant_user_with_scope):
        """Test PUT with proper scope."""
        # Create request with required scope
        request = request_factory.put(
            '/v1/bot/agent-config',
            {
                'agent_name': 'Sarah',
                'tone': 'professional',
                'confidence_threshold': 0.8
            },
            format='json'
        )
        force_authenticate(request, user=user)
        request.tenant = tenant
        request.membership = tenant_user_with_scope
        request.scopes = {'integrations:manage'}
        
        # Should succeed with proper scope
        view = AgentConfigurationView.as_view()
        response = view(request)
        
        assert response.status_code == 200
        assert response.data['agent_name'] == 'Sarah'
        assert response.data['tone'] == 'professional'
        assert response.data['confidence_threshold'] == 0.8
    
    def test_update_agent_config_validation(self, request_factory, tenant, user, tenant_user_with_scope):
        """Test that API validates configuration data."""
        # Create request with invalid data
        request = request_factory.put(
            '/v1/bot/agent-config',
            {'temperature': 3.0},
            format='json'
        )
        force_authenticate(request, user=user)
        request.tenant = tenant
        request.membership = tenant_user_with_scope
        request.scopes = {'integrations:manage'}
        
        # Should return 400 for invalid data
        view = AgentConfigurationView.as_view()
        response = view(request)
        
        assert response.status_code == 400
        assert 'temperature' in response.data
    
    def test_update_agent_config_partial(self, request_factory, tenant, user, tenant_user_with_scope):
        """Test partial update of configuration."""
        # Create initial configuration
        AgentConfiguration.objects.create(
            tenant=tenant,
            agent_name="OldBot",
            tone="casual"
        )
        
        # Create request for partial update
        request = request_factory.put(
            '/v1/bot/agent-config',
            {'agent_name': 'NewBot'},
            format='json'
        )
        force_authenticate(request, user=user)
        request.tenant = tenant
        request.membership = tenant_user_with_scope
        request.scopes = {'integrations:manage'}
        
        # Should succeed and preserve unchanged fields
        view = AgentConfigurationView.as_view()
        response = view(request)
        
        assert response.status_code == 200
        assert response.data['agent_name'] == 'NewBot'
        assert response.data['tone'] == 'casual'  # Should remain unchanged
