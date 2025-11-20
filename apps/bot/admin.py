"""
Django admin configuration for bot app.
"""
from django.contrib import admin
from .models import (
    IntentEvent, 
    AgentConfiguration, 
    AgentInteraction, 
    BrowseSession,
    MessageHarmonizationLog,
    ConversationContext
)


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
            'fields': (
                'enable_proactive_suggestions', 
                'enable_spelling_correction', 
                'enable_rich_messages',
                'enable_grounded_validation',
                'enable_feedback_collection',
                'feedback_frequency'
            )
        }),
        ('UX Enhancement Features', {
            'fields': (
                'enable_message_harmonization',
                'harmonization_wait_seconds',
                'enable_immediate_product_display',
                'max_products_to_show',
                'enable_reference_resolution'
            ),
            'classes': ('collapse',)
        }),
        ('Branding', {
            'fields': (
                'use_business_name_as_identity',
                'custom_bot_greeting',
                'agent_can_do',
                'agent_cannot_do'
            ),
            'classes': ('collapse',)
        }),
        ('RAG Configuration', {
            'fields': (
                'enable_document_retrieval',
                'enable_database_retrieval',
                'enable_internet_enrichment',
                'enable_source_attribution',
                'max_document_results',
                'max_database_results',
                'max_internet_results',
                'semantic_search_weight',
                'keyword_search_weight',
                'embedding_model'
            ),
            'classes': ('collapse',)
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



@admin.register(BrowseSession)
class BrowseSessionAdmin(admin.ModelAdmin):
    """Admin interface for BrowseSession model."""
    list_display = [
        'id',
        'tenant',
        'conversation',
        'catalog_type',
        'current_page',
        'total_pages_display',
        'total_items',
        'is_active',
        'expires_at',
        'created_at'
    ]
    list_filter = [
        'catalog_type',
        'is_active',
        'created_at',
        'expires_at',
        'tenant'
    ]
    search_fields = [
        'conversation__id',
        'tenant__name',
        'search_query'
    ]
    readonly_fields = [
        'id',
        'tenant',
        'conversation',
        'total_pages_display',
        'start_index_display',
        'end_index_display',
        'created_at',
        'updated_at'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'tenant', 'conversation', 'created_at', 'updated_at')
        }),
        ('Catalog Configuration', {
            'fields': ('catalog_type', 'search_query', 'filters')
        }),
        ('Pagination State', {
            'fields': (
                'current_page',
                'items_per_page',
                'total_items',
                'total_pages_display',
                'start_index_display',
                'end_index_display'
            )
        }),
        ('Session Status', {
            'fields': ('is_active', 'expires_at')
        }),
    )
    
    def total_pages_display(self, obj):
        """Display total pages."""
        return obj.total_pages
    total_pages_display.short_description = 'Total Pages'
    
    def start_index_display(self, obj):
        """Display start index (1-indexed)."""
        return obj.start_index + 1
    start_index_display.short_description = 'Start Index'
    
    def end_index_display(self, obj):
        """Display end index (1-indexed)."""
        return obj.end_index
    end_index_display.short_description = 'End Index'


@admin.register(MessageHarmonizationLog)
class MessageHarmonizationLogAdmin(admin.ModelAdmin):
    """Admin interface for MessageHarmonizationLog model."""
    list_display = [
        'id',
        'get_tenant',
        'conversation',
        'message_count',
        'wait_time_ms',
        'response_time_ms',
        'typing_indicator_shown',
        'success',
        'created_at'
    ]
    list_filter = [
        'success',
        'typing_indicator_shown',
        'created_at',
        'conversation__tenant'
    ]
    search_fields = [
        'conversation__id',
        'conversation__tenant__name',
        'combined_text',
        'response_generated'
    ]
    readonly_fields = [
        'id',
        'conversation',
        'message_ids',
        'message_count',
        'combined_text',
        'wait_time_ms',
        'first_message_at',
        'last_message_at',
        'response_generated',
        'response_time_ms',
        'typing_indicator_shown',
        'success',
        'error_message',
        'time_span_display',
        'average_gap_display',
        'created_at',
        'updated_at'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'conversation', 'created_at', 'updated_at')
        }),
        ('Input Messages', {
            'fields': ('message_ids', 'message_count', 'combined_text')
        }),
        ('Timing', {
            'fields': (
                'first_message_at',
                'last_message_at',
                'time_span_display',
                'wait_time_ms',
                'average_gap_display'
            )
        }),
        ('Output', {
            'fields': ('response_generated', 'response_time_ms', 'typing_indicator_shown')
        }),
        ('Status', {
            'fields': ('success', 'error_message')
        }),
    )
    
    def get_tenant(self, obj):
        """Get tenant from conversation relationship."""
        return obj.conversation.tenant.name if obj.conversation and obj.conversation.tenant else '-'
    get_tenant.short_description = 'Tenant'
    get_tenant.admin_order_field = 'conversation__tenant__name'
    
    def time_span_display(self, obj):
        """Display time span between first and last message."""
        return f"{obj.get_time_span_seconds():.2f}s"
    time_span_display.short_description = 'Time Span'
    
    def average_gap_display(self, obj):
        """Display average gap between messages."""
        return f"{obj.get_average_message_gap_ms():.0f}ms"
    average_gap_display.short_description = 'Avg Message Gap'


@admin.register(ConversationContext)
class ConversationContextAdmin(admin.ModelAdmin):
    """Admin interface for ConversationContext model."""
    list_display = [
        'id',
        'get_tenant',
        'conversation',
        'current_topic',
        'pending_action',
        'language_locked',
        'last_interaction',
        'is_expired_display',
        'created_at'
    ]
    list_filter = [
        'current_topic',
        'language_locked',
        'last_interaction',
        'context_expires_at',
        'conversation__tenant'
    ]
    search_fields = [
        'conversation__id',
        'conversation__tenant__name',
        'current_topic',
        'pending_action',
        'conversation_summary'
    ]
    readonly_fields = [
        'id',
        'conversation',
        'last_interaction',
        'is_expired_display',
        'created_at',
        'updated_at'
    ]
    ordering = ['-last_interaction']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'conversation', 'created_at', 'updated_at')
        }),
        ('Current State', {
            'fields': (
                'current_topic',
                'pending_action',
                'extracted_entities',
                'clarification_attempts'
            )
        }),
        ('References', {
            'fields': ('last_product_viewed', 'last_service_viewed')
        }),
        ('Memory', {
            'fields': ('conversation_summary', 'key_facts', 'shopping_cart')
        }),
        ('Message Harmonization', {
            'fields': ('last_message_time', 'message_buffer'),
            'classes': ('collapse',)
        }),
        ('Language', {
            'fields': ('language_locked',),
            'classes': ('collapse',)
        }),
        ('Timing', {
            'fields': ('last_interaction', 'context_expires_at', 'is_expired_display')
        }),
    )
    
    def get_tenant(self, obj):
        """Get tenant from conversation relationship."""
        return obj.conversation.tenant.name if obj.conversation and obj.conversation.tenant else '-'
    get_tenant.short_description = 'Tenant'
    get_tenant.admin_order_field = 'conversation__tenant__name'
    
    def is_expired_display(self, obj):
        """Display whether context is expired."""
        return obj.is_expired()
    is_expired_display.short_description = 'Is Expired'
    is_expired_display.boolean = True
