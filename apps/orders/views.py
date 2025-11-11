"""
Order API views for e-commerce functionality.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from django.utils import timezone
import logging

from apps.orders.models import Order
from apps.orders.serializers import (
    OrderListSerializer, OrderDetailSerializer,
    OrderCreateSerializer, OrderUpdateSerializer
)
from apps.core.permissions import HasTenantScopes, requires_scopes
from apps.rbac.models import AuditLog

logger = logging.getLogger(__name__)


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for list endpoints."""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100


class OrderListView(APIView):
    """
    List and create orders.
    
    GET /v1/orders - List orders with filtering
    POST /v1/orders - Create a new order
    """
    permission_classes = [HasTenantScopes]
    
    def check_permissions(self, request):
        """Set required scopes based on HTTP method before permission check."""
        if request.method == 'GET':
            self.required_scopes = {'orders:view'}
        elif request.method == 'POST':
            self.required_scopes = {'orders:edit'}
        super().check_permissions(request)
    
    @extend_schema(
        summary="List orders",
        description="Retrieve paginated list of orders with optional filtering",
        parameters=[
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by order status',
                enum=['draft', 'placed', 'paid', 'fulfilled', 'canceled']
            ),
            OpenApiParameter(
                name='customer_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description='Filter by customer ID'
            ),
            OpenApiParameter(
                name='from_date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Filter orders created on or after this date'
            ),
            OpenApiParameter(
                name='to_date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Filter orders created on or before this date'
            ),
            OpenApiParameter(
                name='page',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Page number'
            ),
            OpenApiParameter(
                name='page_size',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Number of results per page (max 100)'
            ),
        ],
        responses={
            200: OrderListSerializer(many=True),
            403: {'description': 'Forbidden - Missing required scope: orders:view'}
        }
    )
    def get(self, request):
        """List orders for the authenticated tenant."""
        tenant = request.tenant
        
        # Start with tenant-scoped queryset
        queryset = Order.objects.for_tenant(tenant)
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        customer_id = request.query_params.get('customer_id')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        
        from_date = request.query_params.get('from_date')
        if from_date:
            queryset = queryset.filter(created_at__date__gte=from_date)
        
        to_date = request.query_params.get('to_date')
        if to_date:
            queryset = queryset.filter(created_at__date__lte=to_date)
        
        # Paginate
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = OrderListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = OrderListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Create order",
        description="Create a new order for the authenticated tenant",
        request=OrderCreateSerializer,
        responses={
            201: OrderDetailSerializer,
            400: {'description': 'Bad Request - Invalid order data'},
            403: {'description': 'Forbidden - Missing required scope: orders:edit'}
        }
    )
    def post(self, request):
        """Create a new order."""
        tenant = request.tenant
        membership = request.membership
        
        serializer = OrderCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create order
        order = serializer.save()
        
        # Create audit log
        AuditLog.objects.create(
            tenant=tenant,
            user=request.user,
            action='order.created',
            target_type='Order',
            target_id=str(order.id),
            changes={
                'order_id': str(order.id),
                'customer_id': str(order.customer_id),
                'total': float(order.total),
                'status': order.status
            },
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        logger.info(
            f"Order created",
            extra={
                'tenant': tenant.slug,
                'order_id': str(order.id),
                'user': request.user.email,
                'total': float(order.total)
            }
        )
        
        # Return created order
        response_serializer = OrderDetailSerializer(order)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )


class OrderDetailView(APIView):
    """
    Retrieve and update individual orders.
    
    GET /v1/orders/{id} - Get order details
    PUT /v1/orders/{id} - Update order (status changes)
    """
    permission_classes = [HasTenantScopes]
    
    def check_permissions(self, request):
        """Set required scopes based on HTTP method before permission check."""
        if request.method == 'GET':
            self.required_scopes = {'orders:view'}
        elif request.method in ['PUT', 'PATCH']:
            self.required_scopes = {'orders:edit'}
        super().check_permissions(request)
    
    def get_object(self, tenant, order_id):
        """Get order by ID, ensuring tenant scoping."""
        try:
            return Order.objects.for_tenant(tenant).get(id=order_id)
        except Order.DoesNotExist:
            return None
    
    @extend_schema(
        summary="Get order details",
        description="Retrieve detailed information about a specific order",
        responses={
            200: OrderDetailSerializer,
            403: {'description': 'Forbidden - Missing required scope: orders:view'},
            404: {'description': 'Not Found - Order does not exist'}
        }
    )
    def get(self, request, order_id):
        """Get order details."""
        tenant = request.tenant
        
        order = self.get_object(tenant, order_id)
        if not order:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = OrderDetailSerializer(order)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Update order",
        description="Update order status and metadata. Status changes trigger automated messages.",
        request=OrderUpdateSerializer,
        responses={
            200: OrderDetailSerializer,
            400: {'description': 'Bad Request - Invalid update data'},
            403: {'description': 'Forbidden - Missing required scope: orders:edit'},
            404: {'description': 'Not Found - Order does not exist'}
        }
    )
    def put(self, request, order_id):
        """Update order (primarily for status changes)."""
        tenant = request.tenant
        membership = request.membership
        
        order = self.get_object(tenant, order_id)
        if not order:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Store previous state for audit
        previous_status = order.status
        
        serializer = OrderUpdateSerializer(
            order,
            data=request.data,
            partial=True
        )
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Save changes
        updated_order = serializer.save()
        
        # Update timestamps based on status
        if updated_order.status == 'paid' and previous_status != 'paid':
            updated_order.paid_at = timezone.now()
            updated_order.save(update_fields=['paid_at'])
        elif updated_order.status == 'fulfilled' and previous_status != 'fulfilled':
            updated_order.fulfilled_at = timezone.now()
            updated_order.save(update_fields=['fulfilled_at'])
        
        # Create audit log
        changes = {}
        if previous_status != updated_order.status:
            changes['status'] = {
                'from': previous_status,
                'to': updated_order.status
            }
        if 'payment_ref' in request.data:
            changes['payment_ref'] = request.data['payment_ref']
        if 'tracking_number' in request.data:
            changes['tracking_number'] = request.data['tracking_number']
        
        AuditLog.objects.create(
            tenant=tenant,
            user=request.user,
            action='order.updated',
            target_type='Order',
            target_id=str(order.id),
            changes=changes,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        logger.info(
            f"Order updated",
            extra={
                'tenant': tenant.slug,
                'order_id': str(order.id),
                'user': request.user.email,
                'previous_status': previous_status,
                'new_status': updated_order.status
            }
        )
        
        # Note: Automated messages are triggered by signals in apps/orders/signals.py
        
        # Return updated order
        response_serializer = OrderDetailSerializer(updated_order)
        return Response(response_serializer.data)
