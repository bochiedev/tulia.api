"""
Base LLM Provider abstract class and data models.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from decimal import Decimal


@dataclass
class ModelInfo:
    """Information about an available LLM model."""
    
    name: str
    display_name: str
    provider: str
    context_window: int
    input_cost_per_1k: Decimal
    output_cost_per_1k: Decimal
    capabilities: List[str]
    description: str


@dataclass
class LLMResponse:
    """Normalized response from LLM provider."""
    
    content: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: Decimal
    finish_reason: str
    metadata: Dict[str, Any]


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    All LLM providers must implement this interface to ensure
    consistent behavior across different AI model providers.
    """
    
    def __init__(self, api_key: str, **kwargs):
        """
        Initialize the LLM provider.
        
        Args:
            api_key: API key for the provider
            **kwargs: Additional provider-specific configuration
        """
        self.api_key = api_key
        self.config = kwargs
    
    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> LLMResponse:
        """
        Generate completion from LLM.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            model: Model identifier
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters
            
        Returns:
            LLMResponse with normalized response data
            
        Raises:
            Exception: On API errors or failures
        """
        pass
    
    @abstractmethod
    def get_available_models(self) -> List[ModelInfo]:
        """
        Get list of available models from this provider.
        
        Returns:
            List of ModelInfo objects describing available models
        """
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of this provider."""
        pass
