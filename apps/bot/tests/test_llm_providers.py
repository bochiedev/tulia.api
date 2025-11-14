"""
Tests for LLM Provider abstraction layer.
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

from apps.bot.services.llm import (
    LLMProvider,
    LLMResponse,
    ModelInfo,
    OpenAIProvider,
    LLMProviderFactory
)


class TestLLMProviderBase:
    """Test base LLM provider interface."""
    
    def test_llm_response_dataclass(self):
        """Test LLMResponse dataclass creation."""
        response = LLMResponse(
            content="Hello, world!",
            model="gpt-4o",
            provider="openai",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            estimated_cost=Decimal("0.001"),
            finish_reason="stop",
            metadata={"test": "data"}
        )
        
        assert response.content == "Hello, world!"
        assert response.model == "gpt-4o"
        assert response.provider == "openai"
        assert response.input_tokens == 10
        assert response.output_tokens == 5
        assert response.total_tokens == 15
        assert response.estimated_cost == Decimal("0.001")
        assert response.finish_reason == "stop"
        assert response.metadata == {"test": "data"}
    
    def test_model_info_dataclass(self):
        """Test ModelInfo dataclass creation."""
        model = ModelInfo(
            name="gpt-4o",
            display_name="GPT-4o",
            provider="openai",
            context_window=128000,
            input_cost_per_1k=Decimal("0.0025"),
            output_cost_per_1k=Decimal("0.01"),
            capabilities=["chat", "function_calling"],
            description="Test model"
        )
        
        assert model.name == "gpt-4o"
        assert model.display_name == "GPT-4o"
        assert model.provider == "openai"
        assert model.context_window == 128000
        assert model.input_cost_per_1k == Decimal("0.0025")
        assert model.output_cost_per_1k == Decimal("0.01")
        assert "chat" in model.capabilities
        assert model.description == "Test model"


class TestOpenAIProvider:
    """Test OpenAI provider implementation."""
    
    def test_initialization(self):
        """Test OpenAI provider initialization."""
        provider = OpenAIProvider(api_key="test-key")
        
        assert provider.api_key == "test-key"
        assert provider.provider_name == "openai"
        assert provider.client is not None
    
    def test_initialization_with_config(self):
        """Test OpenAI provider initialization with custom config."""
        provider = OpenAIProvider(
            api_key="test-key",
            timeout=30.0,
            max_retries=5
        )
        
        assert provider.api_key == "test-key"
        assert provider.max_retries == 5
    
    def test_get_available_models(self):
        """Test getting available models."""
        provider = OpenAIProvider(api_key="test-key")
        models = provider.get_available_models()
        
        assert len(models) > 0
        assert all(isinstance(m, ModelInfo) for m in models)
        
        # Check specific models exist
        model_names = [m.name for m in models]
        assert "gpt-4o" in model_names
        assert "gpt-4o-mini" in model_names
        assert "o1-preview" in model_names
        assert "o1-mini" in model_names
    
    def test_model_configurations(self):
        """Test that model configurations are properly defined."""
        provider = OpenAIProvider(api_key="test-key")
        
        # Check GPT-4o configuration
        assert "gpt-4o" in provider.MODELS
        gpt4o = provider.MODELS["gpt-4o"]
        assert gpt4o["context_window"] == 128000
        assert gpt4o["input_cost_per_1k"] > 0
        assert gpt4o["output_cost_per_1k"] > 0
        assert "chat" in gpt4o["capabilities"]
        
        # Check o1-preview configuration
        assert "o1-preview" in provider.MODELS
        o1_preview = provider.MODELS["o1-preview"]
        assert "reasoning" in o1_preview["capabilities"]
    
    def test_calculate_cost(self):
        """Test cost calculation."""
        provider = OpenAIProvider(api_key="test-key")
        
        # Test GPT-4o cost calculation
        cost = provider._calculate_cost("gpt-4o", 1000, 500)
        expected = (Decimal("1000") / 1000 * Decimal("0.0025")) + \
                   (Decimal("500") / 1000 * Decimal("0.01"))
        assert cost == expected
        
        # Test unknown model returns 0
        cost = provider._calculate_cost("unknown-model", 1000, 500)
        assert cost == Decimal("0")
    
    def test_calculate_retry_delay(self):
        """Test exponential backoff calculation."""
        provider = OpenAIProvider(api_key="test-key")
        
        # Test exponential backoff
        delay1 = provider._calculate_retry_delay(1)
        delay2 = provider._calculate_retry_delay(2)
        delay3 = provider._calculate_retry_delay(3)
        
        assert delay1 == 1.0
        assert delay2 == 2.0
        assert delay3 == 4.0
        
        # Test max delay cap
        delay_large = provider._calculate_retry_delay(10)
        assert delay_large <= provider.MAX_RETRY_DELAY
    
    @patch('apps.bot.services.llm.openai_provider.OpenAI')
    def test_generate_success(self, mock_openai_class):
        """Test successful generation."""
        # Mock OpenAI client
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        
        # Mock response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Hello, how can I help?"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_response.id = "test-id"
        mock_response.created = 1234567890
        
        mock_client.chat.completions.create.return_value = mock_response
        
        # Create provider and generate
        provider = OpenAIProvider(api_key="test-key")
        result = provider.generate(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-4o",
            temperature=0.7,
            max_tokens=100
        )
        
        # Verify result
        assert isinstance(result, LLMResponse)
        assert result.content == "Hello, how can I help?"
        assert result.model == "gpt-4o"
        assert result.provider == "openai"
        assert result.input_tokens == 10
        assert result.output_tokens == 5
        assert result.total_tokens == 15
        assert result.finish_reason == "stop"
        assert result.estimated_cost > 0
        
        # Verify API was called correctly
        mock_client.chat.completions.create.assert_called_once()
        call_args = mock_client.chat.completions.create.call_args[1]
        assert call_args["model"] == "gpt-4o"
        assert call_args["temperature"] == 0.7
        assert call_args["max_tokens"] == 100
    
    @patch('apps.bot.services.llm.openai_provider.OpenAI')
    def test_generate_o1_model_no_temperature(self, mock_openai_class):
        """Test that o1 models don't include temperature parameter."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        
        # Mock response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_response.id = "test-id"
        mock_response.created = 1234567890
        
        mock_client.chat.completions.create.return_value = mock_response
        
        provider = OpenAIProvider(api_key="test-key")
        provider.generate(
            messages=[{"role": "user", "content": "Hello"}],
            model="o1-preview",
            temperature=0.7,
            max_tokens=100
        )
        
        # Verify temperature was NOT included for o1 model
        call_args = mock_client.chat.completions.create.call_args[1]
        assert "temperature" not in call_args
        assert call_args["model"] == "o1-preview"
    
    @patch('apps.bot.services.llm.openai_provider.OpenAI')
    @patch('time.sleep')
    def test_generate_retry_on_rate_limit(self, mock_sleep, mock_openai_class):
        """Test retry logic on rate limit error."""
        from openai import RateLimitError
        
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        
        # Mock successful response after retry
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Success"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_response.id = "test-id"
        mock_response.created = 1234567890
        
        # First call raises RateLimitError, second succeeds
        mock_client.chat.completions.create.side_effect = [
            RateLimitError("Rate limit exceeded", response=Mock(), body=None),
            mock_response
        ]
        
        provider = OpenAIProvider(api_key="test-key", max_retries=3)
        result = provider.generate(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-4o"
        )
        
        # Verify retry happened
        assert mock_client.chat.completions.create.call_count == 2
        assert mock_sleep.called
        assert result.content == "Success"
    
    @patch('apps.bot.services.llm.openai_provider.OpenAI')
    @patch('time.sleep')
    def test_generate_max_retries_exceeded(self, mock_sleep, mock_openai_class):
        """Test that max retries are respected."""
        from openai import RateLimitError
        
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        
        # Always raise RateLimitError
        mock_client.chat.completions.create.side_effect = RateLimitError(
            "Rate limit exceeded",
            response=Mock(),
            body=None
        )
        
        provider = OpenAIProvider(api_key="test-key", max_retries=2)
        
        with pytest.raises(RateLimitError):
            provider.generate(
                messages=[{"role": "user", "content": "Hello"}],
                model="gpt-4o"
            )
        
        # Should try initial + 2 retries = 3 total
        assert mock_client.chat.completions.create.call_count == 3


