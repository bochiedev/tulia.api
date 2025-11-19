"""
URL configuration for bot app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Import from bot_views.py
import apps.bot.bot_views as bot_views
from apps.bot.views_agent_interactions import (
    AgentInteractionListView,
    AgentInteractionDetailView,
    AgentInteractionStatsView,
)

app_name = 'bot'

# Create router for ViewSets
router = DefaultRouter()
router.register(r'knowledge', bot_views.KnowledgeEntryViewSet, basename='knowledge')

urlpatterns = [
    # Agent Configuration
    path('agent-config', bot_views.AgentConfigurationView.as_view(), name='agent-config'),
    
    # Agent Interactions
    path('interactions', AgentInteractionListView.as_view(), name='interactions-list'),
    path('interactions/stats', AgentInteractionStatsView.as_view(), name='interactions-stats'),
    path('interactions/<uuid:interaction_id>', AgentInteractionDetailView.as_view(), name='interactions-detail'),
    
    # Analytics Endpoints
    path('analytics/conversations', bot_views.AgentAnalyticsView.as_view(), name='analytics-conversations'),
    path('analytics/handoffs', bot_views.AgentHandoffAnalyticsView.as_view(), name='analytics-handoffs'),
    path('analytics/costs', bot_views.AgentCostAnalyticsView.as_view(), name='analytics-costs'),
    path('analytics/topics', bot_views.AgentTopicsAnalyticsView.as_view(), name='analytics-topics'),
    
    # Knowledge Base (ViewSet routes)
    path('', include(router.urls)),
    
    # RAG Document Management
    path('documents/', include('apps.bot.urls_documents')),
    
    # Feedback Collection
    path('', include('apps.bot.urls_feedback')),
]
