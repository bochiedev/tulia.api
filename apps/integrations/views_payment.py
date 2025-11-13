"""
Payment webhook views for handling payment provider callbacks.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema
import logging
import json

from apps.integrations.services.payment_service import PaymentService, PaymentProcessingError
from apps.integrations.models import WebhookLog

logger = logging.getLogger(__name__)


class StripeWebhookView(APIView):
    """
    Handle Stripe payment webhooks.
    
    POST /v1/webhooks/stripe
    
    This endpoint is public (no authentication) as it receives webhooks
    from Stripe. Signature verification is performed within the handler.
    """
    authentication_classes = []
    permission_classes = []
    
    @extend_schema(
        summary="Stripe webhook handler",
        description="Receive and process Stripe payment webhooks",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'type': {'type': 'string'},
                    'data': {'type': 'object'}
                }
            }
        },
        responses={
            200: {'description': 'Webhook processed successfully'},
            400: {'description': 'Invalid webhook payload'},
            500: {'description': 'Webhook processing failed'}
        }
    )
    def post(self, request):
        """Process Stripe webhook."""
        # Get Stripe signature header
        signature = request.META.get('HTTP_STRIPE_SIGNATURE', '')
        
        # Get raw payload
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            logger.error("Invalid JSON in Stripe webhook")
            return Response(
                {'error': 'Invalid JSON'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Log webhook
        webhook_log = WebhookLog.objects.create(
            provider='stripe',
            event=payload.get('type', 'unknown'),
            payload=payload,
            status='received'
        )
        
        try:
            # Process webhook
            result = PaymentService.process_payment_webhook(
                provider=PaymentService.PROVIDER_STRIPE,
                payload=payload,
                signature=signature
            )
            
            # Update webhook log
            webhook_log.status = 'success'
            webhook_log.response = result
            webhook_log.save(update_fields=['status', 'response'])
            
            logger.info(
                f"Stripe webhook processed successfully",
                extra={
                    'event_type': payload.get('type'),
                    'webhook_id': str(webhook_log.id)
                }
            )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except PaymentProcessingError as e:
            # Update webhook log
            webhook_log.status = 'error'
            webhook_log.error_message = str(e)
            webhook_log.save(update_fields=['status', 'error_message'])
            
            logger.error(
                f"Stripe webhook processing failed: {str(e)}",
                exc_info=True,
                extra={'webhook_id': str(webhook_log.id)}
            )
            
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        except Exception as e:
            # Update webhook log
            webhook_log.status = 'error'
            webhook_log.error_message = str(e)
            webhook_log.save(update_fields=['status', 'error_message'])
            
            logger.error(
                f"Unexpected error processing Stripe webhook: {str(e)}",
                exc_info=True,
                extra={'webhook_id': str(webhook_log.id)}
            )
            
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PaystackWebhookView(APIView):
    """
    Handle Paystack payment webhooks.
    
    POST /v1/webhooks/paystack
    
    This endpoint is public (no authentication) as it receives webhooks
    from Paystack. Signature verification is performed within the handler.
    
    Supported events:
    - charge.success: Payment completed successfully
    - charge.failed: Payment failed
    - transfer.success: Payout completed
    - transfer.failed: Payout failed
    """
    authentication_classes = []
    permission_classes = []
    
    @extend_schema(
        summary="Paystack webhook handler",
        description="Receive and process Paystack payment webhooks with signature verification",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'event': {'type': 'string'},
                    'data': {'type': 'object'}
                }
            }
        },
        responses={
            200: {'description': 'Webhook processed successfully'},
            400: {'description': 'Invalid webhook payload or signature'},
            500: {'description': 'Webhook processing failed'}
        }
    )
    def post(self, request):
        """Process Paystack webhook."""
        from apps.integrations.services.paystack_service import PaystackService
        
        # Get Paystack signature header
        signature = request.META.get('HTTP_X_PAYSTACK_SIGNATURE', '')
        
        # Get raw payload for signature verification
        raw_payload = request.body
        
        # Parse JSON payload
        try:
            payload = json.loads(raw_payload.decode('utf-8'))
        except json.JSONDecodeError:
            logger.error("Invalid JSON in Paystack webhook")
            return Response(
                {'error': 'Invalid JSON'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        event_type = payload.get('event', 'unknown')
        
        # Log webhook
        webhook_log = WebhookLog.objects.create(
            provider='paystack',
            event=event_type,
            payload=payload,
            status='received'
        )
        
        try:
            # Verify webhook signature
            if not PaystackService.verify_webhook_signature(raw_payload, signature):
                logger.warning(
                    "Invalid Paystack webhook signature",
                    extra={'webhook_id': str(webhook_log.id)}
                )
                webhook_log.status = 'error'
                webhook_log.error_message = 'Invalid signature'
                webhook_log.save(update_fields=['status', 'error_message'])
                
                return Response(
                    {'error': 'Invalid signature'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Process webhook
            result = PaymentService.process_payment_webhook(
                provider=PaymentService.PROVIDER_PAYSTACK,
                payload=payload,
                signature=signature
            )
            
            # Update webhook log
            webhook_log.status = 'success'
            webhook_log.response = result
            webhook_log.save(update_fields=['status', 'response'])
            
            logger.info(
                f"Paystack webhook processed successfully",
                extra={
                    'event_type': event_type,
                    'webhook_id': str(webhook_log.id)
                }
            )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except PaymentProcessingError as e:
            # Update webhook log
            webhook_log.status = 'error'
            webhook_log.error_message = str(e)
            webhook_log.save(update_fields=['status', 'error_message'])
            
            logger.error(
                f"Paystack webhook processing failed: {str(e)}",
                exc_info=True,
                extra={'webhook_id': str(webhook_log.id)}
            )
            
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        except Exception as e:
            # Update webhook log
            webhook_log.status = 'error'
            webhook_log.error_message = str(e)
            webhook_log.save(update_fields=['status', 'error_message'])
            
            logger.error(
                f"Unexpected error processing Paystack webhook: {str(e)}",
                exc_info=True,
                extra={'webhook_id': str(webhook_log.id)}
            )
            
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PesapalWebhookView(APIView):
    """
    Handle Pesapal payment webhooks (IPN).
    
    GET/POST /v1/webhooks/pesapal
    """
    authentication_classes = []
    permission_classes = []
    
    @extend_schema(
        summary="Pesapal IPN handler",
        description="Receive and process Pesapal Instant Payment Notifications",
        responses={
            200: {'description': 'Webhook processed successfully'},
            400: {'description': 'Invalid webhook payload'},
            500: {'description': 'Webhook processing failed'}
        }
    )
    def get(self, request):
        """Process Pesapal IPN (GET method)."""
        return self._process_ipn(request.GET.dict())
    
    def post(self, request):
        """Process Pesapal IPN (POST method)."""
        return self._process_ipn(request.data)
    
    def _process_ipn(self, payload):
        """Common IPN processing logic."""
        # Log webhook
        webhook_log = WebhookLog.objects.create(
            provider='pesapal',
            event='ipn',
            payload=payload,
            status='received'
        )
        
        try:
            # Process webhook
            result = PaymentService.process_payment_webhook(
                provider=PaymentService.PROVIDER_PESAPAL,
                payload=payload,
                signature=None  # Pesapal doesn't use signature verification
            )
            
            # Update webhook log
            webhook_log.status = 'success'
            webhook_log.response = result
            webhook_log.save(update_fields=['status', 'response'])
            
            logger.info(
                f"Pesapal IPN processed successfully",
                extra={'webhook_id': str(webhook_log.id)}
            )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except PaymentProcessingError as e:
            # Update webhook log
            webhook_log.status = 'error'
            webhook_log.error_message = str(e)
            webhook_log.save(update_fields=['status', 'error_message'])
            
            logger.error(
                f"Pesapal IPN processing failed: {str(e)}",
                exc_info=True,
                extra={'webhook_id': str(webhook_log.id)}
            )
            
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        except Exception as e:
            # Update webhook log
            webhook_log.status = 'error'
            webhook_log.error_message = str(e)
            webhook_log.save(update_fields=['status', 'error_message'])
            
            logger.error(
                f"Unexpected error processing Pesapal IPN: {str(e)}",
                exc_info=True,
                extra={'webhook_id': str(webhook_log.id)}
            )
            
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MpesaWebhookView(APIView):
    """
    Handle M-Pesa payment webhooks (STK Push callback).
    
    POST /v1/webhooks/mpesa/callback
    """
    authentication_classes = []
    permission_classes = []
    
    @extend_schema(
        summary="M-Pesa STK Push callback handler",
        description="Receive and process M-Pesa STK Push payment callbacks",
        responses={
            200: {'description': 'Webhook processed successfully'},
            400: {'description': 'Invalid webhook payload'},
            500: {'description': 'Webhook processing failed'}
        }
    )
    def post(self, request):
        """Process M-Pesa STK Push callback."""
        # Get raw payload
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            logger.error("Invalid JSON in M-Pesa webhook")
            return Response(
                {'error': 'Invalid JSON'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Log webhook
        webhook_log = WebhookLog.objects.create(
            provider='mpesa',
            event='stk_callback',
            payload=payload,
            status='received'
        )
        
        try:
            # Process webhook
            result = PaymentService.process_payment_webhook(
                provider=PaymentService.PROVIDER_MPESA,
                payload=payload,
                signature=None  # M-Pesa doesn't use signature verification
            )
            
            # Update webhook log
            webhook_log.status = 'success'
            webhook_log.response = result
            webhook_log.save(update_fields=['status', 'response'])
            
            logger.info(
                f"M-Pesa webhook processed successfully",
                extra={'webhook_id': str(webhook_log.id)}
            )
            
            # M-Pesa expects specific response format
            return Response({
                'ResultCode': 0,
                'ResultDesc': 'Success'
            }, status=status.HTTP_200_OK)
            
        except PaymentProcessingError as e:
            # Update webhook log
            webhook_log.status = 'error'
            webhook_log.error_message = str(e)
            webhook_log.save(update_fields=['status', 'error_message'])
            
            logger.error(
                f"M-Pesa webhook processing failed: {str(e)}",
                exc_info=True,
                extra={'webhook_id': str(webhook_log.id)}
            )
            
            # Still return success to M-Pesa to avoid retries
            return Response({
                'ResultCode': 1,
                'ResultDesc': str(e)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            # Update webhook log
            webhook_log.status = 'error'
            webhook_log.error_message = str(e)
            webhook_log.save(update_fields=['status', 'error_message'])
            
            logger.error(
                f"Unexpected error processing M-Pesa webhook: {str(e)}",
                exc_info=True,
                extra={'webhook_id': str(webhook_log.id)}
            )
            
            # Still return success to M-Pesa to avoid retries
            return Response({
                'ResultCode': 1,
                'ResultDesc': 'Internal error'
            }, status=status.HTTP_200_OK)
