"""
Agent Configuration Service for managing AI agent settings.

Provides methods for retrieving, updating, and applying agent configurations
with caching support for performance optimization.
"""
from typing import Optional, Dict, Any
from django.core.cache import cache
from django.core.exceptions import ValidationError
from apps.bot.models import AgentConfiguration


class AgentConfigurationService:
    """
    Service for managing AI agent configurations.
    
    Handles configuration retrieval, updates, persona application,
    and default configuration creation for new tenants.
    """
    
    # Cache TTL in seconds (5 minutes)
    CACHE_TTL = 300
    
    @staticmethod
    def _get_cache_key(tenant_id: str) -> str:
        """Generate cache key for tenant configuration."""
        return f"agent_config:{tenant_id}"
    
    @classmethod
    def get_configuration(cls, tenant) -> AgentConfiguration:
        """
        Get agent configuration for a tenant with caching.
        
        Retrieves the configuration from cache if available, otherwise
        fetches from database and caches for 5 minutes.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            AgentConfiguration instance
            
        Raises:
            AgentConfiguration.DoesNotExist: If no configuration exists
        """
        cache_key = cls._get_cache_key(str(tenant.id))
        
        # Try to get from cache
        config = cache.get(cache_key)
        
        if config is None:
            # Fetch from database
            config = AgentConfiguration.objects.get(tenant=tenant)
            
            # Cache for 5 minutes
            cache.set(cache_key, config, cls.CACHE_TTL)
        
        return config
    
    @classmethod
    def get_or_create_configuration(cls, tenant) -> AgentConfiguration:
        """
        Get existing configuration or create default for tenant.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            AgentConfiguration instance
        """
        try:
            return cls.get_configuration(tenant)
        except AgentConfiguration.DoesNotExist:
            return cls.get_default_configuration(tenant)
    
    @classmethod
    def update_configuration(
        cls,
        tenant,
        config_data: Dict[str, Any]
    ) -> AgentConfiguration:
        """
        Update agent configuration with validation.
        
        Validates the configuration data and updates the tenant's
        agent configuration. Invalidates cache after update.
        
        Args:
            tenant: Tenant instance
            config_data: Dictionary of configuration fields to update
            
        Returns:
            Updated AgentConfiguration instance
            
        Raises:
            ValidationError: If configuration data is invalid
        """
        # Get or create configuration
        config, created = AgentConfiguration.objects.get_or_create(
            tenant=tenant,
            defaults=cls._get_default_config_dict()
        )
        
        # Validate and update fields
        cls._validate_config_data(config_data)
        
        # Update fields
        for field, value in config_data.items():
            if hasattr(config, field):
                setattr(config, field, value)
        
        # Save with full validation
        config.full_clean()
        config.save()
        
        # Invalidate cache
        cls._invalidate_cache(tenant)
        
        return config
    
    @classmethod
    def apply_persona(
        cls,
        base_prompt: str,
        config: AgentConfiguration
    ) -> str:
        """
        Apply persona settings to a base prompt.
        
        Injects agent name, personality traits, tone, and behavioral
        restrictions into the system prompt.
        
        Args:
            base_prompt: Base system prompt template
            config: AgentConfiguration instance
            
        Returns:
            Enhanced prompt with persona applied
        """
        persona_sections = []
        
        # Add agent identity
        persona_sections.append(f"You are {config.agent_name}, an AI assistant.")
        
        # Add tone guidance
        tone_guidance = {
            'professional': "Maintain a professional and business-like tone.",
            'friendly': "Be warm, friendly, and approachable in your responses.",
            'casual': "Use a casual, conversational tone. Feel free to be informal.",
            'formal': "Use formal language and maintain proper etiquette at all times."
        }
        if config.tone in tone_guidance:
            persona_sections.append(tone_guidance[config.tone])
        
        # Add personality traits
        if config.personality_traits:
            traits_list = [
                f"{trait}: {value}"
                for trait, value in config.personality_traits.items()
            ]
            if traits_list:
                persona_sections.append(
                    f"Your personality traits: {', '.join(traits_list)}"
                )
        
        # Add behavioral restrictions
        if config.behavioral_restrictions:
            restrictions = ', '.join(config.behavioral_restrictions)
            persona_sections.append(
                f"Topics to avoid: {restrictions}. "
                "If asked about these topics, politely decline and offer to help with something else."
            )
        
        # Add required disclaimers
        if config.required_disclaimers:
            disclaimers = '\n'.join([f"- {d}" for d in config.required_disclaimers])
            persona_sections.append(
                f"Always include these disclaimers when relevant:\n{disclaimers}"
            )
        
        # Add response length guidance
        persona_sections.append(
            f"Keep responses concise, under {config.max_response_length} characters when possible."
        )
        
        # Add handoff guidance
        persona_sections.append(
            f"If your confidence is below {config.confidence_threshold:.0%}, "
            "or if the topic requires human expertise, offer to connect the customer with a human agent."
        )
        
        # Add agent capabilities (what agent CAN do)
        if config.agent_can_do:
            persona_sections.append(
                f"## What You CAN Do\n\n{config.agent_can_do}"
            )
        
        # Add agent limitations (what agent CANNOT do)
        if config.agent_cannot_do:
            persona_sections.append(
                f"## What You CANNOT Do\n\n{config.agent_cannot_do}"
            )
        
        # Combine base prompt with persona
        persona_prompt = "\n\n".join(persona_sections)
        enhanced_prompt = f"{base_prompt}\n\n## Your Persona\n\n{persona_prompt}"
        
        return enhanced_prompt
    
    @classmethod
    def get_default_configuration(cls, tenant) -> AgentConfiguration:
        """
        Create and return default configuration for a new tenant.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            Newly created AgentConfiguration with default values
        """
        config, created = AgentConfiguration.objects.get_or_create(
            tenant=tenant,
            defaults=cls._get_default_config_dict()
        )
        
        if created:
            # Cache the new configuration
            cache_key = cls._get_cache_key(str(tenant.id))
            cache.set(cache_key, config, cls.CACHE_TTL)
        
        return config
    
    @staticmethod
    def _get_default_config_dict() -> Dict[str, Any]:
        """Get dictionary of default configuration values."""
        return {
            'agent_name': 'Assistant',
            'personality_traits': {
                'helpful': True,
                'patient': True,
                'professional': True
            },
            'tone': 'friendly',
            'default_model': 'gpt-4o',
            'fallback_models': ['gpt-4o-mini', 'gpt-3.5-turbo'],
            'temperature': 0.7,
            'max_response_length': 500,
            'behavioral_restrictions': [],
            'required_disclaimers': [],
            'confidence_threshold': 0.7,
            'auto_handoff_topics': [],
            'max_low_confidence_attempts': 2,
            'enable_proactive_suggestions': True,
            'enable_spelling_correction': True,
            'enable_rich_messages': True,
        }
    
    @staticmethod
    def _validate_config_data(config_data: Dict[str, Any]) -> None:
        """
        Validate configuration data.
        
        Args:
            config_data: Dictionary of configuration fields
            
        Raises:
            ValidationError: If data is invalid
        """
        # Validate temperature
        if 'temperature' in config_data:
            temp = config_data['temperature']
            if not isinstance(temp, (int, float)) or temp < 0.0 or temp > 2.0:
                raise ValidationError("Temperature must be between 0.0 and 2.0")
        
        # Validate confidence_threshold
        if 'confidence_threshold' in config_data:
            threshold = config_data['confidence_threshold']
            if not isinstance(threshold, (int, float)) or threshold < 0.0 or threshold > 1.0:
                raise ValidationError("Confidence threshold must be between 0.0 and 1.0")
        
        # Validate max_response_length
        if 'max_response_length' in config_data:
            length = config_data['max_response_length']
            if not isinstance(length, int) or length < 50 or length > 2000:
                raise ValidationError("Max response length must be between 50 and 2000")
        
        # Validate max_low_confidence_attempts
        if 'max_low_confidence_attempts' in config_data:
            attempts = config_data['max_low_confidence_attempts']
            if not isinstance(attempts, int) or attempts < 1 or attempts > 10:
                raise ValidationError("Max low confidence attempts must be between 1 and 10")
        
        # Validate tone
        if 'tone' in config_data:
            valid_tones = ['professional', 'friendly', 'casual', 'formal']
            if config_data['tone'] not in valid_tones:
                raise ValidationError(f"Tone must be one of: {', '.join(valid_tones)}")
        
        # Validate JSON fields are proper types
        json_fields = [
            'personality_traits',
            'fallback_models',
            'behavioral_restrictions',
            'required_disclaimers',
            'auto_handoff_topics'
        ]
        for field in json_fields:
            if field in config_data:
                value = config_data[field]
                if field == 'personality_traits' and not isinstance(value, dict):
                    raise ValidationError(f"{field} must be a dictionary")
                elif field != 'personality_traits' and not isinstance(value, list):
                    raise ValidationError(f"{field} must be a list")
    
    @classmethod
    def _invalidate_cache(cls, tenant) -> None:
        """Invalidate cached configuration for tenant."""
        cache_key = cls._get_cache_key(str(tenant.id))
        cache.delete(cache_key)


def create_agent_config_service() -> AgentConfigurationService:
    """
    Factory function to create AgentConfigurationService instance.
    
    Returns:
        AgentConfigurationService instance
    """
    return AgentConfigurationService()
