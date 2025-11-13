"""
API views for TenantSettings management.
"""
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.db import transaction

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


@api_view(['GET', 'PATCH'])
@permission_classes([HasTenantScopes])
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



@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([HasTenantScopes])
def woocommerce_credentials_view(request):
    """
    Manage WooCommerce integration credentials.
    
    GET: Return masked credentials and configuration status
    PUT: Update credentials with validation
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
    
    elif request.method == 'PUT':
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


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([HasTenantScopes])
def shopify_credentials_view(request):
    """
    Manage Shopify integration credentials.
    
    GET: Return masked credentials and configuration status
    PUT: Update credentials with validation
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
    
    elif request.method == 'PUT':
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


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([HasTenantScopes])
def twilio_credentials_view(request):
    """
    Manage Twilio integration credentials.
    
    GET: Return masked credentials and configuration status
    PUT: Update credentials with validation
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
    
    elif request.method == 'PUT':
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


@api_view(['POST'])
@permission_classes([HasTenantScopes])
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


@api_view(['GET', 'POST'])
@permission_classes([HasTenantScopes])
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


@api_view(['PUT'])
@permission_classes([HasTenantScopes])
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


@api_view(['DELETE'])
@permission_classes([HasTenantScopes])
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


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([HasTenantScopes])
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
        from apps.core.exceptions import ValidationError
        
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



@api_view(['GET', 'PUT'])
@permission_classes([HasTenantScopes])
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
