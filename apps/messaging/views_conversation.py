"""
Conversation and customer management API views.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
import logging

from apps.messaging.models import Conversation, Message
from apps.tenants.models import Customer
from apps.messaging.serializers_conversation import (
    ConversationListSerializer,
    ConversationDetailSerializer,
    MessageSerializer,
    ConversationHandoffSerializer,
)
from apps.core.permissions import HasTenantScopes

User = get_user_model()
logger = logging.getLogger(__name__)


class ConversationListView(APIView):
    """
    List conversations with filtering and pagination.
    
    GET /v1/conversations - List all conversations for tenant
    
    Required scope: conversations:view
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'conversations:view'}
    
    @extend_schema(
        summary="List conversations",
        description="List all conversations for the authenticated tenant with filtering and pagination",
        parameters=[
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by status (open, bot, handoff, closed, dormant)',
                required=False
            ),
            OpenApiParameter(
                name='customer_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description='Filter by customer ID',
                required=False
            ),
            OpenApiParameter(
                name='channel',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by channel (whatsapp, sms, telegram, web)',
                required=False
            ),
            OpenApiParameter(
                name='page',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Page number (default: 1)',
                required=False
            ),
            OpenApiParameter(
                name='page_size',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Items per page (default: 50, max: 100)',
                required=False
            ),
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'count': {'type': 'integer'},
                    'next': {'type': 'string', 'nullable': True},
                    'previous': {'type': 'string', 'nullable': True},
                    'results': {
                        'type': 'array',
                        'items': {'$ref': '#/components/schemas/ConversationList'}
                    }
                }
            },
            403: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Conversations']
    )
    def get(self, request):
        """List conversations with filtering."""
        tenant = request.tenant
        
        # Start with tenant-scoped queryset
        queryset = Conversation.objects.for_tenant(tenant).select_related('customer', 'last_agent')
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        customer_id = request.query_params.get('customer_id')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        
        channel = request.query_params.get('channel')
        if channel:
            queryset = queryset.filter(channel=channel)
        
        # Pagination
        page = int(request.query_params.get('page', 1))
        page_size = min(int(request.query_params.get('page_size', 50)), 100)
        
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        serializer = ConversationListSerializer(page_obj.object_list, many=True)
        
        return Response({
            'count': paginator.count,
            'next': page_obj.next_page_number() if page_obj.has_next() else None,
            'previous': page_obj.previous_page_number() if page_obj.has_previous() else None,
            'results': serializer.data
        }, status=status.HTTP_200_OK)


class ConversationDetailView(APIView):
    """
    Retrieve conversation details.
    
    GET /v1/conversations/{id} - Get conversation details
    
    Required scope: conversations:view
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'conversations:view'}
    
    @extend_schema(
        summary="Get conversation details",
        description="Retrieve detailed information about a specific conversation",
        parameters=[
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                description='Conversation UUID'
            ),
        ],
        responses={
            200: ConversationDetailSerializer,
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            },
            403: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Conversations']
    )
    def get(self, request, id):
        """Get conversation details."""
        tenant = request.tenant
        
        try:
            conversation = Conversation.objects.select_related('customer', 'last_agent').get(
                id=id,
                tenant=tenant
            )
        except Conversation.DoesNotExist:
            return Response(
                {'error': 'Conversation not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = ConversationDetailSerializer(conversation)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ConversationMessagesView(APIView):
    """
    List messages for a conversation.
    
    GET /v1/conversations/{id}/messages - Get conversation messages
    
    Required scope: conversations:view
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'conversations:view'}
    
    @extend_schema(
        summary="List conversation messages",
        description="List all messages in a conversation with pagination",
        parameters=[
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                description='Conversation UUID'
            ),
            OpenApiParameter(
                name='page',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Page number (default: 1)',
                required=False
            ),
            OpenApiParameter(
                name='page_size',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Items per page (default: 50, max: 100)',
                required=False
            ),
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'count': {'type': 'integer'},
                    'next': {'type': 'string', 'nullable': True},
                    'previous': {'type': 'string', 'nullable': True},
                    'results': {
                        'type': 'array',
                        'items': {'$ref': '#/components/schemas/Message'}
                    }
                }
            },
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            },
            403: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Conversations']
    )
    def get(self, request, id):
        """List messages for conversation."""
        tenant = request.tenant
        
        try:
            conversation = Conversation.objects.get(id=id, tenant=tenant)
        except Conversation.DoesNotExist:
            return Response(
                {'error': 'Conversation not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get messages for conversation
        queryset = Message.objects.for_conversation(conversation)
        
        # Pagination
        page = int(request.query_params.get('page', 1))
        page_size = min(int(request.query_params.get('page_size', 50)), 100)
        
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        serializer = MessageSerializer(page_obj.object_list, many=True)
        
        return Response({
            'count': paginator.count,
            'next': page_obj.next_page_number() if page_obj.has_next() else None,
            'previous': page_obj.previous_page_number() if page_obj.has_previous() else None,
            'results': serializer.data
        }, status=status.HTTP_200_OK)


class ConversationHandoffView(APIView):
    """
    Request human handoff for a conversation.
    
    POST /v1/conversations/{id}/handoff - Mark conversation for human handoff
    
    Required scope: handoff:perform
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'handoff:perform'}
    
    @extend_schema(
        summary="Request human handoff",
        description="Mark a conversation for human agent handoff",
        parameters=[
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                description='Conversation UUID'
            ),
        ],
        request=ConversationHandoffSerializer,
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'conversation': {'$ref': '#/components/schemas/ConversationDetail'}
                }
            },
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            },
            400: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            },
            403: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Conversations']
    )
    def post(self, request, id):
        """Request human handoff."""
        tenant = request.tenant
        
        try:
            conversation = Conversation.objects.select_related('customer').get(
                id=id,
                tenant=tenant
            )
        except Conversation.DoesNotExist:
            return Response(
                {'error': 'Conversation not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Validate request data
        serializer = ConversationHandoffSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid request data', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get agent if specified
        agent = None
        agent_id = serializer.validated_data.get('agent_id')
        if agent_id:
            try:
                agent = User.objects.get(id=agent_id)
            except User.DoesNotExist:
                return Response(
                    {'error': 'Agent not found'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Mark conversation for handoff
        conversation.mark_handoff(agent=agent)
        
        # Log handoff reason if provided
        reason = serializer.validated_data.get('reason')
        if reason:
            if not conversation.metadata:
                conversation.metadata = {}
            conversation.metadata['handoff_reason'] = reason
            conversation.save(update_fields=['metadata'])
        
        logger.info(
            f"Conversation {conversation.id} marked for handoff by user {request.user.id}",
            extra={
                'tenant_id': str(tenant.id),
                'conversation_id': str(conversation.id),
                'agent_id': str(agent.id) if agent else None,
                'reason': reason
            }
        )
        
        # Return updated conversation
        response_serializer = ConversationDetailSerializer(conversation)
        
        return Response({
            'message': 'Conversation marked for human handoff',
            'conversation': response_serializer.data
        }, status=status.HTTP_200_OK)
