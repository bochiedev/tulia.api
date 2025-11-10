"""
Django admin configuration for messaging app.
"""
from django.contrib import admin
from .models import Conversation, Message, MessageTemplate


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """Admin interface for Conversation."""
    
    list_display = [
        'id', 'tenant', 'customer', 'status', 'channel',
        'last_intent', 'updated_at'
    ]
    list_filter = ['status', 'channel', 'tenant']
    search_fields = [
        'id', 'tenant__name', 'customer__name',
        'last_intent'
    ]
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'handoff_at'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'customer', 'status', 'channel')
        }),
        ('Intent Tracking', {
            'fields': (
                'last_intent', 'intent_confidence',
                'low_confidence_count'
            )
        }),
        ('Agent Assignment', {
            'fields': ('last_agent', 'handoff_at')
        }),
        ('Metadata', {
            'fields': ('metadata',)
        }),
        ('System', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Admin interface for Message."""
    
    list_display = [
        'id', 'conversation', 'direction', 'message_type',
        'provider_status', 'created_at'
    ]
    list_filter = ['direction', 'message_type', 'provider_status']
    search_fields = [
        'id', 'conversation__id', 'text',
        'provider_msg_id'
    ]
    readonly_fields = [
        'id', 'created_at', 'sent_at', 'delivered_at',
        'read_at', 'failed_at'
    ]
    
    fieldsets = (
        ('Conversation', {
            'fields': ('conversation',)
        }),
        ('Message Details', {
            'fields': ('direction', 'message_type', 'text', 'payload')
        }),
        ('Template', {
            'fields': ('template',)
        }),
        ('Provider Tracking', {
            'fields': (
                'provider_msg_id', 'provider_status'
            )
        }),
        ('Delivery Tracking', {
            'fields': (
                'sent_at', 'delivered_at', 'read_at',
                'failed_at', 'error_message'
            )
        }),
        ('System', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    """Admin interface for MessageTemplate."""
    
    list_display = [
        'name', 'tenant', 'message_type', 'usage_count',
        'created_at'
    ]
    list_filter = ['message_type', 'tenant']
    search_fields = ['name', 'content', 'tenant__name']
    readonly_fields = ['id', 'usage_count', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'name', 'message_type')
        }),
        ('Content', {
            'fields': ('content', 'description', 'variables')
        }),
        ('Usage', {
            'fields': ('usage_count',)
        }),
        ('System', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
