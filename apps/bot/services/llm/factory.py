"""
LLM Provider Factory for instantiating providers by name.
"""

import logging
from typing import Dict, Type, Optional

from .base import LLMProvider
from .openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


class LLMProviderFactory:
    """
    Factory for creating LLM provider instances.
    
    Supports provider registration and instantiation by name.
    """
    
    # Registry of available providers
    _providers: Dict[str, Type[LLMProvider]] = {
        'openai': OpenAIProvider,
    }
    
    @classmethod
    def register_provider(cls, name: str, provider_class: Type[LLMProvider]) -> None:
        """
        Register a new LLM provider.
        
        Args:
            name: Provider identifier (e.g., 'openai', 'together')
            provider_class: Provider class that extends LLMProvider
        """
        if not issubclass(provider_class, LLMProvider):
            raise ValueError(
                f"Provider class must extend LLMProvider, got {provider_class}"
            )
        
        cls._providers[name.lower()] = provider_class
        logger.info(f"Registered LLM provider: {name}")
    
    @classmethod
    def get_provider(
        cls,
        provider_name: str,
        api_key: str,
        **kwargs
    ) -> LLMProvider:
        """
        Get provider instance by name.
        
        Args:
            provider_name: Provider identifier (e.g., 'openai', 'together')
            api_key: API key for the provider
            **kwargs: Additional provider-specific configuration
            
        Returns:
            Instantiated LLMProvider
            
        Raises:
            ValueError: If provider name is not registered
        """
        provider_name_lower = provider_name.lower()
        
        if provider_name_lower not in cls._providers:
            available = ', '.join(cls._providers.keys())
            raise ValueError(
                f"Unknown provider '{provider_name}'. "
                f"Available providers: {available}"
            )
        
        provider_class = cls._providers[provider_name_lower]
        logger.info(f"Creating LLM provider instance: {provider_name}")
        
        return provider_class(api_key=api_key, **kwargs)
    
    @classmethod
    def list_providers(cls) -> list[str]:
        """
        Get list of registered provider names.
        
        Returns:
            List of provider identifiers
        """
        return list(cls._providers.keys())
    
    @classmethod
    def create_from_tenant_settings(
        cls,
        tenant,
        provider_name: Optional[str] = None
    ) -> LLMProvider:
        """
        Create provider instance from tenant settings.
        
        Args:
            tenant: Tenant instance with settings
            provider_name: Optional provider override, defaults to tenant's configured provider
            
        Returns:
            Instantiated LLMProvider
            
        Raises:
            ValueError: If provider not configured or invalid
        """
        # Get provider name from tenant settings or use override
        if provider_name is None:
            provider_name = getattr(
                tenant.settings,
                'llm_provider',
                'openai'
            )
        
        # Get API key from tenant settings
        api_key_attr = f'{provider_name}_api_key'
        api_key = getattr(tenant.settings, api_key_attr, None)
        
        if not api_key:
            raise ValueError(
                f"No API key configured for provider '{provider_name}' "
                f"in tenant settings (looking for {api_key_attr})"
            )
        
        # Get additional configuration
        config = {}
        
        # Add timeout if configured
        timeout = getattr(tenant.settings, 'llm_timeout', None)
        if timeout:
            config['timeout'] = timeout
        
        # Add max retries if configured
        max_retries = getattr(tenant.settings, 'llm_max_retries', None)
        if max_retries:
            config['max_retries'] = max_retries
        
        logger.info(
            f"Creating LLM provider for tenant {tenant.id}: "
            f"provider={provider_name}"
        )
        
        return cls.get_provider(provider_name, api_key, **config)
