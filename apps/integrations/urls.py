"""
Integration app URL configuration.

Webhook endpoints for external service callbacks.
"""
from django.urls import path
from . import views
from .views_payment import (
    StripeWebhookView,
    PaystackWebhookView,
    PesapalWebhookView,
    MpesaWebhookView
)

app_name = 'integrations'

urlpatterns = [
    # Twilio webhooks
    path('webhooks/twilio/', views.twilio_webhook, name='twilio-webhook'),
    path('webhooks/twilio/status/', views.twilio_status_callback, name='twilio-status-callback'),
    
    # Payment provider webhooks
    path('webhooks/stripe/', StripeWebhookView.as_view(), name='stripe-webhook'),
    path('webhooks/paystack/', PaystackWebhookView.as_view(), name='paystack-webhook'),
    path('webhooks/pesapal/', PesapalWebhookView.as_view(), name='pesapal-webhook'),
    path('webhooks/mpesa/', MpesaWebhookView.as_view(), name='mpesa-webhook'),
]
