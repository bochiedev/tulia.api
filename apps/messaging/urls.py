"""
URL configuration for messaging app.
"""
from django.urls import path
from apps.messaging.views import (
    CustomerPreferencesView,
    CustomerConsentHistoryView
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
]
