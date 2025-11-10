"""
Integration app URL configuration.

Webhook endpoints for external service callbacks.
"""
from django.urls import path
from . import views

app_name = 'integrations'

urlpatterns = [
    # Twilio webhooks
    path('webhooks/twilio/', views.twilio_webhook, name='twilio-webhook'),
    path('webhooks/twilio/status/', views.twilio_status_callback, name='twilio-status-callback'),
]
