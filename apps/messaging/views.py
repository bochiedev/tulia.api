"""
Messaging API views for customer preferences and consent management.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
import logging

from apps.tenants.models import Customer
from apps.messaging.models import CustomerPreferences, ConsentEvent
from apps.messaging.services import ConsentService
from apps.messaging.serializers import (
    CustomerPreferencesSerializer,
    CustomerPreferencesUpdateSerializer,
    CustomerPreferencesWithHistorySerializer,
    ConsentEventSerializer,
    SendMessageSerializer,
    ScheduleMessageSerializer,
    MessageTemplateSerializer,
    MessageTemplateCreateSerializer,
    ScheduledMessageSerializer,
    RateLimitStatusSerializer,
    MessageCampaignSerializer,
    MessageCampaignCreateSerializer,
    CampaignExecuteSerializer,
    CampaignReportSerializer,
    CampaignButtonInteractionSerializer,
    TrackButtonClickSerializer,
)
from apps.core.permissions import HasTenantScopes, requires_scopes

logger = logging.getLogger(__name__)


class CustomerPreferencesView(APIView):
    """
    Get or update customer communication preferences.
    
    GET /v1/customers/{customer_id}/preferences - Get customer preferences
    PUT /v1/customers/{customer_id}/preferences - Update customer preferences
    """
    permission_classes = [HasTenantScopes]
    
    def check_permissions(self, request):
        """Set required scopes based on HTTP method before permission check."""
        if request.method == 'GET':
            self.required_scopes = {'conversations:view'}
        elif request.method == 'PUT':
            self.required_scopes = {'users:manage'}
        super().check_permissions(request)
    
    @extend_schema(
        summary="Get customer preferences",
        description="Retrieve communication preferences for a specific customer",
        parameters=[
            OpenApiParameter(
                name='customer_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                description='Customer UUID'
            ),
            OpenApiParameter(
                name='include_history',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='Include consent change history (default: false)'
            ),
        ],
        responses={
            200: CustomerPreferencesSerializer,
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Messaging']
    )
    def get(self, request, customer_id):
        """Get customer preferences."""
        tenant = request.tenant  # Injected by middleware
        
        try:
            # Get customer
            customer = Customer.objects.get(id=customer_id, tenant=tenant)
        except Customer.DoesNotExist:
            return Response(
                {'error': 'Customer not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get or create preferences
        preferences = ConsentService.get_preferences(tenant, customer)
        
        # Check if history should be included
        include_history = request.query_params.get('include_history', 'false').lower() == 'true'
        
        if include_history:
            serializer = CustomerPreferencesWithHistorySerializer(preferences)
        else:
            serializer = CustomerPreferencesSerializer(preferences)
        
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @extend_schema(
        summary="Update customer preferences",
        description="Update communication preferences for a specific customer. Requires reason for audit trail.",
        parameters=[
            OpenApiParameter(
                name='customer_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                description='Customer UUID'
            ),
        ],
        request=CustomerPreferencesUpdateSerializer,
        responses={
            200: CustomerPreferencesSerializer,
            400: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'},
                    'details': {'type': 'object'}
                }
            },
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Messaging']
    )
    def put(self, request, customer_id):
        """Update customer preferences."""
        tenant = request.tenant  # Injected by middleware
        
        try:
            # Get customer
            customer = Customer.objects.get(id=customer_id, tenant=tenant)
        except Customer.DoesNotExist:
            return Response(
                {'error': 'Customer not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Validate request data
        serializer = CustomerPreferencesUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Invalid request data',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = serializer.validated_data
        reason = data.get('reason', 'Updated by tenant administrator')
        
        # Update each consent type that was provided
        consent_types = ['transactional_messages', 'reminder_messages', 'promotional_messages']
        
        for consent_type in consent_types:
            if consent_type in data:
                try:
                    ConsentService.update_consent(
                        tenant=tenant,
                        customer=customer,
                        consent_type=consent_type,
                        value=data[consent_type],
                        source='tenant_updated',
                        reason=reason,
                        changed_by=request.user if hasattr(request, 'user') else None
                    )
                except Exception as e:
                    logger.error(
                        f"Error updating consent {consent_type}",
                        extra={
                            'tenant_id': str(tenant.id),
                            'customer_id': str(customer.id),
                            'consent_type': consent_type
                        },
                        exc_info=True
                    )
                    return Response(
                        {'error': f'Failed to update {consent_type}: {str(e)}'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
        
        # Get updated preferences
        preferences = ConsentService.get_preferences(tenant, customer)
        response_serializer = CustomerPreferencesSerializer(preferences)
        
        logger.info(
            f"Customer preferences updated by tenant",
            extra={
                'tenant_id': str(tenant.id),
                'customer_id': str(customer.id),
                'updated_by': request.user.email if hasattr(request, 'user') else 'unknown'
            }
        )
        
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class CustomerConsentHistoryView(APIView):
    """
    Get consent change history for a customer.
    
    GET /v1/customers/{customer_id}/consent-history - Get consent event history
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'conversations:view'}
    
    @extend_schema(
        summary="Get customer consent history",
        description="Retrieve audit trail of consent preference changes for a specific customer",
        parameters=[
            OpenApiParameter(
                name='customer_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                description='Customer UUID'
            ),
            OpenApiParameter(
                name='consent_type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by consent type',
                enum=['transactional_messages', 'reminder_messages', 'promotional_messages']
            ),
        ],
        responses={
            200: ConsentEventSerializer(many=True),
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Messaging']
    )
    def get(self, request, customer_id):
        """Get consent change history."""
        tenant = request.tenant  # Injected by middleware
        
        try:
            # Get customer
            customer = Customer.objects.get(id=customer_id, tenant=tenant)
        except Customer.DoesNotExist:
            return Response(
                {'error': 'Customer not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get consent type filter if provided
        consent_type = request.query_params.get('consent_type')
        
        # Get consent history
        if consent_type:
            events = ConsentService.get_consent_history(tenant, customer, consent_type)
        else:
            events = ConsentService.get_consent_history(tenant, customer)
        
        serializer = ConsentEventSerializer(events, many=True)
        
        return Response(serializer.data, status=status.HTTP_200_OK)



class SendMessageView(APIView):
    """
    Send an outbound message to a customer.
    
    POST /v1/messages/send - Send message with consent and rate limit checks
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'conversations:view'}
    
    @extend_schema(
        summary="Send outbound message",
        description="Send a message to a customer with consent validation and rate limiting",
        request=SendMessageSerializer,
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'message_id': {'type': 'string', 'format': 'uuid'},
                    'status': {'type': 'string'},
                    'provider_msg_id': {'type': 'string'},
                }
            },
            400: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'},
                    'details': {'type': 'object'}
                }
            },
            403: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            },
            429: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'},
                    'rate_limit_status': {'type': 'object'}
                }
            }
        },
        tags=['Messaging']
    )
    def post(self, request):
        """Send outbound message."""
        from apps.messaging.services import MessagingService, RateLimitExceeded, ConsentRequired
        from apps.messaging.serializers import SendMessageSerializer
        
        tenant = request.tenant
        
        # Validate request data
        serializer = SendMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Invalid request data',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = serializer.validated_data
        
        # Get customer
        try:
            customer = Customer.objects.get(id=data['customer_id'], tenant=tenant)
        except Customer.DoesNotExist:
            return Response(
                {'error': 'Customer not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Send message
        try:
            message = MessagingService.send_message(
                tenant=tenant,
                customer=customer,
                content=data['content'],
                message_type=data.get('message_type', 'manual_outbound'),
                template_id=data.get('template_id'),
                template_context=data.get('template_context'),
                media_url=data.get('media_url'),
                skip_consent_check=data.get('skip_consent_check', False)
            )
            
            return Response(
                {
                    'message_id': str(message.id),
                    'status': 'sent',
                    'provider_msg_id': message.provider_msg_id,
                    'sent_at': message.sent_at.isoformat() if message.sent_at else None
                },
                status=status.HTTP_200_OK
            )
            
        except ConsentRequired as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        
        except RateLimitExceeded as e:
            rate_limit_status = MessagingService.get_rate_limit_status(tenant)
            return Response(
                {
                    'error': str(e),
                    'rate_limit_status': rate_limit_status
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        except Exception as e:
            logger.error(
                f"Error sending message",
                extra={
                    'tenant_id': str(tenant.id),
                    'customer_id': str(customer.id)
                },
                exc_info=True
            )
            return Response(
                {'error': f'Failed to send message: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ScheduleMessageView(APIView):
    """
    Schedule a message for future delivery.
    
    POST /v1/messages/schedule - Schedule message
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'conversations:view'}
    
    @extend_schema(
        summary="Schedule message for future delivery",
        description="Schedule a message to be sent at a specific time in the future",
        request=ScheduleMessageSerializer,
        responses={
            201: ScheduledMessageSerializer,
            400: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'},
                    'details': {'type': 'object'}
                }
            },
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Messaging']
    )
    def post(self, request):
        """Schedule a message."""
        from apps.messaging.services import MessagingService
        from apps.messaging.serializers import ScheduleMessageSerializer, ScheduledMessageSerializer
        
        tenant = request.tenant
        
        # Validate request data
        serializer = ScheduleMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Invalid request data',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = serializer.validated_data
        
        # Get customer if specified
        customer = None
        if data.get('customer_id'):
            try:
                customer = Customer.objects.get(id=data['customer_id'], tenant=tenant)
            except Customer.DoesNotExist:
                return Response(
                    {'error': 'Customer not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Schedule message
        try:
            scheduled_msg = MessagingService.schedule_message(
                tenant=tenant,
                scheduled_at=data['scheduled_at'],
                content=data['content'],
                customer=customer,
                template_id=data.get('template_id'),
                template_context=data.get('template_context'),
                recipient_criteria=data.get('recipient_criteria'),
                message_type=data.get('message_type', 'scheduled_promotional'),
                metadata=data.get('metadata')
            )
            
            response_serializer = ScheduledMessageSerializer(scheduled_msg)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        except Exception as e:
            logger.error(
                f"Error scheduling message",
                extra={
                    'tenant_id': str(tenant.id),
                    'customer_id': str(customer.id) if customer else None
                },
                exc_info=True
            )
            return Response(
                {'error': f'Failed to schedule message: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MessageTemplateListCreateView(APIView):
    """
    List or create message templates.
    
    GET /v1/templates - List templates
    POST /v1/templates - Create template
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'conversations:view'}
    
    @extend_schema(
        summary="List message templates",
        description="Get all message templates for the tenant",
        parameters=[
            OpenApiParameter(
                name='message_type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by message type',
                enum=['transactional', 'reminder', 'promotional', 'reengagement']
            ),
        ],
        responses={
            200: MessageTemplateSerializer(many=True)
        },
        tags=['Messaging']
    )
    def get(self, request):
        """List message templates."""
        from apps.messaging.models import MessageTemplate
        from apps.messaging.serializers import MessageTemplateSerializer
        
        tenant = request.tenant
        
        # Get templates for tenant
        templates = MessageTemplate.objects.filter(tenant=tenant)
        
        # Filter by message type if provided
        message_type = request.query_params.get('message_type')
        if message_type:
            templates = templates.filter(message_type=message_type)
        
        serializer = MessageTemplateSerializer(templates, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @extend_schema(
        summary="Create message template",
        description="Create a new message template with placeholder support",
        request=MessageTemplateCreateSerializer,
        responses={
            201: MessageTemplateSerializer,
            400: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'},
                    'details': {'type': 'object'}
                }
            }
        },
        tags=['Messaging']
    )
    def post(self, request):
        """Create message template."""
        from apps.messaging.models import MessageTemplate
        from apps.messaging.serializers import MessageTemplateCreateSerializer, MessageTemplateSerializer
        
        tenant = request.tenant
        
        # Validate request data
        serializer = MessageTemplateCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Invalid request data',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = serializer.validated_data
        
        # Create template
        template = MessageTemplate.objects.create(
            tenant=tenant,
            name=data['name'],
            content=data['content'],
            message_type=data['message_type'],
            description=data.get('description', ''),
            variables=data.get('variables', [])
        )
        
        response_serializer = MessageTemplateSerializer(template)
        
        logger.info(
            f"Message template created",
            extra={
                'tenant_id': str(tenant.id),
                'template_id': str(template.id),
                'template_name': template.name
            }
        )
        
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class RateLimitStatusView(APIView):
    """
    Get current rate limit status for tenant.
    
    GET /v1/messages/rate-limit-status - Get rate limit status
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'analytics:view'}
    
    @extend_schema(
        summary="Get rate limit status",
        description="Get current message rate limit status for the tenant",
        responses={
            200: RateLimitStatusSerializer
        },
        tags=['Messaging']
    )
    def get(self, request):
        """Get rate limit status."""
        from apps.messaging.services import MessagingService
        from apps.messaging.serializers import RateLimitStatusSerializer
        
        tenant = request.tenant
        
        rate_limit_status = MessagingService.get_rate_limit_status(tenant)
        
        serializer = RateLimitStatusSerializer(rate_limit_status)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CampaignListCreateView(APIView):
    """
    List or create message campaigns.
    
    GET /v1/campaigns - List campaigns
    POST /v1/campaigns - Create campaign
    """
    permission_classes = [HasTenantScopes]
    
    def check_permissions(self, request):
        """Set required scopes based on HTTP method before permission check."""
        if request.method == 'GET':
            self.required_scopes = {'analytics:view'}
        elif request.method == 'POST':
            self.required_scopes = {'conversations:view'}
        super().check_permissions(request)
    
    @extend_schema(
        summary="List campaigns",
        description="Get all message campaigns for the tenant",
        parameters=[
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by campaign status',
                enum=['draft', 'scheduled', 'sending', 'completed', 'canceled']
            ),
        ],
        responses={
            200: MessageCampaignSerializer(many=True)
        },
        tags=['Campaigns']
    )
    def get(self, request):
        """List campaigns."""
        from apps.messaging.models import MessageCampaign
        from apps.messaging.serializers import MessageCampaignSerializer
        
        tenant = request.tenant
        
        # Get campaigns for tenant
        campaigns = MessageCampaign.objects.filter(tenant=tenant)
        
        # Filter by status if provided
        campaign_status = request.query_params.get('status')
        if campaign_status:
            campaigns = campaigns.filter(status=campaign_status)
        
        serializer = MessageCampaignSerializer(campaigns, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @extend_schema(
        summary="Create campaign",
        description="Create a new message campaign with targeting and optional A/B testing",
        request=MessageCampaignCreateSerializer,
        responses={
            201: MessageCampaignSerializer,
            400: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'},
                    'details': {'type': 'object'}
                }
            },
            403: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Campaigns']
    )
    def post(self, request):
        """Create campaign."""
        from apps.messaging.services import CampaignService
        from apps.messaging.serializers import MessageCampaignCreateSerializer, MessageCampaignSerializer
        from apps.messaging.models import MessageTemplate
        
        tenant = request.tenant
        
        # Validate request data
        serializer = MessageCampaignCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Invalid request data',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = serializer.validated_data
        
        # Get template if specified
        template = None
        if data.get('template_id'):
            try:
                template = MessageTemplate.objects.get(id=data['template_id'], tenant=tenant)
            except MessageTemplate.DoesNotExist:
                return Response(
                    {'error': 'Template not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Create campaign
        try:
            campaign_service = CampaignService()
            campaign = campaign_service.create_campaign(
                tenant=tenant,
                name=data['name'],
                message_content=data['message_content'],
                target_criteria=data.get('target_criteria', {}),
                created_by=request.user if hasattr(request, 'user') else None,
                template=template,
                scheduled_at=data.get('scheduled_at'),
                is_ab_test=data.get('is_ab_test', False),
                variants=data.get('variants', []),
                description=data.get('description', ''),
                media_type=data.get('media_type', 'text'),
                media_url=data.get('media_url'),
                media_caption=data.get('media_caption', ''),
                buttons=data.get('buttons', [])
            )
            
            response_serializer = MessageCampaignSerializer(campaign)
            
            logger.info(
                f"Campaign created",
                extra={
                    'tenant_id': str(tenant.id),
                    'campaign_id': str(campaign.id),
                    'campaign_name': campaign.name
                }
            )
            
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        except Exception as e:
            logger.error(
                f"Error creating campaign",
                extra={
                    'tenant_id': str(tenant.id)
                },
                exc_info=True
            )
            return Response(
                {'error': f'Failed to create campaign: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CampaignDetailView(APIView):
    """
    Get campaign details.
    
    GET /v1/campaigns/{campaign_id} - Get campaign details
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'analytics:view'}
    
    @extend_schema(
        summary="Get campaign details",
        description="Retrieve details for a specific campaign",
        parameters=[
            OpenApiParameter(
                name='campaign_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                description='Campaign UUID'
            ),
        ],
        responses={
            200: MessageCampaignSerializer,
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Campaigns']
    )
    def get(self, request, campaign_id):
        """Get campaign details."""
        from apps.messaging.models import MessageCampaign
        from apps.messaging.serializers import MessageCampaignSerializer
        
        tenant = request.tenant
        
        try:
            campaign = MessageCampaign.objects.get(id=campaign_id, tenant=tenant)
        except MessageCampaign.DoesNotExist:
            return Response(
                {'error': 'Campaign not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = MessageCampaignSerializer(campaign)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CampaignExecuteView(APIView):
    """
    Execute a campaign.
    
    POST /v1/campaigns/{campaign_id}/execute - Execute campaign
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'conversations:view'}
    
    @extend_schema(
        summary="Execute campaign",
        description="Execute a campaign by sending messages to all matching customers with consent",
        parameters=[
            OpenApiParameter(
                name='campaign_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                description='Campaign UUID'
            ),
        ],
        request=CampaignExecuteSerializer,
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'campaign_id': {'type': 'string', 'format': 'uuid'},
                    'status': {'type': 'string'},
                    'results': {
                        'type': 'object',
                        'properties': {
                            'targeted': {'type': 'integer'},
                            'sent': {'type': 'integer'},
                            'failed': {'type': 'integer'},
                            'skipped_no_consent': {'type': 'integer'},
                            'errors': {'type': 'array', 'items': {'type': 'string'}}
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'},
                    'details': {'type': 'object'}
                }
            },
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Campaigns']
    )
    def post(self, request, campaign_id):
        """Execute campaign."""
        from apps.messaging.services import CampaignService
        from apps.messaging.models import MessageCampaign
        from apps.messaging.serializers import CampaignExecuteSerializer
        
        tenant = request.tenant
        
        # Validate request data
        serializer = CampaignExecuteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Invalid request data',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get campaign
        try:
            campaign = MessageCampaign.objects.get(id=campaign_id, tenant=tenant)
        except MessageCampaign.DoesNotExist:
            return Response(
                {'error': 'Campaign not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Execute campaign
        try:
            campaign_service = CampaignService()
            results = campaign_service.execute_campaign(campaign)
            
            return Response(
                {
                    'campaign_id': str(campaign.id),
                    'status': campaign.status,
                    'results': results
                },
                status=status.HTTP_200_OK
            )
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        except Exception as e:
            logger.error(
                f"Error executing campaign",
                extra={
                    'tenant_id': str(tenant.id),
                    'campaign_id': str(campaign_id)
                },
                exc_info=True
            )
            return Response(
                {'error': f'Failed to execute campaign: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CampaignButtonClickView(APIView):
    """
    Track button clicks from campaign messages.
    
    POST /v1/campaigns/{campaign_id}/button-click - Track button click
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'conversations:view'}
    
    @extend_schema(
        summary="Track campaign button click",
        description="Record when a customer clicks a button in a campaign message",
        parameters=[
            OpenApiParameter(
                name='campaign_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                description='Campaign UUID'
            ),
        ],
        request=TrackButtonClickSerializer,
        responses={
            200: CampaignButtonInteractionSerializer,
            400: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'},
                    'details': {'type': 'object'}
                }
            },
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Campaigns']
    )
    def post(self, request, campaign_id):
        """Track button click."""
        from apps.messaging.services import CampaignService
        from apps.messaging.models import MessageCampaign, Message
        from apps.messaging.serializers import (
            TrackButtonClickSerializer,
            CampaignButtonInteractionSerializer
        )
        
        tenant = request.tenant
        
        # Validate request data
        serializer = TrackButtonClickSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Invalid request data',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = serializer.validated_data
        
        # Get campaign
        try:
            campaign = MessageCampaign.objects.get(id=campaign_id, tenant=tenant)
        except MessageCampaign.DoesNotExist:
            return Response(
                {'error': 'Campaign not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get message
        try:
            message = Message.objects.get(
                id=data['message_id'],
                conversation__tenant=tenant
            )
        except Message.DoesNotExist:
            return Response(
                {'error': 'Message not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get customer from message conversation
        customer = message.conversation.customer
        
        # Track button click
        try:
            campaign_service = CampaignService()
            interaction = campaign_service.track_button_click(
                campaign=campaign,
                customer=customer,
                message=message,
                button_id=data['button_id'],
                button_title=data['button_title'],
                button_type=data.get('button_type', 'reply'),
                metadata=data.get('metadata', {})
            )
            
            response_serializer = CampaignButtonInteractionSerializer({
                'id': interaction.id,
                'campaign_id': interaction.campaign_id,
                'customer_id': interaction.customer_id,
                'message_id': interaction.message_id,
                'button_id': interaction.button_id,
                'button_title': interaction.button_title,
                'button_type': interaction.button_type,
                'clicked_at': interaction.clicked_at,
                'led_to_conversion': interaction.led_to_conversion,
                'conversion_type': interaction.conversion_type,
                'conversion_reference_id': interaction.conversion_reference_id
            })
            
            return Response(response_serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(
                f"Error tracking button click",
                extra={
                    'tenant_id': str(tenant.id),
                    'campaign_id': str(campaign_id),
                    'message_id': str(data['message_id'])
                },
                exc_info=True
            )
            return Response(
                {'error': f'Failed to track button click: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CampaignReportView(APIView):
    """
    Get campaign analytics report.
    
    GET /v1/campaigns/{campaign_id}/report - Get campaign report
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'analytics:view'}
    
    @extend_schema(
        summary="Get campaign report",
        description="Generate comprehensive analytics report for a campaign including A/B test results",
        parameters=[
            OpenApiParameter(
                name='campaign_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                description='Campaign UUID'
            ),
        ],
        responses={
            200: CampaignReportSerializer,
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Campaigns']
    )
    def get(self, request, campaign_id):
        """Get campaign report."""
        from apps.messaging.services import CampaignService
        from apps.messaging.models import MessageCampaign
        from apps.messaging.serializers import CampaignReportSerializer
        
        tenant = request.tenant
        
        # Get campaign
        try:
            campaign = MessageCampaign.objects.get(id=campaign_id, tenant=tenant)
        except MessageCampaign.DoesNotExist:
            return Response(
                {'error': 'Campaign not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Generate report
        try:
            campaign_service = CampaignService()
            report = campaign_service.generate_report(campaign)
            
            serializer = CampaignReportSerializer(report)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(
                f"Error generating campaign report",
                extra={
                    'tenant_id': str(tenant.id),
                    'campaign_id': str(campaign_id)
                },
                exc_info=True
            )
            return Response(
                {'error': f'Failed to generate report: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
