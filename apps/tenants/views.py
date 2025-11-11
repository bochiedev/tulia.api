"""
Tenant and wallet API views.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
import logging

from apps.tenants.models import Transaction
from apps.tenants.services import WalletService, InsufficientBalance, InvalidWithdrawalAmount
from apps.tenants.serializers import (
    WalletBalanceSerializer, TransactionSerializer,
    WithdrawalRequestSerializer, WithdrawalProcessSerializer,
    WithdrawalApprovalSerializer, TransactionFilterSerializer
)
from apps.core.exceptions import TuliaException
from apps.core.permissions import requires_scopes, HasTenantScopes, HasTenantScopes

logger = logging.getLogger(__name__)


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for list endpoints."""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100


class WalletBalanceView(APIView):
    """
    Get wallet balance for authenticated tenant.
    
    GET /v1/wallet/balance
    
    Required scope: finance:view
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'finance:view'}
    
    @extend_schema(
        summary="Get wallet balance",
        description="Retrieve current wallet balance for the authenticated tenant",
        responses={
            200: WalletBalanceSerializer,
            403: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'},
                    'details': {'type': 'object'}
                },
                'description': 'Forbidden - Missing required scope: finance:view'
            }
        },
        tags=['Wallet']
    )
    def get(self, request):
        """Get wallet balance."""
        tenant = request.tenant  # Injected by middleware
        
        try:
            wallet = WalletService.get_or_create_wallet(tenant)
            serializer = WalletBalanceSerializer({
                'balance': wallet.balance,
                'currency': wallet.currency,
                'minimum_withdrawal': wallet.minimum_withdrawal
            })
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error getting wallet balance: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Failed to retrieve wallet balance',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class WalletTransactionsView(APIView):
    """
    List wallet transactions for authenticated tenant.
    
    GET /v1/wallet/transactions
    
    Required scope: finance:view
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'finance:view'}
    
    @extend_schema(
        summary="List wallet transactions",
        description="Retrieve paginated list of wallet transactions with optional filtering",
        parameters=[
            OpenApiParameter(
                name='transaction_type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by transaction type',
                enum=['customer_payment', 'platform_fee', 'withdrawal', 'refund', 'adjustment']
            ),
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by status',
                enum=['pending', 'completed', 'failed', 'canceled']
            ),
            OpenApiParameter(
                name='start_date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Filter by start date (YYYY-MM-DD)'
            ),
            OpenApiParameter(
                name='end_date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Filter by end date (YYYY-MM-DD)'
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
            200: TransactionSerializer(many=True),
            400: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'},
                    'details': {'type': 'object'}
                }
            }
        },
        tags=['Wallet']
    )
    def get(self, request):
        """List transactions with filtering."""
        tenant = request.tenant  # Injected by middleware
        
        # Validate query parameters
        filter_serializer = TransactionFilterSerializer(data=request.query_params)
        if not filter_serializer.is_valid():
            return Response(
                {
                    'error': 'Invalid query parameters',
                    'details': filter_serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        filters = filter_serializer.validated_data
        
        try:
            # Get filtered transactions
            transactions = WalletService.get_transactions(
                tenant=tenant,
                transaction_type=filters.get('transaction_type'),
                status=filters.get('status'),
                start_date=filters.get('start_date'),
                end_date=filters.get('end_date')
            )
            
            # Paginate results
            paginator = StandardResultsSetPagination()
            paginator.page_size = filters.get('page_size', 50)
            paginated_transactions = paginator.paginate_queryset(transactions, request)
            
            # Serialize
            serializer = TransactionSerializer(paginated_transactions, many=True)
            
            return paginator.get_paginated_response(serializer.data)
        
        except Exception as e:
            logger.error(f"Error listing transactions: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Failed to retrieve transactions',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema_view(
    post=extend_schema(
        tags=['Finance - Withdrawals'],
        summary='Initiate withdrawal (four-eyes step 1)',
        description='''
Request a withdrawal from the tenant wallet. This is the first step of the four-eyes approval process.

**Required scope:** `finance:withdraw:initiate`

The amount is immediately debited from the wallet and a transaction is created with `pending_approval` status.
A different user with `finance:withdraw:approve` scope must approve the withdrawal.

**Four-eyes validation:** The initiating user CANNOT approve their own withdrawal.

**Example curl:**
```bash
curl -X POST https://api.tulia.ai/v1/wallet/withdraw \\
  -H "X-TENANT-ID: {tenant_id}" \\
  -H "X-TENANT-API-KEY: {api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "amount": 1000.00,
    "currency": "USD",
    "bank_account": "****1234",
    "notes": "Monthly payout"
  }'
```

**Response:** Transaction with `status: "pending_approval"` and `transaction_id` for approval.
        ''',
        request=WithdrawalRequestSerializer,
        responses={
            201: TransactionSerializer,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                'Withdrawal Request',
                value={
                    'amount': 1000.00,
                    'currency': 'USD',
                    'bank_account': '****1234',
                    'notes': 'Monthly payout'
                },
                request_only=True
            ),
            OpenApiExample(
                'Success Response',
                value={
                    'id': '123e4567-e89b-12d3-a456-426614174000',
                    'transaction_type': 'withdrawal',
                    'amount': 1000.00,
                    'currency': 'USD',
                    'status': 'pending_approval',
                    'initiated_by': {
                        'id': 'user-uuid-1',
                        'email': 'finance@example.com'
                    },
                    'created_at': '2025-11-10T12:00:00Z'
                },
                response_only=True
            )
        ]
    )
)
@requires_scopes('finance:withdraw:initiate')
class WalletWithdrawView(APIView):
    """
    Request withdrawal from wallet.
    
    POST /v1/wallet/withdraw
    
    Requires: finance:withdraw:initiate scope
    """
    def post(self, request):
        """Request withdrawal."""
        tenant = request.tenant  # Injected by middleware
        user = request.user  # Current authenticated user
        
        # Validate request data
        serializer = WithdrawalRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Invalid request data',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = serializer.validated_data
        amount = data['amount']
        
        # Prepare metadata
        metadata = {}
        if data.get('bank_account'):
            metadata['bank_account'] = data['bank_account']
        if data.get('notes'):
            metadata['notes'] = data['notes']
        
        try:
            # Request withdrawal with initiating user
            transaction = WalletService.request_withdrawal(
                tenant=tenant,
                amount=amount,
                initiated_by=user,
                metadata=metadata
            )
            
            # Log to audit trail
            from apps.rbac.models import AuditLog
            AuditLog.log_action(
                action='withdrawal_initiated',
                user=user,
                tenant=tenant,
                target_type='Transaction',
                target_id=transaction.id,
                diff={
                    'amount': float(amount),
                    'currency': transaction.currency,
                    'status': 'pending',
                },
                metadata=metadata,
                request=request
            )
            
            # Serialize response
            response_serializer = TransactionSerializer(transaction)
            
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
        
        except InvalidWithdrawalAmount as e:
            return Response(
                {
                    'error': e.message,
                    'details': e.details
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        except InsufficientBalance as e:
            return Response(
                {
                    'error': e.message,
                    'details': e.details
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        except Exception as e:
            logger.error(f"Error requesting withdrawal: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Failed to process withdrawal request',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema_view(
    post=extend_schema(
        tags=['Finance - Withdrawals'],
        summary='Approve withdrawal (four-eyes step 2)',
        description='''
Approve a pending withdrawal with four-eyes validation. This is the second step of the four-eyes approval process.

**Required scope:** `finance:withdraw:approve`

**Four-eyes validation:** The approver MUST be a different user than the initiator.
If the same user attempts approval, returns 409 Conflict.

Once approved, the withdrawal is processed and funds are transferred to the specified destination.

**Example curl:**
```bash
curl -X POST https://api.tulia.ai/v1/wallet/withdrawals/{transaction_id}/approve \\
  -H "X-TENANT-ID: {tenant_id}" \\
  -H "X-TENANT-API-KEY: {api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "notes": "Approved for monthly payout"
  }'
```

**Success:** Transaction status changes to `approved` and withdrawal is processed.

**Failure (same user):**
```json
{
  "error": "Four-eyes validation failed",
  "details": {
    "message": "Initiator and approver must be different users",
    "initiator_id": "user-uuid-1",
    "approver_id": "user-uuid-1"
  }
}
```
        ''',
        request=WithdrawalApprovalSerializer,
        responses={
            200: TransactionSerializer,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
            409: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                'Approval Request',
                value={
                    'notes': 'Approved for monthly payout'
                },
                request_only=True
            ),
            OpenApiExample(
                'Success Response',
                value={
                    'id': '123e4567-e89b-12d3-a456-426614174000',
                    'transaction_type': 'withdrawal',
                    'amount': 1000.00,
                    'currency': 'USD',
                    'status': 'approved',
                    'initiated_by': {
                        'id': 'user-uuid-1',
                        'email': 'finance@example.com'
                    },
                    'approved_by': {
                        'id': 'user-uuid-2',
                        'email': 'manager@example.com'
                    },
                    'approved_at': '2025-11-10T12:30:00Z',
                    'created_at': '2025-11-10T12:00:00Z'
                },
                response_only=True
            ),
            OpenApiExample(
                'Four-Eyes Violation',
                value={
                    'error': 'Four-eyes validation failed',
                    'details': {
                        'message': 'Initiator and approver must be different users',
                        'initiator_id': 'user-uuid-1',
                        'approver_id': 'user-uuid-1'
                    }
                },
                response_only=True,
                status_codes=['409']
            )
        ]
    )
)
@requires_scopes('finance:withdraw:approve')
class WalletWithdrawalApproveView(APIView):
    """
    Approve pending withdrawal with four-eyes validation.
    
    POST /v1/wallet/withdrawals/{id}/approve
    
    Requires: finance:withdraw:approve scope
    Validates that approver is different from initiator (four-eyes pattern).
    """
    
    def post(self, request, transaction_id):
        """Approve withdrawal with four-eyes validation."""
        user = request.user  # Current authenticated user
        
        # Validate request data
        serializer = WithdrawalApprovalSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Invalid request data',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = serializer.validated_data
        notes = data.get('notes', '')
        
        try:
            # Get transaction
            transaction = Transaction.objects.get(id=transaction_id)
            
            # Approve withdrawal with four-eyes validation
            transaction = WalletService.approve_withdrawal(
                transaction_id=transaction_id,
                approved_by=user,
                notes=notes
            )
            
            # Log to audit trail
            from apps.rbac.models import AuditLog
            AuditLog.log_action(
                action='withdrawal_approved',
                user=user,
                tenant=transaction.tenant,
                target_type='Transaction',
                target_id=transaction.id,
                diff={
                    'amount': float(transaction.amount),
                    'currency': transaction.currency,
                    'status': 'completed',
                    'initiated_by': transaction.initiated_by.email if transaction.initiated_by else None,
                    'approved_by': user.email,
                },
                metadata={'notes': notes},
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
        
        except ValueError as e:
            # Four-eyes validation failed
            return Response(
                {
                    'error': str(e),
                    'details': {
                        'message': 'The same user cannot initiate and approve a withdrawal',
                        'transaction_id': str(transaction_id)
                    }
                },
                status=status.HTTP_409_CONFLICT
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
            logger.error(f"Error approving withdrawal: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Failed to approve withdrawal',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdminWithdrawalProcessView(APIView):
    """
    Process pending withdrawal (admin only) - DEPRECATED.
    
    POST /v1/admin/wallet/withdrawals/{id}/process
    
    Use /v1/wallet/withdrawals/{id}/approve instead for four-eyes approval.
    """
    
    @extend_schema(
        summary="Process withdrawal (admin) - DEPRECATED",
        description="Complete or fail a pending withdrawal. "
                   "If failed, the amount is credited back to the wallet. "
                   "DEPRECATED: Use /v1/wallet/withdrawals/{id}/approve for four-eyes approval.",
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
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Admin'],
        deprecated=True
    )
    def post(self, request, transaction_id):
        """Process withdrawal."""
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
