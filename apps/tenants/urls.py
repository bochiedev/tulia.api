"""
Tenant API URLs.
"""
from django.urls import path

app_name = 'tenants'
from apps.tenants.views import (
    WalletBalanceView,
    WalletTransactionsView,
    WalletWithdrawView,
    WalletWithdrawalApproveView,
)
from apps.tenants.views_customer import (
    CustomerListView,
    CustomerDetailView,
    CustomerExportView,
)
from apps.tenants.views_settings import (
    tenant_settings_view,
    set_woocommerce_credentials,
    set_shopify_credentials,
    set_twilio_credentials,
    set_openai_credentials,
    get_payment_methods
)
from apps.tenants.views_payment_features import PaymentFeaturesView
from apps.tenants.views_admin import (
    AdminTenantListView,
    AdminTenantDetailView,
    AdminSubscriptionChangeView,
    AdminSubscriptionWaiverView,
    AdminWithdrawalProcessView
)

urlpatterns = [
    # Customer endpoints
    path('customers', CustomerListView.as_view(), name='customer-list'),
    path('customers/<uuid:id>', CustomerDetailView.as_view(), name='customer-detail'),
    path('customers/<uuid:id>/export', CustomerExportView.as_view(), name='customer-export'),
    
    # Settings endpoints
    path('settings', tenant_settings_view, name='tenant-settings'),
    path('settings/integrations/woocommerce', set_woocommerce_credentials, name='settings-woocommerce'),
    path('settings/integrations/shopify', set_shopify_credentials, name='settings-shopify'),
    path('settings/integrations/twilio', set_twilio_credentials, name='settings-twilio'),
    path('settings/integrations/openai', set_openai_credentials, name='settings-openai'),
    path('settings/payment-methods', get_payment_methods, name='settings-payment-methods'),
    
    # Payment features
    path('payment-features', PaymentFeaturesView.as_view(), name='payment-features'),
    
    # Wallet endpoints
    path('wallet/balance', WalletBalanceView.as_view(), name='wallet-balance'),
    path('wallet/transactions', WalletTransactionsView.as_view(), name='wallet-transactions'),
    path('wallet/withdraw', WalletWithdrawView.as_view(), name='wallet-withdraw'),
    path('wallet/withdrawals/<uuid:transaction_id>/approve', 
         WalletWithdrawalApproveView.as_view(), 
         name='wallet-withdrawal-approve'),
    
    # Admin endpoints
    path('admin/tenants', AdminTenantListView.as_view(), name='admin-tenant-list'),
    path('admin/tenants/<uuid:tenant_id>', AdminTenantDetailView.as_view(), name='admin-tenant-detail'),
    path('admin/tenants/<uuid:tenant_id>/subscription', 
         AdminSubscriptionChangeView.as_view(), 
         name='admin-subscription-change'),
    path('admin/tenants/<uuid:tenant_id>/subscription/waiver', 
         AdminSubscriptionWaiverView.as_view(), 
         name='admin-subscription-waiver'),
    path('admin/wallet/withdrawals/<uuid:transaction_id>/process', 
         AdminWithdrawalProcessView.as_view(), 
         name='admin-withdrawal-process'),
]
