"""
Serializers for bot API endpoints.
"""
from rest_framework import serializers
from apps.bot.models import AgentConfiguration, KnowledgeEntry, AgentInteraction


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



class KnowledgeEntrySerializer(serializers.ModelSerializer):
    """
    Serializer for KnowledgeEntry with full field access.
    
    Provides read/write access to all knowledge entry fields including
    embeddings, metadata, and versioning information.
    """
    
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    keywords_list = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        help_text="List of keywords (will be stored as comma-separated string)"
    )
    
    class Meta:
        model = KnowledgeEntry
        fields = [
            'id',
            'tenant',
            'tenant_name',
            # Classification
            'entry_type',
            'category',
            # Content
            'title',
            'content',
            # Search
            'keywords',
            'keywords_list',
            'embedding',
            # Metadata
            'metadata',
            'priority',
            'is_active',
            'version',
            # Timestamps
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'tenant',
            'tenant_name',
            'embedding',
            'version',
            'created_at',
            'updated_at',
        ]
    
    def validate_entry_type(self, value):
        """Validate entry type is a valid choice."""
        valid_types = ['faq', 'policy', 'product_info', 'service_info', 'procedure', 'general']
        if value not in valid_types:
            raise serializers.ValidationError(
                f"Entry type must be one of: {', '.join(valid_types)}"
            )
        return value
    
    def validate_priority(self, value):
        """Validate priority is within valid range."""
        if value < 0 or value > 100:
            raise serializers.ValidationError("Priority must be between 0 and 100")
        return value
    
    def validate_metadata(self, value):
        """Validate metadata is a dictionary."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Metadata must be a dictionary")
        return value
    
    def to_representation(self, instance):
        """Add keywords_list to output."""
        data = super().to_representation(instance)
        # Add keywords as list in output
        data['keywords_list'] = instance.get_keywords_list()
        return data


class KnowledgeEntryCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new knowledge entries.
    
    Simplified serializer for entry creation that accepts keywords as a list
    and handles embedding generation automatically.
    """
    
    keywords_list = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="List of keywords for search optimization"
    )
    
    class Meta:
        model = KnowledgeEntry
        fields = [
            'entry_type',
            'category',
            'title',
            'content',
            'keywords_list',
            'metadata',
            'priority',
            'is_active',
        ]
    
    def validate_entry_type(self, value):
        """Validate entry type is a valid choice."""
        valid_types = ['faq', 'policy', 'product_info', 'service_info', 'procedure', 'general']
        if value not in valid_types:
            raise serializers.ValidationError(
                f"Entry type must be one of: {', '.join(valid_types)}"
            )
        return value
    
    def validate_priority(self, value):
        """Validate priority is within valid range."""
        if value < 0 or value > 100:
            raise serializers.ValidationError("Priority must be between 0 and 100")
        return value
    
    def validate_metadata(self, value):
        """Validate metadata is a dictionary."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Metadata must be a dictionary")
        return value


class KnowledgeEntryUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating knowledge entries.
    
    Supports partial updates and handles embedding regeneration when
    title or content changes.
    """
    
    keywords_list = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="List of keywords for search optimization"
    )
    
    class Meta:
        model = KnowledgeEntry
        fields = [
            'entry_type',
            'category',
            'title',
            'content',
            'keywords_list',
            'metadata',
            'priority',
            'is_active',
        ]
    
    def validate_entry_type(self, value):
        """Validate entry type is a valid choice."""
        valid_types = ['faq', 'policy', 'product_info', 'service_info', 'procedure', 'general']
        if value not in valid_types:
            raise serializers.ValidationError(
                f"Entry type must be one of: {', '.join(valid_types)}"
            )
        return value
    
    def validate_priority(self, value):
        """Validate priority is within valid range."""
        if value < 0 or value > 100:
            raise serializers.ValidationError("Priority must be between 0 and 100")
        return value
    
    def validate_metadata(self, value):
        """Validate metadata is a dictionary."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Metadata must be a dictionary")
        return value


class KnowledgeEntrySearchSerializer(serializers.Serializer):
    """
    Serializer for knowledge entry search results.
    
    Includes the entry data plus the similarity score from semantic search.
    """
    
    entry = KnowledgeEntrySerializer(read_only=True)
    similarity_score = serializers.FloatField(
        read_only=True,
        help_text="Semantic similarity score (0.0-1.0)"
    )


class KnowledgeEntryBulkImportSerializer(serializers.Serializer):
    """
    Serializer for bulk importing knowledge entries.
    
    Accepts a list of entry data and validates each entry before import.
    """
    
    entries = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        max_length=100,
        help_text="List of knowledge entries to import (max 100 per request)"
    )
    
    def validate_entries(self, value):
        """Validate each entry in the list."""
        validated_entries = []
        
        for idx, entry_data in enumerate(value):
            # Validate required fields
            required_fields = ['entry_type', 'title', 'content']
            for field in required_fields:
                if field not in entry_data:
                    raise serializers.ValidationError(
                        f"Entry {idx}: Missing required field '{field}'"
                    )
            
            # Validate entry type
            valid_types = ['faq', 'policy', 'product_info', 'service_info', 'procedure', 'general']
            if entry_data['entry_type'] not in valid_types:
                raise serializers.ValidationError(
                    f"Entry {idx}: Invalid entry_type. Must be one of: {', '.join(valid_types)}"
                )
            
            # Validate priority if provided
            if 'priority' in entry_data:
                priority = entry_data['priority']
                if not isinstance(priority, int) or priority < 0 or priority > 100:
                    raise serializers.ValidationError(
                        f"Entry {idx}: Priority must be an integer between 0 and 100"
                    )
            
            # Validate metadata if provided
            if 'metadata' in entry_data and not isinstance(entry_data['metadata'], dict):
                raise serializers.ValidationError(
                    f"Entry {idx}: Metadata must be a dictionary"
                )
            
            validated_entries.append(entry_data)
        
        return validated_entries



class AgentInteractionSerializer(serializers.ModelSerializer):
    """
    Serializer for AgentInteraction with full field access.
    
    Provides read-only access to agent interaction tracking data
    for analytics and monitoring purposes.
    """
    
    tenant_id = serializers.UUIDField(source='conversation.tenant.id', read_only=True)
    tenant_name = serializers.CharField(source='conversation.tenant.name', read_only=True)
    customer_phone = serializers.CharField(source='conversation.customer.phone_e164', read_only=True)
    
    # Computed fields
    total_tokens = serializers.SerializerMethodField()
    cost_per_token = serializers.SerializerMethodField()
    intent_names = serializers.SerializerMethodField()
    primary_intent = serializers.SerializerMethodField()
    
    class Meta:
        model = AgentInteraction
        fields = [
            'id',
            'conversation',
            'tenant_id',
            'tenant_name',
            'customer_phone',
            # Input
            'customer_message',
            'detected_intents',
            'intent_names',
            'primary_intent',
            # Processing
            'model_used',
            'context_size',
            'processing_time_ms',
            # Output
            'agent_response',
            'confidence_score',
            'handoff_triggered',
            'handoff_reason',
            'message_type',
            # Metrics
            'token_usage',
            'total_tokens',
            'estimated_cost',
            'cost_per_token',
            # Timestamps
            'created_at',
            'updated_at',
        ]
        read_only_fields = '__all__'
    
    def get_total_tokens(self, obj):
        """Get total token count."""
        return obj.get_total_tokens()
    
    def get_cost_per_token(self, obj):
        """Get cost per token."""
        return obj.get_cost_per_token()
    
    def get_intent_names(self, obj):
        """Get list of detected intent names."""
        return obj.get_intent_names()
    
    def get_primary_intent(self, obj):
        """Get primary intent."""
        return obj.get_primary_intent()


class AgentInteractionListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for listing agent interactions.
    
    Provides essential fields for list views without heavy computed fields.
    """
    
    tenant_name = serializers.CharField(source='conversation.tenant.name', read_only=True)
    
    class Meta:
        model = AgentInteraction
        fields = [
            'id',
            'conversation',
            'tenant_name',
            'model_used',
            'confidence_score',
            'handoff_triggered',
            'message_type',
            'estimated_cost',
            'created_at',
        ]
        read_only_fields = '__all__'


class AgentInteractionStatsSerializer(serializers.Serializer):
    """
    Serializer for agent interaction statistics.
    
    Provides aggregated metrics for analytics dashboards.
    """
    
    total_interactions = serializers.IntegerField(read_only=True)
    total_cost = serializers.DecimalField(max_digits=10, decimal_places=6, read_only=True)
    avg_confidence = serializers.FloatField(read_only=True)
    handoff_count = serializers.IntegerField(read_only=True)
    handoff_rate = serializers.FloatField(read_only=True)
    
    # By model
    interactions_by_model = serializers.DictField(read_only=True)
    cost_by_model = serializers.DictField(read_only=True)
    
    # By message type
    interactions_by_type = serializers.DictField(read_only=True)
    
    # Confidence distribution
    high_confidence_count = serializers.IntegerField(read_only=True)
    low_confidence_count = serializers.IntegerField(read_only=True)
    
    # Performance
    avg_processing_time_ms = serializers.FloatField(read_only=True)
    avg_tokens = serializers.FloatField(read_only=True)
