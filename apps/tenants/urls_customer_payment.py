"""
Customer payment preference URLs.

Endpoints for customers to manage their payment preferences
when paying for products/services from tenants.
"""
from django.urls import path
from apps.tenants.views_customer_payment import (
    CustomerPaymentPreferencesView,
    CustomerPaymentCheckoutOptionsView,
    set_preferred_provider,
    save_payment_method,
    remove_payment_method,
    set_default_payment_method,
)

app_name = 'customer_payment'

urlpatterns = [
    # Customer payment preferences
    path(
        'customers/<uuid:customer_id>/payment-preferences',
        CustomerPaymentPreferencesView.as_view(),
        name='payment-preferences'
    ),
    path(
        'customers/<uuid:customer_id>/checkout-options',
        CustomerPaymentCheckoutOptionsView.as_view(),
        name='checkout-options'
    ),
    path(
        'customers/<uuid:customer_id>/preferred-provider',
        set_preferred_provider,
        name='set-preferred-provider'
    ),
    path(
        'customers/<uuid:customer_id>/payment-methods',
        save_payment_method,
        name='save-payment-method'
    ),
    path(
        'customers/<uuid:customer_id>/payment-methods/<str:method_id>',
        remove_payment_method,
        name='remove-payment-method'
    ),
    path(
        'customers/<uuid:customer_id>/payment-methods/<str:method_id>/default',
        set_default_payment_method,
        name='set-default-payment-method'
    ),
]
