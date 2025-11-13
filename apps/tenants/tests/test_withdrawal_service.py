"""
Tests for withdrawal service with transaction fees.
"""
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from apps.tenants.models import Tenant, TenantWallet, Transaction, TenantSettings, SubscriptionTier
from apps.tenants.services.withdrawal_service import (
    WithdrawalService,
    WithdrawalError,
    InsufficientBalance
)
from apps.rbac.models import User


@pytest.mark.django_db
class TestWithdrawalService:
    """Test withdrawal service with fees and four-eyes approval."""
    
    @pytest.fixture
    def tier(self):
        """Create subscription tier with payment facilitation."""
        return SubscriptionTier.objects.create(
            name='Growth',
            monthly_price=Decimal('99.00'),
            yearly_price=Decimal('999.00'),
            payment_facilitation=True,
            transaction_fee_percentage=Decimal('2.5')
        )
    
    @pytest.fixture
    def tenant(self, tier):
        """Create test tenant."""
        tenant = Tenant.objects.create(
            name="Test Business",
            slug="test-business",
            whatsapp_number="+254712345678",
            status='active',
            subscription_tier=tier
        )
        
        # Create settings with M-Pesa configured
        TenantSettings.objects.create(
            tenant=tenant,
            metadata={
                'mpesa_shortcode': '174379',
                'mpesa_consumer_key': 'key',
                'mpesa_consumer_secret': 'secret',
                'mpesa_passkey': 'passkey'
            }
        )
        
        return tenant
    
    @pytest.fixture
    def wallet(self, tenant):
        """Create wallet with balance."""
        return TenantWallet.objects.create(
            tenant=tenant,
            balance=Decimal('10000.00'),
            currency='KES'
        )
    
    @pytest.fixture
    def user1(self):
        """Create first user (initiator)."""
        return User.objects.create(
            email='user1@example.com',
            username='user1'
        )
    
    @pytest.fixture
    def user2(self):
        """Create second user (approver)."""
        return User.objects.create(
            email='user2@example.com',
            username='user2'
        )
    
    def test_initiate_withdrawal_mpesa(self, tenant, wallet, user1):
        """Test initiating M-Pesa withdrawal."""
        transaction = WithdrawalService.initiate_withdrawal(
            tenant=tenant,
            amount=Decimal('1000.00'),
            method_type='mpesa',
            method_details={'phone_number': '254712345678'},
            initiated_by=user1,
            notes='Test withdrawal'
        )
        
        assert transaction.status == 'pending'
        assert transaction.amount == Decimal('1000.00')
        assert transaction.fee == Decimal('33.00')  # M-Pesa B2C fee
        assert transaction.net_amount == Decimal('967.00')  # 1000 - 33
        assert transaction.initiated_by == user1
        
        # Wallet balance should not change yet (pending approval)
        wallet.refresh_from_db()
        assert wallet.balance == Decimal('10000.00')
    
    def test_initiate_withdrawal_bank_transfer(self, tenant, wallet, user1):
        """Test initiating bank transfer withdrawal."""
        transaction = WithdrawalService.initiate_withdrawal(
            tenant=tenant,
            amount=Decimal('5000.00'),
            method_type='bank_transfer',
            method_details={
                'account_number': '1234567890',
                'bank_code': '063',
                'account_name': 'Test Account'
            },
            initiated_by=user1
        )
        
        assert transaction.status == 'pending'
        assert transaction.amount == Decimal('5000.00')
        assert transaction.fee == Decimal('50.00')  # Bank transfer fee
        assert transaction.net_amount == Decimal('4950.00')  # 5000 - 50
    
    def test_initiate_withdrawal_till(self, tenant, wallet, user1):
        """Test initiating till withdrawal."""
        transaction = WithdrawalService.initiate_withdrawal(
            tenant=tenant,
            amount=Decimal('2000.00'),
            method_type='till',
            method_details={'till_number': '123456'},
            initiated_by=user1
        )
        
        assert transaction.status == 'pending'
        assert transaction.amount == Decimal('2000.00')
        assert transaction.fee == Decimal('27.00')  # M-Pesa B2B fee
        assert transaction.net_amount == Decimal('1973.00')  # 2000 - 27
    
    def test_initiate_withdrawal_insufficient_balance(self, tenant, wallet, user1):
        """Test withdrawal with insufficient balance."""
        with pytest.raises(InsufficientBalance):
            WithdrawalService.initiate_withdrawal(
                tenant=tenant,
                amount=Decimal('20000.00'),  # More than wallet balance
                method_type='mpesa',
                method_details={'phone_number': '254712345678'},
                initiated_by=user1
            )
    
    def test_initiate_withdrawal_below_minimum(self, tenant, wallet, user1):
        """Test withdrawal below minimum amount."""
        with pytest.raises(WithdrawalError, match="Minimum withdrawal"):
            WithdrawalService.initiate_withdrawal(
                tenant=tenant,
                amount=Decimal('5.00'),  # Below minimum
                method_type='mpesa',
                method_details={'phone_number': '254712345678'},
                initiated_by=user1
            )
    
    def test_initiate_withdrawal_invalid_method_details(self, tenant, wallet, user1):
        """Test withdrawal with invalid method details."""
        with pytest.raises(WithdrawalError, match="requires phone_number"):
            WithdrawalService.initiate_withdrawal(
                tenant=tenant,
                amount=Decimal('1000.00'),
                method_type='mpesa',
                method_details={},  # Missing phone_number
                initiated_by=user1
            )
    
    @patch('apps.integrations.services.mpesa_service.MpesaService.b2c_payment')
    def test_approve_withdrawal_success(self, mock_b2c, tenant, wallet, user1, user2):
        """Test successful withdrawal approval and processing."""
        # Mock M-Pesa response
        mock_b2c.return_value = {
            'conversation_id': 'AG_20231113_xxx',
            'response_code': '0',
            'response_description': 'Accept the service request successfully.'
        }
        
        # Initiate withdrawal
        transaction = WithdrawalService.initiate_withdrawal(
            tenant=tenant,
            amount=Decimal('1000.00'),
            method_type='mpesa',
            method_details={'phone_number': '254712345678'},
            initiated_by=user1
        )
        
        # Approve withdrawal
        result = WithdrawalService.approve_withdrawal(transaction, user2)
        
        assert result['success'] is True
        assert result['amount'] == 1000.00
        assert result['net_amount'] == 967.00
        assert result['fee'] == 33.00
        
        # Check transaction updated
        transaction.refresh_from_db()
        assert transaction.status == 'completed'
        assert transaction.approved_by == user2
        
        # Check wallet debited (gross amount including fee)
        wallet.refresh_from_db()
        assert wallet.balance == Decimal('9000.00')  # 10000 - 1000
        
        # Verify M-Pesa called with net amount
        mock_b2c.assert_called_once()
        call_args = mock_b2c.call_args
        assert call_args[1]['amount'] == Decimal('967.00')  # Net amount sent
    
    def test_approve_withdrawal_four_eyes_violation(self, tenant, wallet, user1):
        """Test that same user cannot approve their own withdrawal."""
        # Initiate withdrawal
        transaction = WithdrawalService.initiate_withdrawal(
            tenant=tenant,
            amount=Decimal('1000.00'),
            method_type='mpesa',
            method_details={'phone_number': '254712345678'},
            initiated_by=user1
        )
        
        # Try to approve with same user
        with pytest.raises(WithdrawalError, match="four-eyes approval"):
            WithdrawalService.approve_withdrawal(transaction, user1)
    
    def test_approve_withdrawal_not_pending(self, tenant, wallet, user1, user2):
        """Test approving non-pending withdrawal."""
        # Create completed transaction
        transaction = Transaction.objects.create(
            tenant=tenant,
            wallet=wallet,
            transaction_type='withdrawal',
            amount=Decimal('1000.00'),
            fee=Decimal('33.00'),
            net_amount=Decimal('967.00'),
            status='completed',
            initiated_by=user1
        )
        
        with pytest.raises(WithdrawalError, match="not pending"):
            WithdrawalService.approve_withdrawal(transaction, user2)
    
    @patch('apps.integrations.services.mpesa_service.MpesaService.b2c_payment')
    def test_approve_withdrawal_provider_failure(self, mock_b2c, tenant, wallet, user1, user2):
        """Test withdrawal approval when provider fails."""
        # Mock M-Pesa failure
        from apps.integrations.services.mpesa_service import MpesaError
        mock_b2c.side_effect = MpesaError("Insufficient funds in paybill")
        
        # Initiate withdrawal
        transaction = WithdrawalService.initiate_withdrawal(
            tenant=tenant,
            amount=Decimal('1000.00'),
            method_type='mpesa',
            method_details={'phone_number': '254712345678'},
            initiated_by=user1
        )
        
        # Try to approve
        with pytest.raises(WithdrawalError, match="M-Pesa withdrawal failed"):
            WithdrawalService.approve_withdrawal(transaction, user2)
        
        # Check transaction marked as failed
        transaction.refresh_from_db()
        assert transaction.status == 'failed'
        
        # Wallet balance should not change
        wallet.refresh_from_db()
        assert wallet.balance == Decimal('10000.00')
    
    def test_cancel_withdrawal(self, tenant, wallet, user1, user2):
        """Test canceling a pending withdrawal."""
        # Initiate withdrawal
        transaction = WithdrawalService.initiate_withdrawal(
            tenant=tenant,
            amount=Decimal('1000.00'),
            method_type='mpesa',
            method_details={'phone_number': '254712345678'},
            initiated_by=user1
        )
        
        # Cancel withdrawal
        canceled = WithdrawalService.cancel_withdrawal(
            transaction, user2, reason='Changed mind'
        )
        
        assert canceled.status == 'canceled'
        assert 'cancellation_reason' in canceled.metadata
        assert canceled.metadata['cancellation_reason'] == 'Changed mind'
        
        # Wallet balance should not change
        wallet.refresh_from_db()
        assert wallet.balance == Decimal('10000.00')
    
    def test_cancel_withdrawal_not_pending(self, tenant, wallet, user1, user2):
        """Test canceling non-pending withdrawal."""
        # Create completed transaction
        transaction = Transaction.objects.create(
            tenant=tenant,
            wallet=wallet,
            transaction_type='withdrawal',
            amount=Decimal('1000.00'),
            fee=Decimal('33.00'),
            net_amount=Decimal('967.00'),
            status='completed',
            initiated_by=user1
        )
        
        with pytest.raises(WithdrawalError, match="Cannot cancel"):
            WithdrawalService.cancel_withdrawal(transaction, user2)
    
    def test_get_withdrawal_options(self, tenant, wallet):
        """Test getting withdrawal options for tenant."""
        options = WithdrawalService.get_withdrawal_options(tenant)
        
        assert 'mpesa' in options['available_methods']
        assert 'till' in options['available_methods']
        assert options['wallet_balance'] == 10000.0
        assert options['currency'] == 'KES'
        assert 'minimum_amounts' in options
        assert 'fees' in options
        assert options['fees']['mpesa'] == 33.0
        assert options['fees']['bank_transfer'] == 50.0
        assert options['fees']['till'] == 27.0
    
    @patch('apps.integrations.services.paystack_service.PaystackService.create_transfer_recipient')
    @patch('apps.integrations.services.paystack_service.PaystackService.initiate_transfer')
    def test_approve_withdrawal_paystack(self, mock_transfer, mock_recipient, tenant, wallet, user1, user2):
        """Test Paystack bank transfer withdrawal."""
        # Configure Paystack
        settings = tenant.settings
        settings.metadata['paystack_public_key'] = 'pk_test_xxx'
        settings.metadata['paystack_secret_key'] = 'sk_test_xxx'
        settings.save()
        
        # Mock Paystack responses
        mock_recipient.return_value = {
            'recipient_code': 'RCP_xxx',
            'type': 'nuban',
            'name': 'Test Account'
        }
        mock_transfer.return_value = {
            'transfer_code': 'TRF_xxx',
            'reference': 'withdrawal_xxx',
            'status': 'pending'
        }
        
        # Initiate withdrawal
        transaction = WithdrawalService.initiate_withdrawal(
            tenant=tenant,
            amount=Decimal('5000.00'),
            method_type='bank_transfer',
            method_details={
                'account_number': '1234567890',
                'bank_code': '063',
                'account_name': 'Test Account'
            },
            initiated_by=user1
        )
        
        # Approve withdrawal
        result = WithdrawalService.approve_withdrawal(transaction, user2)
        
        assert result['success'] is True
        assert result['net_amount'] == 4950.0  # 5000 - 50 fee
        
        # Verify Paystack called with net amount
        mock_transfer.assert_called_once()
        call_args = mock_transfer.call_args
        assert call_args[1]['amount'] == Decimal('4950.00')
    
    def test_withdrawal_fee_calculation(self, tenant, wallet, user1):
        """Test that withdrawal fees are correctly calculated."""
        # Test M-Pesa fee
        tx_mpesa = WithdrawalService.initiate_withdrawal(
            tenant=tenant,
            amount=Decimal('1000.00'),
            method_type='mpesa',
            method_details={'phone_number': '254712345678'},
            initiated_by=user1
        )
        assert tx_mpesa.fee == Decimal('33.00')
        assert tx_mpesa.net_amount == Decimal('967.00')
        
        # Test bank transfer fee
        tx_bank = WithdrawalService.initiate_withdrawal(
            tenant=tenant,
            amount=Decimal('5000.00'),
            method_type='bank_transfer',
            method_details={
                'account_number': '1234567890',
                'bank_code': '063',
                'account_name': 'Test'
            },
            initiated_by=user1
        )
        assert tx_bank.fee == Decimal('50.00')
        assert tx_bank.net_amount == Decimal('4950.00')
        
        # Test till fee
        tx_till = WithdrawalService.initiate_withdrawal(
            tenant=tenant,
            amount=Decimal('2000.00'),
            method_type='till',
            method_details={'till_number': '123456'},
            initiated_by=user1
        )
        assert tx_till.fee == Decimal('27.00')
        assert tx_till.net_amount == Decimal('1973.00')
    
    def test_sanitize_method_details(self):
        """Test that sensitive details are masked in storage."""
        details = {
            'phone_number': '254712345678',
            'account_number': '1234567890'
        }
        
        sanitized = WithdrawalService._sanitize_method_details(details)
        
        assert sanitized['phone_number'] == '**********5678'
        assert sanitized['account_number'] == '******7890'
