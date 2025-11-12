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
    """
    authentication_classes = []
    permission_classes = []
    
    @extend_schema(
        summary="Paystack webhook handler",
        description="Receive and process Paystack payment webhooks",
        responses={
            200: {'description': 'Webhook processed successfully'},
            501: {'description': 'Not implemented'}
        }
    )
    def post(self, request):
        """Process Paystack webhook."""
        # TODO: Implement Paystack webhook processing
        logger.warning("Paystack webhook received but not yet implemented")
        
        WebhookLog.objects.create(
            provider='paystack',
            event='unknown',
            payload=request.data,
            status='not_implemented'
        )
        
        return Response(
            {'message': 'Paystack webhooks not yet implemented'},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )


class PesapalWebhookView(APIView):
    """
    Handle Pesapal payment webhooks.
    
    POST /v1/webhooks/pesapal
    """
    authentication_classes = []
    permission_classes = []
    
    @extend_schema(
        summary="Pesapal webhook handler",
        description="Receive and process Pesapal payment webhooks",
        responses={
            200: {'description': 'Webhook processed successfully'},
            501: {'description': 'Not implemented'}
        }
    )
    def post(self, request):
        """Process Pesapal webhook."""
        # TODO: Implement Pesapal webhook processing
        logger.warning("Pesapal webhook received but not yet implemented")
        
        WebhookLog.objects.create(
            provider='pesapal',
            event='unknown',
            payload=request.data,
            status='not_implemented'
        )
        
        return Response(
            {'message': 'Pesapal webhooks not yet implemented'},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )


class MpesaWebhookView(APIView):
    """
    Handle M-Pesa payment webhooks.
    
    POST /v1/webhooks/mpesa
    """
    authentication_classes = []
    permission_classes = []
    
    @extend_schema(
        summary="M-Pesa webhook handler",
        description="Receive and process M-Pesa payment webhooks",
        responses={
            200: {'description': 'Webhook processed successfully'},
            501: {'description': 'Not implemented'}
        }
    )
    def post(self, request):
        """Process M-Pesa webhook."""
        # TODO: Implement M-Pesa webhook processing
        logger.warning("M-Pesa webhook received but not yet implemented")
        
        WebhookLog.objects.create(
            provider='mpesa',
            event='unknown',
            payload=request.data,
            status='not_implemented'
        )
        
        return Response(
            {'message': 'M-Pesa webhooks not yet implemented'},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )
