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
from apps.tenants.views_payment_features import PaymentFeaturesView
from apps.tenants.views_admin import (
    AdminTenantListView,
    AdminTenantDetailView,
    AdminSubscriptionChangeView,
    AdminSubscriptionWaiverView,
    AdminWithdrawalProcessView
)
from apps.tenants.views_tenant_management import (
    TenantListView,
    TenantCreateView,
    TenantDetailView,
    TenantUpdateView,
    TenantDeleteView,
    TenantMembersView,
    TenantMemberInviteView,
    TenantMemberRemoveView,
)

urlpatterns = [
    # Tenant management endpoints
    path('tenants', TenantListView.as_view(), name='tenant-list'),
    path('tenants/create', TenantCreateView.as_view(), name='tenant-create'),
    path('tenants/<uuid:tenant_id>', TenantDetailView.as_view(), name='tenant-detail'),
    path('tenants/<uuid:tenant_id>/update', TenantUpdateView.as_view(), name='tenant-update'),
    path('tenants/<uuid:tenant_id>/delete', TenantDeleteView.as_view(), name='tenant-delete'),
    path('tenants/<uuid:tenant_id>/members', TenantMembersView.as_view(), name='tenant-members'),
    path('tenants/<uuid:tenant_id>/members/invite', TenantMemberInviteView.as_view(), name='tenant-member-invite'),
    path('tenants/<uuid:tenant_id>/members/<uuid:user_id>', TenantMemberRemoveView.as_view(), name='tenant-member-remove'),
    
    # Customer endpoints
    path('customers', CustomerListView.as_view(), name='customer-list'),
    path('customers/<uuid:id>', CustomerDetailView.as_view(), name='customer-detail'),
    path('customers/<uuid:id>/export', CustomerExportView.as_view(), name='customer-export'),
    
    # Settings endpoints
    path('settings', tenant_settings_view, name='tenant-settings'),
    path('settings/integrations', integrations_list_view, name='settings-integrations-list'),
    path('settings/integrations/woocommerce', woocommerce_credentials_view, name='settings-woocommerce'),
    path('settings/integrations/shopify', shopify_credentials_view, name='settings-shopify'),
    path('settings/integrations/twilio', twilio_credentials_view, name='settings-twilio'),
    path('settings/integrations/openai', set_openai_credentials, name='settings-openai'),
    
    # Payment methods endpoints
    path('settings/payment-methods', payment_methods_view, name='settings-payment-methods'),
    path('settings/payment-methods/<str:payment_method_id>/default', payment_method_set_default_view, name='settings-payment-method-set-default'),
    path('settings/payment-methods/<str:payment_method_id>', payment_method_remove_view, name='settings-payment-method-remove'),
    
    # Payout method endpoints
    path('settings/payout-method', payout_method_view, name='settings-payout-method'),
    
    # Business settings endpoints
    path('settings/business', business_settings_view, name='settings-business'),
    
    # Onboarding endpoints
    path('settings/onboarding', OnboardingStatusView.as_view(), name='onboarding-status'),
    path('settings/onboarding/complete', OnboardingCompleteView.as_view(), name='onboarding-complete'),
    
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
