"""
Tenant withdrawal API views with four-eyes approval.

Handles tenant withdrawals of their earnings from the wallet.
Customers do NOT withdraw - they only pay for products/services.
"""
import logging
from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from django.shortcuts import get_object_or_404

from apps.core.permissions import HasTenantScopes
from apps.tenants.models import Transaction
from apps.tenants.services.withdrawal_service import (
    WithdrawalService,
    WithdrawalError,
    InsufficientBalance
)

logger = logging.getLogger(__name__)


class WithdrawalOptionsView(APIView):
    """
    Get withdrawal options for tenant.
    
    GET /v1/wallet/withdrawal-options
    
    Returns available withdrawal methods, fees, minimums, and wallet balance.
    
    Required scope: finance:view
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'finance:view'}
    
    @extend_schema(
        summary="Get withdrawal options",
        description="""
Get available withdrawal options for tenant including:
- Available withdrawal methods (based on configured providers)
- Configured payout method
- Minimum withdrawal amounts by method
- Withdrawal fees by method
- Current wallet balance

**Required scope**: `finance:view`

**Use case**: Display withdrawal options to tenant before initiating withdrawal.
        """,
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'available_methods': {
                        'type': 'array',
                        'items': {'type': 'string'}
                    },
                    'configured_method': {
                        'type': 'object',
                        'nullable': True
                    },
                    'minimum_amounts': {'type': 'object'},
                    'fees': {'type': 'object'},
                    'wallet_balance': {'type': 'number'},
                    'currency': {'type': 'string'}
                }
            },
            403: {'description': 'Forbidden - Missing required scope'}
        },
        tags=['Tenant Withdrawals']
    )
    def get(self, request):
        """Get withdrawal options for tenant."""
        try:
            options = WithdrawalService.get_withdrawal_options(request.tenant)
            
            return Response(options, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(
                f"Error getting withdrawal options: {str(e)}",
                exc_info=True,
                extra={'tenant_id': str(request.tenant.id)}
            )
            return Response(
                {
                    'error': 'Failed to retrieve withdrawal options',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class InitiateWithdrawalView(APIView):
    """
    Initiate a withdrawal request.
    
    POST /v1/wallet/withdrawals
    
    Creates a pending withdrawal that requires approval from a different user.
    
    Required scope: finance:withdraw:initiate
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'finance:withdraw:initiate'}
    
    @extend_schema(
        summary="Initiate withdrawal request",
        description="""
Initiate a withdrawal request from tenant wallet.

**Required scope**: `finance:withdraw:initiate`

**Four-eyes approval**: Withdrawal must be approved by a different user with `finance:withdraw:approve` scope.

**Fees**: Tenant pays withdrawal fees (deducted from gross amount).

**Use case**: Tenant requests withdrawal of their earnings.
        """,
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'amount': {
                        'type': 'number',
                        'description': 'Gross withdrawal amount (includes fee)'
                    },
                    'method_type': {
                        'type': 'string',
                        'enum': ['mpesa', 'bank_transfer', 'till'],
                        'description': 'Withdrawal method'
                    },
                    'method_details': {
                        'type': 'object',
                        'description': 'Method-specific details'
                    },
                    'notes': {
                        'type': 'string',
                        'description': 'Optional notes'
                    }
                },
                'required': ['amount', 'method_type', 'method_details']
            }
        },
        examples=[
            OpenApiExample(
                'M-Pesa Withdrawal',
                value={
                    'amount': 1000.00,
                    'method_type': 'mpesa',
                    'method_details': {'phone_number': '254712345678'},
                    'notes': 'Monthly withdrawal'
                }
            ),
            OpenApiExample(
                'Bank Transfer',
                value={
                    'amount': 5000.00,
                    'method_type': 'bank_transfer',
                    'method_details': {
                        'account_number': '1234567890',
                        'bank_code': '063',
                        'account_name': 'Business Account'
                    }
                }
            ),
            OpenApiExample(
                'Till Withdrawal',
                value={
                    'amount': 2000.00,
                    'method_type': 'till',
                    'method_details': {'till_number': '123456'}
                }
            )
        ],
        responses={
            201: {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'transaction_id': {'type': 'string'},
                    'status': {'type': 'string'},
                    'amount': {'type': 'number'},
                    'fee': {'type': 'number'},
                    'net_amount': {'type': 'number'}
                }
            },
            400: {'description': 'Invalid request or insufficient balance'},
            403: {'description': 'Forbidden'},
            500: {'description': 'Internal server error'}
        },
        tags=['Tenant Withdrawals']
    )
    def post(self, request):
        """Initiate withdrawal request."""
        # Validate input
        amount = request.data.get('amount')
        method_type = request.data.get('method_type')
        method_details = request.data.get('method_details')
        notes = request.data.get('notes', '')
        
        if not amount or not method_type or not method_details:
            return Response(
                {'error': 'amount, method_type, and method_details are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            amount = Decimal(str(amount))
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid amount'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            transaction = WithdrawalService.initiate_withdrawal(
                tenant=request.tenant,
                amount=amount,
                method_type=method_type,
                method_details=method_details,
                initiated_by=request.user,
                notes=notes
            )
            
            return Response({
                'message': 'Withdrawal request initiated successfully',
                'transaction_id': str(transaction.id),
                'status': transaction.status,
                'amount': float(transaction.amount),
                'fee': float(transaction.fee),
                'net_amount': float(transaction.net_amount),
                'requires_approval': True
            }, status=status.HTTP_201_CREATED)
            
        except InsufficientBalance as e:
            return Response(
                {
                    'error': 'Insufficient balance',
                    'details': e.details if hasattr(e, 'details') else {}
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except WithdrawalError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(
                f"Error initiating withdrawal: {str(e)}",
                exc_info=True,
                extra={
                    'tenant_id': str(request.tenant.id),
                    'user_id': str(request.user.id),
                    'amount': float(amount)
                }
            )
            return Response(
                {'error': 'Failed to initiate withdrawal'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ApproveWithdrawalView(APIView):
    """
    Approve a pending withdrawal.
    
    POST /v1/wallet/withdrawals/{transaction_id}/approve
    
    Approves and processes a pending withdrawal (four-eyes approval).
    
    Required scope: finance:withdraw:approve
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'finance:withdraw:approve'}
    
    @extend_schema(
        summary="Approve withdrawal request",
        description="""
Approve and process a pending withdrawal request.

**Required scope**: `finance:withdraw:approve`

**Four-eyes approval**: Approver MUST be different from initiator.

**Processing**: Upon approval, the withdrawal is immediately processed through the payment provider.

**Use case**: Finance manager approves withdrawal initiated by another user.
        """,
        parameters=[
            OpenApiParameter(
                name='transaction_id',
                type=str,
                location=OpenApiParameter.PATH,
                description='Transaction UUID'
            )
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'transaction_id': {'type': 'string'},
                    'amount': {'type': 'number'},
                    'net_amount': {'type': 'number'},
                    'fee': {'type': 'number'},
                    'provider_response': {'type': 'object'}
                }
            },
            400: {'description': 'Invalid request or four-eyes violation'},
            403: {'description': 'Forbidden'},
            404: {'description': 'Transaction not found'},
            500: {'description': 'Processing failed'}
        },
        tags=['Tenant Withdrawals']
    )
    def post(self, request, transaction_id):
        """Approve withdrawal request."""
        # Get transaction (tenant-scoped)
        transaction = get_object_or_404(
            Transaction,
            id=transaction_id,
            tenant=request.tenant,
            transaction_type='withdrawal'
        )
        
        try:
            result = WithdrawalService.approve_withdrawal(
                transaction_obj=transaction,
                approved_by=request.user
            )
            
            return Response({
                'success': True,
                'message': 'Withdrawal approved and processed successfully',
                **result
            }, status=status.HTTP_200_OK)
            
        except WithdrawalError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(
                f"Error approving withdrawal: {str(e)}",
                exc_info=True,
                extra={
                    'tenant_id': str(request.tenant.id),
                    'user_id': str(request.user.id),
                    'transaction_id': str(transaction_id)
                }
            )
            return Response(
                {'error': 'Failed to approve withdrawal'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CancelWithdrawalView(APIView):
    """
    Cancel a pending withdrawal.
    
    POST /v1/wallet/withdrawals/{transaction_id}/cancel
    
    Cancels a pending withdrawal request.
    
    Required scope: finance:withdraw:initiate OR finance:withdraw:approve
    """
    permission_classes = [HasTenantScopes]
    
    def check_permissions(self, request):
        """Allow either initiators or approvers to cancel."""
        if 'finance:withdraw:initiate' in request.scopes or 'finance:withdraw:approve' in request.scopes:
            self.required_scopes = set()  # Already checked
        else:
            self.required_scopes = {'finance:withdraw:initiate'}
        super().check_permissions(request)
    
    @extend_schema(
        summary="Cancel withdrawal request",
        description="""
Cancel a pending withdrawal request.

**Required scope**: `finance:withdraw:initiate` OR `finance:withdraw:approve`

**Use case**: Cancel a withdrawal before it's approved or if no longer needed.
        """,
        parameters=[
            OpenApiParameter(
                name='transaction_id',
                type=str,
                location=OpenApiParameter.PATH,
                description='Transaction UUID'
            )
        ],
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'reason': {
                        'type': 'string',
                        'description': 'Cancellation reason'
                    }
                }
            }
        },
        responses={
            200: {'description': 'Withdrawal canceled'},
            400: {'description': 'Cannot cancel (not pending)'},
            403: {'description': 'Forbidden'},
            404: {'description': 'Transaction not found'}
        },
        tags=['Tenant Withdrawals']
    )
    def post(self, request, transaction_id):
        """Cancel withdrawal request."""
        # Check permissions manually
        if 'finance:withdraw:initiate' not in request.scopes and 'finance:withdraw:approve' not in request.scopes:
            return Response(
                {'detail': 'Missing required scope: finance:withdraw:initiate or finance:withdraw:approve'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get transaction (tenant-scoped)
        transaction = get_object_or_404(
            Transaction,
            id=transaction_id,
            tenant=request.tenant,
            transaction_type='withdrawal'
        )
        
        reason = request.data.get('reason', 'Canceled by user')
        
        try:
            canceled_transaction = WithdrawalService.cancel_withdrawal(
                transaction_obj=transaction,
                canceled_by=request.user,
                reason=reason
            )
            
            return Response({
                'message': 'Withdrawal canceled successfully',
                'transaction_id': str(canceled_transaction.id),
                'status': canceled_transaction.status
            }, status=status.HTTP_200_OK)
            
        except WithdrawalError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(
                f"Error canceling withdrawal: {str(e)}",
                exc_info=True,
                extra={
                    'tenant_id': str(request.tenant.id),
                    'user_id': str(request.user.id),
                    'transaction_id': str(transaction_id)
                }
            )
            return Response(
                {'error': 'Failed to cancel withdrawal'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class WithdrawalListView(APIView):
    """
    List withdrawal transactions.
    
    GET /v1/wallet/withdrawals
    
    Returns list of withdrawal transactions with filtering.
    
    Required scope: finance:view
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'finance:view'}
    
    @extend_schema(
        summary="List withdrawal transactions",
        description="""
List withdrawal transactions for tenant with optional filtering.

**Required scope**: `finance:view`

**Use case**: View withdrawal history and pending approvals.
        """,
        parameters=[
            OpenApiParameter(
                name='status',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Filter by status (pending, completed, failed, canceled)',
                required=False
            ),
            OpenApiParameter(
                name='limit',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Number of results (default 50)',
                required=False
            )
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'count': {'type': 'integer'},
                    'results': {
                        'type': 'array',
                        'items': {'type': 'object'}
                    }
                }
            },
            403: {'description': 'Forbidden'}
        },
        tags=['Tenant Withdrawals']
    )
    def get(self, request):
        """List withdrawal transactions."""
        # Get query params
        status_filter = request.query_params.get('status')
        limit = int(request.query_params.get('limit', 50))
        
        # Query transactions
        queryset = Transaction.objects.filter(
            tenant=request.tenant,
            transaction_type='withdrawal'
        ).order_by('-created_at')
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        queryset = queryset[:limit]
        
        # Serialize results
        results = []
        for txn in queryset:
            results.append({
                'id': str(txn.id),
                'amount': float(txn.amount),
                'fee': float(txn.fee),
                'net_amount': float(txn.net_amount),
                'status': txn.status,
                'method_type': txn.metadata.get('method_type'),
                'initiated_by': str(txn.initiated_by.id) if txn.initiated_by else None,
                'approved_by': str(txn.approved_by.id) if txn.approved_by else None,
                'created_at': txn.created_at.isoformat(),
                'notes': txn.notes
            })
        
        return Response({
            'count': len(results),
            'results': results
        }, status=status.HTTP_200_OK)
