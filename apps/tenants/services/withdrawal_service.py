"""
Tenant withdrawal service with multi-provider support.

Handles:
- Withdrawal requests with four-eyes approval
- Multi-provider payout (M-Pesa B2C, Paystack, Bank transfers)
- Transaction fee calculation based on tenant tier
- Wallet balance management
- Audit logging
"""
import logging
from decimal import Decimal
from typing import Dict, Optional
from django.db import transaction
from django.utils import timezone
from django.conf import settings as django_settings

from apps.tenants.models import Tenant, TenantWallet, Transaction
from apps.rbac.models import User
from apps.core.exceptions import TuliaException
from apps.tenants.services.settings_service import SettingsService

logger = logging.getLogger(__name__)


class WithdrawalError(TuliaException):
    """Raised when withdrawal operation fails."""
    pass


class InsufficientBalance(WithdrawalError):
    """Raised when wallet balance is insufficient."""
    pass


class WithdrawalService:
    """Service for managing tenant withdrawals."""
    
    # Minimum withdrawal amounts by provider
    MINIMUM_WITHDRAWALS = {
        'mpesa': Decimal('10.00'),  # KES 10
        'bank_transfer': Decimal('100.00'),  # KES 100
        'paystack': Decimal('100.00'),  # KES 100
        'till': Decimal('10.00'),  # KES 10
    }
    
    # Withdrawal fees by provider (flat fees, not percentages)
    WITHDRAWAL_FEES = {
        'mpesa': Decimal('33.00'),  # M-Pesa B2C fee
        'bank_transfer': Decimal('50.00'),  # Bank transfer fee
        'paystack': Decimal('50.00'),  # Paystack transfer fee
        'till': Decimal('27.00'),  # M-Pesa B2B fee
    }
    
    @classmethod
    @transaction.atomic
    def initiate_withdrawal(
        cls,
        tenant: Tenant,
        amount: Decimal,
        method_type: str,
        method_details: Dict,
        initiated_by: User,
        notes: str = None
    ) -> Transaction:
        """
        Initiate a withdrawal request (requires approval).
        
        Args:
            tenant: Tenant instance
            amount: Withdrawal amount (gross)
            method_type: 'mpesa', 'bank_transfer', 'paystack', 'till'
            method_details: Method-specific details
            initiated_by: User initiating the withdrawal
            notes: Optional notes
            
        Returns:
            Transaction: Pending withdrawal transaction
            
        Raises:
            InsufficientBalance: If wallet balance is insufficient
            WithdrawalError: If validation fails
        """
        # Get wallet
        wallet = TenantWallet.objects.filter(tenant=tenant).first()
        if not wallet:
            raise WithdrawalError("Wallet not found for tenant")
        
        # Validate minimum withdrawal
        minimum = cls.MINIMUM_WITHDRAWALS.get(method_type, Decimal('10.00'))
        if amount < minimum:
            raise WithdrawalError(
                f"Minimum withdrawal for {method_type} is {minimum}"
            )
        
        # Calculate fee (flat fee, not percentage - tenant pays the fee)
        fee = cls.WITHDRAWAL_FEES.get(method_type, Decimal('0.00'))
        
        # Net amount is what tenant receives (amount - fee)
        net_amount = amount - fee
        
        if net_amount <= 0:
            raise WithdrawalError(
                f"Withdrawal amount must be greater than fee ({fee})"
            )
        
        # Check wallet balance (need gross amount)
        if not wallet.has_sufficient_balance(amount):
            raise InsufficientBalance(
                f"Insufficient balance. Available: {wallet.balance}, Required: {amount}",
                details={
                    'available': float(wallet.balance),
                    'required': float(amount),
                    'currency': wallet.currency
                }
            )
        
        # Validate method details
        cls._validate_method_details(method_type, method_details)
        
        # Create pending transaction
        transaction_obj = Transaction.objects.create(
            tenant=tenant,
            wallet=wallet,
            transaction_type='withdrawal',
            amount=amount,
            fee=fee,
            net_amount=net_amount,
            status='pending',
            reference_type='withdrawal',
            metadata={
                'method_type': method_type,
                'method_details': cls._sanitize_method_details(method_details),
                'initiated_at': timezone.now().isoformat()
            },
            notes=notes or '',
            initiated_by=initiated_by
        )
        
        logger.info(
            f"Withdrawal initiated",
            extra={
                'tenant_id': str(tenant.id),
                'transaction_id': str(transaction_obj.id),
                'amount': float(amount),
                'fee': float(fee),
                'net_amount': float(net_amount),
                'method_type': method_type,
                'initiated_by': str(initiated_by.id)
            }
        )
        
        return transaction_obj
    
    @classmethod
    @transaction.atomic
    def approve_withdrawal(
        cls,
        transaction_obj: Transaction,
        approved_by: User
    ) -> Dict:
        """
        Approve and process a withdrawal (four-eyes approval).
        
        Args:
            transaction_obj: Pending withdrawal transaction
            approved_by: User approving the withdrawal
            
        Returns:
            dict: Processing result with provider response
            
        Raises:
            WithdrawalError: If approval fails or same user tries to approve
        """
        # Validate transaction
        if transaction_obj.transaction_type != 'withdrawal':
            raise WithdrawalError("Transaction is not a withdrawal")
        
        if transaction_obj.status != 'pending':
            raise WithdrawalError(
                f"Transaction is not pending (status: {transaction_obj.status})"
            )
        
        # Four-eyes check: approver must be different from initiator
        if transaction_obj.initiated_by and transaction_obj.initiated_by.id == approved_by.id:
            raise WithdrawalError(
                "Approver must be different from initiator (four-eyes approval)",
                details={
                    'initiated_by': str(transaction_obj.initiated_by.id),
                    'approved_by': str(approved_by.id)
                }
            )
        
        # Get method details
        method_type = transaction_obj.metadata.get('method_type')
        method_details = transaction_obj.metadata.get('method_details', {})
        
        # Process withdrawal through appropriate provider
        try:
            result = cls._process_withdrawal(
                tenant=transaction_obj.tenant,
                amount=transaction_obj.net_amount,  # Send net amount (after fee)
                method_type=method_type,
                method_details=method_details
            )
            
            # Update transaction
            transaction_obj.status = 'completed'
            transaction_obj.approved_by = approved_by
            transaction_obj.metadata['approved_at'] = timezone.now().isoformat()
            transaction_obj.metadata['provider_response'] = result
            transaction_obj.save(update_fields=['status', 'approved_by', 'metadata', 'updated_at'])
            
            # Debit wallet
            wallet = transaction_obj.wallet
            wallet.balance -= transaction_obj.amount  # Deduct gross amount (including fee)
            wallet.save(update_fields=['balance', 'updated_at'])
            
            logger.info(
                f"Withdrawal approved and processed",
                extra={
                    'tenant_id': str(transaction_obj.tenant_id),
                    'transaction_id': str(transaction_obj.id),
                    'amount': float(transaction_obj.amount),
                    'net_amount': float(transaction_obj.net_amount),
                    'approved_by': str(approved_by.id)
                }
            )
            
            return {
                'success': True,
                'transaction_id': str(transaction_obj.id),
                'amount': float(transaction_obj.amount),
                'net_amount': float(transaction_obj.net_amount),
                'fee': float(transaction_obj.fee),
                'provider_response': result
            }
            
        except Exception as e:
            # Mark transaction as failed
            transaction_obj.status = 'failed'
            transaction_obj.metadata['error'] = str(e)
            transaction_obj.metadata['failed_at'] = timezone.now().isoformat()
            transaction_obj.save(update_fields=['status', 'metadata', 'updated_at'])
            
            logger.error(
                f"Withdrawal processing failed: {str(e)}",
                exc_info=True,
                extra={
                    'tenant_id': str(transaction_obj.tenant_id),
                    'transaction_id': str(transaction_obj.id)
                }
            )
            
            raise WithdrawalError(f"Withdrawal processing failed: {str(e)}") from e
    
    @classmethod
    def _process_withdrawal(
        cls,
        tenant: Tenant,
        amount: Decimal,
        method_type: str,
        method_details: Dict
    ) -> Dict:
        """
        Process withdrawal through appropriate provider.
        
        Args:
            tenant: Tenant instance
            amount: Net amount to send
            method_type: Withdrawal method type
            method_details: Method-specific details
            
        Returns:
            dict: Provider response
        """
        if method_type == 'mpesa':
            return cls._process_mpesa_withdrawal(tenant, amount, method_details)
        elif method_type == 'till':
            return cls._process_till_withdrawal(tenant, amount, method_details)
        elif method_type in ['bank_transfer', 'paystack']:
            return cls._process_paystack_withdrawal(tenant, amount, method_details)
        else:
            raise WithdrawalError(f"Unsupported withdrawal method: {method_type}")
    
    @staticmethod
    def _process_mpesa_withdrawal(tenant: Tenant, amount: Decimal, details: Dict) -> Dict:
        """Process M-Pesa B2C withdrawal."""
        from apps.integrations.services.mpesa_service import MpesaService, MpesaError
        
        try:
            result = MpesaService.b2c_payment(
                phone_number=details['phone_number'],
                amount=amount,
                occasion='Withdrawal',
                remarks=f'Withdrawal for {tenant.name}',
                command_id='BusinessPayment'
            )
            
            return {
                'provider': 'mpesa',
                'conversation_id': result['conversation_id'],
                'response_code': result['response_code'],
                'response_description': result['response_description']
            }
            
        except MpesaError as e:
            raise WithdrawalError(f"M-Pesa withdrawal failed: {str(e)}") from e
    
    @staticmethod
    def _process_till_withdrawal(tenant: Tenant, amount: Decimal, details: Dict) -> Dict:
        """Process M-Pesa B2B till withdrawal."""
        from apps.integrations.services.mpesa_service import MpesaService, MpesaError
        
        try:
            result = MpesaService.b2b_payment(
                receiver_shortcode=details['till_number'],
                amount=amount,
                account_reference=f'WD-{tenant.slug}',
                remarks=f'Withdrawal for {tenant.name}',
                command_id='BusinessBuyGoods'
            )
            
            return {
                'provider': 'mpesa_b2b',
                'conversation_id': result['conversation_id'],
                'response_code': result['response_code'],
                'response_description': result['response_description']
            }
            
        except MpesaError as e:
            raise WithdrawalError(f"Till withdrawal failed: {str(e)}") from e
    
    @staticmethod
    def _process_paystack_withdrawal(tenant: Tenant, amount: Decimal, details: Dict) -> Dict:
        """Process Paystack bank transfer withdrawal."""
        from apps.integrations.services.paystack_service import PaystackService, PaystackError
        
        try:
            # Check if recipient already exists
            recipient_code = details.get('recipient_code')
            
            if not recipient_code:
                # Create recipient
                recipient = PaystackService.create_transfer_recipient(
                    account_number=details['account_number'],
                    bank_code=details['bank_code'],
                    name=details['account_name'],
                    currency=details.get('currency', 'KES')
                )
                recipient_code = recipient['recipient_code']
            
            # Initiate transfer
            transfer = PaystackService.initiate_transfer(
                recipient_code=recipient_code,
                amount=amount,
                currency=details.get('currency', 'KES'),
                reference=f'withdrawal_{tenant.id}_{timezone.now().strftime("%Y%m%d%H%M%S")}',
                reason='Tenant withdrawal'
            )
            
            return {
                'provider': 'paystack',
                'transfer_code': transfer.get('transfer_code'),
                'reference': transfer.get('reference'),
                'status': transfer.get('status')
            }
            
        except PaystackError as e:
            raise WithdrawalError(f"Paystack withdrawal failed: {str(e)}") from e
    
    @classmethod
    @transaction.atomic
    def cancel_withdrawal(
        cls,
        transaction_obj: Transaction,
        canceled_by: User,
        reason: str = None
    ) -> Transaction:
        """
        Cancel a pending withdrawal.
        
        Args:
            transaction_obj: Pending withdrawal transaction
            canceled_by: User canceling the withdrawal
            reason: Cancellation reason
            
        Returns:
            Transaction: Updated transaction
        """
        if transaction_obj.status != 'pending':
            raise WithdrawalError(
                f"Cannot cancel transaction with status: {transaction_obj.status}"
            )
        
        transaction_obj.status = 'canceled'
        transaction_obj.metadata['canceled_at'] = timezone.now().isoformat()
        transaction_obj.metadata['canceled_by'] = str(canceled_by.id)
        transaction_obj.metadata['cancellation_reason'] = reason or 'Canceled by user'
        transaction_obj.save(update_fields=['status', 'metadata', 'updated_at'])
        
        logger.info(
            f"Withdrawal canceled",
            extra={
                'tenant_id': str(transaction_obj.tenant_id),
                'transaction_id': str(transaction_obj.id),
                'canceled_by': str(canceled_by.id)
            }
        )
        
        return transaction_obj
    
    @staticmethod
    def _validate_method_details(method_type: str, details: Dict):
        """Validate withdrawal method details."""
        if method_type == 'mpesa':
            if 'phone_number' not in details:
                raise WithdrawalError("M-Pesa withdrawal requires phone_number")
        elif method_type == 'till':
            if 'till_number' not in details:
                raise WithdrawalError("Till withdrawal requires till_number")
        elif method_type in ['bank_transfer', 'paystack']:
            required = ['account_number', 'bank_code', 'account_name']
            missing = [f for f in required if f not in details]
            if missing:
                raise WithdrawalError(
                    f"Bank transfer requires: {', '.join(missing)}"
                )
    
    @staticmethod
    def _sanitize_method_details(details: Dict) -> Dict:
        """Sanitize method details for storage (mask sensitive data)."""
        sanitized = details.copy()
        
        # Mask phone numbers
        if 'phone_number' in sanitized:
            phone = sanitized['phone_number']
            sanitized['phone_number'] = phone[-4:].rjust(len(phone), '*')
        
        # Mask account numbers
        if 'account_number' in sanitized:
            account = sanitized['account_number']
            sanitized['account_number'] = account[-4:].rjust(len(account), '*')
        
        return sanitized
    
    @staticmethod
    def get_withdrawal_options(tenant: Tenant) -> Dict:
        """
        Get available withdrawal options for tenant.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            dict: {
                'available_methods': list,
                'configured_method': dict or None,
                'minimum_amounts': dict,
                'fees': dict,
                'wallet_balance': float
            }
        """
        # Get configured providers
        configured_providers = SettingsService.get_configured_payment_providers(tenant)
        
        # Get configured payout method
        payout_method = SettingsService.get_payout_method(tenant)
        
        # Get wallet balance
        wallet = TenantWallet.objects.filter(tenant=tenant).first()
        balance = float(wallet.balance) if wallet else 0.0
        
        # Map providers to withdrawal methods
        available_methods = []
        if 'mpesa' in configured_providers:
            available_methods.extend(['mpesa', 'till'])
        if 'paystack' in configured_providers:
            available_methods.append('bank_transfer')
        
        return {
            'available_methods': available_methods,
            'configured_method': payout_method,
            'minimum_amounts': {
                k: float(v) for k, v in WithdrawalService.MINIMUM_WITHDRAWALS.items()
            },
            'fees': {
                k: float(v) for k, v in WithdrawalService.WITHDRAWAL_FEES.items()
            },
            'wallet_balance': balance,
            'currency': wallet.currency if wallet else 'KES'
        }
