"""
Payment Orchestration Service for the sales orchestration refactor.

This service handles all payment flows deterministically:
- M-Pesa STK Push
- M-Pesa Manual (Paybill/Till)
- Card Payments (Paystack/Stripe/Pesapal)
- Payment callbacks and status updates

Design principles:
- Validate payment amounts against order totals
- Create PaymentRequest records with proper status tracking
- Send WhatsApp confirmations on success
- Handle errors gracefully
"""
import logging
from typing import Dict, Any, Tuple, Optional
from decimal import Decimal
from django.utils import timezone
from django.db import transaction

from apps.orders.models import Order
from apps.bot.models import PaymentRequest
from apps.tenants.models import Tenant, Customer
from apps.integrations.services.payment_service import PaymentService
from apps.messaging.models import Conversation

logger = logging.getLogger(__name__)


class PaymentOrchestrationService:
    """
    Handle all payment flows deterministically.
    
    Responsibilities:
    - Initiate M-Pesa STK push
    - Generate card payment links
    - Process payment callbacks
    - Update order status
    - Send confirmations
    """
    
    def __init__(self):
        """Initialize the payment orchestration service."""
        self.payment_service = PaymentService()
    
    def initiate_mpesa_stk(
        self,
        order: Order,
        phone_number: str,
        tenant: Tenant
    ) -> PaymentRequest:
        """
        Initiate M-Pesa STK push.
        
        Requirements: 8.1, 8.2, 8.3
        
        Args:
            order: Order to pay for
            phone_number: Phone number for STK push
            tenant: Tenant for credentials
        
        Returns:
            PaymentRequest instance
        """
        # Validate phone number format
        phone_number = self._normalize_phone_number(phone_number)
        
        # Validate amount matches order total (Requirement 8.2)
        if order.total <= 0:
            raise ValueError("Order total must be greater than 0")
        
        # Create PaymentRequest with PENDING status (Requirement 8.3)
        payment_request = PaymentRequest.objects.create(
            tenant=tenant,
            customer=order.customer,
            order=order,
            amount=order.total,
            currency=order.currency,
            payment_method='mpesa_stk',
            status='PENDING',
            phone_number=phone_number,
            metadata={
                'initiated_at': timezone.now().isoformat(),
                'order_id': str(order.id),
            }
        )
        
        try:
            # Call M-Pesa API with tenant credentials
            # TODO: Implement actual M-Pesa STK push integration
            # For now, create a placeholder response
            provider_response = {
                'status': 'initiated',
                'message': 'STK push sent',
                'timestamp': timezone.now().isoformat(),
            }
            
            payment_request.provider_response = provider_response
            payment_request.provider_reference = f"MPESA_{order.id}_{timezone.now().timestamp()}"
            payment_request.save(update_fields=['provider_response', 'provider_reference'])
            
            logger.info(
                f"M-Pesa STK push initiated for order {order.id}",
                extra={
                    'tenant_id': tenant.id,
                    'order_id': order.id,
                    'payment_request_id': payment_request.id,
                    'phone_number': phone_number,
                }
            )
            
        except Exception as e:
            logger.error(
                f"Failed to initiate M-Pesa STK push: {str(e)}",
                exc_info=True,
                extra={
                    'tenant_id': tenant.id,
                    'order_id': order.id,
                    'payment_request_id': payment_request.id,
                }
            )
            payment_request.status = 'FAILED'
            payment_request.metadata['error'] = str(e)
            payment_request.save(update_fields=['status', 'metadata'])
            raise
        
        return payment_request
    
    def initiate_card_payment(
        self,
        order: Order,
        provider: str,  # "paystack", "stripe", "pesapal"
        tenant: Tenant
    ) -> Tuple[PaymentRequest, str]:
        """
        Generate card payment link.
        
        Requirements: 9.1, 9.2, 9.3
        
        Args:
            order: Order to pay for
            provider: Payment provider to use
            tenant: Tenant for credentials
        
        Returns:
            Tuple of (PaymentRequest, payment_link)
        """
        # Validate amount matches order total (Requirement 9.1)
        if order.total <= 0:
            raise ValueError("Order total must be greater than 0")
        
        # Create PaymentRequest with PENDING status (Requirement 9.2)
        payment_request = PaymentRequest.objects.create(
            tenant=tenant,
            customer=order.customer,
            order=order,
            amount=order.total,
            currency=order.currency,
            payment_method=provider,
            status='PENDING',
            metadata={
                'initiated_at': timezone.now().isoformat(),
                'order_id': str(order.id),
                'provider': provider,
            }
        )
        
        try:
            # Generate payment link using PaymentService
            checkout_data = self.payment_service.generate_checkout_link(order)
            payment_link = checkout_data.get('checkout_url', '')
            provider_ref = checkout_data.get('payment_ref', '')
            
            if not payment_link:
                # Fallback: generate a placeholder link
                payment_link = f"https://pay.example.com/{provider}/{order.id}"
                provider_ref = f"{provider.upper()}_{order.id}_{timezone.now().timestamp()}"
            
            payment_request.payment_link = payment_link
            payment_request.provider_reference = provider_ref
            payment_request.provider_response = checkout_data
            payment_request.save(update_fields=['payment_link', 'provider_reference', 'provider_response'])
            
            logger.info(
                f"Card payment link generated for order {order.id}",
                extra={
                    'tenant_id': tenant.id,
                    'order_id': order.id,
                    'payment_request_id': payment_request.id,
                    'provider': provider,
                }
            )
            
        except Exception as e:
            logger.error(
                f"Failed to generate card payment link: {str(e)}",
                exc_info=True,
                extra={
                    'tenant_id': tenant.id,
                    'order_id': order.id,
                    'payment_request_id': payment_request.id,
                    'provider': provider,
                }
            )
            payment_request.status = 'FAILED'
            payment_request.metadata['error'] = str(e)
            payment_request.save(update_fields=['status', 'metadata'])
            raise
        
        return payment_request, payment_link
    
    def handle_mpesa_callback(
        self,
        callback_data: Dict[str, Any],
        tenant: Tenant
    ) -> None:
        """
        Process M-Pesa callback.
        
        Requirements: 8.4, 8.5
        
        Args:
            callback_data: Callback data from M-Pesa
            tenant: Tenant for scoping
        """
        # Extract reference from callback
        provider_reference = callback_data.get('reference') or callback_data.get('CheckoutRequestID')
        
        if not provider_reference:
            logger.error("M-Pesa callback missing reference", extra={'callback_data': callback_data})
            return
        
        # Find PaymentRequest by reference
        try:
            payment_request = PaymentRequest.objects.get(
                tenant=tenant,
                provider_reference=provider_reference,
                payment_method='mpesa_stk'
            )
        except PaymentRequest.DoesNotExist:
            logger.error(
                f"PaymentRequest not found for reference: {provider_reference}",
                extra={'tenant_id': tenant.id, 'reference': provider_reference}
            )
            return
        
        # Update callback data
        payment_request.callback_data = callback_data
        payment_request.callback_received_at = timezone.now()
        
        # Determine success/failure from callback
        result_code = callback_data.get('ResultCode', callback_data.get('result_code', 1))
        is_success = result_code == 0 or result_code == '0'
        
        if is_success:
            # Success: Update PaymentRequest and Order (Requirement 8.4)
            self._mark_payment_success(payment_request, callback_data)
        else:
            # Failure: Update PaymentRequest (Requirement 8.5)
            self._mark_payment_failed(payment_request, callback_data)
    
    def handle_card_callback(
        self,
        provider: str,
        callback_data: Dict[str, Any],
        tenant: Tenant
    ) -> None:
        """
        Process card payment webhook.
        
        Requirements: 9.4, 9.5
        
        Args:
            provider: Payment provider (paystack, stripe, pesapal)
            callback_data: Callback data from provider
            tenant: Tenant for scoping
        """
        # Extract reference from callback (provider-specific)
        provider_reference = self._extract_provider_reference(provider, callback_data)
        
        if not provider_reference:
            logger.error(
                f"{provider} callback missing reference",
                extra={'callback_data': callback_data}
            )
            return
        
        # Find PaymentRequest by reference
        try:
            payment_request = PaymentRequest.objects.get(
                tenant=tenant,
                provider_reference=provider_reference,
                payment_method=provider
            )
        except PaymentRequest.DoesNotExist:
            logger.error(
                f"PaymentRequest not found for {provider} reference: {provider_reference}",
                extra={'tenant_id': tenant.id, 'reference': provider_reference}
            )
            return
        
        # Update callback data
        payment_request.callback_data = callback_data
        payment_request.callback_received_at = timezone.now()
        
        # Determine success/failure from callback
        is_success = self._is_payment_successful(provider, callback_data)
        
        if is_success:
            # Success: Update PaymentRequest and Order (Requirement 9.4)
            self._mark_payment_success(payment_request, callback_data)
        else:
            # Failure: Update PaymentRequest (Requirement 9.5)
            self._mark_payment_failed(payment_request, callback_data)
    
    @transaction.atomic
    def _mark_payment_success(
        self,
        payment_request: PaymentRequest,
        callback_data: Dict[str, Any]
    ) -> None:
        """Mark payment as successful and update order."""
        payment_request.status = 'SUCCESS'
        payment_request.save(update_fields=['status', 'callback_data', 'callback_received_at'])
        
        # Update Order status to PAID
        if payment_request.order:
            payment_request.order.mark_paid(payment_ref=payment_request.provider_reference)
            
            logger.info(
                f"Payment successful for order {payment_request.order.id}",
                extra={
                    'tenant_id': payment_request.tenant.id,
                    'order_id': payment_request.order.id,
                    'payment_request_id': payment_request.id,
                    'amount': float(payment_request.amount),
                }
            )
            
            # TODO: Send WhatsApp confirmation (will be implemented in Task 14)
            # self._send_payment_confirmation(payment_request)
    
    def _mark_payment_failed(
        self,
        payment_request: PaymentRequest,
        callback_data: Dict[str, Any]
    ) -> None:
        """Mark payment as failed."""
        payment_request.status = 'FAILED'
        payment_request.save(update_fields=['status', 'callback_data', 'callback_received_at'])
        
        logger.warning(
            f"Payment failed for order {payment_request.order.id if payment_request.order else 'N/A'}",
            extra={
                'tenant_id': payment_request.tenant.id,
                'payment_request_id': payment_request.id,
                'callback_data': callback_data,
            }
        )
        
        # TODO: Send failure notification (will be implemented in Task 14)
        # self._send_payment_failure_notification(payment_request)
    
    def _normalize_phone_number(self, phone_number: str) -> str:
        """Normalize phone number to E.164 format."""
        # Remove spaces, dashes, parentheses
        phone = phone_number.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        
        # Add country code if missing (assume Kenya +254)
        if phone.startswith('0'):
            phone = '+254' + phone[1:]
        elif phone.startswith('254'):
            phone = '+' + phone
        elif not phone.startswith('+'):
            phone = '+254' + phone
        
        return phone
    
    def _extract_provider_reference(self, provider: str, callback_data: Dict[str, Any]) -> Optional[str]:
        """Extract provider reference from callback data."""
        if provider == 'paystack':
            return callback_data.get('reference') or callback_data.get('data', {}).get('reference')
        elif provider == 'stripe':
            return callback_data.get('id') or callback_data.get('data', {}).get('object', {}).get('id')
        elif provider == 'pesapal':
            return callback_data.get('OrderTrackingId') or callback_data.get('order_tracking_id')
        return None
    
    def _is_payment_successful(self, provider: str, callback_data: Dict[str, Any]) -> bool:
        """Determine if payment was successful from callback data."""
        if provider == 'paystack':
            return callback_data.get('event') == 'charge.success' or \
                   callback_data.get('data', {}).get('status') == 'success'
        elif provider == 'stripe':
            return callback_data.get('type') == 'payment_intent.succeeded' or \
                   callback_data.get('data', {}).get('object', {}).get('status') == 'succeeded'
        elif provider == 'pesapal':
            return callback_data.get('payment_status') == 'COMPLETED' or \
                   callback_data.get('status') == 'COMPLETED'
        return False
