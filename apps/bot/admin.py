"""
Django admin configuration for bot app.
"""
from django.contrib import admin
from .models import IntentEvent, AgentConfiguration, AgentInteraction


@admin.register(IntentEvent)
class IntentEventAdmin(admin.ModelAdmin):
    """Admin interface for IntentEvent model."""
    list_display = ['id', 'tenant', 'conversation', 'intent_name', 'confidence_score', 'model', 'created_at']
    list_filter = ['intent_name', 'model', 'created_at', 'tenant']
    search_fields = ['message_text', 'intent_name', 'conversation__id']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'tenant', 'conversation', 'created_at', 'updated_at')
        }),
        ('Intent Classification', {
            'fields': ('intent_name', 'confidence_score', 'model', 'message_text')
        }),
        ('Extracted Data', {
            'fields': ('slots',)
        }),
        ('Metadata', {
            'fields': ('processing_time_ms', 'metadata'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AgentConfiguration)
class AgentConfigurationAdmin(admin.ModelAdmin):
    """Admin interface for AgentConfiguration model."""
    list_display = ['tenant', 'agent_name', 'tone', 'default_model', 'confidence_threshold', 'created_at']
    list_filter = ['tone', 'default_model', 'enable_proactive_suggestions', 'enable_spelling_correction', 'enable_rich_messages']
    search_fields = ['tenant__name', 'agent_name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'tenant', 'created_at', 'updated_at')
        }),
        ('Persona Configuration', {
            'fields': ('agent_name', 'personality_traits', 'tone')
        }),
        ('Model Configuration', {
            'fields': ('default_model', 'fallback_models', 'temperature')
        }),
        ('Behavior Configuration', {
            'fields': ('max_response_length', 'behavioral_restrictions', 'required_disclaimers')
        }),
        ('Handoff Configuration', {
            'fields': ('confidence_threshold', 'auto_handoff_topics', 'max_low_confidence_attempts')
        }),
        ('Feature Flags', {
            'fields': ('enable_proactive_suggestions', 'enable_spelling_correction', 'enable_rich_messages')
        }),
    )


@admin.register(AgentInteraction)
class AgentInteractionAdmin(admin.ModelAdmin):
    """Admin interface for AgentInteraction model."""
    list_display = [
        'id', 
        'get_tenant', 
        'conversation', 
        'model_used', 
        'confidence_score', 
        'handoff_triggered',
        'message_type',
        'estimated_cost',
        'created_at'
    ]
    list_filter = [
        'model_used', 
        'handoff_triggered', 
        'message_type', 
        'created_at',
        'conversation__tenant'
    ]
    search_fields = [
        'customer_message', 
        'agent_response', 
        'conversation__id',
        'conversation__tenant__name'
    ]
    readonly_fields = [
        'id', 
        'conversation',
        'customer_message',
        'detected_intents',
        'model_used',
        'context_size',
        'processing_time_ms',
        'agent_response',
        'confidence_score',
        'handoff_triggered',
        'handoff_reason',
        'message_type',
        'token_usage',
        'estimated_cost',
        'created_at', 
        'updated_at'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'conversation', 'created_at', 'updated_at')
        }),
        ('Input', {
            'fields': ('customer_message', 'detected_intents')
        }),
        ('Processing', {
            'fields': ('model_used', 'context_size', 'processing_time_ms')
        }),
        ('Output', {
            'fields': ('agent_response', 'confidence_score', 'message_type')
        }),
        ('Handoff', {
            'fields': ('handoff_triggered', 'handoff_reason'),
            'classes': ('collapse',)
        }),
        ('Metrics', {
            'fields': ('token_usage', 'estimated_cost'),
            'classes': ('collapse',)
        }),
    )
    
    def get_tenant(self, obj):
        """Get tenant from conversation relationship."""
        return obj.conversation.tenant.name if obj.conversation and obj.conversation.tenant else '-'
    get_tenant.short_description = 'Tenant'
    get_tenant.admin_order_field = 'conversation__tenant__name'
