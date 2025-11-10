"""
Serializers for tenant and wallet API endpoints.
"""
from rest_framework import serializers
from apps.tenants.models import (
    Tenant, TenantWallet, Transaction, WalletAudit
)


class TenantWalletSerializer(serializers.ModelSerializer):
    """Serializer for TenantWallet."""
    
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    
    class Meta:
        model = TenantWallet
        fields = [
            'id', 'tenant', 'tenant_name', 'balance', 'currency',
            'minimum_withdrawal', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'tenant', 'tenant_name', 'created_at', 'updated_at']


class TransactionSerializer(serializers.ModelSerializer):
    """Serializer for Transaction."""
    
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    currency = serializers.CharField(read_only=True)
    initiated_by_email = serializers.CharField(source='initiated_by.email', read_only=True, allow_null=True)
    approved_by_email = serializers.CharField(source='approved_by.email', read_only=True, allow_null=True)
    
    class Meta:
        model = Transaction
        fields = [
            'id', 'tenant', 'tenant_name', 'wallet', 'transaction_type',
            'amount', 'fee', 'net_amount', 'currency', 'status',
            'reference_type', 'reference_id', 'metadata', 'notes',
            'initiated_by', 'initiated_by_email', 'approved_by', 'approved_by_email',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant', 'tenant_name', 'wallet', 'currency',
            'initiated_by', 'initiated_by_email', 'approved_by', 'approved_by_email',
            'created_at', 'updated_at'
        ]


class WalletBalanceSerializer(serializers.Serializer):
    """Serializer for wallet balance response."""
    
    balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField(max_length=3)
    minimum_withdrawal = serializers.DecimalField(max_digits=10, decimal_places=2)


class WithdrawalRequestSerializer(serializers.Serializer):
    """Serializer for withdrawal request."""
    
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0.01,
        help_text="Withdrawal amount"
    )
    bank_account = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Bank account information"
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Additional notes"
    )


class WithdrawalProcessSerializer(serializers.Serializer):
    """Serializer for processing withdrawal (admin)."""
    
    action = serializers.ChoiceField(
        choices=['complete', 'fail'],
        help_text="Action to take: complete or fail"
    )
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Reason for failure (required if action is 'fail')"
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Admin notes"
    )
    
    def validate(self, data):
        """Validate that reason is provided when failing withdrawal."""
        if data['action'] == 'fail' and not data.get('reason'):
            raise serializers.ValidationError({
                'reason': 'Reason is required when failing a withdrawal'
            })
        return data


class WithdrawalApprovalSerializer(serializers.Serializer):
    """Serializer for withdrawal approval with four-eyes validation."""
    
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Approval notes"
    )


class TransactionFilterSerializer(serializers.Serializer):
    """Serializer for transaction filtering parameters."""
    
    transaction_type = serializers.ChoiceField(
        choices=[
            'customer_payment', 'platform_fee', 'withdrawal', 'refund', 'adjustment'
        ],
        required=False,
        help_text="Filter by transaction type"
    )
    status = serializers.ChoiceField(
        choices=['pending', 'completed', 'failed', 'canceled'],
        required=False,
        help_text="Filter by status"
    )
    start_date = serializers.DateField(
        required=False,
        help_text="Filter by start date (YYYY-MM-DD)"
    )
    end_date = serializers.DateField(
        required=False,
        help_text="Filter by end date (YYYY-MM-DD)"
    )
    page = serializers.IntegerField(
        required=False,
        min_value=1,
        default=1,
        help_text="Page number"
    )
    page_size = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        default=50,
        help_text="Number of items per page"
    )