class TestLLMProviderFactory:
    """Test LLM provider factory."""
    
    def test_list_providers(self):
        """Test listing available providers."""
        providers = LLMProviderFactory.list_providers()
        
        assert "openai" in providers
        assert len(providers) > 0
    
    def test_get_provider_openai(self):
        """Test getting OpenAI provider."""
        provider = LLMProviderFactory.get_provider("openai", "test-key")
        
        assert isinstance(provider, OpenAIProvider)
        assert provider.api_key == "test-key"
    
    def test_get_provider_case_insensitive(self):
        """Test provider name is case insensitive."""
        provider1 = LLMProviderFactory.get_provider("openai", "test-key")
        provider2 = LLMProviderFactory.get_provider("OpenAI", "test-key")
        provider3 = LLMProviderFactory.get_provider("OPENAI", "test-key")
        
        assert isinstance(provider1, OpenAIProvider)
        assert isinstance(provider2, OpenAIProvider)
        assert isinstance(provider3, OpenAIProvider)
    
    def test_get_provider_unknown(self):
        """Test error on unknown provider."""
        with pytest.raises(ValueError) as exc_info:
            LLMProviderFactory.get_provider("unknown-provider", "test-key")
        
        assert "Unknown provider" in str(exc_info.value)
        assert "unknown-provider" in str(exc_info.value)
    
    def test_get_provider_with_config(self):
        """Test getting provider with additional config."""
        provider = LLMProviderFactory.get_provider(
            "openai",
            "test-key",
            timeout=30.0,
            max_retries=5
        )
        
        assert isinstance(provider, OpenAIProvider)
        assert provider.max_retries == 5
    
    def test_register_provider(self):
        """Test registering a new provider."""
        # Create a mock provider class
        class MockProvider(LLMProvider):
            @property
            def provider_name(self):
                return "mock"
            
            def generate(self, messages, model, **kwargs):
                pass
            
            def get_available_models(self):
                return []
        
        # Register it
        LLMProviderFactory.register_provider("mock", MockProvider)
        
        # Verify it's registered
        assert "mock" in LLMProviderFactory.list_providers()
        
        # Verify we can get it
        provider = LLMProviderFactory.get_provider("mock", "test-key")
        assert isinstance(provider, MockProvider)
    
    def test_register_provider_invalid_class(self):
        """Test error when registering non-LLMProvider class."""
        class NotAProvider:
            pass
        
        with pytest.raises(ValueError) as exc_info:
            LLMProviderFactory.register_provider("invalid", NotAProvider)
        
        assert "must extend LLMProvider" in str(exc_info.value)
    
    @pytest.mark.django_db
    def test_create_from_tenant_settings(self):
        """Test creating provider from tenant settings."""
        from apps.tenants.models import Tenant, TenantSettings
        
        # Create tenant (settings will be auto-created by signal)
        tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        
        # Update the auto-created settings with OpenAI API key
        tenant.settings.openai_api_key = "test-openai-key"
        tenant.settings.llm_provider = "openai"
        tenant.settings.llm_timeout = 30.0
        tenant.settings.llm_max_retries = 5
        tenant.settings.save()
        
        # Create provider from tenant settings
        provider = LLMProviderFactory.create_from_tenant_settings(tenant)
        
        assert isinstance(provider, OpenAIProvider)
        assert provider.api_key == "test-openai-key"
        assert provider.max_retries == 5
    
    @pytest.mark.django_db
    def test_create_from_tenant_settings_no_api_key(self):
        """Test error when tenant has no API key configured."""
        from apps.tenants.models import Tenant, TenantSettings
        
        # Create tenant (settings will be auto-created by signal)
        tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        
        # Update settings to set provider but no API key
        tenant.settings.llm_provider = "openai"
        tenant.settings.save()
        # No API key set
        
        with pytest.raises(ValueError) as exc_info:
            LLMProviderFactory.create_from_tenant_settings(tenant)
        
        assert "No API key configured" in str(exc_info.value)
