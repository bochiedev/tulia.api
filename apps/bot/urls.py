"""
URL configuration for bot app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.bot.views import (
    AgentConfigurationView,
    KnowledgeEntryViewSet,
    AgentAnalyticsView,
    AgentHandoffAnalyticsView,
    AgentCostAnalyticsView,
    AgentTopicsAnalyticsView,
)
from apps.bot.views_agent_interactions import (
    AgentInteractionListView,
    AgentInteractionDetailView,
    AgentInteractionStatsView,
)

app_name = 'bot'

# Create router for ViewSets
router = DefaultRouter()
router.register(r'knowledge', KnowledgeEntryViewSet, basename='knowledge')

urlpatterns = [
    # Agent Configuration
    path('agent-config', AgentConfigurationView.as_view(), name='agent-config'),
    
    # Agent Interactions
    path('interactions', AgentInteractionListView.as_view(), name='interactions-list'),
    path('interactions/stats', AgentInteractionStatsView.as_view(), name='interactions-stats'),
    path('interactions/<uuid:interaction_id>', AgentInteractionDetailView.as_view(), name='interactions-detail'),
    
    # Analytics Endpoints
    path('analytics/conversations', AgentAnalyticsView.as_view(), name='analytics-conversations'),
    path('analytics/handoffs', AgentHandoffAnalyticsView.as_view(), name='analytics-handoffs'),
    path('analytics/costs', AgentCostAnalyticsView.as_view(), name='analytics-costs'),
    path('analytics/topics', AgentTopicsAnalyticsView.as_view(), name='analytics-topics'),
    
    # Knowledge Base (ViewSet routes)
    path('', include(router.urls)),
]
