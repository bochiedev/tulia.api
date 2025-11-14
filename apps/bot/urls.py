"""
URL configuration for bot app.
"""
from django.urls import path
from apps.bot.views import AgentConfigurationView

app_name = 'bot'

urlpatterns = [
    # Agent Configuration
    path('agent-config', AgentConfigurationView.as_view(), name='agent-config'),
]
