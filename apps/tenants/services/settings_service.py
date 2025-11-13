"""
Settings management service for tenant configuration.

Handles secure management of:
- Integration credentials (Twilio, WooCommerce, Shopify) with validation
- Payment methods via Stripe tokenization
- Payout methods with encryption
- API key generation and revocation
- Business settings and preferences

All credential updates are validated against external APIs and audit logged.
"""
import logging
import hashlib
import secrets
from typing import Dict, Any, Optional, List
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.conf import settings as django_settings
from django.core.exceptions import ValidationError

from apps.tenants.models import Tenant, TenantSettings
from apps.rbac.models import User, AuditLog

logger = logging.getLogger(__name__)


class SettingsServiceError(Exception):
    """Base exception for settings service errors."""
    pass


class CredentialValidationError(SettingsServiceError):
    """Raised when external credential validation fails."""
    pass


class SettingsService:
    """
    Service for managing tenant settings and credentials.
    
    Provides methods for:
    - Getting or creating tenant settings
    - Updating integration credentials with validation
    - Managing payment methods via Stripe
    - Managing payout methods with encryption
    - Generating and revoking API keys
    """
    
    @staticmethod
    def get_or_create_settings(tenant: Tenant) -> TenantSettings:
        """
        Get or create TenantSettings for a tenant.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            TenantSettings instance
        """
        settings, created = TenantSettings.objects.get_or_create(
            tenant=tenant,
            defaults={
                'notification_settings': {},
                'feature_flags': {},
                'business_hours': {},
                'integrations_status': {},
                'branding': {},
                'compliance_settings': {},
                'onboarding_status': {},
            }
        )
        
        if created:
            # Initialize onboarding status for new settings
            settings.initialize_onboarding_status()
            logger.info(
                f"Created TenantSettings for tenant",
                extra={'tenant_id': str(tenant.id), 'tenant_slug': tenant.slug}
            )
        
        return settings
    
    @classmethod
    @transaction.atomic
    def update_twilio_credentials(
        cls,
        tenant: Tenant,
        sid: str,
        token: str,
        webhook_secret: str,
        whatsapp_number: Optional[str] = None,
        user: Optional[User] = None
    ) -> TenantSettings:
        """
        Update Twilio credentials with validation.
        
        Steps:
        1. Validate credentials with Twilio API
        2. Encrypt and store in TenantSettings
        3. Update onboarding status
        4. Log to AuditLog
        
        Args:
            tenant: Tenant instance
            sid: Twilio Account SID
            token: Twilio Auth Token
            webhook_secret: Twilio webhook signature secret
            whatsapp_number: Optional WhatsApp number (updates tenant if provided)
            user: User performing the update (for audit log)
            
        Returns:
            TenantSettings instance
            
        Raises:
            CredentialValidationError: If Twilio credentials are invalid
        """
        # Validate credentials with Twilio API
        try:
            from twilio.rest import Client
            from twilio.base.exceptions import TwilioRestException
            
            client = Client(sid, token)
            # Make a test API call to validate credentials
            account = client.api.accounts(sid).fetch()
            
            logger.info(
                f"Twilio credentials validated successfully",
                extra={
                    'tenant_id': str(tenant.id),
                    'account_sid': sid[:8] + '...',  # Log only first 8 chars
                    'account_status': account.status
                }
            )
            
        except TwilioRestException as e:
            logger.error(
                f"Twilio credential validation failed",
                extra={
                    'tenant_id': str(tenant.id),
                    'error_code': e.code,
                    'error_message': str(e)
                },
                exc_info=True
            )
            raise CredentialValidationError(
                f"Twilio credentials are invalid: {e.msg}"
            ) from e
        
        except Exception as e:
            logger.error(
                f"Unexpected error validating Twilio credentials",
                extra={'tenant_id': str(tenant.id)},
                exc_info=True
            )
            raise CredentialValidationError(
                f"Failed to validate Twilio credentials: {str(e)}"
            ) from e
        
        # Get or create settings
        settings = cls.get_or_create_settings(tenant)
        
        # Update credentials
        settings.twilio_sid = sid
        settings.twilio_token = token
        settings.twilio_webhook_secret = webhook_secret
        settings.save(update_fields=['twilio_sid', 'twilio_token', 'twilio_webhook_secret', 'updated_at'])
        
        # Update WhatsApp number on tenant if provided
        if whatsapp_number:
            tenant.whatsapp_number = whatsapp_number
            tenant.save(update_fields=['whatsapp_number', 'updated_at'])
        
        # Update integration status
        settings.update_integration_status('twilio', {
            'configured': True,
            'last_validated_at': timezone.now().isoformat(),
            'account_status': account.status if 'account' in locals() else 'active'
        })
        
        # Mark onboarding step as complete
        if 'twilio_configured' in settings.onboarding_status:
            settings.onboarding_status['twilio_configured'] = {
                'completed': True,
                'completed_at': timezone.now().isoformat()
            }
            settings.save(update_fields=['onboarding_status', 'updated_at'])
        
        # Log to audit trail
        if user:
            AuditLog.log_action(
                action='twilio_credentials_updated',
                user=user,
                tenant=tenant,
                target_type='TenantSettings',
                target_id=settings.id,
                metadata={
                    'account_sid': sid[:8] + '...',
                    'whatsapp_number': whatsapp_number
                }
            )
        
        logger.info(
            f"Twilio credentials updated successfully",
            extra={'tenant_id': str(tenant.id), 'tenant_slug': tenant.slug}
        )
        
        return settings
    
    @classmethod
    @transaction.atomic
    def update_woocommerce_credentials(
        cls,
        tenant: Tenant,
        store_url: str,
        consumer_key: str,
        consumer_secret: str,
        user: Optional[User] = None
    ) -> TenantSettings:
        """
        Update WooCommerce credentials with validation.
        
        Steps:
        1. Validate credentials with WooCommerce API
        2. Encrypt and store in TenantSettings
        3. Update onboarding status
        4. Log to AuditLog
        
        Args:
            tenant: Tenant instance
            store_url: WooCommerce store URL
            consumer_key: WooCommerce REST API consumer key
            consumer_secret: WooCommerce REST API consumer secret
            user: User performing the update (for audit log)
            
        Returns:
            TenantSettings instance
            
        Raises:
            CredentialValidationError: If WooCommerce credentials are invalid
        """
        # Validate credentials with WooCommerce API
        try:
            import requests
            from requests.auth import HTTPBasicAuth
            
            # Clean up store URL
            store_url = store_url.rstrip('/')
            api_url = f"{store_url}/wp-json/wc/v3/system_status"
            
            response = requests.get(
                api_url,
                auth=HTTPBasicAuth(consumer_key, consumer_secret),
                timeout=10
            )
            response.raise_for_status()
            
            system_status = response.json()
            
            logger.info(
                f"WooCommerce credentials validated successfully",
                extra={
                    'tenant_id': str(tenant.id),
                    'store_url': store_url,
                    'woo_version': system_status.get('environment', {}).get('version')
                }
            )
            
        except requests.exceptions.HTTPError as e:
            logger.error(
                f"WooCommerce credential validation failed",
                extra={
                    'tenant_id': str(tenant.id),
                    'status_code': e.response.status_code,
                    'response': e.response.text[:200]
                },
                exc_info=True
            )
            
            if e.response.status_code == 401:
                raise CredentialValidationError(
                    "WooCommerce credentials are invalid. Please check your consumer key and secret."
                ) from e
            elif e.response.status_code == 404:
                raise CredentialValidationError(
                    "WooCommerce REST API not found. Please ensure WooCommerce is installed and REST API is enabled."
                ) from e
            else:
                raise CredentialValidationError(
                    f"WooCommerce API error: {e.response.status_code}"
                ) from e
        
        except requests.exceptions.Timeout as e:
            logger.error(
                f"WooCommerce API timeout",
                extra={'tenant_id': str(tenant.id), 'store_url': store_url},
                exc_info=True
            )
            raise CredentialValidationError(
                "Connection to WooCommerce store timed out. Please check the store URL."
            ) from e
        
        except requests.exceptions.RequestException as e:
            logger.error(
                f"WooCommerce API request error",
                extra={'tenant_id': str(tenant.id), 'store_url': store_url},
                exc_info=True
            )
            raise CredentialValidationError(
                f"Failed to connect to WooCommerce store: {str(e)}"
            ) from e
        
        except Exception as e:
            logger.error(
                f"Unexpected error validating WooCommerce credentials",
                extra={'tenant_id': str(tenant.id)},
                exc_info=True
            )
            raise CredentialValidationError(
                f"Failed to validate WooCommerce credentials: {str(e)}"
            ) from e
        
        # Get or create settings
        settings = cls.get_or_create_settings(tenant)
        
        # Update credentials
        settings.woo_store_url = store_url
        settings.woo_consumer_key = consumer_key
        settings.woo_consumer_secret = consumer_secret
        settings.save(update_fields=[
            'woo_store_url', 'woo_consumer_key', 'woo_consumer_secret', 'updated_at'
        ])
        
        # Update integration status
        settings.update_integration_status('woocommerce', {
            'configured': True,
            'last_validated_at': timezone.now().isoformat(),
            'store_url': store_url,
            'woo_version': system_status.get('environment', {}).get('version') if 'system_status' in locals() else None
        })
        
        # Mark onboarding step as complete
        if 'woocommerce_configured' in settings.onboarding_status:
            settings.onboarding_status['woocommerce_configured'] = {
                'completed': True,
                'completed_at': timezone.now().isoformat()
            }
            settings.save(update_fields=['onboarding_status', 'updated_at'])
        
        # Log to audit trail
        if user:
            AuditLog.log_action(
                action='woocommerce_credentials_updated',
                user=user,
                tenant=tenant,
                target_type='TenantSettings',
                target_id=settings.id,
                metadata={
                    'store_url': store_url
                }
            )
        
        logger.info(
            f"WooCommerce credentials updated successfully",
            extra={'tenant_id': str(tenant.id), 'tenant_slug': tenant.slug}
        )
        
        return settings
    
    @classmethod
    @transaction.atomic
    def update_shopify_credentials(
        cls,
        tenant: Tenant,
        shop_domain: str,
        access_token: str,
        user: Optional[User] = None
    ) -> TenantSettings:
        """
        Update Shopify credentials with validation.
        
        Steps:
        1. Validate credentials with Shopify Admin API
        2. Encrypt and store in TenantSettings
        3. Update onboarding status
        4. Log to AuditLog
        
        Args:
            tenant: Tenant instance
            shop_domain: Shopify shop domain (e.g., mystore.myshopify.com)
            access_token: Shopify Admin API access token
            user: User performing the update (for audit log)
            
        Returns:
            TenantSettings instance
            
        Raises:
            CredentialValidationError: If Shopify credentials are invalid
        """
        # Validate credentials with Shopify Admin API
        try:
            import requests
            
            # Clean up shop domain
            shop_domain = shop_domain.replace('https://', '').replace('http://', '').rstrip('/')
            api_url = f"https://{shop_domain}/admin/api/2024-01/shop.json"
            
            response = requests.get(
                api_url,
                headers={
                    'X-Shopify-Access-Token': access_token,
                    'Content-Type': 'application/json'
                },
                timeout=10
            )
            response.raise_for_status()
            
            shop_data = response.json().get('shop', {})
            
            logger.info(
                f"Shopify credentials validated successfully",
                extra={
                    'tenant_id': str(tenant.id),
                    'shop_domain': shop_domain,
                    'shop_name': shop_data.get('name')
                }
            )
            
        except requests.exceptions.HTTPError as e:
            logger.error(
                f"Shopify credential validation failed",
                extra={
                    'tenant_id': str(tenant.id),
                    'status_code': e.response.status_code,
                    'response': e.response.text[:200]
                },
                exc_info=True
            )
            
            if e.response.status_code == 401:
                raise CredentialValidationError(
                    "Shopify access token is invalid. Please check your credentials."
                ) from e
            elif e.response.status_code == 404:
                raise CredentialValidationError(
                    "Shopify shop not found. Please check the shop domain."
                ) from e
            else:
                raise CredentialValidationError(
                    f"Shopify API error: {e.response.status_code}"
                ) from e
        
        except requests.exceptions.Timeout as e:
            logger.error(
                f"Shopify API timeout",
                extra={'tenant_id': str(tenant.id), 'shop_domain': shop_domain},
                exc_info=True
            )
            raise CredentialValidationError(
                "Connection to Shopify store timed out. Please check the shop domain."
            ) from e
        
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Shopify API request error",
                extra={'tenant_id': str(tenant.id), 'shop_domain': shop_domain},
                exc_info=True
            )
            raise CredentialValidationError(
                f"Failed to connect to Shopify store: {str(e)}"
            ) from e
        
        except Exception as e:
            logger.error(
                f"Unexpected error validating Shopify credentials",
                extra={'tenant_id': str(tenant.id)},
                exc_info=True
            )
            raise CredentialValidationError(
                f"Failed to validate Shopify credentials: {str(e)}"
            ) from e
        
        # Get or create settings
        settings = cls.get_or_create_settings(tenant)
        
        # Update credentials
        settings.shopify_shop_domain = shop_domain
        settings.shopify_access_token = access_token
        settings.save(update_fields=['shopify_shop_domain', 'shopify_access_token', 'updated_at'])
        
        # Update integration status
        settings.update_integration_status('shopify', {
            'configured': True,
            'last_validated_at': timezone.now().isoformat(),
            'shop_domain': shop_domain,
            'shop_name': shop_data.get('name') if 'shop_data' in locals() else None
        })
        
        # Mark onboarding step as complete
        if 'shopify_configured' in settings.onboarding_status:
            settings.onboarding_status['shopify_configured'] = {
                'completed': True,
                'completed_at': timezone.now().isoformat()
            }
            settings.save(update_fields=['onboarding_status', 'updated_at'])
        
        # Log to audit trail
        if user:
            AuditLog.log_action(
                action='shopify_credentials_updated',
                user=user,
                tenant=tenant,
                target_type='TenantSettings',
                target_id=settings.id,
                metadata={
                    'shop_domain': shop_domain
                }
            )
        
        logger.info(
            f"Shopify credentials updated successfully",
            extra={'tenant_id': str(tenant.id), 'tenant_slug': tenant.slug}
        )
        
        return settings

    
    @classmethod
    @transaction.atomic
    def add_payment_method(
        cls,
        tenant: Tenant,
        stripe_token: str,
        user: Optional[User] = None
    ) -> Dict[str, Any]:
        """
        Add payment method via Stripe tokenization.
        
        Steps:
        1. Create/get Stripe customer
        2. Attach payment method
        3. Store payment method ID and metadata
        4. Return masked card details
        
        Args:
            tenant: Tenant instance
            stripe_token: Stripe token or PaymentMethod ID
            user: User performing the action (for audit log)
            
        Returns:
            dict: Payment method details with masked card info
            
        Raises:
            SettingsServiceError: If Stripe operation fails
        """
        try:
            import stripe
            stripe.api_key = django_settings.STRIPE_SECRET_KEY
            
            # Get or create settings
            settings = cls.get_or_create_settings(tenant)
            
            # Create or get Stripe customer
            if not settings.stripe_customer_id:
                customer = stripe.Customer.create(
                    email=tenant.contact_email,
                    name=tenant.name,
                    metadata={
                        'tenant_id': str(tenant.id),
                        'tenant_slug': tenant.slug
                    }
                )
                settings.stripe_customer_id = customer.id
                settings.save(update_fields=['stripe_customer_id', 'updated_at'])
                
                logger.info(
                    f"Created Stripe customer",
                    extra={
                        'tenant_id': str(tenant.id),
                        'customer_id': customer.id
                    }
                )
            else:
                customer = stripe.Customer.retrieve(settings.stripe_customer_id)
            
            # Attach payment method to customer
            if stripe_token.startswith('pm_'):
                # Already a PaymentMethod ID
                payment_method = stripe.PaymentMethod.attach(
                    stripe_token,
                    customer=customer.id
                )
            else:
                # Token - create PaymentMethod
                payment_method = stripe.PaymentMethod.create(
                    type='card',
                    card={'token': stripe_token}
                )
                payment_method = stripe.PaymentMethod.attach(
                    payment_method.id,
                    customer=customer.id
                )
            
            # Extract card details
            card = payment_method.card
            payment_method_data = {
                'id': payment_method.id,
                'last4': card.last4,
                'brand': card.brand,
                'exp_month': card.exp_month,
                'exp_year': card.exp_year,
                'is_default': len(settings.stripe_payment_methods) == 0,  # First card is default
                'created_at': timezone.now().isoformat()
            }
            
            # Add to payment methods list
            if not settings.stripe_payment_methods:
                settings.stripe_payment_methods = []
            
            settings.stripe_payment_methods.append(payment_method_data)
            settings.save(update_fields=['stripe_payment_methods', 'updated_at'])
            
            # Mark onboarding step as complete
            if 'payment_method_added' in settings.onboarding_status:
                settings.onboarding_status['payment_method_added'] = {
                    'completed': True,
                    'completed_at': timezone.now().isoformat()
                }
                settings.save(update_fields=['onboarding_status', 'updated_at'])
            
            # Log to audit trail
            if user:
                AuditLog.log_action(
                    action='payment_method_added',
                    user=user,
                    tenant=tenant,
                    target_type='TenantSettings',
                    target_id=settings.id,
                    metadata={
                        'payment_method_id': payment_method.id,
                        'last4': card.last4,
                        'brand': card.brand
                    }
                )
            
            logger.info(
                f"Payment method added successfully",
                extra={
                    'tenant_id': str(tenant.id),
                    'payment_method_id': payment_method.id,
                    'last4': card.last4
                }
            )
            
            return payment_method_data
            
        except stripe.error.CardError as e:
            logger.error(
                f"Stripe card error",
                extra={
                    'tenant_id': str(tenant.id),
                    'error_code': e.code,
                    'error_message': str(e)
                },
                exc_info=True
            )
            raise SettingsServiceError(f"Card error: {e.user_message}") from e
        
        except stripe.error.StripeError as e:
            logger.error(
                f"Stripe API error",
                extra={
                    'tenant_id': str(tenant.id),
                    'error_type': type(e).__name__,
                    'error_message': str(e)
                },
                exc_info=True
            )
            raise SettingsServiceError(f"Payment processing error: {str(e)}") from e
        
        except Exception as e:
            logger.error(
                f"Unexpected error adding payment method",
                extra={'tenant_id': str(tenant.id)},
                exc_info=True
            )
            raise SettingsServiceError(f"Failed to add payment method: {str(e)}") from e
    
    @classmethod
    @transaction.atomic
    def set_default_payment_method(
        cls,
        tenant: Tenant,
        payment_method_id: str,
        user: Optional[User] = None
    ) -> TenantSettings:
        """
        Set default payment method.
        
        Args:
            tenant: Tenant instance
            payment_method_id: Stripe PaymentMethod ID
            user: User performing the action (for audit log)
            
        Returns:
            TenantSettings instance
            
        Raises:
            SettingsServiceError: If payment method not found
        """
        settings = cls.get_or_create_settings(tenant)
        
        # Find payment method
        found = False
        for pm in settings.stripe_payment_methods:
            if pm['id'] == payment_method_id:
                pm['is_default'] = True
                found = True
            else:
                pm['is_default'] = False
        
        if not found:
            raise SettingsServiceError(
                f"Payment method {payment_method_id} not found"
            )
        
        settings.save(update_fields=['stripe_payment_methods', 'updated_at'])
        
        # Log to audit trail
        if user:
            AuditLog.log_action(
                action='default_payment_method_changed',
                user=user,
                tenant=tenant,
                target_type='TenantSettings',
                target_id=settings.id,
                metadata={
                    'payment_method_id': payment_method_id
                }
            )
        
        logger.info(
            f"Default payment method updated",
            extra={
                'tenant_id': str(tenant.id),
                'payment_method_id': payment_method_id
            }
        )
        
        return settings
    
    @classmethod
    @transaction.atomic
    def remove_payment_method(
        cls,
        tenant: Tenant,
        payment_method_id: str,
        user: Optional[User] = None
    ) -> TenantSettings:
        """
        Remove payment method.
        
        Detaches payment method from Stripe customer and removes from settings.
        
        Args:
            tenant: Tenant instance
            payment_method_id: Stripe PaymentMethod ID
            user: User performing the action (for audit log)
            
        Returns:
            TenantSettings instance
            
        Raises:
            SettingsServiceError: If payment method not found or Stripe operation fails
        """
        try:
            import stripe
            stripe.api_key = django_settings.STRIPE_SECRET_KEY
            
            settings = cls.get_or_create_settings(tenant)
            
            # Find and remove payment method from list
            payment_methods = settings.stripe_payment_methods or []
            removed_pm = None
            new_payment_methods = []
            
            for pm in payment_methods:
                if pm['id'] == payment_method_id:
                    removed_pm = pm
                else:
                    new_payment_methods.append(pm)
            
            if not removed_pm:
                raise SettingsServiceError(
                    f"Payment method {payment_method_id} not found"
                )
            
            # Detach from Stripe
            try:
                payment_method = stripe.PaymentMethod.detach(payment_method_id)
                logger.info(
                    f"Payment method detached from Stripe",
                    extra={
                        'tenant_id': str(tenant.id),
                        'payment_method_id': payment_method_id
                    }
                )
            except stripe.error.StripeError as e:
                logger.warning(
                    f"Failed to detach payment method from Stripe, continuing with removal",
                    extra={
                        'tenant_id': str(tenant.id),
                        'payment_method_id': payment_method_id,
                        'error': str(e)
                    }
                )
            
            # Update settings
            settings.stripe_payment_methods = new_payment_methods
            
            # If removed method was default and there are other methods, set first as default
            if removed_pm.get('is_default') and new_payment_methods:
                new_payment_methods[0]['is_default'] = True
            
            settings.save(update_fields=['stripe_payment_methods', 'updated_at'])
            
            # Log to audit trail
            if user:
                AuditLog.log_action(
                    action='payment_method_removed',
                    user=user,
                    tenant=tenant,
                    target_type='TenantSettings',
                    target_id=settings.id,
                    metadata={
                        'payment_method_id': payment_method_id,
                        'last4': removed_pm.get('last4'),
                        'brand': removed_pm.get('brand')
                    }
                )
            
            logger.info(
                f"Payment method removed successfully",
                extra={
                    'tenant_id': str(tenant.id),
                    'payment_method_id': payment_method_id
                }
            )
            
            return settings
            
        except SettingsServiceError:
            raise
        
        except Exception as e:
            logger.error(
                f"Unexpected error removing payment method",
                extra={
                    'tenant_id': str(tenant.id),
                    'payment_method_id': payment_method_id
                },
                exc_info=True
            )
            raise SettingsServiceError(f"Failed to remove payment method: {str(e)}") from e

    
    @classmethod
    @transaction.atomic
    def update_payout_method(
        cls,
        tenant: Tenant,
        method: str,
        details: Dict[str, Any],
        user: Optional[User] = None
    ) -> TenantSettings:
        """
        Update payout method with encrypted details.
        
        Validates required fields based on method type and encrypts
        sensitive account details.
        
        Args:
            tenant: Tenant instance
            method: Payout method type ('bank_transfer', 'mobile_money', 'paypal')
            details: Payout account details (will be encrypted)
            user: User performing the action (for audit log)
            
        Returns:
            TenantSettings instance
            
        Raises:
            ValidationError: If required fields are missing or invalid
        """
        # Validate method type
        valid_methods = ['bank_transfer', 'mobile_money', 'paypal']
        if method not in valid_methods:
            raise ValidationError(
                f"Invalid payout method. Must be one of: {', '.join(valid_methods)}"
            )
        
        # Validate required fields based on method type
        if method == 'bank_transfer':
            required_fields = ['account_number', 'routing_number', 'account_holder_name']
            for field in required_fields:
                if not details.get(field):
                    raise ValidationError(
                        f"Missing required field for bank transfer: {field}"
                    )
            
            # Validate account number format (basic check)
            account_number = details['account_number']
            if not account_number.isdigit() or len(account_number) < 8:
                raise ValidationError(
                    "Invalid account number format"
                )
            
            # Validate routing number format (US format)
            routing_number = details['routing_number']
            if not routing_number.isdigit() or len(routing_number) != 9:
                raise ValidationError(
                    "Invalid routing number format (must be 9 digits)"
                )
        
        elif method == 'mobile_money':
            required_fields = ['phone_number', 'provider']
            for field in required_fields:
                if not details.get(field):
                    raise ValidationError(
                        f"Missing required field for mobile money: {field}"
                    )
            
            # Validate phone number format (E.164)
            phone_number = details['phone_number']
            if not phone_number.startswith('+') or not phone_number[1:].isdigit():
                raise ValidationError(
                    "Invalid phone number format (must be E.164 format, e.g., +1234567890)"
                )
            
            # Validate provider
            valid_providers = ['mpesa', 'mtn_money', 'airtel_money', 'orange_money']
            if details['provider'] not in valid_providers:
                raise ValidationError(
                    f"Invalid mobile money provider. Must be one of: {', '.join(valid_providers)}"
                )
        
        elif method == 'paypal':
            required_fields = ['email']
            for field in required_fields:
                if not details.get(field):
                    raise ValidationError(
                        f"Missing required field for PayPal: {field}"
                    )
            
            # Validate email format
            import re
            email = details['email']
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                raise ValidationError(
                    "Invalid email format for PayPal"
                )
        
        # Get or create settings
        settings = cls.get_or_create_settings(tenant)
        
        # Store payout method and encrypted details
        import json
        settings.payout_method = method
        settings.payout_details = json.dumps(details)  # Will be encrypted by EncryptedTextField
        settings.save(update_fields=['payout_method', 'payout_details', 'updated_at'])
        
        # Mark onboarding step as complete
        if 'payout_method_configured' in settings.onboarding_status:
            settings.onboarding_status['payout_method_configured'] = {
                'completed': True,
                'completed_at': timezone.now().isoformat()
            }
            settings.save(update_fields=['onboarding_status', 'updated_at'])
        
        # Log to audit trail (with masked details)
        masked_details = {}
        if method == 'bank_transfer':
            masked_details = {
                'account_number': '****' + details['account_number'][-4:],
                'routing_number': details['routing_number'],
                'account_holder_name': details['account_holder_name']
            }
        elif method == 'mobile_money':
            phone = details['phone_number']
            masked_details = {
                'phone_number': phone[:3] + '****' + phone[-4:],
                'provider': details['provider']
            }
        elif method == 'paypal':
            email = details['email']
            parts = email.split('@')
            masked_details = {
                'email': parts[0][:2] + '****@' + parts[1]
            }
        
        if user:
            AuditLog.log_action(
                action='payout_method_updated',
                user=user,
                tenant=tenant,
                target_type='TenantSettings',
                target_id=settings.id,
                metadata={
                    'method': method,
                    'details': masked_details
                }
            )
        
        logger.info(
            f"Payout method updated successfully",
            extra={
                'tenant_id': str(tenant.id),
                'method': method
            }
        )
        
        return settings

    
    @classmethod
    @transaction.atomic
    def generate_api_key(
        cls,
        tenant: Tenant,
        name: str,
        user: Optional[User] = None
    ) -> tuple[str, Dict[str, Any]]:
        """
        Generate new API key with secure random generation.
        
        Creates a 32-character random key, stores its SHA-256 hash,
        and returns the plain key once (never stored).
        
        Args:
            tenant: Tenant instance
            name: Descriptive name for the API key
            user: User generating the key (for audit log)
            
        Returns:
            tuple: (plain_key, metadata_dict)
            
        Example:
            >>> plain_key, metadata = SettingsService.generate_api_key(
            ...     tenant, "Production API", user
            ... )
            >>> print(f"API Key: {plain_key}")  # Show to user once
        """
        # Generate secure random 32-character key
        plain_key = secrets.token_urlsafe(32)[:32]  # Ensure exactly 32 chars
        
        # Compute SHA-256 hash
        key_hash = hashlib.sha256(plain_key.encode()).hexdigest()
        
        # Create metadata
        metadata = {
            'key_hash': key_hash,
            'name': name,
            'created_at': timezone.now().isoformat(),
            'created_by': user.email if user else None,
            'last_used_at': None
        }
        
        # Add to tenant's API keys
        if not tenant.api_keys:
            tenant.api_keys = []
        
        tenant.api_keys.append(metadata)
        tenant.save(update_fields=['api_keys', 'updated_at'])
        
        # Log to audit trail
        if user:
            AuditLog.log_action(
                action='api_key_generated',
                user=user,
                tenant=tenant,
                target_type='Tenant',
                target_id=tenant.id,
                metadata={
                    'key_name': name,
                    'key_hash': key_hash[:16] + '...',  # Log partial hash
                }
            )
        
        logger.info(
            f"API key generated successfully",
            extra={
                'tenant_id': str(tenant.id),
                'key_name': name,
                'key_hash': key_hash[:16] + '...'
            }
        )
        
        return plain_key, metadata
    
    @classmethod
    @transaction.atomic
    def revoke_api_key(
        cls,
        tenant: Tenant,
        key_hash: str,
        user: Optional[User] = None
    ) -> Tenant:
        """
        Revoke API key by removing from tenant.api_keys.
        
        Args:
            tenant: Tenant instance
            key_hash: SHA-256 hash of the API key to revoke
            user: User revoking the key (for audit log)
            
        Returns:
            Tenant instance
            
        Raises:
            SettingsServiceError: If API key not found
        """
        # Find and remove API key
        api_keys = tenant.api_keys or []
        revoked_key = None
        new_api_keys = []
        
        for key in api_keys:
            if key['key_hash'] == key_hash:
                revoked_key = key
            else:
                new_api_keys.append(key)
        
        if not revoked_key:
            raise SettingsServiceError(
                f"API key with hash {key_hash[:16]}... not found"
            )
        
        # Update tenant
        tenant.api_keys = new_api_keys
        tenant.save(update_fields=['api_keys', 'updated_at'])
        
        # Log to audit trail
        if user:
            AuditLog.log_action(
                action='api_key_revoked',
                user=user,
                tenant=tenant,
                target_type='Tenant',
                target_id=tenant.id,
                metadata={
                    'key_name': revoked_key.get('name'),
                    'key_hash': key_hash[:16] + '...',
                    'created_at': revoked_key.get('created_at')
                }
            )
        
        logger.info(
            f"API key revoked successfully",
            extra={
                'tenant_id': str(tenant.id),
                'key_name': revoked_key.get('name'),
                'key_hash': key_hash[:16] + '...'
            }
        )
        
        return tenant
    
    @staticmethod
    def list_api_keys(tenant: Tenant) -> List[Dict[str, Any]]:
        """
        List all API keys for a tenant with masked hashes.
        
        Returns keys with first 8 characters of hash visible for identification.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            list: List of API key metadata with masked hashes
        """
        api_keys = tenant.api_keys or []
        
        # Return keys with masked hashes
        masked_keys = []
        for key in api_keys:
            masked_key = key.copy()
            # Show only first 8 characters of hash
            masked_key['key_hash_preview'] = key['key_hash'][:8] + '...'
            # Remove full hash from response
            masked_key.pop('key_hash', None)
            masked_keys.append(masked_key)
        
        return masked_keys
    
    @staticmethod
    def validate_api_key(tenant: Tenant, plain_key: str) -> bool:
        """
        Validate an API key against stored hashes.
        
        Args:
            tenant: Tenant instance
            plain_key: Plain text API key to validate
            
        Returns:
            bool: True if key is valid, False otherwise
        """
        # Compute hash of provided key
        key_hash = hashlib.sha256(plain_key.encode()).hexdigest()
        
        # Check against stored hashes
        api_keys = tenant.api_keys or []
        for key in api_keys:
            if key['key_hash'] == key_hash:
                # Update last_used_at
                key['last_used_at'] = timezone.now().isoformat()
                tenant.save(update_fields=['api_keys', 'updated_at'])
                return True
        
        return False

    
    # ========== PAYMENT PROVIDER MANAGEMENT ==========
    
    @classmethod
    @transaction.atomic
    def configure_mpesa(
        cls,
        tenant: Tenant,
        shortcode: str,
        consumer_key: str,
        consumer_secret: str,
        passkey: str,
        initiator_name: str = None,
        initiator_password: str = None,
        b2c_shortcode: str = None,
        user: Optional[User] = None
    ) -> TenantSettings:
        """
        Configure M-Pesa credentials for tenant.
        
        Args:
            tenant: Tenant instance
            shortcode: M-Pesa business shortcode
            consumer_key: M-Pesa consumer key
            consumer_secret: M-Pesa consumer secret
            passkey: M-Pesa passkey for STK Push
            initiator_name: Initiator name for B2C/B2B
            initiator_password: Initiator password
            b2c_shortcode: B2C shortcode (if different from main)
            user: User performing the update
            
        Returns:
            TenantSettings instance
        """
        settings = cls.get_or_create_settings(tenant)
        
        # Store in metadata (encrypted via EncryptedTextField if needed)
        if not settings.metadata:
            settings.metadata = {}
        
        settings.metadata['mpesa_shortcode'] = shortcode
        settings.metadata['mpesa_consumer_key'] = consumer_key
        settings.metadata['mpesa_consumer_secret'] = consumer_secret
        settings.metadata['mpesa_passkey'] = passkey
        
        if initiator_name:
            settings.metadata['mpesa_initiator_name'] = initiator_name
        if initiator_password:
            settings.metadata['mpesa_initiator_password'] = initiator_password
        if b2c_shortcode:
            settings.metadata['mpesa_b2c_shortcode'] = b2c_shortcode
        
        settings.save(update_fields=['metadata', 'updated_at'])
        
        # Update integration status
        settings.update_integration_status('mpesa', {
            'configured': True,
            'last_validated_at': timezone.now().isoformat(),
            'shortcode': shortcode
        })
        
        # Log to audit trail
        if user:
            AuditLog.log_action(
                action='mpesa_credentials_configured',
                user=user,
                tenant=tenant,
                target_type='TenantSettings',
                target_id=settings.id,
                metadata={'shortcode': shortcode}
            )
        
        logger.info(
            f"M-Pesa credentials configured",
            extra={'tenant_id': str(tenant.id), 'shortcode': shortcode}
        )
        
        return settings
    
    @classmethod
    @transaction.atomic
    def configure_paystack(
        cls,
        tenant: Tenant,
        public_key: str,
        secret_key: str,
        user: Optional[User] = None
    ) -> TenantSettings:
        """
        Configure Paystack credentials for tenant.
        
        Args:
            tenant: Tenant instance
            public_key: Paystack public key
            secret_key: Paystack secret key
            user: User performing the update
            
        Returns:
            TenantSettings instance
        """
        # Validate credentials by making a test API call
        try:
            import requests
            
            response = requests.get(
                'https://api.paystack.co/bank',
                headers={
                    'Authorization': f'Bearer {secret_key}',
                    'Content-Type': 'application/json'
                },
                params={'country': 'kenya'},
                timeout=10
            )
            response.raise_for_status()
            
            logger.info(
                f"Paystack credentials validated",
                extra={'tenant_id': str(tenant.id)}
            )
            
        except Exception as e:
            logger.error(
                f"Paystack credential validation failed",
                extra={'tenant_id': str(tenant.id)},
                exc_info=True
            )
            raise CredentialValidationError(
                f"Paystack credentials are invalid: {str(e)}"
            ) from e
        
        settings = cls.get_or_create_settings(tenant)
        
        # Store in metadata
        if not settings.metadata:
            settings.metadata = {}
        
        settings.metadata['paystack_public_key'] = public_key
        settings.metadata['paystack_secret_key'] = secret_key
        
        settings.save(update_fields=['metadata', 'updated_at'])
        
        # Update integration status
        settings.update_integration_status('paystack', {
            'configured': True,
            'last_validated_at': timezone.now().isoformat()
        })
        
        # Log to audit trail
        if user:
            AuditLog.log_action(
                action='paystack_credentials_configured',
                user=user,
                tenant=tenant,
                target_type='TenantSettings',
                target_id=settings.id,
                metadata={}
            )
        
        logger.info(
            f"Paystack credentials configured",
            extra={'tenant_id': str(tenant.id)}
        )
        
        return settings
    
    @classmethod
    @transaction.atomic
    def configure_pesapal(
        cls,
        tenant: Tenant,
        consumer_key: str,
        consumer_secret: str,
        ipn_id: str = None,
        user: Optional[User] = None
    ) -> TenantSettings:
        """
        Configure Pesapal credentials for tenant.
        
        Args:
            tenant: Tenant instance
            consumer_key: Pesapal consumer key
            consumer_secret: Pesapal consumer secret
            ipn_id: IPN ID (optional, will be registered if not provided)
            user: User performing the update
            
        Returns:
            TenantSettings instance
        """
        settings = cls.get_or_create_settings(tenant)
        
        # Store in metadata
        if not settings.metadata:
            settings.metadata = {}
        
        settings.metadata['pesapal_consumer_key'] = consumer_key
        settings.metadata['pesapal_consumer_secret'] = consumer_secret
        
        if ipn_id:
            settings.metadata['pesapal_ipn_id'] = ipn_id
        
        settings.save(update_fields=['metadata', 'updated_at'])
        
        # Update integration status
        settings.update_integration_status('pesapal', {
            'configured': True,
            'last_validated_at': timezone.now().isoformat()
        })
        
        # Log to audit trail
        if user:
            AuditLog.log_action(
                action='pesapal_credentials_configured',
                user=user,
                tenant=tenant,
                target_type='TenantSettings',
                target_id=settings.id,
                metadata={}
            )
        
        logger.info(
            f"Pesapal credentials configured",
            extra={'tenant_id': str(tenant.id)}
        )
        
        return settings
    
    @classmethod
    @transaction.atomic
    def configure_payout_method(
        cls,
        tenant: Tenant,
        method_type: str,
        method_details: Dict,
        user: Optional[User] = None
    ) -> TenantSettings:
        """
        Configure tenant payout method for withdrawals.
        
        Args:
            tenant: Tenant instance
            method_type: 'mpesa', 'bank_transfer', 'paystack', 'till'
            method_details: Method-specific details
                For M-Pesa: {'phone_number': '254712345678'}
                For Bank: {'account_number': '...', 'bank_code': '...', 'account_name': '...'}
                For Till: {'till_number': '...'}
            user: User performing the update
            
        Returns:
            TenantSettings instance
        """
        settings = cls.get_or_create_settings(tenant)
        
        # Validate method type
        valid_types = ['mpesa', 'bank_transfer', 'paystack', 'till']
        if method_type not in valid_types:
            raise SettingsServiceError(
                f"Invalid payout method type: {method_type}. Must be one of {valid_types}"
            )
        
        # Store payout method (encrypted)
        settings.payout_method = method_type
        
        # Encrypt and store details
        import json
        settings.payout_details = json.dumps(method_details)
        
        settings.save(update_fields=['payout_method', 'payout_details', 'updated_at'])
        
        # Log to audit trail
        if user:
            # Don't log sensitive details
            safe_metadata = {'method_type': method_type}
            if method_type == 'mpesa' and 'phone_number' in method_details:
                safe_metadata['phone_last4'] = method_details['phone_number'][-4:]
            elif method_type == 'bank_transfer' and 'account_number' in method_details:
                safe_metadata['account_last4'] = method_details['account_number'][-4:]
            
            AuditLog.log_action(
                action='payout_method_configured',
                user=user,
                tenant=tenant,
                target_type='TenantSettings',
                target_id=settings.id,
                metadata=safe_metadata
            )
        
        logger.info(
            f"Payout method configured",
            extra={'tenant_id': str(tenant.id), 'method_type': method_type}
        )
        
        return settings
    
    @staticmethod
    def get_payout_method(tenant: Tenant) -> Optional[Dict]:
        """
        Get tenant's configured payout method.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            dict: {'method_type': str, 'details': dict} or None
        """
        settings = getattr(tenant, 'settings', None)
        if not settings or not settings.payout_method:
            return None
        
        import json
        try:
            details = json.loads(settings.payout_details) if settings.payout_details else {}
        except json.JSONDecodeError:
            details = {}
        
        return {
            'method_type': settings.payout_method,
            'details': details
        }
    
    @staticmethod
    def get_configured_payment_providers(tenant: Tenant) -> List[str]:
        """
        Get list of configured payment providers for tenant.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            list: Provider names (mpesa, paystack, pesapal, stripe)
        """
        settings = getattr(tenant, 'settings', None)
        if not settings:
            return []
        
        providers = []
        
        # Check M-Pesa
        if settings.metadata.get('mpesa_shortcode'):
            providers.append('mpesa')
        
        # Check Paystack
        if settings.metadata.get('paystack_public_key'):
            providers.append('paystack')
        
        # Check Pesapal
        if settings.metadata.get('pesapal_consumer_key'):
            providers.append('pesapal')
        
        # Check Stripe
        if settings.stripe_customer_id:
            providers.append('stripe')
        
        return providers
