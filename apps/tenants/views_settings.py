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
    PaymentMethodSerializer
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



@api_view(['POST'])
@permission_classes([HasTenantScopes])
def set_woocommerce_credentials(request):
    """Set WooCommerce integration credentials."""
    if 'integrations:manage' not in request.scopes:
        return Response(
            {'detail': 'Missing required scope: integrations:manage'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    serializer = WooCommerceCredentialsSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    settings, created = TenantSettings.objects.get_or_create(
        tenant=request.tenant
    )
    
    with transaction.atomic():
        settings.woo_store_url = serializer.validated_data['store_url']
        settings.woo_consumer_key = serializer.validated_data['consumer_key']
        settings.woo_consumer_secret = serializer.validated_data['consumer_secret']
        settings.woo_webhook_secret = serializer.validated_data.get('webhook_secret', '')
        settings.update_integration_status('woocommerce', {'enabled': True})
        settings.save()
    
    return Response({
        'message': 'WooCommerce credentials saved successfully',
        'store_url': serializer.validated_data['store_url']
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([HasTenantScopes])
def set_shopify_credentials(request):
    """Set Shopify integration credentials."""
    if 'integrations:manage' not in request.scopes:
        return Response(
            {'detail': 'Missing required scope: integrations:manage'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    serializer = ShopifyCredentialsSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    settings, created = TenantSettings.objects.get_or_create(
        tenant=request.tenant
    )
    
    with transaction.atomic():
        settings.shopify_shop_domain = serializer.validated_data['shop_domain']
        settings.shopify_access_token = serializer.validated_data['access_token']
        settings.shopify_webhook_secret = serializer.validated_data.get('webhook_secret', '')
        settings.update_integration_status('shopify', {'enabled': True})
        settings.save()
    
    return Response({
        'message': 'Shopify credentials saved successfully',
        'shop_domain': serializer.validated_data['shop_domain']
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([HasTenantScopes])
def set_twilio_credentials(request):
    """Set Twilio integration credentials."""
    if 'integrations:manage' not in request.scopes:
        return Response(
            {'detail': 'Missing required scope: integrations:manage'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    serializer = TwilioCredentialsSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    settings, created = TenantSettings.objects.get_or_create(
        tenant=request.tenant
    )
    
    with transaction.atomic():
        settings.twilio_sid = serializer.validated_data['sid']
        settings.twilio_token = serializer.validated_data['token']
        settings.twilio_webhook_secret = serializer.validated_data.get('webhook_secret', '')
        settings.save()
    
    return Response({
        'message': 'Twilio credentials saved successfully'
    }, status=status.HTTP_200_OK)


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
def get_payment_methods(request):
    """Get list of payment methods for tenant."""
    if 'finance:view' not in request.scopes:
        return Response(
            {'detail': 'Missing required scope: finance:view'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    settings = TenantSettings.objects.filter(tenant=request.tenant).first()
    if not settings:
        return Response({'payment_methods': []})
    
    serializer = PaymentMethodSerializer(settings.stripe_payment_methods, many=True)
    
    return Response({
        'stripe_customer_id': settings.stripe_customer_id,
        'payment_methods': serializer.data
    })
