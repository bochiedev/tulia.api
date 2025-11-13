"""
Tenant API URLs (Legacy).

This file contains endpoints that haven't been migrated to the new URL structure yet:
- Customer management
- Wallet operations
- Payment features
- Admin operations

Note: Tenant management, settings, and onboarding endpoints have been moved to:
- apps/tenants/urls_management.py
- apps/tenants/urls_settings.py
- apps/tenants/urls_customer_payment.py (NEW - customer payment preferences)
- apps/tenants/urls_withdrawal.py (NEW - tenant withdrawals with four-eyes)
"""
from django.urls import path, include

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
    # Customer payment preferences (NEW)
    path('', include('apps.tenants.urls_customer_payment')),
    
    # Tenant withdrawals with four-eyes approval (NEW)
    path('', include('apps.tenants.urls_withdrawal')),
    
    # Customer endpoints
    path('customers', CustomerListView.as_view(), name='customer-list'),
    path('customers/<uuid:id>', CustomerDetailView.as_view(), name='customer-detail'),
    path('customers/<uuid:id>/export', CustomerExportView.as_view(), name='customer-export'),
    
    # General settings endpoint (legacy)
    path('settings', tenant_settings_view, name='tenant-settings'),
    
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
