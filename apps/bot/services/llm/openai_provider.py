"""
OpenAI LLM Provider implementation.
"""

import logging
import time
from typing import List, Dict, Any
from decimal import Decimal

from openai import OpenAI, OpenAIError, RateLimitError, APITimeoutError, APIConnectionError

from .base import LLMProvider, LLMResponse, ModelInfo

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """
    OpenAI implementation supporting GPT-4o, o1-preview, and o1-mini models.
    
    Includes error handling and retry logic with exponential backoff.
    """
    
    # Model configurations with pricing (as of Nov 2024)
    MODELS = {
        'gpt-4o': {
            'display_name': 'GPT-4o',
            'context_window': 128000,
            'input_cost_per_1k': Decimal('0.0025'),
            'output_cost_per_1k': Decimal('0.01'),
            'capabilities': ['chat', 'function_calling', 'vision'],
            'description': 'Most advanced GPT-4 model, optimized for speed and cost'
        },
        'gpt-4o-mini': {
            'display_name': 'GPT-4o Mini',
            'context_window': 128000,
            'input_cost_per_1k': Decimal('0.00015'),
            'output_cost_per_1k': Decimal('0.0006'),
            'capabilities': ['chat', 'function_calling'],
            'description': 'Cost-effective model for simple queries'
        },
        'o1-preview': {
            'display_name': 'O1 Preview',
            'context_window': 128000,
            'input_cost_per_1k': Decimal('0.015'),
            'output_cost_per_1k': Decimal('0.06'),
            'capabilities': ['reasoning', 'complex_tasks'],
            'description': 'Advanced reasoning model for complex problem-solving'
        },
        'o1-mini': {
            'display_name': 'O1 Mini',
            'context_window': 128000,
            'input_cost_per_1k': Decimal('0.003'),
            'output_cost_per_1k': Decimal('0.012'),
            'capabilities': ['reasoning'],
            'description': 'Cost-effective reasoning model'
        }
    }
    
    # Retry configuration
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 1.0  # seconds
    MAX_RETRY_DELAY = 60.0  # seconds
    BACKOFF_MULTIPLIER = 2.0
    
    def __init__(self, api_key: str, **kwargs):
        """
        Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key
            **kwargs: Additional configuration (timeout, max_retries, etc.)
        """
        super().__init__(api_key, **kwargs)
        
        # Extract our custom parameters before passing to OpenAI client
        timeout = kwargs.get('timeout', 60.0)
        self.max_retries = kwargs.get('max_retries', self.MAX_RETRIES)
        
        # Create OpenAI client with only supported parameters
        self.client = OpenAI(
            api_key=api_key,
            timeout=timeout,
            max_retries=0  # We handle retries ourselves
        )
    
    @property
    def provider_name(self) -> str:
        """Return the name of this provider."""
        return 'openai'
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> LLMResponse:
        """
        Generate completion from OpenAI with retry logic.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            model: Model identifier (gpt-4o, o1-preview, o1-mini, etc.)
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional OpenAI-specific parameters
            
        Returns:
            LLMResponse with normalized response data
            
        Raises:
            OpenAIError: On API errors after all retries exhausted
        """
        if model not in self.MODELS:
            logger.warning(f"Model {model} not in known models, attempting anyway")
        
        retry_count = 0
        last_exception = None
        
        while retry_count <= self.max_retries:
            try:
                logger.info(
                    f"Calling OpenAI API with model={model}, "
                    f"messages={len(messages)}, attempt={retry_count + 1}"
                )
                
                # Prepare API call parameters
                api_params = {
                    'model': model,
                    'messages': messages,
                    'max_tokens': max_tokens,
                }
                
                # O1 models don't support temperature parameter
                if not model.startswith('o1'):
                    api_params['temperature'] = temperature
                
                # Add any additional parameters
                api_params.update(kwargs)
                
                # Make API call
                response = self.client.chat.completions.create(**api_params)
                
                # Extract response data
                content = response.choices[0].message.content
                finish_reason = response.choices[0].finish_reason
                
                # Calculate token usage
                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens
                total_tokens = response.usage.total_tokens
                
                # Calculate cost
                estimated_cost = self._calculate_cost(
                    model, input_tokens, output_tokens
                )
                
                logger.info(
                    f"OpenAI API call successful: model={model}, "
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
                        'response_id': response.id,
                        'created': response.created,
                        'system_fingerprint': getattr(response, 'system_fingerprint', None)
                    }
                )
                
            except RateLimitError as e:
                last_exception = e
                retry_count += 1
                if retry_count > self.max_retries:
                    logger.error(f"Rate limit exceeded after {self.max_retries} retries")
                    raise
                
                delay = self._calculate_retry_delay(retry_count)
                logger.warning(
                    f"Rate limit hit, retrying in {delay}s "
                    f"(attempt {retry_count}/{self.max_retries})"
                )
                time.sleep(delay)
                
            except (APITimeoutError, APIConnectionError) as e:
                last_exception = e
                retry_count += 1
                if retry_count > self.max_retries:
                    logger.error(
                        f"Connection/timeout error after {self.max_retries} retries: {e}"
                    )
                    raise
                
                delay = self._calculate_retry_delay(retry_count)
                logger.warning(
                    f"Connection error, retrying in {delay}s "
                    f"(attempt {retry_count}/{self.max_retries}): {e}"
                )
                time.sleep(delay)
                
            except OpenAIError as e:
                logger.error(f"OpenAI API error: {e}")
                raise
                
            except Exception as e:
                logger.error(f"Unexpected error calling OpenAI API: {e}")
                raise
        
        # Should not reach here, but just in case
        if last_exception:
            raise last_exception
        raise Exception("Failed to generate response after retries")
    
    def get_available_models(self) -> List[ModelInfo]:
        """
        Get list of available OpenAI models.
        
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
