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
    CheckoutSession,
    ResponseValidationLog,
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
        ('Conversation Flow Fixes', {
            'fields': (
                'enable_echo_prevention',
                'enable_disclaimer_removal',
                'max_response_sentences',
                'enable_quick_checkout',
                'max_checkout_messages',
                'force_interactive_messages',
                'fallback_to_text_on_error'
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


# Sales Orchestration Refactor Admin Interfaces

from .models_sales_orchestration import (
    IntentClassificationLog,
    LLMUsageLog,
    PaymentRequest,
)


@admin.register(IntentClassificationLog)
class IntentClassificationLogAdmin(admin.ModelAdmin):
    """Admin interface for IntentClassificationLog model."""
    list_display = ['id', 'tenant', 'conversation', 'detected_intent', 'confidence', 'method', 'classification_time_ms', 'created_at']
    list_filter = ['detected_intent', 'method', 'created_at', 'tenant']
    search_fields = ['detected_intent', 'conversation__id', 'tenant__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'tenant', 'conversation', 'message', 'created_at', 'updated_at')
        }),
        ('Classification', {
            'fields': ('detected_intent', 'confidence', 'method', 'classification_time_ms')
        }),
        ('Extracted Data', {
            'fields': ('extracted_slots', 'detected_language')
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Disable manual creation - logs are auto-generated."""
        return False


@admin.register(LLMUsageLog)
class LLMUsageLogAdmin(admin.ModelAdmin):
    """Admin interface for LLMUsageLog model."""
    list_display = ['id', 'tenant', 'model_name', 'task_type', 'total_tokens', 'estimated_cost_usd', 'created_at']
    list_filter = ['model_name', 'task_type', 'created_at', 'tenant']
    search_fields = ['model_name', 'task_type', 'tenant__name', 'conversation__id']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'tenant', 'conversation', 'created_at', 'updated_at')
        }),
        ('Model', {
            'fields': ('model_name', 'task_type')
        }),
        ('Usage', {
            'fields': ('input_tokens', 'output_tokens', 'total_tokens')
        }),
        ('Cost', {
            'fields': ('estimated_cost_usd',)
        }),
        ('Metadata', {
            'fields': ('prompt_template', 'response_preview', 'metadata'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Disable manual creation - logs are auto-generated."""
        return False


@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    """Admin interface for PaymentRequest model."""
    list_display = ['id', 'tenant', 'customer', 'amount', 'currency', 'payment_method', 'status', 'created_at']
    list_filter = ['payment_method', 'status', 'currency', 'created_at', 'tenant']
    search_fields = ['provider_reference', 'phone_number', 'customer__phone_e164', 'tenant__name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'callback_received_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'tenant', 'customer', 'order', 'appointment', 'created_at', 'updated_at')
        }),
        ('Payment Details', {
            'fields': ('amount', 'currency', 'payment_method', 'phone_number', 'payment_link')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Provider Details', {
            'fields': ('provider_reference', 'provider_response')
        }),
        ('Callback', {
            'fields': ('callback_received_at', 'callback_data'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_success', 'mark_as_failed', 'mark_as_cancelled']
    
    def mark_as_success(self, request, queryset):
        """Mark selected payment requests as successful."""
        updated = queryset.update(status='SUCCESS')
        self.message_user(request, f'{updated} payment request(s) marked as successful.')
    mark_as_success.short_description = 'Mark as successful'
    
    def mark_as_failed(self, request, queryset):
        """Mark selected payment requests as failed."""
        updated = queryset.update(status='FAILED')
        self.message_user(request, f'{updated} payment request(s) marked as failed.')
    mark_as_failed.short_description = 'Mark as failed'
    
    def mark_as_cancelled(self, request, queryset):
        """Mark selected payment requests as cancelled."""
        updated = queryset.update(status='CANCELLED')
        self.message_user(request, f'{updated} payment request(s) marked as cancelled.')
    mark_as_cancelled.short_description = 'Mark as cancelled'


# Bot Conversation Flow Fixes Admin Interfaces

@admin.register(CheckoutSession)
class CheckoutSessionAdmin(admin.ModelAdmin):
    """Admin interface for CheckoutSession model."""
    list_display = [
        'id',
        'tenant',
        'conversation',
        'customer',
        'state',
        'message_count',
        'started_at',
        'completed_at',
        'is_active_display'
    ]
    list_filter = [
        'state',
        'started_at',
        'completed_at',
        'abandoned_at',
        'tenant'
    ]
    search_fields = [
        'conversation__id',
        'customer__phone_e164',
        'tenant__name'
    ]
    readonly_fields = [
        'id',
        'conversation',
        'customer',
        'tenant',
        'started_at',
        'completed_at',
        'abandoned_at',
        'is_active_display',
        'is_completed_display',
        'is_abandoned_display',
        'created_at',
        'updated_at'
    ]
    ordering = ['-started_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'tenant', 'conversation', 'customer', 'created_at', 'updated_at')
        }),
        ('State', {
            'fields': ('state', 'message_count')
        }),
        ('Data', {
            'fields': ('selected_product', 'quantity', 'order', 'payment_request')
        }),
        ('Timing', {
            'fields': (
                'started_at',
                'completed_at',
                'abandoned_at',
                'is_active_display',
                'is_completed_display',
                'is_abandoned_display'
            )
        }),
    )
    
    def is_active_display(self, obj):
        """Display whether checkout is active."""
        return obj.is_active()
    is_active_display.short_description = 'Is Active'
    is_active_display.boolean = True
    
    def is_completed_display(self, obj):
        """Display whether checkout is completed."""
        return obj.is_completed()
    is_completed_display.short_description = 'Is Completed'
    is_completed_display.boolean = True
    
    def is_abandoned_display(self, obj):
        """Display whether checkout is abandoned."""
        return obj.is_abandoned()
    is_abandoned_display.short_description = 'Is Abandoned'
    is_abandoned_display.boolean = True
    
    actions = ['mark_as_abandoned']
    
    def mark_as_abandoned(self, request, queryset):
        """Mark selected checkout sessions as abandoned."""
        count = 0
        for session in queryset:
            if session.is_active():
                session.mark_abandoned()
                count += 1
        self.message_user(request, f'{count} checkout session(s) marked as abandoned.')
    mark_as_abandoned.short_description = 'Mark as abandoned'


@admin.register(ResponseValidationLog)
class ResponseValidationLogAdmin(admin.ModelAdmin):
    """Admin interface for ResponseValidationLog model."""
    list_display = [
        'id',
        'get_tenant',
        'conversation',
        'had_echo',
        'had_disclaimer',
        'exceeded_length',
        'missing_cta',
        'validation_time_ms',
        'issue_count_display',
        'created_at'
    ]
    list_filter = [
        'had_echo',
        'had_disclaimer',
        'exceeded_length',
        'missing_cta',
        'created_at',
        'conversation__tenant'
    ]
    search_fields = [
        'conversation__id',
        'conversation__tenant__name',
        'original_response',
        'cleaned_response'
    ]
    readonly_fields = [
        'id',
        'conversation',
        'message',
        'had_echo',
        'had_disclaimer',
        'exceeded_length',
        'missing_cta',
        'original_response',
        'cleaned_response',
        'validation_time_ms',
        'issues_found',
        'issue_count_display',
        'has_any_issues_display',
        'created_at',
        'updated_at'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'conversation', 'message', 'created_at', 'updated_at')
        }),
        ('Validation Results', {
            'fields': (
                'had_echo',
                'had_disclaimer',
                'exceeded_length',
                'missing_cta',
                'has_any_issues_display',
                'issue_count_display'
            )
        }),
        ('Content', {
            'fields': ('original_response', 'cleaned_response')
        }),
        ('Metadata', {
            'fields': ('validation_time_ms', 'issues_found'),
            'classes': ('collapse',)
        }),
    )
    
    def get_tenant(self, obj):
        """Get tenant from conversation relationship."""
        return obj.conversation.tenant.name if obj.conversation and obj.conversation.tenant else '-'
    get_tenant.short_description = 'Tenant'
    get_tenant.admin_order_field = 'conversation__tenant__name'
    
    def issue_count_display(self, obj):
        """Display count of issues found."""
        return obj.get_issue_count()
    issue_count_display.short_description = 'Issue Count'
    
    def has_any_issues_display(self, obj):
        """Display whether any issues were found."""
        return obj.has_any_issues()
    has_any_issues_display.short_description = 'Has Issues'
    has_any_issues_display.boolean = True
    
    def has_add_permission(self, request):
        """Disable manual creation - logs are auto-generated."""
        return False
