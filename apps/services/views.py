"""
Views for services and appointments API endpoints.
"""
from datetime import datetime, timedelta
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.core.permissions import HasTenantScopes, requires_scopes
from apps.services.models import Service, ServiceVariant, AvailabilityWindow, Appointment
from apps.services.serializers import (
    ServiceListSerializer,
    ServiceDetailSerializer,
    ServiceCreateSerializer,
    ServiceVariantSerializer,
    AvailabilityWindowSerializer,
    AvailabilitySlotSerializer,
    AppointmentListSerializer,
    AppointmentDetailSerializer,
    AppointmentCreateSerializer,
    AppointmentCancelSerializer
)
from apps.services.services import BookingService
from apps.tenants.services.subscription_service import SubscriptionService


@requires_scopes('services:view', 'services:edit')
class ServiceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing services.
    
    Provides CRUD operations for bookable services with tenant isolation.
    
    Required scopes:
    - services:view: For GET operations
    - services:edit: For POST, PUT, PATCH, DELETE operations
    """
    
    permission_classes = [IsAuthenticated, HasTenantScopes]
    
    def get_queryset(self):
        """Get services for the authenticated tenant."""
        return Service.objects.for_tenant(self.request.tenant).select_related('tenant')
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return ServiceListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ServiceCreateSerializer
        return ServiceDetailSerializer
    
    @extend_schema(
        summary="List services",
        description="Get list of services for the authenticated tenant",
        parameters=[
            OpenApiParameter('is_active', bool, description='Filter by active status'),
            OpenApiParameter('search', str, description='Search in title and description'),
            OpenApiParameter('page', int, description='Page number'),
            OpenApiParameter('page_size', int, description='Number of items per page (max 100)'),
        ],
        responses={200: ServiceListSerializer(many=True)}
    )
    def list(self, request):
        """List services with optional filters."""
        queryset = self.get_queryset()
        
        # Filter by active status
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            is_active_bool = is_active.lower() in ['true', '1', 'yes']
            queryset = queryset.filter(is_active=is_active_bool)
        
        # Search
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(title__icontains=search) | queryset.filter(description__icontains=search)
        
        # Paginate (ViewSets automatically use pagination_class from settings)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Create service",
        description="Create a new bookable service. Enforces max_services limit based on subscription tier.",
        request=ServiceCreateSerializer,
        responses={
            201: ServiceDetailSerializer,
            403: OpenApiResponse(description="Feature limit exceeded")
        }
    )
    def create(self, request):
        """Create a new service with feature limit enforcement."""
        # Check feature limit
        subscription_service = SubscriptionService(request.tenant)
        current_count = Service.objects.for_tenant(request.tenant).count()
        
        is_within_limit, limit = subscription_service.check_feature_limit('max_services', current_count)
        if not is_within_limit:
            return Response(
                {
                    'error': {
                        'code': 'FEATURE_LIMIT_EXCEEDED',
                        'message': f'Service limit reached. Your plan allows {limit} services. Please upgrade to add more.',
                        'current_count': current_count,
                        'limit': limit
                    }
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Add tenant
        service = serializer.save(tenant=request.tenant)
        
        # Return detail serializer
        detail_serializer = ServiceDetailSerializer(service)
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)
    
    @extend_schema(
        summary="Get service details",
        description="Get detailed information about a service including variants",
        responses={200: ServiceDetailSerializer}
    )
    def retrieve(self, request, pk=None):
        """Get service details."""
        service = self.get_object()
        serializer = self.get_serializer(service)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Update service",
        description="Update service information",
        request=ServiceCreateSerializer,
        responses={200: ServiceDetailSerializer}
    )
    def update(self, request, pk=None):
        """Update service."""
        service = self.get_object()
        serializer = self.get_serializer(service, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        detail_serializer = ServiceDetailSerializer(service)
        return Response(detail_serializer.data)
    
    @extend_schema(
        summary="Partial update service",
        description="Partially update service information",
        request=ServiceCreateSerializer,
        responses={200: ServiceDetailSerializer}
    )
    def partial_update(self, request, pk=None):
        """Partially update service."""
        service = self.get_object()
        serializer = self.get_serializer(service, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        detail_serializer = ServiceDetailSerializer(service)
        return Response(detail_serializer.data)
    
    @extend_schema(
        summary="Delete service",
        description="Soft delete a service",
        responses={204: None}
    )
    def destroy(self, request, pk=None):
        """Soft delete service."""
        service = self.get_object()
        service.delete()  # Soft delete
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @extend_schema(
        summary="Get service availability",
        description="Get available time slots for a service",
        parameters=[
            OpenApiParameter('from_dt', str, description='Start datetime (ISO 8601)', required=True),
            OpenApiParameter('to_dt', str, description='End datetime (ISO 8601)', required=True),
            OpenApiParameter('variant_id', str, description='Service variant ID (optional)'),
        ],
        responses={200: AvailabilitySlotSerializer(many=True)}
    )
    @action(detail=True, methods=['get'], url_path='availability')
    def availability(self, request, pk=None):
        """
        Get available time slots for a service.
        
        Query parameters:
        - from_dt: Start datetime (ISO 8601 format)
        - to_dt: End datetime (ISO 8601 format)
        - variant_id: Optional service variant ID
        """
        service = self.get_object()
        
        # Parse datetime parameters
        from_dt_str = request.query_params.get('from_dt')
        to_dt_str = request.query_params.get('to_dt')
        variant_id = request.query_params.get('variant_id')
        
        if not from_dt_str or not to_dt_str:
            return Response(
                {'error': 'from_dt and to_dt parameters are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from_dt = datetime.fromisoformat(from_dt_str.replace('Z', '+00:00'))
            to_dt = datetime.fromisoformat(to_dt_str.replace('Z', '+00:00'))
        except ValueError as e:
            return Response(
                {'error': f'Invalid datetime format: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get availability
        booking_service = BookingService(request.tenant)
        try:
            slots = booking_service.find_availability(
                str(service.id),
                from_dt,
                to_dt,
                variant_id
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = AvailabilitySlotSerializer(slots, many=True)
        return Response(serializer.data)


@requires_scopes('appointments:view', 'appointments:edit')
class AppointmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing appointments.
    
    Provides CRUD operations for service appointments with capacity validation.
    
    Required scopes:
    - appointments:view: For GET operations
    - appointments:edit: For POST, PUT, PATCH, DELETE operations
    """
    
    permission_classes = [IsAuthenticated, HasTenantScopes]
    
    def get_queryset(self):
        """Get appointments for the authenticated tenant."""
        return Appointment.objects.for_tenant(self.request.tenant).select_related(
            'customer', 'service', 'variant'
        )
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return AppointmentListSerializer
        elif self.action == 'create':
            return AppointmentCreateSerializer
        elif self.action == 'cancel':
            return AppointmentCancelSerializer
        return AppointmentDetailSerializer
    
    @extend_schema(
        summary="List appointments",
        description="Get list of appointments for the authenticated tenant",
        parameters=[
            OpenApiParameter('customer_id', str, description='Filter by customer ID'),
            OpenApiParameter('service_id', str, description='Filter by service ID'),
            OpenApiParameter('status', str, description='Filter by status'),
            OpenApiParameter('from_dt', str, description='Filter by start datetime >= from_dt'),
            OpenApiParameter('to_dt', str, description='Filter by start datetime <= to_dt'),
            OpenApiParameter('page', int, description='Page number'),
            OpenApiParameter('page_size', int, description='Number of items per page (max 100)'),
        ],
        responses={200: AppointmentListSerializer(many=True)}
    )
    def list(self, request):
        """List appointments with optional filters."""
        queryset = self.get_queryset()
        
        # Apply filters
        customer_id = request.query_params.get('customer_id')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        
        service_id = request.query_params.get('service_id')
        if service_id:
            queryset = queryset.filter(service_id=service_id)
        
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        from_dt_str = request.query_params.get('from_dt')
        if from_dt_str:
            try:
                from_dt = datetime.fromisoformat(from_dt_str.replace('Z', '+00:00'))
                queryset = queryset.filter(start_dt__gte=from_dt)
            except ValueError:
                pass
        
        to_dt_str = request.query_params.get('to_dt')
        if to_dt_str:
            try:
                to_dt = datetime.fromisoformat(to_dt_str.replace('Z', '+00:00'))
                queryset = queryset.filter(start_dt__lte=to_dt)
            except ValueError:
                pass
        
        # Paginate (ViewSets automatically use pagination_class from settings)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Create appointment",
        description="Create a new appointment with capacity validation",
        request=AppointmentCreateSerializer,
        responses={
            201: AppointmentDetailSerializer,
            400: OpenApiResponse(description="Validation error or no capacity")
        }
    )
    def create(self, request):
        """Create a new appointment with capacity validation."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create appointment using BookingService
        booking_service = BookingService(request.tenant)
        
        try:
            appointment = booking_service.create_appointment(
                customer_id=str(serializer.validated_data['customer_id']),
                service_id=str(serializer.validated_data['service_id']),
                start_dt=serializer.validated_data['start_dt'],
                end_dt=serializer.validated_data['end_dt'],
                variant_id=str(serializer.validated_data.get('variant_id')) if serializer.validated_data.get('variant_id') else None,
                notes=serializer.validated_data.get('notes'),
                status=serializer.validated_data.get('status', 'pending')
            )
        except (DjangoValidationError, Exception) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Return detail serializer
        detail_serializer = AppointmentDetailSerializer(appointment)
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)
    
    @extend_schema(
        summary="Get appointment details",
        description="Get detailed information about an appointment",
        responses={200: AppointmentDetailSerializer}
    )
    def retrieve(self, request, pk=None):
        """Get appointment details."""
        appointment = self.get_object()
        serializer = self.get_serializer(appointment)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Cancel appointment",
        description="Cancel an appointment",
        request=AppointmentCancelSerializer,
        responses={
            200: AppointmentDetailSerializer,
            400: OpenApiResponse(description="Cannot cancel appointment")
        }
    )
    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        """Cancel an appointment."""
        appointment = self.get_object()
        
        # Cancel using BookingService
        booking_service = BookingService(request.tenant)
        
        try:
            appointment = booking_service.cancel_appointment(str(appointment.id))
        except (DjangoValidationError, Exception) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = AppointmentDetailSerializer(appointment)
        return Response(serializer.data)
