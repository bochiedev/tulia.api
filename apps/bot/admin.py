"""
Django admin configuration for bot app.
"""
from django.contrib import admin
from .models import IntentEvent, AgentConfiguration


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
