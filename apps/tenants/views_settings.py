"""
API views for TenantSettings management.
"""
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import ratelimit
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes

from apps.core.permissions import HasTenantScopes
from apps.tenants.models import TenantSettings
from apps.tenants.serializers_settings import (
    TenantSettingsReadSerializer,
    WooCommerceCredentialsSerializer,
    ShopifyCredentialsSerializer,
    TwilioCredentialsSerializer,
    OpenAICredentialsSerializer,
    PaymentMethodSerializer,
    BusinessSettingsSerializer
)

logger = logging.getLogger(__name__)


@extend_schema(
    tags=['Settings'],
    summary='Get or update tenant settings',
    description='''
Get or update general tenant settings including notification preferences, feature flags, business hours, branding, and compliance settings.

**GET**: Requires `integrations:view` scope
**PATCH**: Requires `integrations:manage` scope

**Rate limit**: 60 requests/minute for PATCH
    ''',
    request=TenantSettingsReadSerializer,
    responses={
        200: TenantSettingsReadSerializer,
        403: OpenApiTypes.OBJECT,
        429: OpenApiTypes.OBJECT,
    },
    examples=[
        OpenApiExample(
            'Update Settings',
            value={
                'notification_settings': {
                    'email_enabled': True,
                    'sms_enabled': False
                },
                'feature_flags': {
                    'ai_enabled': True
                }
            },
            request_only=True
        )
    ]
)
@api_view(['GET', 'PATCH'])
@permission_classes([HasTenantScopes])
@ratelimit(key='user_or_ip', rate='60/m', method=['PATCH'])
def tenant_settings_view(request):
    """Get or update tenant settings."""
    settings, created = TenantSettings.objects.get_or_create(
        tenant=request.tenant
    )
    
    if request.method == 'GET':
        if 'integrations:view' not in request.scopes:
            return Response(
                {'detail': 'Missing required scope: integrations:view'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = TenantSettingsReadSerializer(settings)
        return Response(serializer.data)
    
    elif request.method == 'PATCH':
        if 'integrations:manage' not in request.scopes:
            return Response(
                {'detail': 'Missing required scope: integrations:manage'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        allowed_fields = [
            'notification_settings', 'feature_flags', 'business_hours',
            'branding', 'compliance_settings'
        ]
        
        updated_fields = []
        for field in allowed_fields:
            if field in request.data:
                setattr(settings, field, request.data[field])
                updated_fields.append(field)
        
        if updated_fields:
            settings.save(update_fields=updated_fields + ['updated_at'])
        
        serializer = TenantSettingsReadSerializer(settings)
        return Response(serializer.data)



@extend_schema(
    tags=['Integrations'],
    summary='Manage WooCommerce credentials',
    description='''
Manage WooCommerce integration credentials with validation.

**GET**: Return masked credentials and configuration status
**PUT**: Update credentials with validation against WooCommerce API
**DELETE**: Remove credentials

**Required scope**: `integrations:manage`
**Rate limit**: 60 requests/minute for PUT/DELETE

**Requirements**: 6.1, 6.2, 6.3, 6.4, 6.5, 11.1, 11.5
    ''',
    request=WooCommerceCredentialsSerializer,
    responses={
        200: OpenApiTypes.OBJECT,
        400: OpenApiTypes.OBJECT,
        403: OpenApiTypes.OBJECT,
        429: OpenApiTypes.OBJECT,
    },
    examples=[
        OpenApiExample(
            'Update Credentials',
            value={
                'store_url': 'https://mystore.com',
                'consumer_key': 'ck_1234567890abcdef',
                'consumer_secret': 'cs_1234567890abcdef'
            },
            request_only=True
        ),
        OpenApiExample(
            'Success Response',
            value={
                'message': 'WooCommerce credentials updated successfully',
                'configured': True,
                'credentials': {
                    'store_url': 'https://mystore.com',
                    'consumer_key_masked': 'ck_****cdef',
                    'has_consumer_secret': True,
                    'has_webhook_secret': True
                }
            },
            response_only=True
        ),
        OpenApiExample(
            'Validation Error',
            value={
                'error': 'Invalid WooCommerce credentials',
                'code': 'CREDENTIAL_VALIDATION_FAILED'
            },
            response_only=True,
            status_codes=['400']
        )
    ]
)
@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([HasTenantScopes])
@ratelimit(key='user_or_ip', rate='60/m', method=['POST', 'DELETE'])
def woocommerce_credentials_view(request):
    """
    Manage WooCommerce integration credentials.
    
    GET: Return masked credentials and configuration status
    POST: Create/update credentials with validation
    DELETE: Remove credentials
    
    Required scope: integrations:manage
    """
    if 'integrations:manage' not in request.scopes:
        return Response(
            {'detail': 'Missing required scope: integrations:manage'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    settings, created = TenantSettings.objects.get_or_create(
        tenant=request.tenant
    )
    
    if request.method == 'GET':
        # Return masked credentials
        if not settings.has_woocommerce_configured():
            return Response({
                'configured': False,
                'credentials': None
            })
        
        return Response({
            'configured': True,
            'credentials': {
                'store_url': settings.woo_store_url,
                'consumer_key_masked': _mask_credential(settings.woo_consumer_key, prefix='ck_'),
                'has_consumer_secret': bool(settings.woo_consumer_secret),
                'has_webhook_secret': bool(settings.woo_webhook_secret),
            },
            'integration_status': settings.integrations_status.get('woocommerce', {})
        })
    
    elif request.method == 'POST':
        from apps.tenants.services.settings_service import SettingsService, CredentialValidationError
        
        serializer = WooCommerceCredentialsSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            settings = SettingsService.update_woocommerce_credentials(
                tenant=request.tenant,
                store_url=serializer.validated_data['store_url'],
                consumer_key=serializer.validated_data['consumer_key'],
                consumer_secret=serializer.validated_data['consumer_secret'],
                user=request.user
            )
            
            return Response({
                'message': 'WooCommerce credentials updated successfully',
                'configured': True,
                'credentials': {
                    'store_url': settings.woo_store_url,
                    'consumer_key_masked': _mask_credential(settings.woo_consumer_key, prefix='ck_'),
                    'has_consumer_secret': bool(settings.woo_consumer_secret),
                    'has_webhook_secret': bool(settings.woo_webhook_secret),
                }
            }, status=status.HTTP_200_OK)
            
        except CredentialValidationError as e:
            return Response({
                'error': str(e),
                'code': 'CREDENTIAL_VALIDATION_FAILED'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        # Remove WooCommerce credentials
        with transaction.atomic():
            settings.woo_store_url = ''
            settings.woo_consumer_key = ''
            settings.woo_consumer_secret = ''
            settings.woo_webhook_secret = ''
            settings.update_integration_status('woocommerce', {'configured': False})
            settings.save()
            
            # Log to audit trail
            from apps.rbac.models import AuditLog
            AuditLog.log_action(
                action='woocommerce_credentials_removed',
                user=request.user,
                tenant=request.tenant,
                target_type='TenantSettings',
                target_id=settings.id,
                metadata={}
            )
        
        return Response({
            'message': 'WooCommerce credentials removed successfully'
        }, status=status.HTTP_200_OK)


@extend_schema(
    tags=['Integrations'],
    summary='Manage Shopify credentials',
    description='''
Manage Shopify integration credentials with validation.

**GET**: Return masked credentials and configuration status
**PUT**: Update credentials with validation against Shopify API
**DELETE**: Remove credentials

**Required scope**: `integrations:manage`
**Rate limit**: 60 requests/minute for PUT/DELETE

**Requirements**: 6.1, 6.2, 6.3, 6.4, 6.5, 11.1, 11.5
    ''',
    request=ShopifyCredentialsSerializer,
    responses={
        200: OpenApiTypes.OBJECT,
        400: OpenApiTypes.OBJECT,
        403: OpenApiTypes.OBJECT,
        429: OpenApiTypes.OBJECT,
    },
    examples=[
        OpenApiExample(
            'Update Credentials',
            value={
                'shop_domain': 'mystore.myshopify.com',
                'access_token': 'shpat_1234567890abcdef'
            },
            request_only=True
        ),
        OpenApiExample(
            'Success Response',
            value={
                'message': 'Shopify credentials updated successfully',
                'configured': True,
                'credentials': {
                    'shop_domain': 'mystore.myshopify.com',
                    'has_access_token': True,
                    'has_webhook_secret': True
                }
            },
            response_only=True
        )
    ]
)
@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([HasTenantScopes])
@ratelimit(key='user_or_ip', rate='60/m', method=['POST', 'DELETE'])
def shopify_credentials_view(request):
    """
    Manage Shopify integration credentials.
    
    GET: Return masked credentials and configuration status
    POST: Create/update credentials with validation
    DELETE: Remove credentials
    
    Required scope: integrations:manage
    """
    if 'integrations:manage' not in request.scopes:
        return Response(
            {'detail': 'Missing required scope: integrations:manage'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    settings, created = TenantSettings.objects.get_or_create(
        tenant=request.tenant
    )
    
    if request.method == 'GET':
        # Return masked credentials
        if not settings.has_shopify_configured():
            return Response({
                'configured': False,
                'credentials': None
            })
        
        return Response({
            'configured': True,
            'credentials': {
                'shop_domain': settings.shopify_shop_domain,
                'has_access_token': bool(settings.shopify_access_token),
                'has_webhook_secret': bool(settings.shopify_webhook_secret),
            },
            'integration_status': settings.integrations_status.get('shopify', {})
        })
    
    elif request.method == 'POST':
        from apps.tenants.services.settings_service import SettingsService, CredentialValidationError
        
        serializer = ShopifyCredentialsSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            settings = SettingsService.update_shopify_credentials(
                tenant=request.tenant,
                shop_domain=serializer.validated_data['shop_domain'],
                access_token=serializer.validated_data['access_token'],
                user=request.user
            )
            
            return Response({
                'message': 'Shopify credentials updated successfully',
                'configured': True,
                'credentials': {
                    'shop_domain': settings.shopify_shop_domain,
                    'has_access_token': bool(settings.shopify_access_token),
                    'has_webhook_secret': bool(settings.shopify_webhook_secret),
                }
            }, status=status.HTTP_200_OK)
            
        except CredentialValidationError as e:
            return Response({
                'error': str(e),
                'code': 'CREDENTIAL_VALIDATION_FAILED'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        # Remove Shopify credentials
        with transaction.atomic():
            settings.shopify_shop_domain = ''
            settings.shopify_access_token = ''
            settings.shopify_webhook_secret = ''
            settings.update_integration_status('shopify', {'configured': False})
            settings.save()
            
            # Log to audit trail
            from apps.rbac.models import AuditLog
            AuditLog.log_action(
                action='shopify_credentials_removed',
                user=request.user,
                tenant=request.tenant,
                target_type='TenantSettings',
                target_id=settings.id,
                metadata={}
            )
        
        return Response({
            'message': 'Shopify credentials removed successfully'
        }, status=status.HTTP_200_OK)


@extend_schema(
    tags=['Integrations'],
    summary='Manage Twilio credentials',
    description='''
Manage Twilio integration credentials with validation.

**GET**: Return masked credentials and configuration status
**PUT**: Update credentials with validation against Twilio API
**DELETE**: Remove credentials

**Required scope**: `integrations:manage`
**Rate limit**: 60 requests/minute for PUT/DELETE

**Requirements**: 5.1, 5.2, 5.3, 5.4, 5.5, 11.1, 11.5
    ''',
    request=TwilioCredentialsSerializer,
    responses={
        200: OpenApiTypes.OBJECT,
        400: OpenApiTypes.OBJECT,
        403: OpenApiTypes.OBJECT,
        429: OpenApiTypes.OBJECT,
    },
    examples=[
        OpenApiExample(
            'Update Credentials',
            value={
                'sid': 'AC1234567890abcdef',
                'token': 'your_auth_token',
                'webhook_secret': 'your_webhook_secret',
                'whatsapp_number': 'whatsapp:+1234567890'
            },
            request_only=True
        ),
        OpenApiExample(
            'Success Response',
            value={
                'message': 'Twilio credentials updated successfully',
                'configured': True,
                'credentials': {
                    'sid_masked': 'AC****cdef',
                    'has_token': True,
                    'has_webhook_secret': True
                }
            },
            response_only=True
        )
    ]
)
@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([HasTenantScopes])
@ratelimit(key='user_or_ip', rate='60/m', method=['POST', 'DELETE'])
def twilio_credentials_view(request):
    """
    Manage Twilio integration credentials.
    
    GET: Return masked credentials and configuration status
    POST: Create/update credentials with validation
    DELETE: Remove credentials
    
    Required scope: integrations:manage
    """
    if 'integrations:manage' not in request.scopes:
        return Response(
            {'detail': 'Missing required scope: integrations:manage'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    settings, created = TenantSettings.objects.get_or_create(
        tenant=request.tenant
    )
    
    if request.method == 'GET':
        # Return masked credentials
        if not settings.has_twilio_configured():
            return Response({
                'configured': False,
                'credentials': None
            })
        
        return Response({
            'configured': True,
            'credentials': {
                'sid_masked': _mask_credential(settings.twilio_sid, prefix='AC'),
                'has_token': bool(settings.twilio_token),
                'has_webhook_secret': bool(settings.twilio_webhook_secret),
            },
            'integration_status': settings.integrations_status.get('twilio', {})
        })
    
    elif request.method == 'POST':
        from apps.tenants.services.settings_service import SettingsService, CredentialValidationError
        
        serializer = TwilioCredentialsSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            settings = SettingsService.update_twilio_credentials(
                tenant=request.tenant,
                sid=serializer.validated_data['sid'],
                token=serializer.validated_data['token'],
                webhook_secret=serializer.validated_data.get('webhook_secret', ''),
                whatsapp_number=serializer.validated_data.get('whatsapp_number'),
                user=request.user
            )
            
            return Response({
                'message': 'Twilio credentials updated successfully',
                'configured': True,
                'credentials': {
                    'sid_masked': _mask_credential(settings.twilio_sid, prefix='AC'),
                    'has_token': bool(settings.twilio_token),
                    'has_webhook_secret': bool(settings.twilio_webhook_secret),
                }
            }, status=status.HTTP_200_OK)
            
        except CredentialValidationError as e:
            return Response({
                'error': str(e),
                'code': 'CREDENTIAL_VALIDATION_FAILED'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        # Remove Twilio credentials
        with transaction.atomic():
            settings.twilio_sid = ''
            settings.twilio_token = ''
            settings.twilio_webhook_secret = ''
            settings.update_integration_status('twilio', {'configured': False})
            settings.save()
            
            # Log to audit trail
            from apps.rbac.models import AuditLog
            AuditLog.log_action(
                action='twilio_credentials_removed',
                user=request.user,
                tenant=request.tenant,
                target_type='TenantSettings',
                target_id=settings.id,
                metadata={}
            )
        
        return Response({
            'message': 'Twilio credentials removed successfully'
        }, status=status.HTTP_200_OK)


def _mask_credential(value, prefix=''):
    """Mask credential showing only last 4 characters."""
    if not value:
        return None
    
    if len(value) <= 4:
        return '****'
    
    return f"{prefix}****{value[-4:]}"


@extend_schema(
    tags=['Integrations'],
    summary='Set OpenAI credentials',
    description='''
Set OpenAI API credentials for AI-powered features.

**Required scope**: `integrations:manage`
**Rate limit**: 60 requests/minute
    ''',
    request=OpenAICredentialsSerializer,
    responses={
        200: OpenApiTypes.OBJECT,
        400: OpenApiTypes.OBJECT,
        403: OpenApiTypes.OBJECT,
        429: OpenApiTypes.OBJECT,
    },
    examples=[
        OpenApiExample(
            'Set Credentials',
            value={
                'api_key': 'sk-1234567890abcdef',
                'org_id': 'org-1234567890'
            },
            request_only=True
        )
    ]
)
@api_view(['POST'])
@permission_classes([HasTenantScopes])
@ratelimit(key='user_or_ip', rate='60/m', method='POST')
def set_openai_credentials(request):
    """Set OpenAI API credentials."""
    if 'integrations:manage' not in request.scopes:
        return Response(
            {'detail': 'Missing required scope: integrations:manage'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    serializer = OpenAICredentialsSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    settings, created = TenantSettings.objects.get_or_create(
        tenant=request.tenant
    )
    
    with transaction.atomic():
        settings.openai_api_key = serializer.validated_data['api_key']
        settings.openai_org_id = serializer.validated_data.get('org_id', '')
        settings.save()
    
    return Response({
        'message': 'OpenAI credentials saved successfully'
    }, status=status.HTTP_200_OK)


@extend_schema(
    tags=['Integrations'],
    summary='List all integrations',
    description='''
List all integrations with their configuration status.

Returns masked credentials and last sync status for each integration (Twilio, WooCommerce, Shopify, OpenAI).

**Required scope**: `integrations:manage`

**Requirements**: 6.5, 11.1
    ''',
    responses={
        200: OpenApiTypes.OBJECT,
        403: OpenApiTypes.OBJECT,
    },
    examples=[
        OpenApiExample(
            'Success Response',
            value={
                'integrations': [
                    {
                        'name': 'twilio',
                        'display_name': 'Twilio',
                        'configured': True,
                        'credentials': {
                            'sid_masked': 'AC****cdef',
                            'has_token': True,
                            'has_webhook_secret': True
                        },
                        'status': {
                            'last_sync': '2024-01-15T10:30:00Z',
                            'status': 'active'
                        }
                    }
                ],
                'total_configured': 2
            },
            response_only=True
        )
    ]
)
@api_view(['GET'])
@permission_classes([HasTenantScopes])
def integrations_list_view(request):
    """
    List all integrations with their configuration status.
    
    Returns masked credentials and last sync status for each integration.
    
    Required scope: integrations:manage
    """
    if 'integrations:manage' not in request.scopes:
        return Response(
            {'detail': 'Missing required scope: integrations:manage'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    settings, created = TenantSettings.objects.get_or_create(
        tenant=request.tenant
    )
    
    integrations = []
    
    # Twilio
    if settings.has_twilio_configured():
        integrations.append({
            'name': 'twilio',
            'display_name': 'Twilio',
            'configured': True,
            'credentials': {
                'sid_masked': _mask_credential(settings.twilio_sid, prefix='AC'),
                'has_token': bool(settings.twilio_token),
                'has_webhook_secret': bool(settings.twilio_webhook_secret),
            },
            'status': settings.integrations_status.get('twilio', {})
        })
    else:
        integrations.append({
            'name': 'twilio',
            'display_name': 'Twilio',
            'configured': False,
            'credentials': None,
            'status': {}
        })
    
    # WooCommerce
    if settings.has_woocommerce_configured():
        integrations.append({
            'name': 'woocommerce',
            'display_name': 'WooCommerce',
            'configured': True,
            'credentials': {
                'store_url': settings.woo_store_url,
                'consumer_key_masked': _mask_credential(settings.woo_consumer_key, prefix='ck_'),
                'has_consumer_secret': bool(settings.woo_consumer_secret),
                'has_webhook_secret': bool(settings.woo_webhook_secret),
            },
            'status': settings.integrations_status.get('woocommerce', {})
        })
    else:
        integrations.append({
            'name': 'woocommerce',
            'display_name': 'WooCommerce',
            'configured': False,
            'credentials': None,
            'status': {}
        })
    
    # Shopify
    if settings.has_shopify_configured():
        integrations.append({
            'name': 'shopify',
            'display_name': 'Shopify',
            'configured': True,
            'credentials': {
                'shop_domain': settings.shopify_shop_domain,
                'has_access_token': bool(settings.shopify_access_token),
                'has_webhook_secret': bool(settings.shopify_webhook_secret),
            },
            'status': settings.integrations_status.get('shopify', {})
        })
    else:
        integrations.append({
            'name': 'shopify',
            'display_name': 'Shopify',
            'configured': False,
            'credentials': None,
            'status': {}
        })
    
    # OpenAI
    if settings.openai_api_key:
        integrations.append({
            'name': 'openai',
            'display_name': 'OpenAI',
            'configured': True,
            'credentials': {
                'has_api_key': True,
                'has_org_id': bool(settings.openai_org_id),
            },
            'status': {}
        })
    else:
        integrations.append({
            'name': 'openai',
            'display_name': 'OpenAI',
            'configured': False,
            'credentials': None,
            'status': {}
        })
    
    return Response({
        'integrations': integrations,
        'total_configured': sum(1 for i in integrations if i['configured'])
    })


@extend_schema(
    tags=['Finance - Payment Methods'],
    summary='Manage payment methods',
    description='''
Manage payment methods for subscription billing.

**GET**: List all payment methods with masked card details
**POST**: Add new payment method via Stripe tokenization

**Required scope**: `finance:manage`
**Rate limit**: 60 requests/minute for POST

**Requirements**: 7.1, 7.2, 7.3, 7.4, 7.5, 11.2, 11.5
    ''',
    request=OpenApiTypes.OBJECT,
    responses={
        200: OpenApiTypes.OBJECT,
        201: OpenApiTypes.OBJECT,
        400: OpenApiTypes.OBJECT,
        403: OpenApiTypes.OBJECT,
        429: OpenApiTypes.OBJECT,
    },
    examples=[
        OpenApiExample(
            'Add Payment Method',
            value={
                'stripe_token': 'tok_1234567890abcdef'
            },
            request_only=True
        ),
        OpenApiExample(
            'List Response',
            value={
                'stripe_customer_id': 'cus_1234567890',
                'payment_methods': [
                    {
                        'id': 'pm_1234567890',
                        'last4': '4242',
                        'brand': 'visa',
                        'exp_month': 12,
                        'exp_year': 2025,
                        'is_default': True
                    }
                ]
            },
            response_only=True
        )
    ]
)
@api_view(['GET', 'POST'])
@permission_classes([HasTenantScopes])
@ratelimit(key='user_or_ip', rate='60/m', method='POST')
def payment_methods_view(request):
    """
    Manage payment methods for subscription billing.
    
    GET: List all payment methods with masked card details
    POST: Add new payment method via Stripe tokenization
    
    Required scope: finance:manage
    """
    if 'finance:manage' not in request.scopes:
        return Response(
            {'detail': 'Missing required scope: finance:manage'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    settings, created = TenantSettings.objects.get_or_create(
        tenant=request.tenant
    )
    
    if request.method == 'GET':
        # Return list of payment methods
        serializer = PaymentMethodSerializer(settings.stripe_payment_methods or [], many=True)
        
        return Response({
            'stripe_customer_id': settings.stripe_customer_id,
            'payment_methods': serializer.data
        })
    
    elif request.method == 'POST':
        # Add new payment method
        from apps.tenants.services.settings_service import SettingsService, SettingsServiceError
        
        stripe_token = request.data.get('stripe_token')
        if not stripe_token:
            return Response({
                'error': 'stripe_token is required',
                'code': 'INVALID_INPUT'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            payment_method_data = SettingsService.add_payment_method(
                tenant=request.tenant,
                stripe_token=stripe_token,
                user=request.user
            )
            
            return Response({
                'message': 'Payment method added successfully',
                'payment_method': payment_method_data
            }, status=status.HTTP_201_CREATED)
            
        except SettingsServiceError as e:
            return Response({
                'error': str(e),
                'code': 'PAYMENT_METHOD_ERROR'
            }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=['Finance - Payment Methods'],
    summary='Set default payment method',
    description='''
Set a payment method as the default for subscription billing.

**Required scope**: `finance:manage`
**Rate limit**: 60 requests/minute

**Requirements**: 7.3, 11.2, 11.5
    ''',
    responses={
        200: OpenApiTypes.OBJECT,
        400: OpenApiTypes.OBJECT,
        403: OpenApiTypes.OBJECT,
        404: OpenApiTypes.OBJECT,
        429: OpenApiTypes.OBJECT,
    }
)
@api_view(['PUT'])
@permission_classes([HasTenantScopes])
@ratelimit(key='user_or_ip', rate='60/m', method='PUT')
def payment_method_set_default_view(request, payment_method_id):
    """
    Set default payment method.
    
    Required scope: finance:manage
    """
    if 'finance:manage' not in request.scopes:
        return Response(
            {'detail': 'Missing required scope: finance:manage'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    from apps.tenants.services.settings_service import SettingsService, SettingsServiceError
    
    try:
        settings = SettingsService.set_default_payment_method(
            tenant=request.tenant,
            payment_method_id=payment_method_id,
            user=request.user
        )
        
        serializer = PaymentMethodSerializer(settings.stripe_payment_methods or [], many=True)
        
        return Response({
            'message': 'Default payment method updated successfully',
            'payment_methods': serializer.data
        })
        
    except SettingsServiceError as e:
        return Response({
            'error': str(e),
            'code': 'PAYMENT_METHOD_ERROR'
        }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=['Finance - Payment Methods'],
    summary='Remove payment method',
    description='''
Remove a payment method.

Detaches payment method from Stripe and removes from tenant settings.

**Required scope**: `finance:manage`
**Rate limit**: 60 requests/minute

**Requirements**: 7.5, 11.2, 11.5
    ''',
    responses={
        200: OpenApiTypes.OBJECT,
        400: OpenApiTypes.OBJECT,
        403: OpenApiTypes.OBJECT,
        404: OpenApiTypes.OBJECT,
        429: OpenApiTypes.OBJECT,
    }
)
@api_view(['DELETE'])
@permission_classes([HasTenantScopes])
@ratelimit(key='user_or_ip', rate='60/m', method='DELETE')
def payment_method_remove_view(request, payment_method_id):
    """
    Remove payment method.
    
    Detaches payment method from Stripe and removes from tenant settings.
    
    Required scope: finance:manage
    """
    if 'finance:manage' not in request.scopes:
        return Response(
            {'detail': 'Missing required scope: finance:manage'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    from apps.tenants.services.settings_service import SettingsService, SettingsServiceError
    
    try:
        settings = SettingsService.remove_payment_method(
            tenant=request.tenant,
            payment_method_id=payment_method_id,
            user=request.user
        )
        
        serializer = PaymentMethodSerializer(settings.stripe_payment_methods or [], many=True)
        
        return Response({
            'message': 'Payment method removed successfully',
            'payment_methods': serializer.data
        })
        
    except SettingsServiceError as e:
        return Response({
            'error': str(e),
            'code': 'PAYMENT_METHOD_ERROR'
        }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=['Finance - Payout Methods'],
    summary='Manage payout method',
    description='''
Manage payout method for receiving tenant earnings.

**GET**: Return masked payout method details
**PUT**: Update payout method with encrypted details
**DELETE**: Remove payout method

**Required scope**: `finance:manage`
**Rate limit**: 60 requests/minute for PUT/DELETE

**Note**: Payout method configuration requires payment facilitation to be enabled for the tenant's subscription tier.

**Requirements**: 8.1, 8.2, 8.3, 8.4, 8.5, 11.2, 11.5
    ''',
    request=OpenApiTypes.OBJECT,
    responses={
        200: OpenApiTypes.OBJECT,
        400: OpenApiTypes.OBJECT,
        403: OpenApiTypes.OBJECT,
        429: OpenApiTypes.OBJECT,
    },
    examples=[
        OpenApiExample(
            'Bank Transfer',
            value={
                'method': 'bank_transfer',
                'details': {
                    'account_number': '1234567890',
                    'routing_number': '021000021',
                    'account_holder_name': 'John Doe',
                    'bank_name': 'Chase Bank'
                }
            },
            request_only=True
        ),
        OpenApiExample(
            'Mobile Money',
            value={
                'method': 'mobile_money',
                'details': {
                    'phone_number': '+254712345678',
                    'provider': 'M-Pesa'
                }
            },
            request_only=True
        ),
        OpenApiExample(
            'Success Response',
            value={
                'message': 'Payout method updated successfully',
                'configured': True,
                'payout_method': 'bank_transfer',
                'details': {
                    'account_number': '****7890',
                    'routing_number': '021000021',
                    'account_holder_name': 'John Doe',
                    'bank_name': 'Chase Bank'
                }
            },
            response_only=True
        )
    ]
)
@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([HasTenantScopes])
@ratelimit(key='user_or_ip', rate='60/m', method=['PUT', 'DELETE'])
def payout_method_view(request):
    """
    Manage payout method for receiving tenant earnings.
    
    GET: Return masked payout method details
    PUT: Update payout method with encrypted details
    DELETE: Remove payout method
    
    Required scope: finance:manage
    
    Note: Payout method configuration requires payment facilitation to be enabled
    for the tenant's subscription tier.
    """
    if 'finance:manage' not in request.scopes:
        return Response(
            {'detail': 'Missing required scope: finance:manage'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Check if payment facilitation is enabled for tenant tier
    if not request.tenant.subscription_tier or not request.tenant.subscription_tier.payment_facilitation:
        return Response({
            'error': 'Payment facilitation is not enabled for your subscription tier',
            'code': 'PAYMENT_FACILITATION_NOT_ENABLED'
        }, status=status.HTTP_403_FORBIDDEN)
    
    settings, created = TenantSettings.objects.get_or_create(
        tenant=request.tenant
    )
    
    if request.method == 'GET':
        # Return masked payout method details
        if not settings.payout_method:
            return Response({
                'configured': False,
                'payout_method': None
            })
        
        import json
        payout_details = json.loads(settings.payout_details) if settings.payout_details else {}
        
        # Mask sensitive details
        masked_details = {}
        if settings.payout_method == 'bank_transfer':
            masked_details = {
                'account_number': '****' + payout_details.get('account_number', '')[-4:],
                'routing_number': payout_details.get('routing_number', ''),
                'account_holder_name': payout_details.get('account_holder_name', ''),
                'bank_name': payout_details.get('bank_name', '')
            }
        elif settings.payout_method == 'mobile_money':
            phone = payout_details.get('phone_number', '')
            masked_details = {
                'phone_number': phone[:3] + '****' + phone[-4:] if len(phone) > 7 else '****',
                'provider': payout_details.get('provider', '')
            }
        elif settings.payout_method == 'paypal':
            email = payout_details.get('email', '')
            if '@' in email:
                parts = email.split('@')
                masked_details = {
                    'email': parts[0][:2] + '****@' + parts[1]
                }
            else:
                masked_details = {'email': '****'}
        
        return Response({
            'configured': True,
            'payout_method': settings.payout_method,
            'details': masked_details
        })
    
    elif request.method == 'PUT':
        # Update payout method
        from apps.tenants.services.settings_service import SettingsService
        from django.core.exceptions import ValidationError
        
        method = request.data.get('method')
        details = request.data.get('details')
        
        if not method or not details:
            return Response({
                'error': 'Both method and details are required',
                'code': 'INVALID_INPUT'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            settings = SettingsService.update_payout_method(
                tenant=request.tenant,
                method=method,
                details=details,
                user=request.user
            )
            
            # Return masked details
            import json
            payout_details = json.loads(settings.payout_details) if settings.payout_details else {}
            
            masked_details = {}
            if method == 'bank_transfer':
                masked_details = {
                    'account_number': '****' + payout_details.get('account_number', '')[-4:],
                    'routing_number': payout_details.get('routing_number', ''),
                    'account_holder_name': payout_details.get('account_holder_name', ''),
                    'bank_name': payout_details.get('bank_name', '')
                }
            elif method == 'mobile_money':
                phone = payout_details.get('phone_number', '')
                masked_details = {
                    'phone_number': phone[:3] + '****' + phone[-4:] if len(phone) > 7 else '****',
                    'provider': payout_details.get('provider', '')
                }
            elif method == 'paypal':
                email = payout_details.get('email', '')
                if '@' in email:
                    parts = email.split('@')
                    masked_details = {
                        'email': parts[0][:2] + '****@' + parts[1]
                    }
                else:
                    masked_details = {'email': '****'}
            
            return Response({
                'message': 'Payout method updated successfully',
                'configured': True,
                'payout_method': method,
                'details': masked_details
            }, status=status.HTTP_200_OK)
            
        except ValidationError as e:
            return Response({
                'error': str(e),
                'code': 'VALIDATION_ERROR'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        # Remove payout method
        with transaction.atomic():
            settings.payout_method = ''
            settings.payout_details = ''
            settings.save(update_fields=['payout_method', 'payout_details', 'updated_at'])
            
            # Update onboarding status
            if 'payout_method_configured' in settings.onboarding_status:
                settings.onboarding_status['payout_method_configured'] = {
                    'completed': False,
                    'completed_at': None
                }
                settings.save(update_fields=['onboarding_status', 'updated_at'])
            
            # Log to audit trail
            from apps.rbac.models import AuditLog
            AuditLog.log_action(
                action='payout_method_removed',
                user=request.user,
                tenant=request.tenant,
                target_type='TenantSettings',
                target_id=settings.id,
                metadata={}
            )
        
        return Response({
            'message': 'Payout method removed successfully'
        }, status=status.HTTP_200_OK)



@extend_schema(
    tags=['Settings'],
    summary='Manage business settings',
    description='''
Manage business settings including timezone, business hours, quiet hours, and notification preferences.

**GET**: Return current business settings (no specific scope required)
**PUT**: Update business settings with validation (requires `users:manage` OR `integrations:manage` scope)

**Rate limit**: 60 requests/minute for PUT

**Requirements**: 9.1, 9.2, 9.3, 9.4, 9.5, 11.3, 11.5
    ''',
    request=BusinessSettingsSerializer,
    responses={
        200: OpenApiTypes.OBJECT,
        400: OpenApiTypes.OBJECT,
        403: OpenApiTypes.OBJECT,
        429: OpenApiTypes.OBJECT,
    },
    examples=[
        OpenApiExample(
            'Update Settings',
            value={
                'timezone': 'Africa/Nairobi',
                'business_hours': {
                    'monday': {'open': '09:00', 'close': '17:00'},
                    'tuesday': {'open': '09:00', 'close': '17:00'}
                },
                'quiet_hours': {
                    'enabled': True,
                    'start': '22:00',
                    'end': '08:00'
                },
                'notification_preferences': {
                    'email': {
                        'order_created': True,
                        'payment_received': True
                    }
                }
            },
            request_only=True
        ),
        OpenApiExample(
            'Success Response',
            value={
                'message': 'Business settings updated successfully',
                'settings': {
                    'timezone': 'Africa/Nairobi',
                    'business_hours': {},
                    'quiet_hours': {
                        'enabled': True,
                        'start': '22:00',
                        'end': '08:00'
                    },
                    'notification_preferences': {}
                }
            },
            response_only=True
        )
    ]
)
@api_view(['GET', 'PUT'])
@permission_classes([HasTenantScopes])
@ratelimit(key='user_or_ip', rate='60/m', method='PUT')
def business_settings_view(request):
    """
    Manage business settings including timezone, business hours, quiet hours, and notification preferences.
    
    GET: Return current business settings
    PUT: Update business settings with validation
    
    Required scopes:
    - GET: No specific scope required (authenticated users can view)
    - PUT: users:manage OR integrations:manage
    
    Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 11.3, 11.5
    """
    settings, created = TenantSettings.objects.get_or_create(
        tenant=request.tenant
    )
    
    if request.method == 'GET':
        # Return current business settings
        # Extract business settings from tenant and tenant settings
        business_settings = {
            'timezone': request.tenant.timezone,
            'business_hours': settings.business_hours or {},
            'quiet_hours': {
                'enabled': bool(request.tenant.quiet_hours_start and request.tenant.quiet_hours_end),
                'start': str(request.tenant.quiet_hours_start) if request.tenant.quiet_hours_start else None,
                'end': str(request.tenant.quiet_hours_end) if request.tenant.quiet_hours_end else None
            },
            'notification_preferences': settings.notification_settings or {}
        }
        
        return Response(business_settings)
    
    elif request.method == 'PUT':
        # Check required scopes for update
        if 'users:manage' not in request.scopes and 'integrations:manage' not in request.scopes:
            return Response(
                {'detail': 'Missing required scope: users:manage OR integrations:manage'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = BusinessSettingsSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data
        
        # Update settings in transaction
        with transaction.atomic():
            updated_fields = []
            
            # Update timezone on Tenant model
            if 'timezone' in validated_data:
                request.tenant.timezone = validated_data['timezone']
                request.tenant.save(update_fields=['timezone', 'updated_at'])
            
            # Update business hours on TenantSettings
            if 'business_hours' in validated_data:
                settings.business_hours = validated_data['business_hours']
                updated_fields.append('business_hours')
            
            # Update quiet hours on Tenant model
            if 'quiet_hours' in validated_data:
                quiet_hours = validated_data['quiet_hours']
                
                if quiet_hours.get('enabled', False):
                    # Parse time strings to time objects
                    from datetime import datetime
                    
                    start_str = quiet_hours.get('start')
                    end_str = quiet_hours.get('end')
                    
                    if start_str:
                        start_time = datetime.strptime(start_str, '%H:%M').time()
                        request.tenant.quiet_hours_start = start_time
                    
                    if end_str:
                        end_time = datetime.strptime(end_str, '%H:%M').time()
                        request.tenant.quiet_hours_end = end_time
                    
                    request.tenant.save(update_fields=['quiet_hours_start', 'quiet_hours_end', 'updated_at'])
                else:
                    # Disable quiet hours by setting to None
                    request.tenant.quiet_hours_start = None
                    request.tenant.quiet_hours_end = None
                    request.tenant.save(update_fields=['quiet_hours_start', 'quiet_hours_end', 'updated_at'])
            
            # Update notification preferences on TenantSettings
            if 'notification_preferences' in validated_data:
                settings.notification_settings = validated_data['notification_preferences']
                updated_fields.append('notification_settings')
            
            # Save TenantSettings if any fields were updated
            if updated_fields:
                settings.save(update_fields=updated_fields + ['updated_at'])
            
            # Update onboarding status
            if 'business_settings_configured' in settings.onboarding_status:
                from django.utils import timezone as django_timezone
                settings.onboarding_status['business_settings_configured'] = {
                    'completed': True,
                    'completed_at': django_timezone.now().isoformat()
                }
                settings.save(update_fields=['onboarding_status', 'updated_at'])
            
            # Log to audit trail
            from apps.rbac.models import AuditLog
            AuditLog.log_action(
                action='business_settings_updated',
                user=request.user,
                tenant=request.tenant,
                target_type='TenantSettings',
                target_id=settings.id,
                metadata={
                    'updated_fields': list(validated_data.keys())
                }
            )
        
        # Return updated settings
        business_settings = {
            'timezone': request.tenant.timezone,
            'business_hours': settings.business_hours or {},
            'quiet_hours': {
                'enabled': bool(request.tenant.quiet_hours_start and request.tenant.quiet_hours_end),
                'start': str(request.tenant.quiet_hours_start) if request.tenant.quiet_hours_start else None,
                'end': str(request.tenant.quiet_hours_end) if request.tenant.quiet_hours_end else None
            },
            'notification_preferences': settings.notification_settings or {}
        }
        
        return Response({
            'message': 'Business settings updated successfully',
            'settings': business_settings
        }, status=status.HTTP_200_OK)



@extend_schema(
    tags=['Integrations'],
    summary='Manage Together AI credentials',
    description='''
Manage Together AI integration credentials with optional validation.

**GET**: Return configuration status
**POST**: Update credentials with optional validation
**DELETE**: Remove credentials

**Required scope**: `integrations:manage`
**Rate limit**: 60 requests/minute for POST/DELETE

**Requirements**: 14.1, 14.2, 14.4
    ''',
    request='apps.tenants.serializers_settings.TogetherAICredentialsSerializer',
    responses={
        200: OpenApiTypes.OBJECT,
        400: OpenApiTypes.OBJECT,
        403: OpenApiTypes.OBJECT,
        429: OpenApiTypes.OBJECT,
    },
    examples=[
        OpenApiExample(
            'Update Credentials',
            value={
                'api_key': 'together_api_key_here',
                'test_connection': True
            },
            request_only=True
        ),
        OpenApiExample(
            'Success Response',
            value={
                'message': 'Together AI credentials updated successfully',
                'configured': True,
                'available_models': 7
            },
            response_only=True
        )
    ]
)
@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([HasTenantScopes])
@ratelimit(key='user_or_ip', rate='60/m', method=['POST', 'DELETE'])
def together_ai_credentials_view(request):
    """
    Manage Together AI integration credentials.
    
    GET: Return configuration status
    POST: Create/update credentials with optional validation
    DELETE: Remove credentials
    
    Required scope: integrations:manage
    """
    if 'integrations:manage' not in request.scopes:
        return Response(
            {'detail': 'Missing required scope: integrations:manage'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    settings, created = TenantSettings.objects.get_or_create(
        tenant=request.tenant
    )
    
    if request.method == 'GET':
        # Return configuration status
        has_together = bool(settings.together_api_key)
        
        response_data = {
            'configured': has_together,
        }
        
        if has_together:
            # Get available models
            try:
                from apps.bot.services.llm import TogetherAIProvider
                provider = TogetherAIProvider(api_key=settings.together_api_key)
                models = provider.get_available_models()
                response_data['available_models'] = len(models)
            except Exception as e:
                logger.warning(f"Failed to get Together AI models: {e}")
                response_data['available_models'] = 0
        
        return Response(response_data)
    
    elif request.method == 'POST':
        from apps.tenants.serializers_settings import TogetherAICredentialsSerializer
        
        serializer = TogetherAICredentialsSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                settings.together_api_key = serializer.validated_data['api_key']
                settings.update_integration_status('together_ai', {
                    'configured': True,
                    'configured_at': str(timezone.now())
                })
                settings.save()
                
                # Log to audit trail
                from apps.rbac.models import AuditLog
                AuditLog.log_action(
                    action='together_ai_credentials_updated',
                    user=request.user,
                    tenant=request.tenant,
                    target_type='TenantSettings',
                    target_id=settings.id,
                    metadata={}
                )
            
            # Get available models count
            try:
                from apps.bot.services.llm import TogetherAIProvider
                provider = TogetherAIProvider(api_key=settings.together_api_key)
                models = provider.get_available_models()
                available_models = len(models)
            except Exception as e:
                logger.warning(f"Failed to get Together AI models: {e}")
                available_models = 0
            
            return Response({
                'message': 'Together AI credentials updated successfully',
                'configured': True,
                'available_models': available_models
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error updating Together AI credentials: {e}", exc_info=True)
            return Response({
                'error': 'Failed to update Together AI credentials',
                'code': 'CREDENTIAL_UPDATE_FAILED'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        # Remove Together AI credentials
        with transaction.atomic():
            settings.together_api_key = ''
            settings.update_integration_status('together_ai', {'configured': False})
            settings.save()
            
            # Log to audit trail
            from apps.rbac.models import AuditLog
            AuditLog.log_action(
                action='together_ai_credentials_removed',
                user=request.user,
                tenant=request.tenant,
                target_type='TenantSettings',
                target_id=settings.id,
                metadata={}
            )
        
        return Response({
            'message': 'Together AI credentials removed successfully'
        }, status=status.HTTP_200_OK)


@extend_schema(
    tags=['Integrations'],
    summary='Manage LLM configuration',
    description='''
Manage LLM provider selection and configuration for the AI agent.

**GET**: Return current LLM configuration
**PATCH**: Update LLM configuration

**Required scope**: `integrations:manage`
**Rate limit**: 60 requests/minute for PATCH

**Requirements**: 14.1, 14.2, 14.4
    ''',
    request='apps.tenants.serializers_settings.LLMConfigurationSerializer',
    responses={
        200: OpenApiTypes.OBJECT,
        400: OpenApiTypes.OBJECT,
        403: OpenApiTypes.OBJECT,
        429: OpenApiTypes.OBJECT,
    },
    examples=[
        OpenApiExample(
            'Update Configuration',
            value={
                'llm_provider': 'together',
                'llm_timeout': 60.0,
                'llm_max_retries': 3
            },
            request_only=True
        ),
        OpenApiExample(
            'Success Response',
            value={
                'message': 'LLM configuration updated successfully',
                'configuration': {
                    'llm_provider': 'together',
                    'llm_timeout': 60.0,
                    'llm_max_retries': 3
                }
            },
            response_only=True
        )
    ]
)
@api_view(['GET', 'PATCH'])
@permission_classes([HasTenantScopes])
@ratelimit(key='user_or_ip', rate='60/m', method=['PATCH'])
def llm_configuration_view(request):
    """
    Manage LLM configuration for the AI agent.
    
    GET: Return current LLM configuration
    PATCH: Update LLM configuration
    
    Required scope: integrations:manage
    """
    if 'integrations:manage' not in request.scopes:
        return Response(
            {'detail': 'Missing required scope: integrations:manage'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    settings, created = TenantSettings.objects.get_or_create(
        tenant=request.tenant
    )
    
    if request.method == 'GET':
        # Return current configuration
        return Response({
            'llm_provider': settings.llm_provider or 'openai',
            'llm_timeout': settings.llm_timeout,
            'llm_max_retries': settings.llm_max_retries,
        })
    
    elif request.method == 'PATCH':
        from apps.tenants.serializers_settings import LLMConfigurationSerializer
        
        serializer = LLMConfigurationSerializer(
            data=request.data,
            context={'tenant': request.tenant}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                updated_fields = []
                
                if 'llm_provider' in serializer.validated_data:
                    settings.llm_provider = serializer.validated_data['llm_provider']
                    updated_fields.append('llm_provider')
                
                if 'llm_timeout' in serializer.validated_data:
                    settings.llm_timeout = serializer.validated_data['llm_timeout']
                    updated_fields.append('llm_timeout')
                
                if 'llm_max_retries' in serializer.validated_data:
                    settings.llm_max_retries = serializer.validated_data['llm_max_retries']
                    updated_fields.append('llm_max_retries')
                
                if updated_fields:
                    settings.save(update_fields=updated_fields + ['updated_at'])
                
                # Log to audit trail
                from apps.rbac.models import AuditLog
                AuditLog.log_action(
                    action='llm_configuration_updated',
                    user=request.user,
                    tenant=request.tenant,
                    target_type='TenantSettings',
                    target_id=settings.id,
                    metadata={
                        'updated_fields': updated_fields,
                        'llm_provider': settings.llm_provider
                    }
                )
            
            return Response({
                'message': 'LLM configuration updated successfully',
                'configuration': {
                    'llm_provider': settings.llm_provider,
                    'llm_timeout': settings.llm_timeout,
                    'llm_max_retries': settings.llm_max_retries,
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error updating LLM configuration: {e}", exc_info=True)
            return Response({
                'error': 'Failed to update LLM configuration',
                'code': 'CONFIGURATION_UPDATE_FAILED'
            }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=['Integrations'],
    summary='Get available LLM providers',
    description='''
Get list of available LLM providers and their configuration status.

Returns information about each provider including:
- Configuration status
- Available models
- Pricing information

**Required scope**: `integrations:view`

**Requirements**: 14.1, 14.2, 14.3
    ''',
    responses={
        200: OpenApiTypes.OBJECT,
        403: OpenApiTypes.OBJECT,
    },
    examples=[
        OpenApiExample(
            'Success Response',
            value={
                'providers': [
                    {
                        'provider': 'openai',
                        'display_name': 'OpenAI',
                        'is_configured': True,
                        'available_models': [
                            {
                                'name': 'gpt-4o',
                                'display_name': 'GPT-4o',
                                'context_window': 128000,
                                'input_cost_per_1k': '0.0025',
                                'output_cost_per_1k': '0.01'
                            }
                        ]
                    },
                    {
                        'provider': 'together',
                        'display_name': 'Together AI',
                        'is_configured': False,
                        'available_models': []
                    }
                ]
            },
            response_only=True
        )
    ]
)
@api_view(['GET'])
@permission_classes([HasTenantScopes])
def llm_providers_view(request):
    """
    Get available LLM providers and their configuration status.
    
    Required scope: integrations:view
    """
    if 'integrations:view' not in request.scopes:
        return Response(
            {'detail': 'Missing required scope: integrations:view'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    settings, created = TenantSettings.objects.get_or_create(
        tenant=request.tenant
    )
    
    providers = []
    
    # OpenAI
    openai_configured = bool(settings.openai_api_key)
    openai_models = []
    
    if openai_configured:
        try:
            from apps.bot.services.llm import OpenAIProvider
            provider = OpenAIProvider(api_key=settings.openai_api_key)
            models = provider.get_available_models()
            openai_models = [
                {
                    'name': m.name,
                    'display_name': m.display_name,
                    'provider': m.provider,
                    'context_window': m.context_window,
                    'input_cost_per_1k': str(m.input_cost_per_1k),
                    'output_cost_per_1k': str(m.output_cost_per_1k),
                    'capabilities': m.capabilities,
                    'description': m.description
                }
                for m in models
            ]
        except Exception as e:
            logger.warning(f"Failed to get OpenAI models: {e}")
    
    providers.append({
        'provider': 'openai',
        'display_name': 'OpenAI',
        'is_configured': openai_configured,
        'available_models': openai_models
    })
    
    # Together AI
    together_configured = bool(settings.together_api_key)
    together_models = []
    
    if together_configured:
        try:
            from apps.bot.services.llm import TogetherAIProvider
            provider = TogetherAIProvider(api_key=settings.together_api_key)
            models = provider.get_available_models()
            together_models = [
                {
                    'name': m.name,
                    'display_name': m.display_name,
                    'provider': m.provider,
                    'context_window': m.context_window,
                    'input_cost_per_1k': str(m.input_cost_per_1k),
                    'output_cost_per_1k': str(m.output_cost_per_1k),
                    'capabilities': m.capabilities,
                    'description': m.description
                }
                for m in models
            ]
        except Exception as e:
            logger.warning(f"Failed to get Together AI models: {e}")
    
    providers.append({
        'provider': 'together',
        'display_name': 'Together AI',
        'is_configured': together_configured,
        'available_models': together_models
    })
    
    return Response({
        'providers': providers,
        'current_provider': settings.llm_provider or 'openai'
    })


def _mask_credential(value, prefix=''):
    """Mask credential showing only last 4 characters."""
    if not value:
        return None
    
    if len(value) <= 4:
        return '****'
    
    return f"{prefix}****{value[-4:]}"
