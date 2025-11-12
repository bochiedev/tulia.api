"""
Payment facilitation service for checking tier-based payment features.

Handles:
- Payment facilitation eligibility checks
- Wallet auto-creation on tier upgrade
- Balance validation on tier downgrade
"""
from decimal import Decimal
import logging
from django.db import transaction as db_transaction

from apps.tenants.models import Tenant, TenantWallet
from apps.core.exceptions import TuliaException

logger = logging.getLogger(__name__)


class PaymentFacilitationNotEnabled(TuliaException):
    """Raised when payment facilitation is not enabled for tenant's tier."""
    pass


class WalletBalanceNotZero(TuliaException):
    """Raised when attempting tier downgrade with non-zero wallet balance."""
    pass


class PaymentFacilitationService:
    """Service for payment facilitation tier checks and management."""
    
    @staticmethod
    def is_payment_facilitation_enabled(tenant: Tenant) -> bool:
        """
        Check if payment facilitation is enabled for tenant's subscription tier.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            bool: True if payment facilitation is enabled
        """
        if not tenant.subscription_tier:
            return False
        
        return tenant.subscription_tier.payment_facilitation
    
    @staticmethod
    def require_payment_facilitation(tenant: Tenant):
        """
        Require payment facilitation to be enabled, raise exception if not.
        
        Args:
            tenant: Tenant instance
            
        Raises:
            PaymentFacilitationNotEnabled: If payment facilitation is not enabled
        """
        if not PaymentFacilitationService.is_payment_facilitation_enabled(tenant):
            tier_name = tenant.subscription_tier.name if tenant.subscription_tier else 'None'
            raise PaymentFacilitationNotEnabled(
                f"Payment facilitation is not enabled for your subscription tier ({tier_name}). "
                f"Please upgrade to Growth or Enterprise tier to use wallet features.",
                details={
                    'tenant_id': str(tenant.id),
                    'current_tier': tier_name,
                    'payment_facilitation_enabled': False,
                    'upgrade_required': True
                }
            )
    
    @staticmethod
    @db_transaction.atomic
    def handle_tier_upgrade(tenant: Tenant, new_tier):
        """
        Handle tier upgrade: auto-create wallet if payment facilitation is newly enabled.
        
        Args:
            tenant: Tenant instance
            new_tier: New SubscriptionTier instance
            
        Returns:
            dict: {
                'wallet_created': bool,
                'wallet_id': str (if created)
            }
        """
        old_tier = tenant.subscription_tier
        old_has_payment = old_tier.payment_facilitation if old_tier else False
        new_has_payment = new_tier.payment_facilitation
        
        result = {
            'wallet_created': False,
            'wallet_id': None
        }
        
        # If payment facilitation is newly enabled, create wallet
        if new_has_payment and not old_has_payment:
            wallet, created = TenantWallet.objects.get_or_create(
                tenant=tenant,
                defaults={
                    'balance': Decimal('0'),
                    'currency': 'USD',
                    'minimum_withdrawal': Decimal('10')
                }
            )
            
            if created:
                result['wallet_created'] = True
                result['wallet_id'] = str(wallet.id)
                
                logger.info(
                    f"Wallet auto-created for tenant {tenant.id} on tier upgrade",
                    extra={
                        'tenant_id': str(tenant.id),
                        'old_tier': old_tier.name if old_tier else None,
                        'new_tier': new_tier.name,
                        'wallet_id': str(wallet.id)
                    }
                )
        
        return result
    
    @staticmethod
    def validate_tier_downgrade(tenant: Tenant, new_tier):
        """
        Validate tier downgrade: ensure wallet balance is zero if losing payment facilitation.
        
        Args:
            tenant: Tenant instance
            new_tier: New SubscriptionTier instance
            
        Raises:
            WalletBalanceNotZero: If wallet has non-zero balance and payment facilitation is being disabled
        """
        old_tier = tenant.subscription_tier
        old_has_payment = old_tier.payment_facilitation if old_tier else False
        new_has_payment = new_tier.payment_facilitation
        
        # If losing payment facilitation, check wallet balance
        if old_has_payment and not new_has_payment:
            try:
                wallet = TenantWallet.objects.get(tenant=tenant)
                
                if wallet.balance > 0:
                    raise WalletBalanceNotZero(
                        f"Cannot downgrade tier while wallet has a balance of {wallet.currency} {wallet.balance}. "
                        f"Please withdraw all funds before downgrading.",
                        details={
                            'tenant_id': str(tenant.id),
                            'wallet_balance': float(wallet.balance),
                            'currency': wallet.currency,
                            'old_tier': old_tier.name,
                            'new_tier': new_tier.name
                        }
                    )
                
                logger.info(
                    f"Tier downgrade validated for tenant {tenant.id} - wallet balance is zero",
                    extra={
                        'tenant_id': str(tenant.id),
                        'old_tier': old_tier.name,
                        'new_tier': new_tier.name
                    }
                )
                
            except TenantWallet.DoesNotExist:
                # No wallet exists, downgrade is allowed
                pass
    
    @staticmethod
    def get_payment_features_info(tenant: Tenant) -> dict:
        """
        Get information about payment features for tenant.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            dict: {
                'payment_facilitation_enabled': bool,
                'has_wallet': bool,
                'wallet_balance': Decimal (if has_wallet),
                'currency': str (if has_wallet),
                'transaction_fee_percentage': Decimal,
                'tier_name': str
            }
        """
        tier = tenant.subscription_tier
        has_payment = tier.payment_facilitation if tier else False
        
        info = {
            'payment_facilitation_enabled': has_payment,
            'has_wallet': False,
            'wallet_balance': None,
            'currency': None,
            'transaction_fee_percentage': tier.transaction_fee_percentage if tier else Decimal('0'),
            'tier_name': tier.name if tier else 'None'
        }
        
        if has_payment:
            try:
                wallet = TenantWallet.objects.get(tenant=tenant)
                info['has_wallet'] = True
                info['wallet_balance'] = wallet.balance
                info['currency'] = wallet.currency
            except TenantWallet.DoesNotExist:
                pass
        
        return info
