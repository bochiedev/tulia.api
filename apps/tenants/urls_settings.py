"""
Tenant Settings API URLs.

Endpoints for:
- Onboarding status tracking
- Integration credentials (Twilio, WooCommerce, Shopify, OpenAI)
- Payment methods
- Payout methods
- Business settings
- API key management
"""
from django.urls import path
from apps.tenants.views_settings import (
    tenant_settings_view,
    woocommerce_credentials_view,
    shopify_credentials_view,
    twilio_credentials_view,
    set_openai_credentials,
    integrations_list_view,
    payment_methods_view,
    payment_method_set_default_view,
    payment_method_remove_view,
    payout_method_view,
    business_settings_view
)
from apps.tenants.views_onboarding import (
    OnboardingStatusView,
    OnboardingCompleteView,
)
from apps.tenants.views_api_keys import (
    api_keys_view,
    api_key_revoke_view,
)

app_name = 'tenant_settings'

urlpatterns = [
    # Onboarding
    path('settings/onboarding', OnboardingStatusView.as_view(), name='onboarding-status'),
    path('settings/onboarding/complete', OnboardingCompleteView.as_view(), name='onboarding-complete'),
    
    # Integration credentials
    path('settings/integrations', integrations_list_view, name='settings-integrations-list'),
    path('settings/integrations/twilio', twilio_credentials_view, name='settings-twilio'),
    path('settings/integrations/woocommerce', woocommerce_credentials_view, name='settings-woocommerce'),
    path('settings/integrations/shopify', shopify_credentials_view, name='settings-shopify'),
    path('settings/integrations/openai', set_openai_credentials, name='settings-openai'),
    
    # Payment methods
    path('settings/payment-methods', payment_methods_view, name='settings-payment-methods'),
    path('settings/payment-methods/<str:payment_method_id>/default', payment_method_set_default_view, name='settings-payment-method-set-default'),
    path('settings/payment-methods/<str:payment_method_id>', payment_method_remove_view, name='settings-payment-method-remove'),
    
    # Payout method
    path('settings/payout-method', payout_method_view, name='settings-payout-method'),
    
    # Business settings
    path('settings/business', business_settings_view, name='settings-business'),
    
    # API keys
    path('settings/api-keys', api_keys_view, name='settings-api-keys'),
    path('settings/api-keys/<str:key_id>', api_key_revoke_view, name='settings-api-key-revoke'),
]
