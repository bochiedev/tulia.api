"""
URL configuration for LangGraph orchestration endpoints.
"""
from django.urls import path
from apps.bot.langgraph.webhook import LangGraphWebhookView, WebhookHealthCheckView

app_name = 'langgraph'

urlpatterns = [
    # LangGraph webhook entry point
    path('webhook/', LangGraphWebhookView.as_view(), name='webhook'),
    
    # Health check for LangGraph system
    path('health/', WebhookHealthCheckView.as_view(), name='health'),
]