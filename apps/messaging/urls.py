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
    CampaignReportView,
)

app_name = 'messaging'

urlpatterns = [
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
        'messages/send',
        SendMessageView.as_view(),
        name='send-message'
    ),
    path(
        'messages/schedule',
        ScheduleMessageView.as_view(),
        name='schedule-message'
    ),
    path(
        'messages/rate-limit-status',
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
        'campaigns/<uuid:campaign_id>/report',
        CampaignReportView.as_view(),
        name='campaign-report'
    ),
]
