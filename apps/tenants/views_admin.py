"""
Admin API views for platform operators.

Provides endpoints for:
- Tenant management
- Subscription tier changes
- Subscription waivers
- Withdrawal processing
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
import logging

from apps.tenants.models import Tenant, Subscription, SubscriptionTier, SubscriptionEvent, Transaction
from apps.tenants.serializers import (
    AdminTenantListSerializer,
    AdminTenantDetailSerializer,
    AdminSubscriptionChangeSerializer,
    AdminSubscriptionWaiverSerializer,
    TransactionSerializer,
    WithdrawalProcessSerializer
)
from apps.tenants.services import WalletService
from apps.core.exceptions import TuliaException

logger = logging.getLogger(__name__)


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for list endpoints."""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100


class AdminTenantListView(APIView):
    """
    List all tenants (admin only).
    
    GET /v1/admin/tenants
    
    Required: Platform operator (superuser) access
    """
    # permission_classes = [IsAuthenticated]  # Removed - auth handled by middleware
    
    @extend_schema(
        summary="List all tenants (admin)",
        description="Retrieve paginated list of all tenants with subscription and wallet info. "
                    "Requires platform operator (superuser) access.",
        parameters=[
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by tenant status',
                enum=['active', 'trial', 'trial_expired', 'suspended', 'canceled']
            ),
            OpenApiParameter(
                name='tier',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description='Filter by subscription tier ID'
            ),
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Search by tenant name or slug'
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
                description='Number of items per page (max 100)'
            ),
        ],
        responses={
            200: AdminTenantListSerializer(many=True),
            403: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Admin - Tenants']
    )
    def get(self, request):
        """List all tenants with filtering."""
        # Check if user is superuser (platform operator)
        if not request.user or not hasattr(request.user, 'is_superuser') or not request.user.is_superuser:
            return Response(
                {'error': 'This endpoint requires platform operator access'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Start with all tenants
        queryset = Tenant.objects.all().select_related('subscription_tier')
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        tier_filter = request.query_params.get('tier')
        if tier_filter:
            queryset = queryset.filter(subscription_tier_id=tier_filter)
        
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                name__icontains=search
            ) | queryset.filter(
                slug__icontains=search
            )
        
        # Paginate results
        paginator = StandardResultsSetPagination()
        paginated_tenants = paginator.paginate_queryset(queryset, request)
        
        # Serialize
        serializer = AdminTenantListSerializer(paginated_tenants, many=True)
        
        return paginator.get_paginated_response(serializer.data)


class AdminTenantDetailView(APIView):
    """
    Get tenant details (admin only).
    
    GET /v1/admin/tenants/{id}
    
    Required: Platform operator (superuser) access
    """
    # permission_classes = [IsAuthenticated]  # Removed - auth handled by middleware
    
    @extend_schema(
        summary="Get tenant details (admin)",
        description="Retrieve detailed information about a specific tenant. "
                    "Requires platform operator (superuser) access.",
        responses={
            200: AdminTenantDetailSerializer,
            403: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            },
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Admin - Tenants']
    )
    def get(self, request, tenant_id):
        """Get tenant details."""
        # Check if user is superuser (platform operator)
        if not request.user or not hasattr(request.user, 'is_superuser') or not request.user.is_superuser:
            return Response(
                {'error': 'This endpoint requires platform operator access'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            tenant = Tenant.objects.select_related('subscription_tier').get(id=tenant_id)
            serializer = AdminTenantDetailSerializer(tenant)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        except Tenant.DoesNotExist:
            return Response(
                {'error': 'Tenant not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class AdminSubscriptionChangeView(APIView):
    """
    Change tenant subscription tier (admin only).
    
    POST /v1/admin/tenants/{id}/subscription
    
    Required: Platform operator (superuser) access
    """
    # permission_classes = [IsAuthenticated]  # Removed - auth handled by middleware
    
    @extend_schema(
        summary="Change tenant subscription tier (admin)",
        description="""
Change a tenant's subscription tier. This will:
- Update the tenant's subscription_tier
- Create or update the Subscription record
- Log a SubscriptionEvent for audit trail
- Apply new feature limits immediately

**Example curl:**
```bash
curl -X POST https://api.tulia.ai/v1/admin/tenants/{tenant_id}/subscription \\
  -H "Authorization: Bearer {admin_token}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "tier_id": "tier-uuid",
    "billing_cycle": "monthly",
    "notes": "Upgraded to Growth tier"
  }'
```

Requires platform operator (superuser) access.
        """,
        request=AdminSubscriptionChangeSerializer,
        responses={
            200: AdminTenantDetailSerializer,
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
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Admin - Tenants']
    )
    def post(self, request, tenant_id):
        """Change subscription tier."""
        # Check if user is superuser (platform operator)
        if not request.user or not hasattr(request.user, 'is_superuser') or not request.user.is_superuser:
            return Response(
                {'error': 'This endpoint requires platform operator access'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validate request data
        serializer = AdminSubscriptionChangeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Invalid request data',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = serializer.validated_data
        tier_id = data['tier_id']
        billing_cycle = data.get('billing_cycle', 'monthly')
        notes = data.get('notes', '')
        
        try:
            # Get tenant
            tenant = Tenant.objects.get(id=tenant_id)
            
            # Get new tier
            new_tier = SubscriptionTier.objects.get(id=tier_id)
            
            # Store old tier for event logging
            old_tier = tenant.subscription_tier
            
            # Update tenant tier
            tenant.subscription_tier = new_tier
            tenant.save(update_fields=['subscription_tier', 'updated_at'])
            
            # Create or update subscription
            from django.utils import timezone
            from datetime import timedelta
            
            subscription, created = Subscription.objects.get_or_create(
                tenant=tenant,
                defaults={
                    'tier': new_tier,
                    'billing_cycle': billing_cycle,
                    'status': 'active',
                    'start_date': timezone.now().date(),
                    'next_billing_date': timezone.now().date() + timedelta(days=30 if billing_cycle == 'monthly' else 365)
                }
            )
            
            if not created:
                # Update existing subscription
                subscription.tier = new_tier
                subscription.billing_cycle = billing_cycle
                subscription.save(update_fields=['tier', 'billing_cycle', 'updated_at'])
            
            # Log subscription event
            SubscriptionEvent.objects.create(
                subscription=subscription,
                event_type='tier_changed',
                metadata={
                    'previous_tier': old_tier.name if old_tier else None,
                    'new_tier': new_tier.name,
                    'changed_by': 'admin',
                    'admin_user': request.user.email,
                    'notes': notes
                }
            )
            
            # If new tier has payment facilitation and tenant doesn't have wallet, create one
            if new_tier.payment_facilitation:
                from apps.tenants.services import WalletService
                WalletService.get_or_create_wallet(tenant)
            
            # Log to audit trail
            from apps.rbac.models import AuditLog
            AuditLog.log_action(
                action='subscription_tier_changed',
                user=request.user,
                tenant=tenant,
                target_type='Tenant',
                target_id=tenant.id,
                diff={
                    'previous_tier': old_tier.name if old_tier else None,
                    'new_tier': new_tier.name,
                    'billing_cycle': billing_cycle,
                },
                metadata={'notes': notes},
                request=request
            )
            
            # Return updated tenant
            tenant.refresh_from_db()
            response_serializer = AdminTenantDetailSerializer(tenant)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        
        except Tenant.DoesNotExist:
            return Response(
                {'error': 'Tenant not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        except SubscriptionTier.DoesNotExist:
            return Response(
                {'error': 'Subscription tier not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        except Exception as e:
            logger.error(f"Error changing subscription tier: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Failed to change subscription tier',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdminSubscriptionWaiverView(APIView):
    """
    Waive or unwaive subscription fees (admin only).
    
    POST /v1/admin/tenants/{id}/subscription/waiver
    
    Required: Platform operator (superuser) access
    """
    # permission_classes = [IsAuthenticated]  # Removed - auth handled by middleware
    
    @extend_schema(
        summary="Waive subscription fees (admin)",
        description="""
Waive or unwaive subscription fees for a tenant. When waived:
- Tenant status remains 'active'
- No invoices are generated
- All tier features remain accessible
- Displayed as "Subscription Waived" in tenant dashboard

**Example curl:**
```bash
curl -X POST https://api.tulia.ai/v1/admin/tenants/{tenant_id}/subscription/waiver \\
  -H "Authorization: Bearer {admin_token}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "waived": true,
    "notes": "Strategic partnership - waive fees for 12 months"
  }'
```

Requires platform operator (superuser) access.
        """,
        request=AdminSubscriptionWaiverSerializer,
        responses={
            200: AdminTenantDetailSerializer,
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
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Admin - Tenants']
    )
    def post(self, request, tenant_id):
        """Waive or unwaive subscription fees."""
        # Check if user is superuser (platform operator)
        if not request.user or not hasattr(request.user, 'is_superuser') or not request.user.is_superuser:
            return Response(
                {'error': 'This endpoint requires platform operator access'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validate request data
        serializer = AdminSubscriptionWaiverSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Invalid request data',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = serializer.validated_data
        waived = data['waived']
        notes = data.get('notes', '')
        
        try:
            # Get tenant
            tenant = Tenant.objects.get(id=tenant_id)
            
            # Store old value
            old_waived = tenant.subscription_waived
            
            # Update waiver status
            tenant.subscription_waived = waived
            
            # If waiving and tenant is not active, set to active
            if waived and tenant.status != 'active':
                tenant.status = 'active'
            
            tenant.save(update_fields=['subscription_waived', 'status', 'updated_at'])
            
            # Log to subscription events if subscription exists
            if hasattr(tenant, 'subscription'):
                SubscriptionEvent.objects.create(
                    subscription=tenant.subscription,
                    event_type='tier_changed' if waived else 'reactivated',
                    metadata={
                        'waiver_changed': True,
                        'waived': waived,
                        'changed_by': 'admin',
                        'admin_user': request.user.email,
                        'notes': notes
                    }
                )
            
            # Log to audit trail
            from apps.rbac.models import AuditLog
            AuditLog.log_action(
                action='subscription_waiver_changed',
                user=request.user,
                tenant=tenant,
                target_type='Tenant',
                target_id=tenant.id,
                diff={
                    'previous_waived': old_waived,
                    'new_waived': waived,
                },
                metadata={'notes': notes},
                request=request
            )
            
            # Return updated tenant
            tenant.refresh_from_db()
            response_serializer = AdminTenantDetailSerializer(tenant)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        
        except Tenant.DoesNotExist:
            return Response(
                {'error': 'Tenant not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        except Exception as e:
            logger.error(f"Error changing subscription waiver: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Failed to change subscription waiver',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdminWithdrawalProcessView(APIView):
    """
    Process pending withdrawal (admin only).
    
    POST /v1/admin/wallet/withdrawals/{id}/process
    
    Required: Platform operator (superuser) access
    
    Note: This is for admin processing. For four-eyes approval within a tenant,
    use /v1/wallet/withdrawals/{id}/approve instead.
    """
    # permission_classes = [IsAuthenticated]  # Removed - auth handled by middleware
    
    @extend_schema(
        summary="Process withdrawal (admin)",
        description="""
Complete or fail a pending withdrawal. This is for platform operator processing.

**Actions:**
- `complete`: Mark withdrawal as completed (funds transferred)
- `fail`: Mark withdrawal as failed and credit amount back to wallet

**Example curl:**
```bash
curl -X POST https://api.tulia.ai/v1/admin/wallet/withdrawals/{transaction_id}/process \\
  -H "Authorization: Bearer {admin_token}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "action": "complete",
    "notes": "Bank transfer completed"
  }'
```

For four-eyes approval within a tenant, use `/v1/wallet/withdrawals/{id}/approve` instead.

Requires platform operator (superuser) access.
        """,
        request=WithdrawalProcessSerializer,
        responses={
            200: TransactionSerializer,
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
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Admin - Withdrawals']
    )
    def post(self, request, transaction_id):
        """Process withdrawal."""
        # Check if user is superuser (platform operator)
        if not request.user or not hasattr(request.user, 'is_superuser') or not request.user.is_superuser:
            return Response(
                {'error': 'This endpoint requires platform operator access'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validate request data
        serializer = WithdrawalProcessSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Invalid request data',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = serializer.validated_data
        action = data['action']
        reason = data.get('reason', '')
        notes = data.get('notes', '')
        
        try:
            # Get transaction
            transaction = Transaction.objects.get(id=transaction_id)
            
            # Process based on action
            if action == 'complete':
                transaction = WalletService.complete_withdrawal(
                    transaction_id=transaction_id,
                    notes=notes
                )
            else:  # fail
                transaction = WalletService.fail_withdrawal(
                    transaction_id=transaction_id,
                    reason=reason,
                    notes=notes
                )
            
            # Log to audit trail
            from apps.rbac.models import AuditLog
            AuditLog.log_action(
                action=f'withdrawal_{action}d',
                user=request.user,
                tenant=transaction.tenant,
                target_type='Transaction',
                target_id=transaction.id,
                diff={
                    'amount': float(transaction.amount),
                    'currency': transaction.currency,
                    'status': transaction.status,
                    'action': action,
                },
                metadata={'reason': reason, 'notes': notes},
                request=request
            )
            
            # Serialize response
            response_serializer = TransactionSerializer(transaction)
            
            return Response(
                response_serializer.data,
                status=status.HTTP_200_OK
            )
        
        except Transaction.DoesNotExist:
            return Response(
                {'error': 'Transaction not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        except TuliaException as e:
            return Response(
                {
                    'error': e.message,
                    'details': e.details
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        except Exception as e:
            logger.error(f"Error processing withdrawal: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Failed to process withdrawal',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
