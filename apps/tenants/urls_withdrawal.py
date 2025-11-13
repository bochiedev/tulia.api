"""
Tenant withdrawal URLs.

Endpoints for tenants to withdraw their earnings from the wallet.
Four-eyes approval required for all withdrawals.
"""
from django.urls import path
from apps.tenants.views_withdrawal import (
    WithdrawalOptionsView,
    InitiateWithdrawalView,
    ApproveWithdrawalView,
    CancelWithdrawalView,
    WithdrawalListView,
)

app_name = 'withdrawals'

urlpatterns = [
    # Withdrawal management
    path(
        'wallet/withdrawal-options',
        WithdrawalOptionsView.as_view(),
        name='withdrawal-options'
    ),
    path(
        'wallet/withdrawals',
        WithdrawalListView.as_view(),
        name='withdrawal-list'
    ),
    path(
        'wallet/withdrawals',
        InitiateWithdrawalView.as_view(),
        name='initiate-withdrawal'
    ),
    path(
        'wallet/withdrawals/<uuid:transaction_id>/approve',
        ApproveWithdrawalView.as_view(),
        name='approve-withdrawal'
    ),
    path(
        'wallet/withdrawals/<uuid:transaction_id>/cancel',
        CancelWithdrawalView.as_view(),
        name='cancel-withdrawal'
    ),
]
