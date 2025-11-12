"""
Customer management API views.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from django.core.paginator import Paginator
from django.http import HttpResponse
import logging
import json
import csv
from io import StringIO

from apps.tenants.models import Customer
from apps.messaging.models import CustomerPreferences, ConsentEvent
from apps.tenants.serializers_customer import (
    CustomerListSerializer,
    CustomerDetailSerializer,
    CustomerExportSerializer,
)
from apps.core.permissions import HasTenantScopes

logger = logging.getLogger(__name__)


class CustomerListView(APIView):
    """
    List customers with filtering.
    
    GET /v1/customers - List all customers for tenant
    
    Required scope: conversations:view
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'conversations:view'}
    
    @extend_schema(
        summary="List customers",
        description="List all customers for the authenticated tenant with filtering and pagination",
        parameters=[
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Search by name or phone number',
                required=False
            ),
            OpenApiParameter(
                name='tag',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by tag',
                required=False
            ),
            OpenApiParameter(
                name='has_promotional_consent',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='Filter by promotional message consent',
                required=False
            ),
            OpenApiParameter(
                name='active_days',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Filter customers active in last N days',
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
                        'items': {'$ref': '#/components/schemas/CustomerList'}
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
        tags=['Customers']
    )
    def get(self, request):
        """List customers with filtering."""
        tenant = request.tenant
        
        # Start with tenant-scoped queryset
        queryset = Customer.objects.for_tenant(tenant)
        
        # Apply search filter
        search = request.query_params.get('search')
        if search:
            # Search by name or phone (note: phone is encrypted, so this is limited)
            queryset = queryset.filter(name__icontains=search)
        
        # Filter by tag
        tag = request.query_params.get('tag')
        if tag:
            queryset = queryset.filter(tags__contains=[tag])
        
        # Filter by promotional consent
        has_promotional_consent = request.query_params.get('has_promotional_consent')
        if has_promotional_consent is not None:
            consent_value = has_promotional_consent.lower() == 'true'
            # Get customer IDs with matching consent
            customer_ids = CustomerPreferences.objects.filter(
                tenant=tenant,
                promotional_messages=consent_value
            ).values_list('customer_id', flat=True)
            queryset = queryset.filter(id__in=customer_ids)
        
        # Filter by activity
        active_days = request.query_params.get('active_days')
        if active_days:
            from django.utils import timezone
            from datetime import timedelta
            cutoff = timezone.now() - timedelta(days=int(active_days))
            queryset = queryset.filter(last_seen_at__gte=cutoff)
        
        # Order by last seen
        queryset = queryset.order_by('-last_seen_at')
        
        # Pagination
        page = int(request.query_params.get('page', 1))
        page_size = min(int(request.query_params.get('page_size', 50)), 100)
        
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        serializer = CustomerListSerializer(page_obj.object_list, many=True)
        
        return Response({
            'count': paginator.count,
            'next': page_obj.next_page_number() if page_obj.has_next() else None,
            'previous': page_obj.previous_page_number() if page_obj.has_previous() else None,
            'results': serializer.data
        }, status=status.HTTP_200_OK)


class CustomerDetailView(APIView):
    """
    Retrieve customer details.
    
    GET /v1/customers/{id} - Get customer details
    
    Required scope: conversations:view
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'conversations:view'}
    
    @extend_schema(
        summary="Get customer details",
        description="Retrieve detailed information about a specific customer",
        parameters=[
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                description='Customer UUID'
            ),
        ],
        responses={
            200: CustomerDetailSerializer,
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
        tags=['Customers']
    )
    def get(self, request, id):
        """Get customer details."""
        tenant = request.tenant
        
        try:
            customer = Customer.objects.get(id=id, tenant=tenant)
        except Customer.DoesNotExist:
            return Response(
                {'error': 'Customer not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = CustomerDetailSerializer(customer)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CustomerExportView(APIView):
    """
    Export customer data with PII masking options.
    
    POST /v1/customers/{id}/export - Export customer data
    
    Required scope: conversations:view
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'conversations:view'}
    
    @extend_schema(
        summary="Export customer data",
        description="Export customer data with optional PII masking for compliance",
        parameters=[
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                description='Customer UUID'
            ),
        ],
        request=CustomerExportSerializer,
        responses={
            200: {
                'type': 'object',
                'description': 'Customer data export (JSON or CSV)'
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
        tags=['Customers']
    )
    def post(self, request, id):
        """Export customer data."""
        tenant = request.tenant
        
        try:
            customer = Customer.objects.get(id=id, tenant=tenant)
        except Customer.DoesNotExist:
            return Response(
                {'error': 'Customer not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Validate request data
        serializer = CustomerExportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid request data', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        options = serializer.validated_data
        mask_pii = options.get('mask_pii', False)
        include_conversations = options.get('include_conversations', False)
        include_consent_history = options.get('include_consent_history', False)
        export_format = options.get('format', 'json')
        
        # Build export data
        export_data = {
            'customer_id': str(customer.id),
            'phone_e164': '***MASKED***' if mask_pii else customer.phone_e164,
            'name': customer.name,
            'timezone': customer.timezone,
            'language': customer.language,
            'tags': customer.tags,
            'metadata': customer.metadata,
            'last_seen_at': customer.last_seen_at.isoformat() if customer.last_seen_at else None,
            'first_interaction_at': customer.first_interaction_at.isoformat() if customer.first_interaction_at else None,
            'created_at': customer.created_at.isoformat(),
        }
        
        # Add consent preferences
        try:
            preferences = CustomerPreferences.objects.get(tenant=tenant, customer=customer)
            export_data['consent_preferences'] = {
                'transactional_messages': preferences.transactional_messages,
                'reminder_messages': preferences.reminder_messages,
                'promotional_messages': preferences.promotional_messages,
                'last_updated': preferences.updated_at.isoformat(),
            }
        except CustomerPreferences.DoesNotExist:
            export_data['consent_preferences'] = None
        
        # Add consent history if requested
        if include_consent_history:
            consent_events = ConsentEvent.objects.for_customer(tenant, customer)
            export_data['consent_history'] = [{
                'consent_type': event.consent_type,
                'previous_value': event.previous_value,
                'new_value': event.new_value,
                'source': event.source,
                'reason': event.reason,
                'changed_at': event.created_at.isoformat(),
            } for event in consent_events]
        
        # Add conversations if requested
        if include_conversations:
            conversations = customer.conversations.order_by('-updated_at')
            export_data['conversations'] = [{
                'conversation_id': str(conv.id),
                'status': conv.status,
                'channel': conv.channel,
                'message_count': conv.messages.count(),
                'created_at': conv.created_at.isoformat(),
                'updated_at': conv.updated_at.isoformat(),
            } for conv in conversations]
        
        # Log export for audit trail
        logger.info(
            f"Customer data exported by user {request.user.id}",
            extra={
                'tenant_id': str(tenant.id),
                'customer_id': str(customer.id),
                'mask_pii': mask_pii,
                'include_conversations': include_conversations,
                'include_consent_history': include_consent_history,
                'format': export_format,
            }
        )
        
        # Return in requested format
        if export_format == 'csv':
            # Flatten data for CSV
            output = StringIO()
            writer = csv.writer(output)
            
            # Write headers
            headers = ['Field', 'Value']
            writer.writerow(headers)
            
            # Write basic fields
            for key, value in export_data.items():
                if key not in ['consent_history', 'conversations', 'consent_preferences', 'tags', 'metadata']:
                    writer.writerow([key, value])
            
            # Write consent preferences
            if export_data.get('consent_preferences'):
                for key, value in export_data['consent_preferences'].items():
                    writer.writerow([f'consent_{key}', value])
            
            csv_content = output.getvalue()
            output.close()
            
            response = HttpResponse(csv_content, content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="customer_{customer.id}_export.csv"'
            return response
        
        else:  # JSON format
            return Response(export_data, status=status.HTTP_200_OK)
