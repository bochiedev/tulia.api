"""
Serializers for bot API endpoints.
"""
from rest_framework import serializers
from apps.bot.models import AgentConfiguration


class AgentConfigurationSerializer(serializers.ModelSerializer):
    """
    Serializer for AgentConfiguration.
    
    Provides full read/write access to agent configuration fields
    with validation for all constraints.
    """
    
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    
    class Meta:
        model = AgentConfiguration
        fields = [
            'id',
            'tenant',
            'tenant_name',
            # Persona Configuration
            'agent_name',
            'personality_traits',
            'tone',
            # Model Configuration
            'default_model',
            'fallback_models',
            'temperature',
            # Behavior Configuration
            'max_response_length',
            'behavioral_restrictions',
            'required_disclaimers',
            # Handoff Configuration
            'confidence_threshold',
            'auto_handoff_topics',
            'max_low_confidence_attempts',
            # Feature Flags
            'enable_proactive_suggestions',
            'enable_spelling_correction',
            'enable_rich_messages',
            # Timestamps
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'tenant_name', 'created_at', 'updated_at']
    
    def validate_temperature(self, value):
        """Validate temperature is within valid range."""
        if value < 0.0 or value > 2.0:
            raise serializers.ValidationError("Temperature must be between 0.0 and 2.0")
        return value
    
    def validate_confidence_threshold(self, value):
        """Validate confidence threshold is within valid range."""
        if value < 0.0 or value > 1.0:
            raise serializers.ValidationError("Confidence threshold must be between 0.0 and 1.0")
        return value
    
    def validate_max_response_length(self, value):
        """Validate max response length is within valid range."""
        if value < 50 or value > 2000:
            raise serializers.ValidationError("Max response length must be between 50 and 2000")
        return value
    
    def validate_max_low_confidence_attempts(self, value):
        """Validate max low confidence attempts is within valid range."""
        if value < 1 or value > 10:
            raise serializers.ValidationError("Max low confidence attempts must be between 1 and 10")
        return value
    
    def validate_tone(self, value):
        """Validate tone is a valid choice."""
        valid_tones = ['professional', 'friendly', 'casual', 'formal']
        if value not in valid_tones:
            raise serializers.ValidationError(
                f"Tone must be one of: {', '.join(valid_tones)}"
            )
        return value
    
    def validate_personality_traits(self, value):
        """Validate personality traits is a dictionary."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Personality traits must be a dictionary")
        return value
    
    def validate_fallback_models(self, value):
        """Validate fallback models is a list."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Fallback models must be a list")
        return value
    
    def validate_behavioral_restrictions(self, value):
        """Validate behavioral restrictions is a list."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Behavioral restrictions must be a list")
        return value
    
    def validate_required_disclaimers(self, value):
        """Validate required disclaimers is a list."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Required disclaimers must be a list")
        return value
    
    def validate_auto_handoff_topics(self, value):
        """Validate auto handoff topics is a list."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Auto handoff topics must be a list")
        return value


class AgentConfigurationUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating AgentConfiguration.
    
    Allows partial updates to agent configuration fields.
    """
    
    class Meta:
        model = AgentConfiguration
        fields = [
            # Persona Configuration
            'agent_name',
            'personality_traits',
            'tone',
            # Model Configuration
            'default_model',
            'fallback_models',
            'temperature',
            # Behavior Configuration
            'max_response_length',
            'behavioral_restrictions',
            'required_disclaimers',
            # Handoff Configuration
            'confidence_threshold',
            'auto_handoff_topics',
            'max_low_confidence_attempts',
            # Feature Flags
            'enable_proactive_suggestions',
            'enable_spelling_correction',
            'enable_rich_messages',
        ]
    
    def validate_temperature(self, value):
        """Validate temperature is within valid range."""
        if value < 0.0 or value > 2.0:
            raise serializers.ValidationError("Temperature must be between 0.0 and 2.0")
        return value
    
    def validate_confidence_threshold(self, value):
        """Validate confidence threshold is within valid range."""
        if value < 0.0 or value > 1.0:
            raise serializers.ValidationError("Confidence threshold must be between 0.0 and 1.0")
        return value
    
    def validate_max_response_length(self, value):
        """Validate max response length is within valid range."""
        if value < 50 or value > 2000:
            raise serializers.ValidationError("Max response length must be between 50 and 2000")
        return value
    
    def validate_max_low_confidence_attempts(self, value):
        """Validate max low confidence attempts is within valid range."""
        if value < 1 or value > 10:
            raise serializers.ValidationError("Max low confidence attempts must be between 1 and 10")
        return value
    
    def validate_tone(self, value):
        """Validate tone is a valid choice."""
        valid_tones = ['professional', 'friendly', 'casual', 'formal']
        if value not in valid_tones:
            raise serializers.ValidationError(
                f"Tone must be one of: {', '.join(valid_tones)}"
            )
        return value
