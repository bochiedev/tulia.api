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

urlpatterns = [
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
