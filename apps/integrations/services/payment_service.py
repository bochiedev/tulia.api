"""
Payment service for handling payment gateway integrations.

Supports multiple payment providers:
- Stripe (credit/debit cards, international)
- Pesapal (East Africa)
- M-Pesa (Kenya mobile money)
- Paystack (Africa)

Handles:
- Checkout link generation
- Payment webhook processing
- Wallet crediting on successful payment
- Transaction fee calculation
"""
from decimal import Decimal
from typing import Dict, Optional, Tuple
import logging
import hashlib
import hmac
import json
from django.conf import settings
from django.utils import timezone

from apps.core.exceptions import TuliaException
from apps.core.logging import SecurityLogger
from apps.tenants.models import Tenant, Transaction
from apps.tenants.services.wallet_service import WalletService
from apps.orders.models import Order

logger = logging.getLogger(__name__)


class PaymentProviderNotConfigured(TuliaException):
    """Raised when payment provider is not configured for tenant."""
    pass


class PaymentProcessingError(TuliaException):
    """Raised when payment processing fails."""
    pass


class PaymentService:
    """Service for payment gateway integration and processing."""
    
    # Supported payment providers
    PROVIDER_STRIPE = 'stripe'
    PROVIDER_PESAPAL = 'pesapal'
    PROVIDER_MPESA = 'mpesa'
    PROVIDER_PAYSTACK = 'paystack'
    
    @staticmethod
    def get_configured_provider(tenant: Tenant) -> Optional[str]:
        """
        Get the configured payment provider for a tenant.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            str: Provider name or None if none configured
        """
        # Check if payment facilitation is enabled for tenant's tier
        if not tenant.subscription_tier or not tenant.subscription_tier.payment_facilitation:
            return None
        
        # Check tenant settings for configured providers
        settings_obj = getattr(tenant, 'settings', None)
        if not settings_obj:
            return None
        
        # Priority order: Stripe > Paystack > Pesapal > M-Pesa
        if settings_obj.stripe_customer_id:
            return PaymentService.PROVIDER_STRIPE
        
        # Check for other providers in metadata
        payment_config = settings_obj.metadata.get('payment_provider', {})
        if payment_config.get('paystack_public_key'):
            return PaymentService.PROVIDER_PAYSTACK
        if payment_config.get('pesapal_consumer_key'):
            return PaymentService.PROVIDER_PESAPAL
        if payment_config.get('mpesa_shortcode'):
            return PaymentService.PROVIDER_MPESA
        
        return None
    
    @staticmethod
    def generate_checkout_link(order: Order) -> Dict:
        """
        Generate payment checkout link for an order.
        
        Args:
            order: Order instance
            
        Returns:
            dict: {
                'checkout_url': str,
                'provider': str,
                'payment_ref': str,
                'expires_at': datetime (optional)
            }
            
        Raises:
            PaymentProviderNotConfigured: If no provider is configured
            PaymentProcessingError: If checkout link generation fails
        """
        tenant = order.tenant
        provider = PaymentService.get_configured_provider(tenant)
        
        if not provider:
            raise PaymentProviderNotConfigured(
                "No payment provider configured for this tenant",
                details={
                    'tenant_id': str(tenant.id),
                    'payment_facilitation_enabled': tenant.subscription_tier.payment_facilitation if tenant.subscription_tier else False
                }
            )
        
        # Route to appropriate provider
        if provider == PaymentService.PROVIDER_STRIPE:
            return PaymentService._generate_stripe_checkout(order)
        elif provider == PaymentService.PROVIDER_PAYSTACK:
            return PaymentService._generate_paystack_checkout(order)
        elif provider == PaymentService.PROVIDER_PESAPAL:
            return PaymentService._generate_pesapal_checkout(order)
        elif provider == PaymentService.PROVIDER_MPESA:
            return PaymentService._generate_mpesa_checkout(order)
        else:
            raise PaymentProcessingError(
                f"Unsupported payment provider: {provider}",
                details={'provider': provider}
            )
    
    @staticmethod
    def _generate_stripe_checkout(order: Order) -> Dict:
        """
        Generate Stripe checkout session.
        
        Args:
            order: Order instance
            
        Returns:
            dict: Checkout details
        """
        try:
            import stripe
            
            # Get Stripe API key from settings
            stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', None)
            
            if not stripe.api_key:
                # Fallback to stub for development
                logger.warning(f"Stripe not configured, generating stub checkout link for order {order.id}")
                return PaymentService._generate_stub_checkout(order, PaymentService.PROVIDER_STRIPE)
            
            # Create Stripe checkout session
            session = stripe.checkout.Session.create(
                customer=order.tenant.settings.stripe_customer_id if hasattr(order.tenant, 'settings') else None,
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': order.currency.lower(),
                        'product_data': {
                            'name': f'Order {order.id}',
                            'description': f'{order.item_count} items',
                        },
                        'unit_amount': int(order.total * 100),  # Convert to cents
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=f"{settings.FRONTEND_URL}/orders/{order.id}/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{settings.FRONTEND_URL}/orders/{order.id}/cancel",
                metadata={
                    'order_id': str(order.id),
                    'tenant_id': str(order.tenant_id),
                    'customer_id': str(order.customer_id),
                },
            )
            
            # Update order with payment reference
            order.payment_ref = session.id
            order.save(update_fields=['payment_ref'])
            
            logger.info(
                f"Stripe checkout session created",
                extra={
                    'order_id': str(order.id),
                    'session_id': session.id,
                    'amount': float(order.total)
                }
            )
            
            return {
                'checkout_url': session.url,
                'provider': PaymentService.PROVIDER_STRIPE,
                'payment_ref': session.id,
                'expires_at': None  # Stripe sessions expire after 24 hours by default
            }
            
        except Exception as e:
            logger.error(
                f"Failed to create Stripe checkout session: {str(e)}",
                exc_info=True,
                extra={'order_id': str(order.id)}
            )
            # Fallback to stub in case of error
            return PaymentService._generate_stub_checkout(order, PaymentService.PROVIDER_STRIPE)
    
    @staticmethod
    def _generate_paystack_checkout(order: Order) -> Dict:
        """
        Generate Paystack payment link.
        
        Args:
            order: Order instance
            
        Returns:
            dict: Checkout details
        """
        try:
            from apps.integrations.services.paystack_service import PaystackService, PaystackError
            
            # Get customer email (required by Paystack)
            customer_email = order.customer.metadata.get('email') or order.tenant.contact_email
            
            if not customer_email:
                logger.warning(f"No email for Paystack checkout, using placeholder for order {order.id}")
                customer_email = f"customer_{order.customer_id}@{order.tenant.slug}.placeholder.com"
            
            # Generate unique reference
            reference = f"order_{order.id}_{timezone.now().strftime('%Y%m%d%H%M%S')}"
            
            # Initialize transaction
            result = PaystackService.initialize_transaction(
                email=customer_email,
                amount=order.total,
                currency=order.currency,
                reference=reference,
                callback_url=f"{settings.FRONTEND_URL}/orders/{order.id}/success",
                metadata={
                    'order_id': str(order.id),
                    'tenant_id': str(order.tenant_id),
                    'customer_id': str(order.customer_id),
                }
            )
            
            # Update order with payment reference
            order.payment_ref = result['reference']
            order.save(update_fields=['payment_ref'])
            
            logger.info(
                f"Paystack checkout created",
                extra={
                    'order_id': str(order.id),
                    'reference': result['reference'],
                    'amount': float(order.total)
                }
            )
            
            return {
                'checkout_url': result['authorization_url'],
                'provider': PaymentService.PROVIDER_PAYSTACK,
                'payment_ref': result['reference'],
                'expires_at': None
            }
            
        except PaystackError as e:
            logger.error(
                f"Paystack checkout failed: {str(e)}",
                exc_info=True,
                extra={'order_id': str(order.id)}
            )
            # Fallback to stub
            return PaymentService._generate_stub_checkout(order, PaymentService.PROVIDER_PAYSTACK)
        except Exception as e:
            logger.error(
                f"Unexpected error in Paystack checkout: {str(e)}",
                exc_info=True,
                extra={'order_id': str(order.id)}
            )
            return PaymentService._generate_stub_checkout(order, PaymentService.PROVIDER_PAYSTACK)
    
    @staticmethod
    def _generate_pesapal_checkout(order: Order) -> Dict:
        """
        Generate Pesapal payment link.
        
        Args:
            order: Order instance
            
        Returns:
            dict: Checkout details
        """
        try:
            from apps.integrations.services.pesapal_service import PesapalService, PesapalError
            
            # Get customer details
            customer_email = order.customer.metadata.get('email') or order.tenant.contact_email
            customer_phone = str(order.customer.phone_e164) if hasattr(order.customer, 'phone_e164') else None
            
            # Generate unique reference
            merchant_reference = f"order_{order.id}"
            
            # Prepare billing address
            billing_address = {
                'country_code': 'KE',
                'first_name': order.customer.name or 'Customer',
                'last_name': '',
                'email_address': customer_email,
                'phone_number': customer_phone
            }
            
            # Submit order
            result = PesapalService.submit_order(
                merchant_reference=merchant_reference,
                amount=order.total,
                currency=order.currency,
                description=f'Order {order.id} - {order.item_count} items',
                callback_url=f"{settings.FRONTEND_URL}/orders/{order.id}/success",
                notification_id=settings.PESAPAL_IPN_ID,
                billing_address=billing_address,
                customer_email=customer_email,
                customer_phone=customer_phone
            )
            
            # Update order with payment reference
            order.payment_ref = result['order_tracking_id']
            order.save(update_fields=['payment_ref'])
            
            logger.info(
                f"Pesapal checkout created",
                extra={
                    'order_id': str(order.id),
                    'order_tracking_id': result['order_tracking_id'],
                    'amount': float(order.total)
                }
            )
            
            return {
                'checkout_url': result['redirect_url'],
                'provider': PaymentService.PROVIDER_PESAPAL,
                'payment_ref': result['order_tracking_id'],
                'expires_at': None
            }
            
        except PesapalError as e:
            logger.error(
                f"Pesapal checkout failed: {str(e)}",
                exc_info=True,
                extra={'order_id': str(order.id)}
            )
            return PaymentService._generate_stub_checkout(order, PaymentService.PROVIDER_PESAPAL)
        except Exception as e:
            logger.error(
                f"Unexpected error in Pesapal checkout: {str(e)}",
                exc_info=True,
                extra={'order_id': str(order.id)}
            )
            return PaymentService._generate_stub_checkout(order, PaymentService.PROVIDER_PESAPAL)
    
    @staticmethod
    def _generate_mpesa_checkout(order: Order) -> Dict:
        """
        Generate M-Pesa STK push request.
        
        Args:
            order: Order instance
            
        Returns:
            dict: Checkout details (STK push initiated)
        """
        try:
            from apps.integrations.services.mpesa_service import MpesaService, MpesaError
            
            # Get customer phone number
            customer_phone = str(order.customer.phone_e164) if hasattr(order.customer, 'phone_e164') else None
            
            if not customer_phone:
                raise MpesaError("Customer phone number required for M-Pesa payment")
            
            # Initiate STK push
            result = MpesaService.stk_push(
                phone_number=customer_phone,
                amount=order.total,
                account_reference=f"ORD{order.id}",
                transaction_desc=f"Order {order.id}",
                callback_url=f"{settings.FRONTEND_URL}/api/v1/webhooks/mpesa/callback"
            )
            
            # Update order with payment reference
            order.payment_ref = result['checkout_request_id']
            order.metadata['mpesa_merchant_request_id'] = result['merchant_request_id']
            order.save(update_fields=['payment_ref', 'metadata'])
            
            logger.info(
                f"M-Pesa STK push initiated",
                extra={
                    'order_id': str(order.id),
                    'checkout_request_id': result['checkout_request_id'],
                    'amount': float(order.total)
                }
            )
            
            # M-Pesa doesn't have a checkout URL - payment happens on phone
            return {
                'checkout_url': None,  # No URL - customer completes on phone
                'provider': PaymentService.PROVIDER_MPESA,
                'payment_ref': result['checkout_request_id'],
                'expires_at': None,
                'customer_message': result['customer_message'],
                'stk_push_initiated': True
            }
            
        except MpesaError as e:
            logger.error(
                f"M-Pesa STK push failed: {str(e)}",
                exc_info=True,
                extra={'order_id': str(order.id)}
            )
            return PaymentService._generate_stub_checkout(order, PaymentService.PROVIDER_MPESA)
        except Exception as e:
            logger.error(
                f"Unexpected error in M-Pesa STK push: {str(e)}",
                exc_info=True,
                extra={'order_id': str(order.id)}
            )
            return PaymentService._generate_stub_checkout(order, PaymentService.PROVIDER_MPESA)
    
    @staticmethod
    def _generate_stub_checkout(order: Order, provider: str) -> Dict:
        """
        Generate stub checkout link for development/testing.
        
        Args:
            order: Order instance
            provider: Provider name
            
        Returns:
            dict: Stub checkout details
        """
        payment_ref = f"stub_{provider}_{order.id}"
        order.payment_ref = payment_ref
        order.save(update_fields=['payment_ref'])
        
        return {
            'checkout_url': f"https://checkout.example.com/{provider}/order/{order.id}",
            'provider': provider,
            'payment_ref': payment_ref,
            'expires_at': None
        }
    
    @staticmethod
    def process_payment_webhook(provider: str, payload: Dict, signature: str = None) -> Dict:
        """
        Process payment webhook from provider.
        
        Args:
            provider: Payment provider name
            payload: Webhook payload
            signature: Webhook signature for verification
            
        Returns:
            dict: {
                'success': bool,
                'order_id': str,
                'transaction_id': str,
                'message': str
            }
            
        Raises:
            PaymentProcessingError: If webhook processing fails
        """
        if provider == PaymentService.PROVIDER_STRIPE:
            return PaymentService._process_stripe_webhook(payload, signature)
        elif provider == PaymentService.PROVIDER_PAYSTACK:
            return PaymentService._process_paystack_webhook(payload, signature)
        elif provider == PaymentService.PROVIDER_PESAPAL:
            return PaymentService._process_pesapal_webhook(payload, signature)
        elif provider == PaymentService.PROVIDER_MPESA:
            return PaymentService._process_mpesa_webhook(payload, signature)
        else:
            raise PaymentProcessingError(
                f"Unsupported payment provider: {provider}",
                details={'provider': provider}
            )
    
    @staticmethod
    def _process_stripe_webhook(payload: Dict, signature: str) -> Dict:
        """
        Process Stripe webhook event.
        
        Args:
            payload: Webhook payload
            signature: Stripe signature header
            
        Returns:
            dict: Processing result
        """
        try:
            import stripe
            
            # Get webhook secret from settings
            webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)
            
            if webhook_secret and signature:
                # Verify webhook signature
                try:
                    event = stripe.Webhook.construct_event(
                        json.dumps(payload), signature, webhook_secret
                    )
                except stripe.error.SignatureVerificationError:
                    # Log as critical security event
                    SecurityLogger.log_invalid_webhook_signature(
                        provider='stripe',
                        tenant_id=None,  # Tenant not resolved yet for Stripe webhooks
                        ip_address=None,  # Not available in service layer
                        url=None,  # Not available in service layer
                        user_agent=None
                    )
                    raise PaymentProcessingError(
                        "Invalid Stripe webhook signature",
                        details={'signature_valid': False}
                    )
            else:
                # Development mode - accept without verification
                event = payload
            
            # Handle checkout.session.completed event
            if event.get('type') == 'checkout.session.completed':
                session = event['data']['object']
                order_id = session['metadata'].get('order_id')
                
                if not order_id:
                    raise PaymentProcessingError(
                        "Order ID not found in webhook metadata",
                        details={'session_id': session.get('id')}
                    )
                
                # Get order
                order = Order.objects.get(id=order_id)
                
                # Process successful payment
                result = PaymentService.process_successful_payment(
                    order=order,
                    payment_amount=Decimal(str(session['amount_total'] / 100)),  # Convert from cents
                    payment_ref=session['id'],
                    provider=PaymentService.PROVIDER_STRIPE,
                    payment_metadata={
                        'payment_intent': session.get('payment_intent'),
                        'customer_email': session.get('customer_email'),
                    }
                )
                
                return {
                    'success': True,
                    'order_id': str(order_id),
                    'transaction_id': str(result['payment_transaction'].id),
                    'message': 'Payment processed successfully'
                }
            
            # Handle payment_intent.payment_failed event
            elif event.get('type') == 'payment_intent.payment_failed':
                payment_intent = event['data']['object']
                # Extract order_id from metadata if available
                order_id = payment_intent.get('metadata', {}).get('order_id')
                
                if order_id:
                    order = Order.objects.get(id=order_id)
                    PaymentService.process_failed_payment(
                        order=order,
                        reason=payment_intent.get('last_payment_error', {}).get('message', 'Payment failed'),
                        provider=PaymentService.PROVIDER_STRIPE
                    )
                
                return {
                    'success': False,
                    'order_id': str(order_id) if order_id else None,
                    'message': 'Payment failed'
                }
            
            # Other events - log and ignore
            logger.info(f"Received Stripe webhook event: {event.get('type')}")
            return {
                'success': True,
                'message': f"Event {event.get('type')} received"
            }
            
        except Order.DoesNotExist:
            raise PaymentProcessingError(
                "Order not found",
                details={'order_id': order_id}
            )
        except Exception as e:
            logger.error(
                f"Failed to process Stripe webhook: {str(e)}",
                exc_info=True
            )
            raise PaymentProcessingError(
                f"Webhook processing failed: {str(e)}",
                details={'error': str(e)}
            )
    
    @staticmethod
    def _process_paystack_webhook(payload: Dict, signature: str) -> Dict:
        """
        Process Paystack webhook event.
        
        Handles:
        - charge.success: Payment completed successfully
        - charge.failed: Payment failed
        - transfer.success: Payout completed
        - transfer.failed: Payout failed
        
        Args:
            payload: Webhook payload
            signature: Paystack signature header
            
        Returns:
            dict: Processing result
        """
        try:
            from apps.integrations.services.paystack_service import PaystackService
            
            # Verify signature
            if signature and not PaystackService.verify_webhook_signature(
                json.dumps(payload).encode('utf-8'), signature
            ):
                raise PaymentProcessingError(
                    "Invalid Paystack webhook signature",
                    details={'signature_valid': False}
                )
            
            event_type = payload.get('event')
            data = payload.get('data', {})
            
            # Handle charge.success event (customer payment)
            if event_type == 'charge.success':
                reference = data.get('reference')
                
                # Verify transaction status with Paystack API for extra security
                transaction = PaystackService.verify_transaction(reference)
                
                if transaction.get('status') != 'success':
                    logger.warning(
                        f"Paystack transaction not successful: {transaction.get('status')}",
                        extra={'reference': reference}
                    )
                    return {
                        'success': False,
                        'message': f"Transaction status: {transaction.get('status')}"
                    }
                
                # Extract order_id from metadata
                metadata = transaction.get('metadata', {})
                order_id = metadata.get('order_id')
                
                if not order_id:
                    raise PaymentProcessingError(
                        "Order ID not found in webhook metadata",
                        details={'reference': reference}
                    )
                
                # Get order
                order = Order.objects.get(id=order_id)
                
                # Process successful payment
                amount = Decimal(str(transaction['amount'])) / 100  # Convert from kobo
                result = PaymentService.process_successful_payment(
                    order=order,
                    payment_amount=amount,
                    payment_ref=reference,
                    provider=PaymentService.PROVIDER_PAYSTACK,
                    payment_metadata={
                        'transaction_id': transaction.get('id'),
                        'customer_email': transaction.get('customer', {}).get('email'),
                        'channel': transaction.get('channel'),
                        'paid_at': transaction.get('paid_at'),
                        'ip_address': transaction.get('ip_address'),
                    }
                )
                
                return {
                    'success': True,
                    'order_id': str(order_id),
                    'transaction_id': str(result['payment_transaction'].id) if result['payment_transaction'] else None,
                    'message': 'Payment processed successfully'
                }
            
            # Handle charge.failed event
            elif event_type in ['charge.failed', 'charge.declined']:
                reference = data.get('reference')
                metadata = data.get('metadata', {})
                order_id = metadata.get('order_id')
                
                if order_id:
                    order = Order.objects.get(id=order_id)
                    PaymentService.process_failed_payment(
                        order=order,
                        reason=data.get('gateway_response', 'Payment failed'),
                        provider=PaymentService.PROVIDER_PAYSTACK
                    )
                
                return {
                    'success': False,
                    'order_id': str(order_id) if order_id else None,
                    'message': 'Payment failed'
                }
            
            # Handle transfer events (for payouts)
            elif event_type == 'transfer.success':
                reference = data.get('reference')
                logger.info(
                    f"Paystack transfer successful",
                    extra={
                        'reference': reference,
                        'amount': data.get('amount'),
                        'recipient': data.get('recipient', {}).get('name')
                    }
                )
                return {
                    'success': True,
                    'reference': reference,
                    'message': 'Transfer completed'
                }
            
            elif event_type == 'transfer.failed':
                reference = data.get('reference')
                logger.warning(
                    f"Paystack transfer failed",
                    extra={
                        'reference': reference,
                        'reason': data.get('reason')
                    }
                )
                return {
                    'success': False,
                    'reference': reference,
                    'message': 'Transfer failed'
                }
            
            # Other events - log and acknowledge
            else:
                logger.info(f"Received Paystack webhook event: {event_type}")
                return {
                    'success': True,
                    'message': f"Event {event_type} received"
                }
            
        except Order.DoesNotExist:
            raise PaymentProcessingError(
                "Order not found",
                details={'order_id': order_id if 'order_id' in locals() else 'unknown'}
            )
        except Exception as e:
            logger.error(
                f"Failed to process Paystack webhook: {str(e)}",
                exc_info=True,
                extra={'event_type': payload.get('event', 'unknown')}
            )
            raise PaymentProcessingError(
                f"Webhook processing failed: {str(e)}",
                details={'error': str(e)}
            )
    
    @staticmethod
    def _process_pesapal_webhook(payload: Dict, signature: str) -> Dict:
        """Process Pesapal webhook event (IPN)."""
        try:
            from apps.integrations.services.pesapal_service import PesapalService
            
            # Pesapal IPN sends OrderTrackingId and OrderMerchantReference
            order_tracking_id = payload.get('OrderTrackingId')
            merchant_reference = payload.get('OrderMerchantReference')
            
            if not order_tracking_id:
                raise PaymentProcessingError(
                    "OrderTrackingId not found in Pesapal IPN",
                    details=payload
                )
            
            # Get transaction status from Pesapal
            transaction = PesapalService.get_transaction_status(order_tracking_id)
            
            payment_status = transaction.get('payment_status_description', '').lower()
            
            # Extract order_id from merchant_reference (format: order_{uuid})
            if merchant_reference and merchant_reference.startswith('order_'):
                order_id = merchant_reference.replace('order_', '')
            else:
                # Fallback: find by payment_ref
                order = Order.objects.filter(payment_ref=order_tracking_id).first()
                if not order:
                    raise PaymentProcessingError(
                        "Order not found",
                        details={'order_tracking_id': order_tracking_id}
                    )
                order_id = order.id
            
            # Get order
            order = Order.objects.get(id=order_id)
            
            # Check payment status
            if payment_status == 'completed':
                # Payment successful
                amount = Decimal(str(transaction.get('amount')))
                confirmation_code = transaction.get('confirmation_code')
                
                result = PaymentService.process_successful_payment(
                    order=order,
                    payment_amount=amount,
                    payment_ref=confirmation_code,
                    provider=PaymentService.PROVIDER_PESAPAL,
                    payment_metadata={
                        'order_tracking_id': order_tracking_id,
                        'payment_method': transaction.get('payment_method'),
                        'currency': transaction.get('currency'),
                    }
                )
                
                return {
                    'success': True,
                    'order_id': str(order_id),
                    'transaction_id': str(result['payment_transaction'].id) if result['payment_transaction'] else None,
                    'message': 'Payment processed successfully'
                }
            elif payment_status in ['failed', 'cancelled']:
                # Payment failed
                PaymentService.process_failed_payment(
                    order=order,
                    reason=f"Payment {payment_status}",
                    provider=PaymentService.PROVIDER_PESAPAL
                )
                
                return {
                    'success': False,
                    'order_id': str(order_id),
                    'message': f"Payment {payment_status}"
                }
            else:
                # Payment pending or other status
                logger.info(
                    f"Pesapal payment status: {payment_status}",
                    extra={'order_tracking_id': order_tracking_id}
                )
                return {
                    'success': True,
                    'message': f"Payment status: {payment_status}"
                }
            
        except Order.DoesNotExist:
            raise PaymentProcessingError(
                "Order not found",
                details={'order_id': order_id}
            )
        except Exception as e:
            logger.error(
                f"Failed to process Pesapal webhook: {str(e)}",
                exc_info=True
            )
            raise PaymentProcessingError(
                f"Webhook processing failed: {str(e)}",
                details={'error': str(e)}
            )
    
    @staticmethod
    def _process_mpesa_webhook(payload: Dict, signature: str) -> Dict:
        """Process M-Pesa webhook event (STK Push callback)."""
        try:
            # M-Pesa STK Push callback structure
            body = payload.get('Body', {})
            stk_callback = body.get('stkCallback', {})
            
            result_code = stk_callback.get('ResultCode')
            checkout_request_id = stk_callback.get('CheckoutRequestID')
            
            if not checkout_request_id:
                raise PaymentProcessingError(
                    "CheckoutRequestID not found in M-Pesa callback",
                    details=payload
                )
            
            # Find order by payment_ref
            order = Order.objects.filter(payment_ref=checkout_request_id).first()
            
            if not order:
                logger.warning(
                    f"Order not found for M-Pesa CheckoutRequestID: {checkout_request_id}"
                )
                return {
                    'success': False,
                    'message': 'Order not found'
                }
            
            # Check result code
            if result_code == 0:
                # Payment successful
                callback_metadata = stk_callback.get('CallbackMetadata', {})
                items = callback_metadata.get('Item', [])
                
                # Extract payment details
                amount = None
                mpesa_receipt = None
                phone_number = None
                
                for item in items:
                    name = item.get('Name')
                    if name == 'Amount':
                        amount = Decimal(str(item.get('Value')))
                    elif name == 'MpesaReceiptNumber':
                        mpesa_receipt = item.get('Value')
                    elif name == 'PhoneNumber':
                        phone_number = item.get('Value')
                
                # Process successful payment
                result = PaymentService.process_successful_payment(
                    order=order,
                    payment_amount=amount,
                    payment_ref=mpesa_receipt,
                    provider=PaymentService.PROVIDER_MPESA,
                    payment_metadata={
                        'checkout_request_id': checkout_request_id,
                        'phone_number': phone_number,
                    }
                )
                
                return {
                    'success': True,
                    'order_id': str(order.id),
                    'transaction_id': str(result['payment_transaction'].id) if result['payment_transaction'] else None,
                    'message': 'Payment processed successfully'
                }
            else:
                # Payment failed
                result_desc = stk_callback.get('ResultDesc', 'Payment failed')
                
                PaymentService.process_failed_payment(
                    order=order,
                    reason=result_desc,
                    provider=PaymentService.PROVIDER_MPESA
                )
                
                return {
                    'success': False,
                    'order_id': str(order.id),
                    'message': result_desc
                }
            
        except Order.DoesNotExist:
            raise PaymentProcessingError(
                "Order not found",
                details={'checkout_request_id': checkout_request_id}
            )
        except Exception as e:
            logger.error(
                f"Failed to process M-Pesa webhook: {str(e)}",
                exc_info=True
            )
            raise PaymentProcessingError(
                f"Webhook processing failed: {str(e)}",
                details={'error': str(e)}
            )
    
    @staticmethod
    def process_successful_payment(order: Order, payment_amount: Decimal, 
                                   payment_ref: str, provider: str,
                                   payment_metadata: Dict = None) -> Dict:
        """
        Process successful payment: update order, credit wallet, calculate fees.
        
        Args:
            order: Order instance
            payment_amount: Amount paid by customer
            payment_ref: Payment reference from provider
            provider: Payment provider name
            payment_metadata: Additional payment metadata
            
        Returns:
            dict: Result from WalletService.process_customer_payment
        """
        tenant = order.tenant
        
        # Check if payment facilitation is enabled
        if not tenant.subscription_tier or not tenant.subscription_tier.payment_facilitation:
            logger.warning(
                f"Payment facilitation not enabled for tenant {tenant.id}, skipping wallet credit"
            )
            # Just mark order as paid without wallet processing
            order.mark_paid(payment_ref=payment_ref)
            return {
                'payment_transaction': None,
                'fee_transaction': None,
                'wallet_audit': None,
                'gross_amount': payment_amount,
                'fee_amount': Decimal('0'),
                'net_amount': payment_amount
            }
        
        # Process payment through wallet service
        result = WalletService.process_customer_payment(
            tenant=tenant,
            payment_amount=payment_amount,
            reference_type='order',
            reference_id=order.id,
            metadata={
                'provider': provider,
                'payment_ref': payment_ref,
                **(payment_metadata or {})
            }
        )
        
        # Mark order as paid
        order.mark_paid(payment_ref=payment_ref)
        
        logger.info(
            f"Payment processed successfully",
            extra={
                'order_id': str(order.id),
                'tenant_id': str(tenant.id),
                'amount': float(payment_amount),
                'fee': float(result['fee_amount']),
                'net': float(result['net_amount']),
                'provider': provider
            }
        )
        
        return result
    
    @staticmethod
    def process_failed_payment(order: Order, reason: str, provider: str,
                              retry_url: str = None) -> Dict:
        """
        Process failed payment: log failure, optionally notify customer.
        
        Args:
            order: Order instance
            reason: Failure reason
            provider: Payment provider name
            retry_url: Optional URL for customer to retry payment
            
        Returns:
            dict: Processing result
        """
        logger.warning(
            f"Payment failed for order {order.id}",
            extra={
                'order_id': str(order.id),
                'tenant_id': str(order.tenant_id),
                'reason': reason,
                'provider': provider
            }
        )
        
        # Update order metadata
        order.metadata['payment_failure'] = {
            'reason': reason,
            'provider': provider,
            'failed_at': timezone.now().isoformat(),
            'retry_url': retry_url
        }
        order.save(update_fields=['metadata'])
        
        # TODO: Trigger automated message to customer
        # This would be handled by messaging service
        
        return {
            'success': False,
            'order_id': str(order.id),
            'reason': reason
        }
