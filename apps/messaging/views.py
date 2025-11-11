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
    ConsentEventSerializer
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
