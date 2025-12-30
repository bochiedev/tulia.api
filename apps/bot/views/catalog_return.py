"""
Catalog return webhook handler for deep-linking from web catalog.

Handles when customers return from the web catalog with a selected product
and need to resume their WhatsApp conversation.
"""
import logging
from typing import Dict, Any
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.http import HttpResponse
from apps.bot.conversation_state import ConversationState, ConversationStateManager
from apps.bot.models import ConversationSession
from apps.bot.langgraph.sales_journey import SalesJourneySubgraph
from apps.tenants.models import Tenant

logger = logging.getLogger(__name__)


class CatalogReturnWebhookView(APIView):
    """
    Webhook endpoint for handling catalog returns with product selection.
    
    This endpoint is called when a customer selects a product from the web catalog
    and needs to return to their WhatsApp conversation with the selection.
    """
    
    permission_classes = [AllowAny]  # Public webhook endpoint
    
    async def post(self, request):
        """
        Handle catalog return webhook.
        
        Expected payload:
        {
            "tenant_id": "uuid",
            "conversation_id": "uuid", 
            "selected_product_id": "uuid",
            "return_message": "optional message from catalog"
        }
        """
        try:
            # Extract payload
            tenant_id = request.data.get('tenant_id')
            conversation_id = request.data.get('conversation_id')
            selected_product_id = request.data.get('selected_product_id')
            return_message = request.data.get('return_message')
            
            # Validate required fields
            if not all([tenant_id, conversation_id, selected_product_id]):
                return Response(
                    {"error": "Missing required fields: tenant_id, conversation_id, selected_product_id"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate tenant exists
            try:
                tenant = await Tenant.objects.aget(id=tenant_id)
            except Tenant.DoesNotExist:
                return Response(
                    {"error": "Invalid tenant_id"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get conversation session
            try:
                session = await ConversationSession.objects.aget(
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    is_active=True
                )
            except ConversationSession.DoesNotExist:
                return Response(
                    {"error": "Conversation session not found or inactive"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Deserialize conversation state
            conv_state = ConversationStateManager.deserialize_from_storage(session.state_data)
            
            # Handle catalog return using sales journey
            sales_journey = SalesJourneySubgraph()
            updated_state = await sales_journey.handle_catalog_return(
                state=conv_state,
                selected_product_id=selected_product_id,
                return_message=return_message
            )
            
            # Update session with new state
            session.state_data = ConversationStateManager.serialize_for_storage(updated_state)
            await session.asave()
            
            # Send response back to customer via WhatsApp
            await self._send_whatsapp_response(updated_state, tenant)
            
            logger.info(
                f"Catalog return processed successfully",
                extra={
                    "tenant_id": tenant_id,
                    "conversation_id": conversation_id,
                    "selected_product_id": selected_product_id,
                    "return_message": return_message
                }
            )
            
            return Response(
                {
                    "success": True,
                    "message": "Catalog return processed successfully",
                    "conversation_id": conversation_id,
                    "selected_product_id": selected_product_id
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(
                f"Catalog return webhook failed: {e}",
                extra={
                    "tenant_id": request.data.get('tenant_id'),
                    "conversation_id": request.data.get('conversation_id'),
                    "selected_product_id": request.data.get('selected_product_id')
                },
                exc_info=True
            )
            
            return Response(
                {"error": "Internal server error processing catalog return"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    async def _send_whatsapp_response(self, state: ConversationState, tenant: Tenant):
        """
        Send WhatsApp response to customer.
        
        Args:
            state: Updated conversation state with response
            tenant: Tenant instance for WhatsApp service
        """
        try:
            # Import here to avoid circular imports
            from apps.integrations.services.twilio_service import create_twilio_service_for_tenant
            
            # Get customer phone number from state
            if not state.phone_e164:
                # Try to get from customer record
                from apps.tenants.models import Customer
                try:
                    customer = await Customer.objects.aget(
                        tenant_id=state.tenant_id,
                        id=state.customer_id
                    )
                    state.phone_e164 = customer.phone_e164
                except Customer.DoesNotExist:
                    logger.error(f"Customer not found for catalog return response: {state.customer_id}")
                    return
            
            if not state.phone_e164:
                logger.error(f"No phone number available for catalog return response")
                return
            
            # Create Twilio service
            twilio_service = create_twilio_service_for_tenant(tenant)
            
            # Send response message
            if state.response_text:
                await twilio_service.send_message(
                    to_number=state.phone_e164,
                    message=state.response_text
                )
                
                logger.info(
                    f"Catalog return response sent via WhatsApp",
                    extra={
                        "tenant_id": state.tenant_id,
                        "conversation_id": state.conversation_id,
                        "customer_phone": state.phone_e164,
                        "response_length": len(state.response_text)
                    }
                )
        
        except Exception as e:
            logger.error(
                f"Failed to send WhatsApp response for catalog return: {e}",
                extra={
                    "tenant_id": state.tenant_id,
                    "conversation_id": state.conversation_id,
                    "customer_id": state.customer_id
                },
                exc_info=True
            )


class CatalogReturnPageView(APIView):
    """
    Simple page view for catalog returns that shows a success message.
    
    This can be used as a landing page after catalog selection to inform
    the customer that their selection has been processed.
    """
    
    permission_classes = [AllowAny]
    
    def get(self, request):
        """
        Show catalog return success page.
        
        Query parameters:
        - tenant_id: Tenant identifier
        - conversation_id: Conversation identifier  
        - product_id: Selected product identifier
        """
        tenant_id = request.GET.get('tenant_id')
        conversation_id = request.GET.get('conversation_id')
        product_id = request.GET.get('product_id')
        
        # Simple HTML response
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Selection Confirmed</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    text-align: center;
                    padding: 50px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    background: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    max-width: 400px;
                    margin: 0 auto;
                }}
                .success-icon {{
                    font-size: 48px;
                    color: #25D366;
                    margin-bottom: 20px;
                }}
                h1 {{
                    color: #333;
                    margin-bottom: 20px;
                }}
                p {{
                    color: #666;
                    line-height: 1.5;
                }}
                .whatsapp-link {{
                    display: inline-block;
                    background: #25D366;
                    color: white;
                    padding: 12px 24px;
                    text-decoration: none;
                    border-radius: 5px;
                    margin-top: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success-icon">✅</div>
                <h1>Product Selected!</h1>
                <p>Your product selection has been confirmed. Return to WhatsApp to continue with your order.</p>
                <a href="https://wa.me/" class="whatsapp-link">Return to WhatsApp</a>
            </div>
        </body>
        </html>
        """
        
        return HttpResponse(html_content, content_type='text/html')