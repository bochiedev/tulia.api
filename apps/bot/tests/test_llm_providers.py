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
    TogetherAIProvider,
    GeminiProvider,
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


class TestTogetherAIProvider:
    """Test Together AI provider implementation."""
    
    def test_initialization(self):
        """Test Together AI provider initialization."""
        provider = TogetherAIProvider(api_key="test-key")
        
        assert provider.api_key == "test-key"
        assert provider.provider_name == "together"
        assert provider.session is not None
    
    def test_initialization_with_config(self):
        """Test Together AI provider initialization with custom config."""
        provider = TogetherAIProvider(
            api_key="test-key",
            timeout=30.0,
            max_retries=5
        )
        
        assert provider.api_key == "test-key"
        assert provider.timeout == 30.0
        assert provider.max_retries == 5
    
    def test_get_available_models(self):
        """Test getting available models."""
        provider = TogetherAIProvider(api_key="test-key")
        models = provider.get_available_models()
        
        assert len(models) > 0
        assert all(isinstance(m, ModelInfo) for m in models)
        
        # Check specific models exist
        model_names = [m.name for m in models]
        assert "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo" in model_names
        assert "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo" in model_names
        assert "mistralai/Mistral-7B-Instruct-v0.3" in model_names
    
    def test_model_configurations(self):
        """Test that model configurations are properly defined."""
        provider = TogetherAIProvider(api_key="test-key")
        
        # Check Llama 3.1 8B configuration
        assert "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo" in provider.MODELS
        llama_8b = provider.MODELS["meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"]
        assert llama_8b["context_window"] == 131072
        assert llama_8b["input_cost_per_1k"] > 0
        assert llama_8b["output_cost_per_1k"] > 0
        assert "chat" in llama_8b["capabilities"]
        
        # Check Llama 3.1 405B configuration
        assert "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo" in provider.MODELS
        llama_405b = provider.MODELS["meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo"]
        assert "reasoning" in llama_405b["capabilities"]
        assert "complex_tasks" in llama_405b["capabilities"]
    
    def test_calculate_cost(self):
        """Test cost calculation."""
        provider = TogetherAIProvider(api_key="test-key")
        
        # Test Llama 3.1 8B cost calculation
        cost = provider._calculate_cost(
            "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
            1000,
            500
        )
        expected = (Decimal("1000") / 1000 * Decimal("0.00018")) + \
                   (Decimal("500") / 1000 * Decimal("0.00018"))
        assert cost == expected
        
        # Test unknown model returns 0
        cost = provider._calculate_cost("unknown-model", 1000, 500)
        assert cost == Decimal("0")
    
    def test_calculate_retry_delay(self):
        """Test exponential backoff calculation."""
        provider = TogetherAIProvider(api_key="test-key")
        
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
    
    @patch('apps.bot.services.llm.together_provider.requests.Session')
    def test_generate_success(self, mock_session_class):
        """Test successful generation."""
        # Mock session
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'id': 'test-id',
            'created': 1234567890,
            'model': 'meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo',
            'choices': [{
                'message': {
                    'content': 'Hello, how can I help?'
                },
                'finish_reason': 'stop'
            }],
            'usage': {
                'prompt_tokens': 10,
                'completion_tokens': 5,
                'total_tokens': 15
            }
        }
        mock_session.post.return_value = mock_response
        
        # Create provider and generate
        provider = TogetherAIProvider(api_key="test-key")
        result = provider.generate(
            messages=[{"role": "user", "content": "Hello"}],
            model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
            temperature=0.7,
            max_tokens=100
        )
        
        # Verify result
        assert isinstance(result, LLMResponse)
        assert result.content == "Hello, how can I help?"
        assert result.model == "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"
        assert result.provider == "together"
        assert result.input_tokens == 10
        assert result.output_tokens == 5
        assert result.total_tokens == 15
        assert result.finish_reason == "stop"
        assert result.estimated_cost > 0
        
        # Verify API was called correctly
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert "chat/completions" in call_args[0][0]
        payload = call_args[1]['json']
        assert payload["model"] == "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"
        assert payload["temperature"] == 0.7
        assert payload["max_tokens"] == 100
    
    @patch('apps.bot.services.llm.together_provider.requests.Session')
    @patch('time.sleep')
    def test_generate_retry_on_rate_limit(self, mock_sleep, mock_session_class):
        """Test retry logic on rate limit error."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        # Mock successful response after retry
        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {
            'id': 'test-id',
            'created': 1234567890,
            'model': 'meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo',
            'choices': [{
                'message': {'content': 'Success'},
                'finish_reason': 'stop'
            }],
            'usage': {
                'prompt_tokens': 10,
                'completion_tokens': 5,
                'total_tokens': 15
            }
        }
        
        # First call returns 429, second succeeds
        rate_limit_response = Mock()
        rate_limit_response.status_code = 429
        
        mock_session.post.side_effect = [rate_limit_response, success_response]
        
        provider = TogetherAIProvider(api_key="test-key", max_retries=3)
        result = provider.generate(
            messages=[{"role": "user", "content": "Hello"}],
            model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"
        )
        
        # Verify retry happened
        assert mock_session.post.call_count == 2
        assert mock_sleep.called
        assert result.content == "Success"
    
    @patch('apps.bot.services.llm.together_provider.requests.Session')
    @patch('time.sleep')
    def test_generate_max_retries_exceeded(self, mock_sleep, mock_session_class):
        """Test that max retries are respected."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        # Always return 429
        rate_limit_response = Mock()
        rate_limit_response.status_code = 429
        rate_limit_response.raise_for_status.side_effect = Exception("Rate limit exceeded")
        
        mock_session.post.return_value = rate_limit_response
        
        provider = TogetherAIProvider(api_key="test-key", max_retries=2)
        
        with pytest.raises(Exception):
            provider.generate(
                messages=[{"role": "user", "content": "Hello"}],
                model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"
            )
        
        # Should try initial + 2 retries = 3 total
        assert mock_session.post.call_count == 3
    
    @patch('apps.bot.services.llm.together_provider.requests.Session')
    @patch('time.sleep')
    def test_generate_retry_on_server_error(self, mock_sleep, mock_session_class):
        """Test retry logic on server error."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        # Mock successful response after retry
        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {
            'id': 'test-id',
            'created': 1234567890,
            'model': 'meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo',
            'choices': [{
                'message': {'content': 'Success'},
                'finish_reason': 'stop'
            }],
            'usage': {
                'prompt_tokens': 10,
                'completion_tokens': 5,
                'total_tokens': 15
            }
        }
        
        # First call returns 500, second succeeds
        server_error_response = Mock()
        server_error_response.status_code = 500
        
        mock_session.post.side_effect = [server_error_response, success_response]
        
        provider = TogetherAIProvider(api_key="test-key", max_retries=3)
        result = provider.generate(
            messages=[{"role": "user", "content": "Hello"}],
            model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"
        )
        
        # Verify retry happened
        assert mock_session.post.call_count == 2
        assert mock_sleep.called
        assert result.content == "Success"


class TestGeminiProvider:
    """Test Gemini provider implementation."""
    
    def test_initialization(self):
        """Test Gemini provider initialization."""
        provider = GeminiProvider(api_key="test-key")
        
        assert provider.api_key == "test-key"
        assert provider.provider_name == "gemini"
    
    def test_initialization_with_config(self):
        """Test Gemini provider initialization with custom config."""
        provider = GeminiProvider(
            api_key="test-key",
            timeout=30.0,
            max_retries=5
        )
        
        assert provider.api_key == "test-key"
        assert provider.timeout == 30.0
        assert provider.max_retries == 5
    
    def test_get_available_models(self):
        """Test getting available models."""
        provider = GeminiProvider(api_key="test-key")
        models = provider.get_available_models()
        
        assert len(models) > 0
        assert all(isinstance(m, ModelInfo) for m in models)
        
        # Check specific models exist
        model_names = [m.name for m in models]
        assert "gemini-1.5-pro" in model_names
        assert "gemini-1.5-flash" in model_names
        assert "gemini-1.5-pro-latest" in model_names
        assert "gemini-1.5-flash-latest" in model_names
    
    def test_model_configurations(self):
        """Test that model configurations are properly defined."""
        provider = GeminiProvider(api_key="test-key")
        
        # Check Gemini 1.5 Pro configuration
        assert "gemini-1.5-pro" in provider.MODELS
        pro = provider.MODELS["gemini-1.5-pro"]
        assert pro["context_window"] == 1000000  # 1M tokens
        assert pro["input_cost_per_1k"] > 0
        assert pro["output_cost_per_1k"] > 0
        assert "chat" in pro["capabilities"]
        assert "long_context" in pro["capabilities"]
        
        # Check Gemini 1.5 Flash configuration
        assert "gemini-1.5-flash" in provider.MODELS
        flash = provider.MODELS["gemini-1.5-flash"]
        assert flash["context_window"] == 1000000
        assert "fast_inference" in flash["capabilities"]
        # Flash should be cheaper than Pro
        assert flash["input_cost_per_1k"] < pro["input_cost_per_1k"]
        assert flash["output_cost_per_1k"] < pro["output_cost_per_1k"]
    
    def test_calculate_cost(self):
        """Test cost calculation."""
        provider = GeminiProvider(api_key="test-key")
        
        # Test Gemini 1.5 Pro cost calculation
        cost = provider._calculate_cost("gemini-1.5-pro", 1000, 500)
        expected = (Decimal("1000") / 1000 * Decimal("0.00125")) + \
                   (Decimal("500") / 1000 * Decimal("0.005"))
        assert cost == expected
        
        # Test Gemini 1.5 Flash cost calculation (should be cheaper)
        flash_cost = provider._calculate_cost("gemini-1.5-flash", 1000, 500)
        assert flash_cost < cost
        
        # Test unknown model returns 0
        cost = provider._calculate_cost("unknown-model", 1000, 500)
        assert cost == Decimal("0")
    
    def test_calculate_retry_delay(self):
        """Test exponential backoff calculation."""
        provider = GeminiProvider(api_key="test-key")
        
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
    
    def test_convert_messages(self):
        """Test message format conversion."""
        provider = GeminiProvider(api_key="test-key")
        
        # Test system + user message
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"}
        ]
        converted = provider._convert_messages(messages)
        
        # System message creates first user message, then actual user message follows
        assert len(converted) == 2
        assert converted[0]["role"] == "user"
        assert "System instructions" in converted[0]["parts"][0]
        assert converted[1]["role"] == "user"
        assert converted[1]["parts"][0] == "Hello"
        
        # Test user + assistant conversation
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"}
        ]
        converted = provider._convert_messages(messages)
        
        assert len(converted) == 3
        assert converted[0]["role"] == "user"
        assert converted[1]["role"] == "model"  # assistant -> model
        assert converted[2]["role"] == "user"
    
    def test_map_finish_reason(self):
        """Test finish reason mapping."""
        provider = GeminiProvider(api_key="test-key")
        
        assert provider._map_finish_reason(1) == "stop"
        assert provider._map_finish_reason(2) == "length"
        assert provider._map_finish_reason(3) == "safety"
        assert provider._map_finish_reason(4) == "recitation"
        assert provider._map_finish_reason(5) == "other"
        assert provider._map_finish_reason(99) == "unknown"
    
    def test_estimate_tokens(self):
        """Test token estimation."""
        provider = GeminiProvider(api_key="test-key")
        
        # Test string estimation
        text = "Hello, world! This is a test message."
        tokens = provider._estimate_tokens(text)
        assert tokens > 0
        assert tokens == len(text) // 4  # Rough estimate
        
        # Test list estimation
        messages = [
            {"role": "user", "parts": ["Hello"]},
            {"role": "model", "parts": ["Hi there!"]}
        ]
        tokens = provider._estimate_tokens(messages)
        assert tokens > 0
    
    @patch('apps.bot.services.llm.gemini_provider.genai')
    def test_generate_success(self, mock_genai):
        """Test successful generation."""
        # Mock Gemini model
        mock_model = Mock()
        mock_genai.GenerativeModel.return_value = mock_model
        
        # Mock response
        mock_response = Mock()
        mock_response.text = "Hello, how can I help?"
        mock_response.candidates = [Mock()]
        mock_response.candidates[0].finish_reason = 1  # STOP
        mock_response.candidates[0].safety_ratings = []
        
        # Mock usage metadata
        mock_response.usage_metadata = Mock()
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 5
        mock_response.usage_metadata.total_token_count = 15
        
        mock_model.generate_content.return_value = mock_response
        
        # Create provider and generate
        provider = GeminiProvider(api_key="test-key")
        result = provider.generate(
            messages=[{"role": "user", "content": "Hello"}],
            model="gemini-1.5-pro",
            temperature=0.7,
            max_tokens=100
        )
        
        # Verify result
        assert isinstance(result, LLMResponse)
        assert result.content == "Hello, how can I help?"
        assert result.model == "gemini-1.5-pro"
        assert result.provider == "gemini"
        assert result.input_tokens == 10
        assert result.output_tokens == 5
        assert result.total_tokens == 15
        assert result.finish_reason == "stop"
        assert result.estimated_cost > 0
        
        # Verify API was called correctly
        mock_model.generate_content.assert_called_once()
    
    @patch('apps.bot.services.llm.gemini_provider.genai')
    @patch('time.sleep')
    def test_generate_retry_on_rate_limit(self, mock_sleep, mock_genai):
        """Test retry logic on rate limit error."""
        from google.api_core import exceptions as google_exceptions
        
        mock_model = Mock()
        mock_genai.GenerativeModel.return_value = mock_model
        
        # Mock successful response after retry
        mock_response = Mock()
        mock_response.text = "Success"
        mock_response.candidates = [Mock()]
        mock_response.candidates[0].finish_reason = 1
        mock_response.candidates[0].safety_ratings = []
        mock_response.usage_metadata = Mock()
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 5
        mock_response.usage_metadata.total_token_count = 15
        
        # First call raises ResourceExhausted, second succeeds
        mock_model.generate_content.side_effect = [
            google_exceptions.ResourceExhausted("Rate limit exceeded"),
            mock_response
        ]
        
        provider = GeminiProvider(api_key="test-key", max_retries=3)
        result = provider.generate(
            messages=[{"role": "user", "content": "Hello"}],
            model="gemini-1.5-pro"
        )
        
        # Verify retry happened
        assert mock_model.generate_content.call_count == 2
        assert mock_sleep.called
        assert result.content == "Success"
    
    @patch('apps.bot.services.llm.gemini_provider.genai')
    @patch('time.sleep')
    def test_generate_max_retries_exceeded(self, mock_sleep, mock_genai):
        """Test that max retries are respected."""
        from google.api_core import exceptions as google_exceptions
        
        mock_model = Mock()
        mock_genai.GenerativeModel.return_value = mock_model
        
        # Always raise ResourceExhausted
        mock_model.generate_content.side_effect = google_exceptions.ResourceExhausted(
            "Rate limit exceeded"
        )
        
        provider = GeminiProvider(api_key="test-key", max_retries=2)
        
        with pytest.raises(google_exceptions.ResourceExhausted):
            provider.generate(
                messages=[{"role": "user", "content": "Hello"}],
                model="gemini-1.5-pro"
            )
        
        # Should try initial + 2 retries = 3 total
        assert mock_model.generate_content.call_count == 3
    
    @patch('apps.bot.services.llm.gemini_provider.genai')
    @patch('time.sleep')
    def test_generate_retry_on_timeout(self, mock_sleep, mock_genai):
        """Test retry logic on timeout error."""
        from google.api_core import exceptions as google_exceptions
        
        mock_model = Mock()
        mock_genai.GenerativeModel.return_value = mock_model
        
        # Mock successful response after retry
        mock_response = Mock()
        mock_response.text = "Success"
        mock_response.candidates = [Mock()]
        mock_response.candidates[0].finish_reason = 1
        mock_response.candidates[0].safety_ratings = []
        mock_response.usage_metadata = Mock()
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 5
        mock_response.usage_metadata.total_token_count = 15
        
        # First call raises DeadlineExceeded, second succeeds
        mock_model.generate_content.side_effect = [
            google_exceptions.DeadlineExceeded("Timeout"),
            mock_response
        ]
        
        provider = GeminiProvider(api_key="test-key", max_retries=3)
        result = provider.generate(
            messages=[{"role": "user", "content": "Hello"}],
            model="gemini-1.5-pro"
        )
        
        # Verify retry happened
        assert mock_model.generate_content.call_count == 2
        assert mock_sleep.called
        assert result.content == "Success"


class TestLLMProviderFactory:
    """Test LLM provider factory."""
    
    def test_list_providers(self):
        """Test listing available providers."""
        providers = LLMProviderFactory.list_providers()
        
        assert "openai" in providers
        assert "together" in providers
        assert "gemini" in providers
        assert len(providers) >= 3
    
    def test_get_provider_openai(self):
        """Test getting OpenAI provider."""
        provider = LLMProviderFactory.get_provider("openai", "test-key")
        
        assert isinstance(provider, OpenAIProvider)
        assert provider.api_key == "test-key"
    
    def test_get_provider_together(self):
        """Test getting Together AI provider."""
        provider = LLMProviderFactory.get_provider("together", "test-key")
        
        assert isinstance(provider, TogetherAIProvider)
        assert provider.api_key == "test-key"
    
    def test_get_provider_gemini(self):
        """Test getting Gemini provider."""
        provider = LLMProviderFactory.get_provider("gemini", "test-key")
        
        assert isinstance(provider, GeminiProvider)
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
    def test_create_from_tenant_settings_together(self):
        """Test creating Together AI provider from tenant settings."""
        from apps.tenants.models import Tenant, TenantSettings
        
        # Create tenant (settings will be auto-created by signal)
        tenant = Tenant.objects.create(
            name="Test Tenant Together",
            slug="test-tenant-together"
        )
        
        # Update the auto-created settings with Together AI API key
        tenant.settings.together_api_key = "test-together-key"
        tenant.settings.llm_provider = "together"
        tenant.settings.llm_timeout = 45.0
        tenant.settings.llm_max_retries = 4
        tenant.settings.save()
        
        # Create provider from tenant settings
        provider = LLMProviderFactory.create_from_tenant_settings(tenant)
        
        assert isinstance(provider, TogetherAIProvider)
        assert provider.api_key == "test-together-key"
        assert provider.timeout == 45.0
        assert provider.max_retries == 4
    
    @pytest.mark.django_db
    def test_create_from_tenant_settings_gemini(self):
        """Test creating Gemini provider from tenant settings."""
        from apps.tenants.models import Tenant, TenantSettings
        
        # Create tenant (settings will be auto-created by signal)
        tenant = Tenant.objects.create(
            name="Test Tenant Gemini",
            slug="test-tenant-gemini"
        )
        
        # Update the auto-created settings with Gemini API key
        tenant.settings.gemini_api_key = "test-gemini-key"
        tenant.settings.llm_provider = "gemini"
        tenant.settings.llm_timeout = 60.0
        tenant.settings.llm_max_retries = 3
        tenant.settings.save()
        
        # Create provider from tenant settings
        provider = LLMProviderFactory.create_from_tenant_settings(tenant)
        
        assert isinstance(provider, GeminiProvider)
        assert provider.api_key == "test-gemini-key"
        assert provider.timeout == 60.0
        assert provider.max_retries == 3
    
    @pytest.mark.django_db
    def test_create_from_tenant_settings_fallback_to_system_key(self):
        """Test fallback to system-level API key when tenant has no API key configured."""
        from apps.tenants.models import Tenant, TenantSettings
        import os
        
        # Create tenant (settings will be auto-created by signal)
        tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant-fallback"
        )
        
        # Update settings to set provider but no API key
        tenant.settings.llm_provider = "openai"
        tenant.settings.save()
        # No tenant-specific API key set
        
        # If system has OPENAI_API_KEY, it should use that
        if os.getenv('OPENAI_API_KEY'):
            provider = LLMProviderFactory.create_from_tenant_settings(tenant)
            assert isinstance(provider, OpenAIProvider)
            assert provider.api_key == os.getenv('OPENAI_API_KEY')
        else:
            # If no system key either, should raise error
            with pytest.raises(ValueError) as exc_info:
                LLMProviderFactory.create_from_tenant_settings(tenant)
            
            assert "No API key configured" in str(exc_info.value)
    
    @pytest.mark.django_db
    def test_create_from_tenant_settings_no_api_key_anywhere(self):
        """Test error when no API key is available (tenant or system)."""
        from apps.tenants.models import Tenant, TenantSettings
        import os
        from unittest.mock import patch
        
        # Create tenant (settings will be auto-created by signal)
        tenant = Tenant.objects.create(
            name="Test Tenant No Key",
            slug="test-tenant-no-key"
        )
        
        # Update settings to set provider but no API key
        tenant.settings.llm_provider = "openai"
        tenant.settings.save()
        # No tenant-specific API key set
        
        # Mock environment to have no system key either
        with patch.dict(os.environ, {'OPENAI_API_KEY': ''}, clear=False):
            with pytest.raises(ValueError) as exc_info:
                LLMProviderFactory.create_from_tenant_settings(tenant)
            
            assert "No API key configured" in str(exc_info.value)
            assert "OPENAI_API_KEY" in str(exc_info.value)
