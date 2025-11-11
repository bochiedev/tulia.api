"""
Tenant API URLs.
"""
from django.urls import path
from apps.tenants.views import (
    WalletBalanceView,
    WalletTransactionsView,
    WalletWithdrawView,
    WalletWithdrawalApproveView,
    AdminWithdrawalProcessView
)
from apps.tenants.views_settings import (
    tenant_settings_view,
    set_woocommerce_credentials,
    set_shopify_credentials,
    set_twilio_credentials,
    set_openai_credentials,
    get_payment_methods
)

urlpatterns = [
    # Settings endpoints
    path('settings', tenant_settings_view, name='tenant-settings'),
    path('settings/integrations/woocommerce', set_woocommerce_credentials, name='settings-woocommerce'),
    path('settings/integrations/shopify', set_shopify_credentials, name='settings-shopify'),
    path('settings/integrations/twilio', set_twilio_credentials, name='settings-twilio'),
    path('settings/integrations/openai', set_openai_credentials, name='settings-openai'),
    path('settings/payment-methods', get_payment_methods, name='settings-payment-methods'),
    
    # Wallet endpoints
    path('wallet/balance', WalletBalanceView.as_view(), name='wallet-balance'),
    path('wallet/transactions', WalletTransactionsView.as_view(), name='wallet-transactions'),
    path('wallet/withdraw', WalletWithdrawView.as_view(), name='wallet-withdraw'),
    path('wallet/withdrawals/<uuid:transaction_id>/approve', 
         WalletWithdrawalApproveView.as_view(), 
         name='wallet-withdrawal-approve'),
    
    # Admin endpoints (deprecated)
    path('admin/wallet/withdrawals/<uuid:transaction_id>/process', 
         AdminWithdrawalProcessView.as_view(), 
         name='admin-withdrawal-process'),
]
