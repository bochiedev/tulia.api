"""
Wallet service for managing tenant wallets and transactions.

Handles wallet credits, debits, fee calculations, payment processing,
and withdrawal management.
"""
from decimal import Decimal
from django.db import transaction as db_transaction
from django.utils import timezone
from apps.tenants.models import (
    Tenant, TenantWallet, Transaction, WalletAudit
)
from apps.core.exceptions import TuliaException


class InsufficientBalance(TuliaException):
    """Raised when wallet has insufficient balance for operation."""
    pass


class InvalidWithdrawalAmount(TuliaException):
    """Raised when withdrawal amount is invalid."""
    pass


class WalletService:
    """Service for wallet and transaction management."""
    
    @staticmethod
    def get_or_create_wallet(tenant):
        """
        Get or create wallet for a tenant.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            TenantWallet: Wallet instance
        """
        wallet, created = TenantWallet.objects.get_or_create(
            tenant=tenant,
            defaults={
                'balance': Decimal('0'),
                'currency': 'USD',
                'minimum_withdrawal': Decimal('10')
            }
        )
        return wallet
    
    @staticmethod
    @db_transaction.atomic
    def credit_wallet(tenant, amount, transaction_type='customer_payment', 
                     reference_type=None, reference_id=None, metadata=None, notes=''):
        """
        Credit amount to tenant wallet with audit trail.
        
        Args:
            tenant: Tenant instance
            amount: Amount to credit (Decimal)
            transaction_type: Type of transaction
            reference_type: Type of related entity (e.g., 'order', 'appointment')
            reference_id: ID of related entity
            metadata: Additional transaction metadata
            notes: Internal notes
            
        Returns:
            tuple: (Transaction, WalletAudit)
        """
        wallet = WalletService.get_or_create_wallet(tenant)
        
        # Record previous balance
        previous_balance = wallet.balance
        
        # Create transaction record
        txn = Transaction.objects.create(
            tenant=tenant,
            wallet=wallet,
            transaction_type=transaction_type,
            amount=amount,
            fee=Decimal('0'),
            net_amount=amount,
            status='completed',
            reference_type=reference_type,
            reference_id=reference_id,
            metadata=metadata or {},
            notes=notes
        )
        
        # Update wallet balance
        wallet.balance += amount
        wallet.save(update_fields=['balance', 'updated_at'])
        
        # Create audit record
        audit = WalletAudit.objects.create(
            wallet=wallet,
            transaction=txn,
            previous_balance=previous_balance,
            amount=amount,
            new_balance=wallet.balance
        )
        
        return txn, audit
    
    @staticmethod
    @db_transaction.atomic
    def debit_wallet(tenant, amount, transaction_type='withdrawal',
                    reference_type=None, reference_id=None, metadata=None, notes=''):
        """
        Debit amount from tenant wallet with balance validation.
        
        Args:
            tenant: Tenant instance
            amount: Amount to debit (Decimal)
            transaction_type: Type of transaction
            reference_type: Type of related entity
            reference_id: ID of related entity
            metadata: Additional transaction metadata
            notes: Internal notes
            
        Returns:
            tuple: (Transaction, WalletAudit)
            
        Raises:
            InsufficientBalance: If wallet balance is insufficient
        """
        wallet = WalletService.get_or_create_wallet(tenant)
        
        # Validate sufficient balance
        if wallet.balance < amount:
            raise InsufficientBalance(
                f"Insufficient wallet balance. Available: {wallet.currency} {wallet.balance}, "
                f"Required: {wallet.currency} {amount}",
                details={
                    'available_balance': float(wallet.balance),
                    'required_amount': float(amount),
                    'currency': wallet.currency,
                    'tenant_id': str(tenant.id)
                }
            )
        
        # Record previous balance
        previous_balance = wallet.balance
        
        # Create transaction record
        txn = Transaction.objects.create(
            tenant=tenant,
            wallet=wallet,
            transaction_type=transaction_type,
            amount=amount,
            fee=Decimal('0'),
            net_amount=amount,
            status='completed',
            reference_type=reference_type,
            reference_id=reference_id,
            metadata=metadata or {},
            notes=notes
        )
        
        # Update wallet balance
        wallet.balance -= amount
        wallet.save(update_fields=['balance', 'updated_at'])
        
        # Create audit record (negative amount for debit)
        audit = WalletAudit.objects.create(
            wallet=wallet,
            transaction=txn,
            previous_balance=previous_balance,
            amount=-amount,  # Negative for debit
            new_balance=wallet.balance
        )
        
        return txn, audit
    
    @staticmethod
    def calculate_transaction_fee(tenant, payment_amount):
        """
        Calculate platform transaction fee based on tenant's subscription tier.
        
        Args:
            tenant: Tenant instance
            payment_amount: Payment amount (Decimal)
            
        Returns:
            Decimal: Fee amount
        """
        # Get tenant's subscription tier
        tier = tenant.subscription_tier
        
        if not tier or not tier.payment_facilitation:
            return Decimal('0')
        
        # Calculate fee based on tier percentage
        fee_percentage = tier.transaction_fee_percentage
        fee_amount = payment_amount * (fee_percentage / Decimal('100'))
        
        # Round to 2 decimal places
        return fee_amount.quantize(Decimal('0.01'))
    
    @staticmethod
    @db_transaction.atomic
    def process_customer_payment(tenant, payment_amount, reference_type, reference_id, 
                                metadata=None):
        """
        Process customer payment: calculate fee, credit wallet, record platform fee.
        
        Args:
            tenant: Tenant instance
            payment_amount: Total payment amount from customer (Decimal)
            reference_type: Type of related entity (e.g., 'order', 'appointment')
            reference_id: ID of related entity
            metadata: Additional metadata
            
        Returns:
            dict: {
                'payment_transaction': Transaction,
                'fee_transaction': Transaction,
                'wallet_audit': WalletAudit,
                'gross_amount': Decimal,
                'fee_amount': Decimal,
                'net_amount': Decimal
            }
        """
        wallet = WalletService.get_or_create_wallet(tenant)
        
        # Calculate fee
        fee_amount = WalletService.calculate_transaction_fee(tenant, payment_amount)
        net_amount = payment_amount - fee_amount
        
        # Record previous balance
        previous_balance = wallet.balance
        
        # Create customer payment transaction
        payment_txn = Transaction.objects.create(
            tenant=tenant,
            wallet=wallet,
            transaction_type='customer_payment',
            amount=payment_amount,
            fee=fee_amount,
            net_amount=net_amount,
            status='completed',
            reference_type=reference_type,
            reference_id=reference_id,
            metadata=metadata or {},
            notes=f"Customer payment for {reference_type} {reference_id}"
        )
        
        # Create platform fee transaction (for accounting)
        fee_txn = None
        if fee_amount > 0:
            fee_txn = Transaction.objects.create(
                tenant=tenant,
                wallet=wallet,
                transaction_type='platform_fee',
                amount=fee_amount,
                fee=Decimal('0'),
                net_amount=fee_amount,
                status='completed',
                reference_type=reference_type,
                reference_id=reference_id,
                metadata={
                    'payment_transaction_id': str(payment_txn.id),
                    'fee_percentage': float(tenant.subscription_tier.transaction_fee_percentage)
                },
                notes=f"Platform fee for {reference_type} {reference_id}"
            )
        
        # Credit wallet with net amount
        wallet.balance += net_amount
        wallet.save(update_fields=['balance', 'updated_at'])
        
        # Create audit record
        audit = WalletAudit.objects.create(
            wallet=wallet,
            transaction=payment_txn,
            previous_balance=previous_balance,
            amount=net_amount,
            new_balance=wallet.balance
        )
        
        return {
            'payment_transaction': payment_txn,
            'fee_transaction': fee_txn,
            'wallet_audit': audit,
            'gross_amount': payment_amount,
            'fee_amount': fee_amount,
            'net_amount': net_amount
        }
    
    @staticmethod
    @db_transaction.atomic
    def request_withdrawal(tenant, amount, initiated_by=None, metadata=None):
        """
        Request withdrawal from wallet.
        
        Immediately debits the amount from wallet and creates pending transaction.
        Admin must process the withdrawal to complete or fail it.
        
        Args:
            tenant: Tenant instance
            amount: Withdrawal amount (Decimal)
            initiated_by: User who initiated the withdrawal (for four-eyes approval)
            metadata: Additional metadata (e.g., bank account info)
            
        Returns:
            Transaction: Pending withdrawal transaction
            
        Raises:
            InvalidWithdrawalAmount: If amount is below minimum or exceeds balance
        """
        wallet = WalletService.get_or_create_wallet(tenant)
        
        # Validate minimum withdrawal amount
        if amount < wallet.minimum_withdrawal:
            raise InvalidWithdrawalAmount(
                f"Withdrawal amount must be at least {wallet.currency} {wallet.minimum_withdrawal}",
                details={
                    'requested_amount': float(amount),
                    'minimum_amount': float(wallet.minimum_withdrawal),
                    'currency': wallet.currency,
                    'tenant_id': str(tenant.id)
                }
            )
        
        # Validate sufficient balance
        if wallet.balance < amount:
            raise InsufficientBalance(
                f"Insufficient wallet balance. Available: {wallet.currency} {wallet.balance}, "
                f"Requested: {wallet.currency} {amount}",
                details={
                    'available_balance': float(wallet.balance),
                    'requested_amount': float(amount),
                    'currency': wallet.currency,
                    'tenant_id': str(tenant.id)
                }
            )
        
        # Record previous balance
        previous_balance = wallet.balance
        
        # Create pending withdrawal transaction
        txn = Transaction.objects.create(
            tenant=tenant,
            wallet=wallet,
            transaction_type='withdrawal',
            amount=amount,
            fee=Decimal('0'),
            net_amount=amount,
            status='pending',
            initiated_by=initiated_by,
            metadata=metadata or {},
            notes='Withdrawal requested by tenant'
        )
        
        # Immediately debit from wallet (prevents double-spending)
        wallet.balance -= amount
        wallet.save(update_fields=['balance', 'updated_at'])
        
        # Create audit record
        WalletAudit.objects.create(
            wallet=wallet,
            transaction=txn,
            previous_balance=previous_balance,
            amount=-amount,  # Negative for debit
            new_balance=wallet.balance
        )
        
        return txn
    
    @staticmethod
    @db_transaction.atomic
    def approve_withdrawal(transaction_id, approved_by, notes=''):
        """
        Approve a pending withdrawal with four-eyes validation.
        
        Validates that the approver is different from the initiator (four-eyes pattern).
        Updates transaction status to completed and records the approver.
        
        Args:
            transaction_id: Transaction ID
            approved_by: User who is approving the withdrawal
            notes: Admin notes
            
        Returns:
            Transaction: Updated transaction
            
        Raises:
            TuliaException: If transaction is not a withdrawal or not pending
            ValueError: If approver is same as initiator (four-eyes violation)
        """
        from apps.rbac.services import RBACService
        
        txn = Transaction.objects.select_for_update().get(id=transaction_id)
        
        if txn.transaction_type != 'withdrawal':
            raise TuliaException(
                "Transaction is not a withdrawal",
                details={'transaction_id': str(transaction_id)}
            )
        
        if txn.status != 'pending':
            raise TuliaException(
                f"Transaction is not pending (current status: {txn.status})",
                details={'transaction_id': str(transaction_id), 'status': txn.status}
            )
        
        # Validate four-eyes: approver must be different from initiator
        if txn.initiated_by:
            RBACService.validate_four_eyes(
                initiator_user_id=txn.initiated_by.id,
                approver_user_id=approved_by.id
            )
        
        # Update transaction status
        txn.status = 'completed'
        txn.approved_by = approved_by
        txn.notes = f"{txn.notes}\nApproved by {approved_by.email}\n{notes}" if notes else f"{txn.notes}\nApproved by {approved_by.email}"
        txn.save(update_fields=['status', 'approved_by', 'notes', 'updated_at'])
        
        return txn
    
    @staticmethod
    @db_transaction.atomic
    def complete_withdrawal(transaction_id, notes=''):
        """
        Complete a pending withdrawal (admin action) - DEPRECATED.
        
        Use approve_withdrawal() instead for four-eyes approval.
        This method is kept for backward compatibility.
        
        Args:
            transaction_id: Transaction ID
            notes: Admin notes
            
        Returns:
            Transaction: Updated transaction
        """
        txn = Transaction.objects.select_for_update().get(id=transaction_id)
        
        if txn.transaction_type != 'withdrawal':
            raise TuliaException(
                "Transaction is not a withdrawal",
                details={'transaction_id': str(transaction_id)}
            )
        
        if txn.status != 'pending':
            raise TuliaException(
                f"Transaction is not pending (current status: {txn.status})",
                details={'transaction_id': str(transaction_id), 'status': txn.status}
            )
        
        # Update transaction status
        txn.status = 'completed'
        txn.notes = f"{txn.notes}\n{notes}" if notes else txn.notes
        txn.save(update_fields=['status', 'notes', 'updated_at'])
        
        return txn
    
    @staticmethod
    @db_transaction.atomic
    def fail_withdrawal(transaction_id, reason='', notes=''):
        """
        Fail a pending withdrawal and credit amount back to wallet.
        
        Args:
            transaction_id: Transaction ID
            reason: Failure reason
            notes: Admin notes
            
        Returns:
            Transaction: Updated transaction
        """
        txn = Transaction.objects.select_for_update().get(id=transaction_id)
        
        if txn.transaction_type != 'withdrawal':
            raise TuliaException(
                "Transaction is not a withdrawal",
                details={'transaction_id': str(transaction_id)}
            )
        
        if txn.status != 'pending':
            raise TuliaException(
                f"Transaction is not pending (current status: {txn.status})",
                details={'transaction_id': str(transaction_id), 'status': txn.status}
            )
        
        wallet = txn.wallet
        previous_balance = wallet.balance
        
        # Credit amount back to wallet
        wallet.balance += txn.amount
        wallet.save(update_fields=['balance', 'updated_at'])
        
        # Create audit record for credit-back
        WalletAudit.objects.create(
            wallet=wallet,
            transaction=txn,
            previous_balance=previous_balance,
            amount=txn.amount,  # Positive for credit
            new_balance=wallet.balance
        )
        
        # Update transaction status
        txn.status = 'failed'
        txn.metadata['failure_reason'] = reason
        txn.notes = f"{txn.notes}\nFailed: {reason}\n{notes}" if notes else f"{txn.notes}\nFailed: {reason}"
        txn.save(update_fields=['status', 'metadata', 'notes', 'updated_at'])
        
        return txn
    
    @staticmethod
    @db_transaction.atomic
    def fail_payment_transaction(transaction_id, reason='', retry_url=None, notify_customer=True):
        """
        Fail a payment transaction and optionally notify customer.
        
        This is used when a customer payment fails (e.g., card declined, 
        payment gateway error). Optionally sends a notification to the customer
        with instructions to retry.
        
        Args:
            transaction_id: Transaction ID
            reason: Failure reason
            retry_url: Optional URL for customer to retry payment
            notify_customer: Whether to send notification to customer (default: True)
            
        Returns:
            dict: {
                'transaction': Transaction,
                'notification_sent': bool,
                'notification_task_id': str (if sent)
            }
        """
        txn = Transaction.objects.select_for_update().get(id=transaction_id)
        
        # Update transaction status
        txn.status = 'failed'
        txn.metadata['failure_reason'] = reason
        if retry_url:
            txn.metadata['retry_url'] = retry_url
        txn.notes = f"{txn.notes}\nFailed: {reason}" if txn.notes else f"Failed: {reason}"
        txn.save(update_fields=['status', 'metadata', 'notes', 'updated_at'])
        
        result = {
            'transaction': txn,
            'notification_sent': False
        }
        
        # Send notification to customer if requested
        if notify_customer:
            try:
                from apps.messaging.tasks import send_payment_failed_notification
                
                # Trigger async notification task
                task = send_payment_failed_notification.delay(
                    str(transaction_id),
                    retry_url=retry_url
                )
                
                result['notification_sent'] = True
                result['notification_task_id'] = task.id
                
            except Exception as e:
                # Log error but don't fail the transaction update
                import logging
                logger = logging.getLogger(__name__)
                logger.error(
                    f"Failed to send payment failure notification for transaction {transaction_id}: {str(e)}",
                    exc_info=True
                )
        
        return result
    
    @staticmethod
    def get_wallet_balance(tenant):
        """
        Get current wallet balance for tenant.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            dict: {'balance': Decimal, 'currency': str}
        """
        wallet = WalletService.get_or_create_wallet(tenant)
        return {
            'balance': wallet.balance,
            'currency': wallet.currency
        }
    
    @staticmethod
    def get_transactions(tenant, transaction_type=None, status=None, 
                        start_date=None, end_date=None):
        """
        Get transactions for tenant with optional filtering.
        
        Args:
            tenant: Tenant instance
            transaction_type: Filter by transaction type
            status: Filter by status
            start_date: Filter by start date
            end_date: Filter by end date
            
        Returns:
            QuerySet: Filtered transactions
        """
        queryset = Transaction.objects.filter(tenant=tenant)
        
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        
        if status:
            queryset = queryset.filter(status=status)
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        return queryset.order_by('-created_at')
