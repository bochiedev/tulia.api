"""
Payment features API views for tenant payment facilitation info.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema
import logging

from apps.core.permissions import HasTenantScopes
from apps.tenants.services.payment_facilitation_service import PaymentFacilitationService

logger = logging.getLogger(__name__)


class PaymentFeaturesView(APIView):
    """
    Get payment features information for authenticated tenant.
    
    GET /v1/payment-features
    
    Returns information about payment facilitation status, wallet availability,
    and transaction fees for the tenant's subscription tier.
    
    Required scope: finance:view
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'finance:view'}
    
    @extend_schema(
        summary="Get payment features info",
        description="""
Get information about payment features for the authenticated tenant.

Returns:
- Whether payment facilitation is enabled for the tenant's tier
- Wallet availability and balance (if applicable)
- Transaction fee percentage
- Current subscription tier

This endpoint helps frontends determine which payment features to display.
        """,
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'payment_facilitation_enabled': {
                        'type': 'boolean',
                        'description': 'Whether payment facilitation is enabled for this tier'
                    },
                    'has_wallet': {
                        'type': 'boolean',
                        'description': 'Whether tenant has a wallet'
                    },
                    'wallet_balance': {
                        'type': 'number',
                        'nullable': True,
                        'description': 'Current wallet balance (if has_wallet is true)'
                    },
                    'currency': {
                        'type': 'string',
                        'nullable': True,
                        'description': 'Wallet currency (if has_wallet is true)'
                    },
                    'transaction_fee_percentage': {
                        'type': 'number',
                        'description': 'Platform transaction fee percentage'
                    },
                    'tier_name': {
                        'type': 'string',
                        'description': 'Current subscription tier name'
                    }
                }
            },
            403: {'description': 'Forbidden - Missing required scope: finance:view'}
        },
        tags=['Payment Features']
    )
    def get(self, request):
        """Get payment features information."""
        tenant = request.tenant
        
        try:
            info = PaymentFacilitationService.get_payment_features_info(tenant)
            
            # Convert Decimal to float for JSON serialization
            if info['wallet_balance'] is not None:
                info['wallet_balance'] = float(info['wallet_balance'])
            info['transaction_fee_percentage'] = float(info['transaction_fee_percentage'])
            
            return Response(info, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(
                f"Error getting payment features info: {str(e)}",
                exc_info=True,
                extra={'tenant_id': str(tenant.id)}
            )
            return Response(
                {
                    'error': 'Failed to retrieve payment features information',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
