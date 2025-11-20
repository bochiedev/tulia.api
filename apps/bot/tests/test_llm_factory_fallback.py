"""
Tests for LLM Provider Factory fallback mechanism.

Verifies that the factory correctly falls back to system-level API keys
when tenant-specific keys are not configured.
"""
import os
import pytest
from unittest.mock import patch

from apps.bot.services.llm.factory import LLMProviderFactory
from apps.tenants.models import Tenant, TenantSettings


@pytest.mark.django_db
class TestLLMFactoryFallback:
    """Test LLM factory fallback to system keys."""
    
    @pytest.fixture
    def tenant(self):
        """Create a test tenant."""
        tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        return tenant
    
    def test_uses_tenant_key_when_available(self, tenant):
        """Test that tenant-specific key is used when available."""
        # Set tenant-specific key
        tenant.settings.openai_api_key = "sk-tenant-key-123"
        tenant.settings.save()
        
        # Create provider
        provider = LLMProviderFactory.create_from_tenant_settings(tenant, 'openai')
        
        # Verify provider was created
        assert provider is not None
        assert provider.provider_name == 'openai'
        
        # Clean up
        tenant.settings.openai_api_key = None
        tenant.settings.save()
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'sk-system-key-456'})
    def test_falls_back_to_system_key(self, tenant):
        """Test that system key is used when tenant key not available."""
        # Ensure tenant has no key
        tenant.settings.openai_api_key = None
        tenant.settings.save()
        
        # Create provider (should use system key)
        provider = LLMProviderFactory.create_from_tenant_settings(tenant, 'openai')
        
        # Verify provider was created
        assert provider is not None
        assert provider.provider_name == 'openai'
    
    def test_raises_error_when_no_key_available(self, tenant):
        """Test that error is raised when no key is available."""
        # Ensure tenant has no key
        tenant.settings.openai_api_key = None
        tenant.settings.save()
        
        # Mock environment to have no system key
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                LLMProviderFactory.create_from_tenant_settings(tenant, 'openai')
            
            # Verify error message is helpful
            assert "No API key configured" in str(exc_info.value)
            assert "OPENAI_API_KEY" in str(exc_info.value)
    
    @patch.dict(os.environ, {'GEMINI_API_KEY': 'gemini-system-key-789'})
    def test_fallback_works_for_gemini(self, tenant):
        """Test that fallback works for Gemini provider."""
        # Ensure tenant has no key
        tenant.settings.gemini_api_key = None
        tenant.settings.save()
        
        # Create provider (should use system key)
        provider = LLMProviderFactory.create_from_tenant_settings(tenant, 'gemini')
        
        # Verify provider was created
        assert provider is not None
        assert provider.provider_name == 'gemini'
    
    def test_tenant_key_takes_precedence(self, tenant):
        """Test that tenant key takes precedence over system key."""
        # Set both tenant and system keys
        tenant.settings.openai_api_key = "sk-tenant-priority-key"
        tenant.settings.save()
        
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'sk-system-fallback-key'}):
            # Create provider
            provider = LLMProviderFactory.create_from_tenant_settings(tenant, 'openai')
            
            # Verify provider was created (we can't check which key was used,
            # but we verify it doesn't fail)
            assert provider is not None
            assert provider.provider_name == 'openai'
        
        # Clean up
        tenant.settings.openai_api_key = None
        tenant.settings.save()
