"""
Customer payment preference API views.

Handles customer payment method preferences and checkout options.
Customers use these to pay for products/services from tenants.
"""
import logging
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from django.shortcuts import get_object_or_404

from apps.core.permissions import HasTenantScopes
from apps.tenants.models import Customer
from apps.tenants.services.customer_payment_service import (
    CustomerPaymentService,
    PaymentPreferenceError
)

logger = logging.getLogger(__name__)


class CustomerPaymentPreferencesView(APIView):
    """
    Get customer payment preferences.
    
    GET /v1/customers/{customer_id}/payment-preferences
    
    Returns customer's preferred provider, saved methods, and available providers.
    
    Required scope: conversations:view (customer data access)
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'conversations:view'}
    
    @extend_schema(
        summary="Get customer payment preferences",
        description="""
Get payment preferences for a customer including:
- Preferred payment provider
- Saved payment methods
- Available payment providers for this tenant

**Required scope**: `conversations:view`

**Use case**: Display customer's payment preferences in conversation or checkout.
        """,
        parameters=[
            OpenApiParameter(
                name='customer_id',
                type=str,
                location=OpenApiParameter.PATH,
                description='Customer UUID'
            )
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'preferred_provider': {
                        'type': 'string',
                        'nullable': True,
                        'enum': ['mpesa', 'paystack', 'pesapal', 'stripe']
                    },
                    'saved_methods': {
                        'type': 'array',
                        'items': {'type': 'object'}
                    },
                    'available_providers': {
                        'type': 'array',
                        'items': {'type': 'string'}
                    }
                }
            },
            403: {'description': 'Forbidden - Missing required scope'},
            404: {'description': 'Customer not found'}
        },
        tags=['Customer Payments']
    )
    def get(self, request, customer_id):
        """Get customer payment preferences."""
        # Get customer (tenant-scoped)
        customer = get_object_or_404(
            Customer,
            id=customer_id,
            tenant=request.tenant
        )
        
        try:
            preferences = CustomerPaymentService.get_payment_preferences(customer)
            
            return Response(preferences, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(
                f"Error getting payment preferences: {str(e)}",
                exc_info=True,
                extra={
                    'customer_id': str(customer_id),
                    'tenant_id': str(request.tenant.id)
                }
            )
            return Response(
                {
                    'error': 'Failed to retrieve payment preferences',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CustomerPaymentCheckoutOptionsView(APIView):
    """
    Get checkout options for customer payment.
    
    GET /v1/customers/{customer_id}/checkout-options?amount=1000
    
    Returns checkout options with customer preferences for paying for products/services.
    
    Required scope: conversations:view
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'conversations:view'}
    
    @extend_schema(
        summary="Get customer checkout options",
        description="""
Get checkout options for customer including preferred method and available providers.

**Required scope**: `conversations:view`

**Use case**: Present payment options when customer is checking out to pay for products/services.
        """,
        parameters=[
            OpenApiParameter(
                name='customer_id',
                type=str,
                location=OpenApiParameter.PATH,
                description='Customer UUID'
            ),
            OpenApiParameter(
                name='amount',
                type=float,
                location=OpenApiParameter.QUERY,
                description='Payment amount',
                required=True
            )
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'preferred_provider': {'type': 'string', 'nullable': True},
                    'preferred_method': {'type': 'object', 'nullable': True},
                    'available_providers': {'type': 'array'},
                    'saved_methods': {'type': 'array'},
                    'can_change_provider': {'type': 'boolean'},
                    'amount': {'type': 'number'}
                }
            },
            400: {'description': 'Invalid amount'},
            403: {'description': 'Forbidden'},
            404: {'description': 'Customer not found'}
        },
        tags=['Customer Payments']
    )
    def get(self, request, customer_id):
        """Get checkout options for customer."""
        # Get customer (tenant-scoped)
        customer = get_object_or_404(
            Customer,
            id=customer_id,
            tenant=request.tenant
        )
        
        # Get amount from query params
        try:
            amount = float(request.query_params.get('amount', 0))
            if amount <= 0:
                return Response(
                    {'error': 'Amount must be greater than 0'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid amount parameter'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            options = CustomerPaymentService.get_checkout_options(customer, amount)
            
            return Response(options, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(
                f"Error getting checkout options: {str(e)}",
                exc_info=True,
                extra={
                    'customer_id': str(customer_id),
                    'tenant_id': str(request.tenant.id),
                    'amount': amount
                }
            )
            return Response(
                {
                    'error': 'Failed to retrieve checkout options',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    tags=['Customer Payments'],
    summary='Set customer preferred payment provider',
    description='''
Set customer's preferred payment provider for future checkouts.

**Required scope**: `conversations:view`

**Use case**: Customer selects their preferred payment method during or after checkout.
    ''',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'provider': {
                    'type': 'string',
                    'enum': ['mpesa', 'paystack', 'pesapal', 'stripe']
                }
            },
            'required': ['provider']
        }
    },
    responses={
        200: {'description': 'Preferred provider updated'},
        400: {'description': 'Invalid provider or not configured'},
        403: {'description': 'Forbidden'},
        404: {'description': 'Customer not found'}
    }
)
@api_view(['PUT'])
@permission_classes([HasTenantScopes])
def set_preferred_provider(request, customer_id):
    """
    Set customer's preferred payment provider.
    
    Required scope: conversations:view
    """
    if 'conversations:view' not in request.scopes:
        return Response(
            {'detail': 'Missing required scope: conversations:view'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Get customer (tenant-scoped)
    customer = get_object_or_404(
        Customer,
        id=customer_id,
        tenant=request.tenant
    )
    
    provider = request.data.get('provider')
    if not provider:
        return Response(
            {'error': 'provider is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        updated_customer = CustomerPaymentService.set_preferred_provider(
            customer, provider
        )
        
        preferences = CustomerPaymentService.get_payment_preferences(updated_customer)
        
        return Response({
            'message': 'Preferred provider updated successfully',
            'preferences': preferences
        }, status=status.HTTP_200_OK)
        
    except PaymentPreferenceError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(
            f"Error setting preferred provider: {str(e)}",
            exc_info=True,
            extra={
                'customer_id': str(customer_id),
                'tenant_id': str(request.tenant.id),
                'provider': provider
            }
        )
        return Response(
            {'error': 'Failed to update preferred provider'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Customer Payments'],
    summary='Save customer payment method',
    description='''
Save a payment method for customer to reuse in future payments.

**Required scope**: `conversations:view`

**Use case**: After successful payment, save the method for faster checkout next time.
    ''',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'provider': {
                    'type': 'string',
                    'enum': ['mpesa', 'paystack', 'pesapal', 'stripe']
                },
                'details': {
                    'type': 'object',
                    'description': 'Provider-specific payment method details'
                },
                'set_as_default': {
                    'type': 'boolean',
                    'default': False
                }
            },
            'required': ['provider', 'details']
        }
    },
    examples=[
        OpenApiExample(
            'M-Pesa',
            value={
                'provider': 'mpesa',
                'details': {'phone_number': '254712345678'},
                'set_as_default': True
            }
        ),
        OpenApiExample(
            'Paystack',
            value={
                'provider': 'paystack',
                'details': {
                    'authorization_code': 'AUTH_xxx',
                    'last4': '1234',
                    'bank': 'Access Bank'
                }
            }
        )
    ],
    responses={
        201: {'description': 'Payment method saved'},
        400: {'description': 'Invalid method details'},
        403: {'description': 'Forbidden'},
        404: {'description': 'Customer not found'}
    }
)
@api_view(['POST'])
@permission_classes([HasTenantScopes])
def save_payment_method(request, customer_id):
    """
    Save payment method for customer.
    
    Required scope: conversations:view
    """
    if 'conversations:view' not in request.scopes:
        return Response(
            {'detail': 'Missing required scope: conversations:view'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Get customer (tenant-scoped)
    customer = get_object_or_404(
        Customer,
        id=customer_id,
        tenant=request.tenant
    )
    
    provider = request.data.get('provider')
    details = request.data.get('details')
    set_as_default = request.data.get('set_as_default', False)
    
    if not provider or not details:
        return Response(
            {'error': 'provider and details are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        updated_customer = CustomerPaymentService.save_payment_method(
            customer, provider, details
        )
        
        # Set as default if requested
        if set_as_default:
            method_id = CustomerPaymentService._get_method_id(provider, details)
            updated_customer = CustomerPaymentService.set_default_method(
                updated_customer, method_id
            )
        
        preferences = CustomerPaymentService.get_payment_preferences(updated_customer)
        
        return Response({
            'message': 'Payment method saved successfully',
            'preferences': preferences
        }, status=status.HTTP_201_CREATED)
        
    except PaymentPreferenceError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(
            f"Error saving payment method: {str(e)}",
            exc_info=True,
            extra={
                'customer_id': str(customer_id),
                'tenant_id': str(request.tenant.id),
                'provider': provider
            }
        )
        return Response(
            {'error': 'Failed to save payment method'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Customer Payments'],
    summary='Remove customer payment method',
    description='''
Remove a saved payment method.

**Required scope**: `conversations:view`
    ''',
    responses={
        200: {'description': 'Payment method removed'},
        400: {'description': 'Method not found'},
        403: {'description': 'Forbidden'},
        404: {'description': 'Customer not found'}
    }
)
@api_view(['DELETE'])
@permission_classes([HasTenantScopes])
def remove_payment_method(request, customer_id, method_id):
    """
    Remove saved payment method.
    
    Required scope: conversations:view
    """
    if 'conversations:view' not in request.scopes:
        return Response(
            {'detail': 'Missing required scope: conversations:view'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Get customer (tenant-scoped)
    customer = get_object_or_404(
        Customer,
        id=customer_id,
        tenant=request.tenant
    )
    
    try:
        updated_customer = CustomerPaymentService.remove_payment_method(
            customer, method_id
        )
        
        preferences = CustomerPaymentService.get_payment_preferences(updated_customer)
        
        return Response({
            'message': 'Payment method removed successfully',
            'preferences': preferences
        }, status=status.HTTP_200_OK)
        
    except PaymentPreferenceError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(
            f"Error removing payment method: {str(e)}",
            exc_info=True,
            extra={
                'customer_id': str(customer_id),
                'tenant_id': str(request.tenant.id),
                'method_id': method_id
            }
        )
        return Response(
            {'error': 'Failed to remove payment method'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Customer Payments'],
    summary='Set default payment method',
    description='''
Set a saved payment method as default for future checkouts.

**Required scope**: `conversations:view`
    ''',
    responses={
        200: {'description': 'Default method updated'},
        400: {'description': 'Method not found'},
        403: {'description': 'Forbidden'},
        404: {'description': 'Customer not found'}
    }
)
@api_view(['PUT'])
@permission_classes([HasTenantScopes])
def set_default_payment_method(request, customer_id, method_id):
    """
    Set default payment method.
    
    Required scope: conversations:view
    """
    if 'conversations:view' not in request.scopes:
        return Response(
            {'detail': 'Missing required scope: conversations:view'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Get customer (tenant-scoped)
    customer = get_object_or_404(
        Customer,
        id=customer_id,
        tenant=request.tenant
    )
    
    try:
        updated_customer = CustomerPaymentService.set_default_method(
            customer, method_id
        )
        
        preferences = CustomerPaymentService.get_payment_preferences(updated_customer)
        
        return Response({
            'message': 'Default payment method updated successfully',
            'preferences': preferences
        }, status=status.HTTP_200_OK)
        
    except PaymentPreferenceError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(
            f"Error setting default method: {str(e)}",
            exc_info=True,
            extra={
                'customer_id': str(customer_id),
                'tenant_id': str(request.tenant.id),
                'method_id': method_id
            }
        )
        return Response(
            {'error': 'Failed to set default method'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
