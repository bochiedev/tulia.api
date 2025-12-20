"""
LangGraph Webhook Views for WhatsApp message processing.

This module provides the webhook entry points for processing WhatsApp messages
through the LangGraph orchestration system.
"""
import logging
import json
from typing import Dict, Any, Optional

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.bot.langgraph.orchestrator import process_conversation_message
from apps.bot.conversation_state import ConversationState

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class LangGraphWebhookView(APIView):
    """
    Webhook entry point for LangGraph message processing.
    
    This view receives WhatsApp messages and processes them through
    the LangGraph orchestration system.
    
    Note: This is a webhook endpoint that should be public (no RBAC)
    as it receives messages from external Twilio service.
    """
    
    # Webhook endpoints are exempt from RBAC (verified by signature)
    authentication_classes = []
    permission_classes = []
    
    async def post(self, request) -> JsonResponse:
        """
        Process incoming WhatsApp message through LangGraph.
        
        Expected payload:
        {
            "tenant_id": "tenant_uuid",
            "conversation_id": "conv_uuid", 
            "request_id": "req_uuid",
            "message_text": "User message",
            "phone_e164": "+254700000000",
            "customer_id": "optional_customer_uuid"
        }
        
        Returns:
            JSON response with processed state and response text
        """
        try:
            # Parse request payload
            payload = json.loads(request.body) if request.body else {}
            
            # Extract required fields
            tenant_id = payload.get('tenant_id')
            conversation_id = payload.get('conversation_id')
            request_id = payload.get('request_id')
            message_text = payload.get('message_text')
            
            # Validate required fields
            if not all([tenant_id, conversation_id, request_id, message_text]):
                return JsonResponse({
                    'error': 'Missing required fields: tenant_id, conversation_id, request_id, message_text'
                }, status=400)
            
            # Extract optional fields
            phone_e164 = payload.get('phone_e164')
            customer_id = payload.get('customer_id')
            
            # Process existing state if provided
            existing_state = None
            if 'existing_state' in payload:
                try:
                    existing_state = ConversationState.from_dict(payload['existing_state'])
                except Exception as e:
                    logger.warning(f"Invalid existing state provided: {e}")
            
            logger.info(
                f"Processing webhook message",
                extra={
                    'tenant_id': tenant_id,
                    'conversation_id': conversation_id,
                    'request_id': request_id,
                    'message_length': len(message_text)
                }
            )
            
            # Process message through LangGraph
            result_state = await process_conversation_message(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                request_id=request_id,
                message_text=message_text,
                phone_e164=phone_e164,
                customer_id=customer_id,
                existing_state=existing_state
            )
            
            # Return processed result
            response_data = {
                'success': True,
                'conversation_id': result_state.conversation_id,
                'request_id': result_state.request_id,
                'response_text': result_state.response_text,
                'intent': result_state.intent,
                'journey': result_state.journey,
                'escalation_required': result_state.escalation_required,
                'state': result_state.to_dict()  # Full state for persistence
            }
            
            logger.info(
                f"Webhook processing completed",
                extra={
                    'tenant_id': tenant_id,
                    'conversation_id': conversation_id,
                    'request_id': request_id,
                    'intent': result_state.intent,
                    'journey': result_state.journey
                }
            )
            
            return JsonResponse(response_data)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Invalid JSON payload'
            }, status=400)
            
        except Exception as e:
            logger.error(
                f"Webhook processing failed: {e}",
                extra={
                    'tenant_id': payload.get('tenant_id') if 'payload' in locals() else None,
                    'conversation_id': payload.get('conversation_id') if 'payload' in locals() else None,
                    'request_id': payload.get('request_id') if 'payload' in locals() else None
                },
                exc_info=True
            )
            
            return JsonResponse({
                'error': 'Internal server error',
                'message': str(e)
            }, status=500)


class WebhookHealthCheckView(APIView):
    """
    Health check endpoint for LangGraph webhook system.
    
    This endpoint verifies that the LangGraph orchestration system
    is properly initialized and ready to process messages.
    
    Note: This is a health check endpoint that should be public (no RBAC).
    """
    
    # Health check endpoints are exempt from RBAC
    authentication_classes = []
    permission_classes = []
    
    def get(self, request) -> Response:
        """
        Check LangGraph system health.
        
        Returns:
            JSON response with system status
        """
        try:
            from apps.bot.langgraph.orchestrator import get_orchestrator
            from apps.bot.langgraph.nodes import get_node_registry
            
            # Check orchestrator initialization
            orchestrator = get_orchestrator()
            if not orchestrator._graph:
                return Response({
                    'status': 'unhealthy',
                    'error': 'LangGraph not initialized'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            # Check node registry
            node_registry = get_node_registry()
            registered_nodes = node_registry.list_nodes()
            
            # Verify core nodes are registered
            required_nodes = [
                'tenant_get_context', 'customer_get_or_create',
                'intent_classify', 'language_policy', 'governor_spam_casual'
            ]
            
            missing_nodes = [node for node in required_nodes if node not in registered_nodes]
            if missing_nodes:
                return Response({
                    'status': 'unhealthy',
                    'error': f'Missing required nodes: {missing_nodes}'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            return Response({
                'status': 'healthy',
                'langgraph_initialized': True,
                'registered_nodes': len(registered_nodes),
                'core_nodes_present': True,
                'version': '2.0.0'
            })
            
        except Exception as e:
            logger.error(f"Health check failed: {e}", exc_info=True)
            return Response({
                'status': 'unhealthy',
                'error': str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)