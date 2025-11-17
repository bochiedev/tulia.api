"""
URL configuration for messaging app.
"""
from django.urls import path
from apps.messaging.views import (
    CustomerPreferencesView,
    CustomerConsentHistoryView,
    SendMessageView,
    ScheduleMessageView,
    MessageTemplateListCreateView,
    RateLimitStatusView,
    CampaignListCreateView,
    CampaignDetailView,
    CampaignExecuteView,
    CampaignButtonClickView,
    CampaignReportView,
)
from apps.messaging.views_conversation import (
    ConversationListView,
    ConversationDetailView,
    ConversationMessagesView,
    ConversationHandoffView,
)

app_name = 'messaging'

urlpatterns = [
    # Conversation endpoints
    path(
        'conversations',
        ConversationListView.as_view(),
        name='conversation-list'
    ),
    path(
        'conversations/<uuid:id>',
        ConversationDetailView.as_view(),
        name='conversation-detail'
    ),
    path(
        'conversations/<uuid:id>/messages',
        ConversationMessagesView.as_view(),
        name='conversation-messages'
    ),
    path(
        'conversations/<uuid:id>/handoff',
        ConversationHandoffView.as_view(),
        name='conversation-handoff'
    ),
    
    # Customer preferences endpoints
    path(
        'customers/<uuid:customer_id>/preferences',
        CustomerPreferencesView.as_view(),
        name='customer-preferences'
    ),
    path(
        'customers/<uuid:customer_id>/consent-history',
        CustomerConsentHistoryView.as_view(),
        name='customer-consent-history'
    ),
    
    # Message sending endpoints
    path(
        'send',
        SendMessageView.as_view(),
        name='send-message'
    ),
    path(
        'schedule',
        ScheduleMessageView.as_view(),
        name='schedule-message'
    ),
    path(
        'rate-limit-status',
        RateLimitStatusView.as_view(),
        name='rate-limit-status'
    ),
    
    # Template endpoints
    path(
        'templates',
        MessageTemplateListCreateView.as_view(),
        name='template-list-create'
    ),
    
    # Campaign endpoints
    path(
        'campaigns',
        CampaignListCreateView.as_view(),
        name='campaign-list-create'
    ),
    path(
        'campaigns/<uuid:campaign_id>',
        CampaignDetailView.as_view(),
        name='campaign-detail'
    ),
    path(
        'campaigns/<uuid:campaign_id>/execute',
        CampaignExecuteView.as_view(),
        name='campaign-execute'
    ),
    path(
        'campaigns/<uuid:campaign_id>/button-click',
        CampaignButtonClickView.as_view(),
        name='campaign-button-click'
    ),
    path(
        'campaigns/<uuid:campaign_id>/report',
        CampaignReportView.as_view(),
        name='campaign-report'
    ),
]
