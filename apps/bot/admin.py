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
    ConversationContext,
    IntentClassificationLog,
    LLMUsageLog,
    PaymentRequest,
    KnowledgeEntry,
    Document,
    DocumentChunk,
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
        ('Checkout State', {
            'fields': (
                'checkout_state',
                'selected_product_id',
                'selected_quantity'
            ),
            'classes': ('collapse',)
        }),
        ('Session Tracking', {
            'fields': (
                'current_session_start',
                'session_message_count',
                'last_bot_message',
                'last_customer_message'
            ),
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


@admin.register(IntentClassificationLog)
class IntentClassificationLogAdmin(admin.ModelAdmin):
    """Admin interface for IntentClassificationLog model."""
    list_display = [
        'id',
        'get_tenant',
        'conversation',
        'intent_name',
        'confidence_score',
        'model_used',
        'processing_time_ms',
        'created_at'
    ]
    list_filter = [
        'intent_name',
        'model_used',
        'created_at',
        'tenant'
    ]
    search_fields = [
        'message_text',
        'intent_name',
        'conversation__id',
        'tenant__name'
    ]
    readonly_fields = [
        'id',
        'tenant',
        'conversation',
        'message_text',
        'intent_name',
        'confidence_score',
        'model_used',
        'processing_time_ms',
        'all_intents',
        'slots',
        'metadata',
        'created_at',
        'updated_at'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'tenant', 'conversation', 'created_at', 'updated_at')
        }),
        ('Input', {
            'fields': ('message_text',)
        }),
        ('Classification Results', {
            'fields': ('intent_name', 'confidence_score', 'all_intents')
        }),
        ('Processing', {
            'fields': ('model_used', 'processing_time_ms')
        }),
        ('Extracted Data', {
            'fields': ('slots',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )
    
    def get_tenant(self, obj):
        """Get tenant name."""
        return obj.tenant.name if obj.tenant else '-'
    get_tenant.short_description = 'Tenant'
    get_tenant.admin_order_field = 'tenant__name'


@admin.register(LLMUsageLog)
class LLMUsageLogAdmin(admin.ModelAdmin):
    """Admin interface for LLMUsageLog model."""
    list_display = [
        'id',
        'get_tenant',
        'provider',
        'model',
        'task_type',
        'total_tokens',
        'cost',
        'success',
        'created_at'
    ]
    list_filter = [
        'provider',
        'model',
        'task_type',
        'success',
        'created_at',
        'tenant'
    ]
    search_fields = [
        'provider',
        'model',
        'task_type',
        'tenant__name'
    ]
    readonly_fields = [
        'id',
        'tenant',
        'conversation',
        'provider',
        'model',
        'task_type',
        'input_tokens',
        'output_tokens',
        'total_tokens',
        'cost',
        'response_time_ms',
        'success',
        'error_message',
        'metadata',
        'created_at',
        'updated_at'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'tenant', 'conversation', 'created_at', 'updated_at')
        }),
        ('Provider Information', {
            'fields': ('provider', 'model', 'task_type')
        }),
        ('Usage Metrics', {
            'fields': ('input_tokens', 'output_tokens', 'total_tokens', 'cost')
        }),
        ('Performance', {
            'fields': ('response_time_ms', 'success', 'error_message')
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )
    
    def get_tenant(self, obj):
        """Get tenant name."""
        return obj.tenant.name if obj.tenant else '-'
    get_tenant.short_description = 'Tenant'
    get_tenant.admin_order_field = 'tenant__name'


@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    """Admin interface for PaymentRequest model."""
    list_display = [
        'id',
        'get_tenant',
        'conversation',
        'amount',
        'currency',
        'status',
        'payment_provider',
        'initiated_at',
        'completed_at'
    ]
    list_filter = [
        'status',
        'payment_provider',
        'currency',
        'initiated_at',
        'tenant'
    ]
    search_fields = [
        'provider_transaction_id',
        'conversation__id',
        'tenant__name'
    ]
    readonly_fields = [
        'id',
        'tenant',
        'conversation',
        'order',
        'amount',
        'currency',
        'status',
        'payment_provider',
        'provider_transaction_id',
        'initiated_at',
        'completed_at',
        'error_code',
        'error_message',
        'metadata',
        'processing_time_display',
        'created_at',
        'updated_at'
    ]
    ordering = ['-initiated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'tenant', 'conversation', 'order', 'created_at', 'updated_at')
        }),
        ('Payment Information', {
            'fields': ('amount', 'currency', 'status')
        }),
        ('Provider Information', {
            'fields': ('payment_provider', 'provider_transaction_id')
        }),
        ('Timing', {
            'fields': ('initiated_at', 'completed_at', 'processing_time_display')
        }),
        ('Error Information', {
            'fields': ('error_code', 'error_message'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )
    
    def get_tenant(self, obj):
        """Get tenant name."""
        return obj.tenant.name if obj.tenant else '-'
    get_tenant.short_description = 'Tenant'
    get_tenant.admin_order_field = 'tenant__name'
    
    def processing_time_display(self, obj):
        """Display processing time."""
        time_seconds = obj.get_processing_time_seconds()
        if time_seconds is not None:
            return f"{time_seconds:.2f}s"
        return '-'
    processing_time_display.short_description = 'Processing Time'


@admin.register(KnowledgeEntry)
class KnowledgeEntryAdmin(admin.ModelAdmin):
    """Admin interface for KnowledgeEntry model."""
    list_display = [
        'id',
        'get_tenant',
        'title',
        'entry_type',
        'category',
        'priority',
        'is_active',
        'version',
        'created_at'
    ]
    list_filter = [
        'entry_type',
        'category',
        'is_active',
        'priority',
        'created_at',
        'tenant'
    ]
    search_fields = [
        'title',
        'content',
        'keywords',
        'tenant__name'
    ]
    readonly_fields = [
        'id',
        'embedding',
        'version',
        'created_at',
        'updated_at'
    ]
    ordering = ['-priority', '-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'tenant', 'created_at', 'updated_at')
        }),
        ('Classification', {
            'fields': ('entry_type', 'category', 'priority', 'is_active')
        }),
        ('Content', {
            'fields': ('title', 'content', 'keywords')
        }),
        ('Search Optimization', {
            'fields': ('embedding',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata', 'version'),
            'classes': ('collapse',)
        }),
    )
    
    def get_tenant(self, obj):
        """Get tenant name."""
        return obj.tenant.name if obj.tenant else '-'
    get_tenant.short_description = 'Tenant'
    get_tenant.admin_order_field = 'tenant__name'


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    """Admin interface for Document model."""
    list_display = [
        'id',
        'get_tenant',
        'file_name',
        'file_type',
        'status',
        'processing_progress',
        'chunk_count',
        'total_tokens',
        'created_at'
    ]
    list_filter = [
        'file_type',
        'status',
        'created_at',
        'tenant'
    ]
    search_fields = [
        'file_name',
        'tenant__name'
    ]
    readonly_fields = [
        'id',
        'file_path',
        'file_size',
        'chunk_count',
        'total_tokens',
        'created_at',
        'updated_at'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'tenant', 'created_at', 'updated_at')
        }),
        ('File Information', {
            'fields': ('file_name', 'file_type', 'file_path', 'file_size')
        }),
        ('Processing Status', {
            'fields': ('status', 'processing_progress', 'error_message')
        }),
        ('Statistics', {
            'fields': ('chunk_count', 'total_tokens')
        }),
    )
    
    def get_tenant(self, obj):
        """Get tenant name."""
        return obj.tenant.name if obj.tenant else '-'
    get_tenant.short_description = 'Tenant'
    get_tenant.admin_order_field = 'tenant__name'


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    """Admin interface for DocumentChunk model."""
    list_display = [
        'id',
        'get_document',
        'chunk_index',
        'token_count',
        'created_at'
    ]
    list_filter = [
        'document__file_type',
        'created_at',
        'document__tenant'
    ]
    search_fields = [
        'content',
        'document__file_name',
        'document__tenant__name'
    ]
    readonly_fields = [
        'id',
        'document',
        'chunk_index',
        'content',
        'token_count',
        'embedding',
        'created_at',
        'updated_at'
    ]
    ordering = ['document', 'chunk_index']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'document', 'chunk_index', 'created_at', 'updated_at')
        }),
        ('Content', {
            'fields': ('content', 'token_count')
        }),
        ('Embedding', {
            'fields': ('embedding',),
            'classes': ('collapse',)
        }),
    )
    
    def get_document(self, obj):
        """Get document file name."""
        return obj.document.file_name if obj.document else '-'
    get_document.short_description = 'Document'
    get_document.admin_order_field = 'document__file_name'


# End of admin configuration
