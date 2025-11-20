"""
Gemini LLM Provider implementation.

Supports Google's Gemini models including gemini-1.5-pro and gemini-1.5-flash.
"""

import logging
import time
from typing import List, Dict, Any
from decimal import Decimal

import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from google.api_core import exceptions as google_exceptions

from .base import LLMProvider, LLMResponse, ModelInfo

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """
    Google Gemini implementation supporting gemini-1.5-pro and gemini-1.5-flash.
    
    Includes error handling and retry logic with exponential backoff.
    """
    
    # Model configurations with pricing (as of Nov 2024)
    MODELS = {
        'gemini-1.5-pro': {
            'display_name': 'Gemini 1.5 Pro',
            'api_model_name': 'gemini-1.5-pro',  # Use stable version, not -latest
            'context_window': 1000000,  # 1M tokens
            'input_cost_per_1k': Decimal('0.00125'),  # $1.25 per 1M = $0.00125 per 1K
            'output_cost_per_1k': Decimal('0.005'),   # $5 per 1M = $0.005 per 1K
            'capabilities': ['chat', 'vision', 'long_context', 'function_calling'],
            'description': 'Advanced model with 1M token context window for complex tasks'
        },
        'gemini-1.5-flash': {
            'display_name': 'Gemini 1.5 Flash',
            'api_model_name': 'gemini-1.5-flash',  # Use stable version, not -latest
            'context_window': 1000000,  # 1M tokens
            'input_cost_per_1k': Decimal('0.000075'),  # $0.075 per 1M = $0.000075 per 1K
            'output_cost_per_1k': Decimal('0.0003'),   # $0.30 per 1M = $0.0003 per 1K
            'capabilities': ['chat', 'vision', 'long_context', 'fast_inference'],
            'description': 'Fast and cost-effective model for simple queries'
        },
        'gemini-1.5-pro-latest': {
            'display_name': 'Gemini 1.5 Pro (Latest)',
            'api_model_name': 'gemini-1.5-pro',  # -latest suffix not supported in v1beta
            'context_window': 1000000,
            'input_cost_per_1k': Decimal('0.00125'),
            'output_cost_per_1k': Decimal('0.005'),
            'capabilities': ['chat', 'vision', 'long_context', 'function_calling'],
            'description': 'Latest version of Gemini 1.5 Pro with improvements'
        },
        'gemini-1.5-flash-latest': {
            'display_name': 'Gemini 1.5 Flash (Latest)',
            'api_model_name': 'gemini-1.5-flash',  # -latest suffix not supported in v1beta
            'context_window': 1000000,
            'input_cost_per_1k': Decimal('0.000075'),
            'output_cost_per_1k': Decimal('0.0003'),
            'capabilities': ['chat', 'vision', 'long_context', 'fast_inference'],
            'description': 'Latest version of Gemini 1.5 Flash with improvements'
        }
    }
    
    # Retry configuration
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 1.0  # seconds
    MAX_RETRY_DELAY = 60.0  # seconds
    BACKOFF_MULTIPLIER = 2.0
    
    def __init__(self, api_key: str, **kwargs):
        """
        Initialize Gemini provider.
        
        Args:
            api_key: Google AI API key
            **kwargs: Additional configuration (timeout, max_retries, etc.)
        """
        super().__init__(api_key, **kwargs)
        
        # Configure Gemini SDK
        genai.configure(api_key=api_key)
        
        # Extract configuration
        self.timeout = kwargs.get('timeout', 60.0)
        self.max_retries = kwargs.get('max_retries', self.MAX_RETRIES)
    
    @property
    def provider_name(self) -> str:
        """Return the name of this provider."""
        return 'gemini'
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> LLMResponse:
        """
        Generate completion from Gemini with retry logic.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            model: Model identifier (gemini-1.5-pro, gemini-1.5-flash, etc.)
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional Gemini-specific parameters
            
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
                    f"Calling Gemini API with model={model}, "
                    f"messages={len(messages)}, attempt={retry_count + 1}"
                )
                
                # Convert messages to Gemini format
                gemini_messages = self._convert_messages(messages)
                
                # Get API model name (may differ from our internal name)
                api_model_name = self.MODELS.get(model, {}).get('api_model_name', model)
                
                # Create model instance
                gemini_model = genai.GenerativeModel(api_model_name)
                
                # Prepare generation config
                generation_config = GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    **kwargs
                )
                
                # Make API call
                response = gemini_model.generate_content(
                    gemini_messages,
                    generation_config=generation_config
                )
                
                # Extract response data
                content = response.text
                finish_reason = self._map_finish_reason(response.candidates[0].finish_reason)
                
                # Estimate token usage (Gemini doesn't always provide exact counts)
                input_tokens = self._estimate_tokens(gemini_messages)
                output_tokens = self._estimate_tokens(content)
                total_tokens = input_tokens + output_tokens
                
                # Try to get actual usage if available
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    input_tokens = response.usage_metadata.prompt_token_count
                    output_tokens = response.usage_metadata.candidates_token_count
                    total_tokens = response.usage_metadata.total_token_count
                
                # Calculate cost
                estimated_cost = self._calculate_cost(
                    model, input_tokens, output_tokens
                )
                
                logger.info(
                    f"Gemini API call successful: model={model}, "
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
                        'safety_ratings': [
                            {
                                'category': rating.category.name,
                                'probability': rating.probability.name
                            }
                            for rating in response.candidates[0].safety_ratings
                        ] if response.candidates else []
                    }
                )
                
            except google_exceptions.ResourceExhausted as e:
                # Rate limit error
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
                
            except (google_exceptions.DeadlineExceeded, google_exceptions.ServiceUnavailable) as e:
                # Timeout or service unavailable
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
                
            except Exception as e:
                logger.error(f"Gemini API error: {e}")
                raise
        
        # Should not reach here, but just in case
        if last_exception:
            raise last_exception
        raise Exception("Failed to generate response after retries")
    
    def get_available_models(self) -> List[ModelInfo]:
        """
        Get list of available Gemini models.
        
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
    
    def _convert_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Convert OpenAI-style messages to Gemini format.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            
        Returns:
            List of messages in Gemini format
        """
        gemini_messages = []
        
        for msg in messages:
            role = msg['role']
            content = msg['content']
            
            # Map roles: OpenAI uses 'system', 'user', 'assistant'
            # Gemini uses 'user' and 'model'
            if role == 'system':
                # Prepend system message to first user message
                if not gemini_messages:
                    gemini_messages.append({
                        'role': 'user',
                        'parts': [f"System instructions: {content}"]
                    })
                else:
                    # Append to last user message
                    if gemini_messages[-1]['role'] == 'user':
                        gemini_messages[-1]['parts'].append(f"\n\nSystem: {content}")
                    else:
                        gemini_messages.append({
                            'role': 'user',
                            'parts': [f"System: {content}"]
                        })
            elif role == 'user':
                gemini_messages.append({
                    'role': 'user',
                    'parts': [content]
                })
            elif role == 'assistant':
                gemini_messages.append({
                    'role': 'model',
                    'parts': [content]
                })
        
        return gemini_messages
    
    def _map_finish_reason(self, finish_reason) -> str:
        """
        Map Gemini finish reason to standard format.
        
        Args:
            finish_reason: Gemini finish reason enum
            
        Returns:
            Standardized finish reason string
        """
        # Map Gemini finish reasons to OpenAI-style reasons
        reason_map = {
            1: 'stop',  # STOP
            2: 'length',  # MAX_TOKENS
            3: 'safety',  # SAFETY
            4: 'recitation',  # RECITATION
            5: 'other',  # OTHER
        }
        
        return reason_map.get(finish_reason, 'unknown')
    
    def _estimate_tokens(self, text: Any) -> int:
        """
        Estimate token count for text.
        
        Args:
            text: Text string or list of messages
            
        Returns:
            Estimated token count
        """
        if isinstance(text, list):
            # Sum up all parts
            total = 0
            for item in text:
                if isinstance(item, dict):
                    for part in item.get('parts', []):
                        total += len(str(part)) // 4  # Rough estimate: 4 chars per token
                else:
                    total += len(str(item)) // 4
            return total
        else:
            # Simple character-based estimation
            return len(str(text)) // 4
    
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
