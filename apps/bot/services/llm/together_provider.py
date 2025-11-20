"""
Together AI LLM Provider implementation.

Provides access to multiple open-source models through Together AI's unified API,
including Llama, Mistral, and other popular models.
"""

import logging
import time
import requests
from typing import List, Dict, Any
from decimal import Decimal

from .base import LLMProvider, LLMResponse, ModelInfo

logger = logging.getLogger(__name__)


class TogetherAIProvider(LLMProvider):
    """
    Together AI implementation for accessing multiple open-source models.
    
    Supports models like:
    - Meta Llama 3.1 (8B, 70B, 405B)
    - Mistral (7B, 8x7B)
    - Qwen 2.5 (7B, 72B)
    - And many more
    
    Includes error handling and retry logic with exponential backoff.
    """
    
    # API Configuration
    API_BASE_URL = "https://api.together.xyz/v1"
    
    # Model configurations with pricing (as of Nov 2024)
    # Prices are per million tokens
    MODELS = {
        # Meta Llama models
        'meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo': {
            'display_name': 'Llama 3.1 8B Instruct Turbo',
            'context_window': 131072,
            'input_cost_per_1k': Decimal('0.00018'),
            'output_cost_per_1k': Decimal('0.00018'),
            'capabilities': ['chat', 'instruct'],
            'description': 'Fast and efficient Llama 3.1 8B model optimized for instruction following'
        },
        'meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo': {
            'display_name': 'Llama 3.1 70B Instruct Turbo',
            'context_window': 131072,
            'input_cost_per_1k': Decimal('0.00088'),
            'output_cost_per_1k': Decimal('0.00088'),
            'capabilities': ['chat', 'instruct', 'reasoning'],
            'description': 'Powerful Llama 3.1 70B model with strong reasoning capabilities'
        },
        'meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo': {
            'display_name': 'Llama 3.1 405B Instruct Turbo',
            'context_window': 130815,
            'input_cost_per_1k': Decimal('0.00500'),
            'output_cost_per_1k': Decimal('0.00500'),
            'capabilities': ['chat', 'instruct', 'reasoning', 'complex_tasks'],
            'description': 'Most capable Llama model for complex reasoning and tasks'
        },
        'meta-llama/Llama-3.2-3B-Instruct-Turbo': {
            'display_name': 'Llama 3.2 3B Instruct Turbo',
            'context_window': 131072,
            'input_cost_per_1k': Decimal('0.00006'),
            'output_cost_per_1k': Decimal('0.00006'),
            'capabilities': ['chat', 'instruct'],
            'description': 'Ultra-efficient small model for simple tasks'
        },
        
        # Mistral models
        'mistralai/Mistral-7B-Instruct-v0.3': {
            'display_name': 'Mistral 7B Instruct v0.3',
            'context_window': 32768,
            'input_cost_per_1k': Decimal('0.00020'),
            'output_cost_per_1k': Decimal('0.00020'),
            'capabilities': ['chat', 'instruct'],
            'description': 'Efficient Mistral 7B model for general tasks'
        },
        'mistralai/Mixtral-8x7B-Instruct-v0.1': {
            'display_name': 'Mixtral 8x7B Instruct',
            'context_window': 32768,
            'input_cost_per_1k': Decimal('0.00060'),
            'output_cost_per_1k': Decimal('0.00060'),
            'capabilities': ['chat', 'instruct', 'reasoning'],
            'description': 'Mixture of experts model with strong performance'
        },
        'mistralai/Mixtral-8x22B-Instruct-v0.1': {
            'display_name': 'Mixtral 8x22B Instruct',
            'context_window': 65536,
            'input_cost_per_1k': Decimal('0.00120'),
            'output_cost_per_1k': Decimal('0.00120'),
            'capabilities': ['chat', 'instruct', 'reasoning', 'complex_tasks'],
            'description': 'Large mixture of experts model for complex reasoning'
        },
        
        # Qwen models (excellent for multilingual including Swahili)
        'Qwen/Qwen2.5-7B-Instruct-Turbo': {
            'display_name': 'Qwen 2.5 7B Instruct Turbo',
            'context_window': 32768,
            'input_cost_per_1k': Decimal('0.00030'),
            'output_cost_per_1k': Decimal('0.00030'),
            'capabilities': ['chat', 'instruct', 'multilingual'],
            'description': 'Multilingual model with strong performance across languages including Swahili'
        },
        'Qwen/Qwen2.5-72B-Instruct-Turbo': {
            'display_name': 'Qwen 2.5 72B Instruct Turbo',
            'context_window': 32768,
            'input_cost_per_1k': Decimal('0.00120'),
            'output_cost_per_1k': Decimal('0.00120'),
            'capabilities': ['chat', 'instruct', 'reasoning', 'multilingual'],
            'description': 'Large multilingual model with advanced reasoning and excellent Swahili support'
        },
        
        # DeepSeek models (cost-effective)
        'deepseek-ai/deepseek-llm-67b-chat': {
            'display_name': 'DeepSeek LLM 67B Chat',
            'context_window': 4096,
            'input_cost_per_1k': Decimal('0.00090'),
            'output_cost_per_1k': Decimal('0.00090'),
            'capabilities': ['chat', 'reasoning'],
            'description': 'Cost-effective large model with strong reasoning'
        },
    }
    
    # Retry configuration
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 1.0  # seconds
    MAX_RETRY_DELAY = 60.0  # seconds
    BACKOFF_MULTIPLIER = 2.0
    
    def __init__(self, api_key: str, **kwargs):
        """
        Initialize Together AI provider.
        
        Args:
            api_key: Together AI API key
            **kwargs: Additional configuration (timeout, max_retries, etc.)
        """
        super().__init__(api_key, **kwargs)
        
        self.timeout = kwargs.get('timeout', 60.0)
        self.max_retries = kwargs.get('max_retries', self.MAX_RETRIES)
        
        # Set up session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        })
    
    @property
    def provider_name(self) -> str:
        """Return the name of this provider."""
        return 'together'
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> LLMResponse:
        """
        Generate completion from Together AI with retry logic.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            model: Model identifier (e.g., 'meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo')
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional Together AI-specific parameters
            
        Returns:
            LLMResponse with normalized response data
            
        Raises:
            Exception: On API errors after all retries exhausted
        """
        if model not in self.MODELS:
            logger.warning(f"Model {model} not in known models, attempting anyway")
        
        retry_count = 0
        last_exception = None
        
        while retry_count <= self.max_retries:
            try:
                logger.info(
                    f"Calling Together AI API with model={model}, "
                    f"messages={len(messages)}, attempt={retry_count + 1}"
                )
                
                # Prepare API call payload
                payload = {
                    'model': model,
                    'messages': messages,
                    'max_tokens': max_tokens,
                    'temperature': temperature,
                }
                
                # Add any additional parameters
                payload.update(kwargs)
                
                # Make API call
                response = self.session.post(
                    f"{self.API_BASE_URL}/chat/completions",
                    json=payload,
                    timeout=self.timeout
                )
                
                # Check for HTTP errors
                if response.status_code == 429:
                    # Rate limit error
                    retry_count += 1
                    if retry_count > self.max_retries:
                        logger.error(f"Rate limit exceeded after {self.max_retries} retries")
                        response.raise_for_status()
                    
                    delay = self._calculate_retry_delay(retry_count)
                    logger.warning(
                        f"Rate limit hit, retrying in {delay}s "
                        f"(attempt {retry_count}/{self.max_retries})"
                    )
                    time.sleep(delay)
                    continue
                
                elif response.status_code >= 500:
                    # Server error - retry
                    retry_count += 1
                    if retry_count > self.max_retries:
                        logger.error(
                            f"Server error after {self.max_retries} retries: "
                            f"{response.status_code}"
                        )
                        response.raise_for_status()
                    
                    delay = self._calculate_retry_delay(retry_count)
                    logger.warning(
                        f"Server error {response.status_code}, retrying in {delay}s "
                        f"(attempt {retry_count}/{self.max_retries})"
                    )
                    time.sleep(delay)
                    continue
                
                # Raise for other HTTP errors
                response.raise_for_status()
                
                # Parse response
                data = response.json()
                
                # Extract response data
                content = data['choices'][0]['message']['content']
                finish_reason = data['choices'][0]['finish_reason']
                
                # Calculate token usage
                usage = data.get('usage', {})
                input_tokens = usage.get('prompt_tokens', 0)
                output_tokens = usage.get('completion_tokens', 0)
                total_tokens = usage.get('total_tokens', input_tokens + output_tokens)
                
                # Calculate cost
                estimated_cost = self._calculate_cost(
                    model, input_tokens, output_tokens
                )
                
                logger.info(
                    f"Together AI API call successful: model={model}, "
                    f"tokens={total_tokens}, cost=${estimated_cost}"
                )
                
                return LLMResponse(
                    content=content,
                    model=model,
                    provider=self.provider_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    estimated_cost=estimated_cost,
                    finish_reason=finish_reason,
                    metadata={
                        'response_id': data.get('id'),
                        'created': data.get('created'),
                        'model': data.get('model')
                    }
                )
                
            except requests.exceptions.Timeout as e:
                last_exception = e
                retry_count += 1
                if retry_count > self.max_retries:
                    logger.error(f"Timeout error after {self.max_retries} retries: {e}")
                    raise
                
                delay = self._calculate_retry_delay(retry_count)
                logger.warning(
                    f"Timeout error, retrying in {delay}s "
                    f"(attempt {retry_count}/{self.max_retries}): {e}"
                )
                time.sleep(delay)
                
            except requests.exceptions.ConnectionError as e:
                last_exception = e
                retry_count += 1
                if retry_count > self.max_retries:
                    logger.error(f"Connection error after {self.max_retries} retries: {e}")
                    raise
                
                delay = self._calculate_retry_delay(retry_count)
                logger.warning(
                    f"Connection error, retrying in {delay}s "
                    f"(attempt {retry_count}/{self.max_retries}): {e}"
                )
                time.sleep(delay)
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Together AI API error: {e}")
                raise
                
            except Exception as e:
                logger.error(f"Unexpected error calling Together AI API: {e}")
                raise
        
        # Should not reach here, but just in case
        if last_exception:
            raise last_exception
        raise Exception("Failed to generate response after retries")
    
    def get_available_models(self) -> List[ModelInfo]:
        """
        Get list of available Together AI models.
        
        Returns:
            List of ModelInfo objects for supported models
        """
        models = []
        for model_id, config in self.MODELS.items():
            models.append(ModelInfo(
                name=model_id,
                display_name=config['display_name'],
                provider=self.provider_name,
                context_window=config['context_window'],
                input_cost_per_1k=config['input_cost_per_1k'],
                output_cost_per_1k=config['output_cost_per_1k'],
                capabilities=config['capabilities'],
                description=config['description']
            ))
        return models
    
    def _calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> Decimal:
        """
        Calculate estimated cost for API call.
        
        Args:
            model: Model identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Estimated cost in USD
        """
        if model not in self.MODELS:
            # Unknown model, return 0
            return Decimal('0')
        
        config = self.MODELS[model]
        input_cost = (Decimal(input_tokens) / 1000) * config['input_cost_per_1k']
        output_cost = (Decimal(output_tokens) / 1000) * config['output_cost_per_1k']
        
        return input_cost + output_cost
    
    def _calculate_retry_delay(self, retry_count: int) -> float:
        """
        Calculate exponential backoff delay.
        
        Args:
            retry_count: Current retry attempt number
            
        Returns:
            Delay in seconds
        """
        delay = self.INITIAL_RETRY_DELAY * (self.BACKOFF_MULTIPLIER ** (retry_count - 1))
        return min(delay, self.MAX_RETRY_DELAY)
    
    def __del__(self):
        """Clean up session on deletion."""
        if hasattr(self, 'session'):
            self.session.close()
