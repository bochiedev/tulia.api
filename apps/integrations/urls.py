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
    path('twilio/', views.twilio_webhook, name='twilio-webhook'),
    path('twilio/status/', views.twilio_status_callback, name='twilio-status-callback'),
    
    # Payment provider webhooks
    path('stripe/', StripeWebhookView.as_view(), name='stripe-webhook'),
    path('paystack/', PaystackWebhookView.as_view(), name='paystack-webhook'),
    path('pesapal/', PesapalWebhookView.as_view(), name='pesapal-webhook'),
    path('mpesa/', MpesaWebhookView.as_view(), name='mpesa-webhook'),
]
