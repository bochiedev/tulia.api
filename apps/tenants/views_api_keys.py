"""
API views for API key management.

Implements secure API key generation, listing, and revocation with:
- SHA-256 hashing for storage
- Audit logging for all operations
- RBAC enforcement (users:manage scope required)
"""
import logging
import secrets
import hashlib
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from drf_spectacular.utils import extend_schema, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from apps.core.permissions import HasTenantScopes
from apps.rbac.models import AuditLog
from apps.tenants.serializers_settings import (
    APIKeySerializer,
    APIKeyCreateSerializer,
    APIKeyResponseSerializer
)

logger = logging.getLogger(__name__)


def check_scope(request, required_scope):
    """Helper to check if request has required scope."""
    if required_scope not in request.scopes:
        return Response(
            {'detail': f'Missing required scope: {required_scope}'},
            status=status.HTTP_403_FORBIDDEN
        )
    return None


@extend_schema(
    tags=['Settings - API Keys'],
    summary='Manage API keys',
    description='''
Manage API keys for tenant authentication.

**GET**: List all API keys with masked values (first 8 characters shown)
**POST**: Generate new API key with SHA-256 hashing

**Required scope**: `users:manage`
**Rate limit**: 60 requests/minute for POST

**Security**:
- API keys are 32-character random strings
- Only key hashes stored in database (SHA-256)
- Plain key shown once during generation
- All operations logged to audit trail

**Requirements**: 13.1, 13.2, 13.3, 11.5
    ''',
    request=APIKeyCreateSerializer,
    responses={
        200: OpenApiTypes.OBJECT,
        201: APIKeyResponseSerializer,
        400: OpenApiTypes.OBJECT,
        403: OpenApiTypes.OBJECT,
        429: OpenApiTypes.OBJECT,
    },
    examples=[
        OpenApiExample(
            'Generate API Key',
            value={
                'name': 'Production API Key'
            },
            request_only=True
        ),
        OpenApiExample(
            'List Response',
            value={
                'api_keys': [
                    {
                        'id': 'key_abc123',
                        'key_preview': 'AbCdEfGh',
                        'name': 'Production API Key',
                        'created_at': '2024-01-15T10:30:00Z',
                        'created_by_email': 'user@example.com',
                        'last_used_at': '2024-01-16T14:20:00Z'
                    }
                ],
                'total': 1
            },
            response_only=True
        ),
        OpenApiExample(
            'Generate Response',
            value={
                'message': 'API key generated successfully',
                'api_key': 'AbCdEfGhIjKlMnOpQrStUvWxYz012345',
                'key_id': 'key_abc123',
                'name': 'Production API Key',
                'key_preview': 'AbCdEfGh',
                'created_at': '2024-01-15T10:30:00Z',
                'warning': 'Save this key now. You will not be able to see it again.'
            },
            response_only=True,
            status_codes=['201']
        )
    ]
)
@api_view(['GET', 'POST'])
@permission_classes([HasTenantScopes])
@ratelimit(key='user_or_ip', rate='60/m', method='POST')
def api_keys_view(request):
    """
    Manage API keys for tenant.
    
    GET: List all API keys with masked values
    POST: Generate new API key
    
    Required scope: users:manage
    
    Requirements: 13.1, 13.2, 13.3, 11.5
    """
    # Check scope
    scope_check = check_scope(request, 'users:manage')
    if scope_check:
        return scope_check
    
    if request.method == 'GET':
        # Return list of API keys with masked values
        api_keys = request.tenant.api_keys or []
        
        # Serialize keys using APIKeySerializer
        serializer = APIKeySerializer(api_keys, many=True)
        
        return Response({
            'api_keys': serializer.data,
            'total': len(api_keys)
        })
    
    elif request.method == 'POST':
        # Validate request data
        serializer = APIKeyCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        name = serializer.validated_data['name']
        
        # Generate 32-character random key
        plain_key = secrets.token_urlsafe(32)
        
        # Hash the key for storage (SHA-256)
        key_hash = hashlib.sha256(plain_key.encode()).hexdigest()
        
        # Generate unique ID for this key
        key_id = secrets.token_urlsafe(16)
        
        # Store key metadata (not the plain key!)
        key_data = {
            'id': key_id,
            'key_hash': key_hash,
            'key_preview': plain_key[:8],  # First 8 chars for display
            'name': name,
            'created_at': timezone.now().isoformat(),
            'created_by': str(request.user.id),  # Convert UUID to string for JSON
            'created_by_email': request.user.email,
            'last_used_at': None,
        }
        
        # Add to tenant's api_keys array
        with transaction.atomic():
            request.tenant.api_keys = request.tenant.api_keys or []
            request.tenant.api_keys.append(key_data)
            request.tenant.save(update_fields=['api_keys', 'updated_at'])
            
            # Log to audit trail
            AuditLog.log_action(
                action='api_key_generated',
                user=request.user,
                tenant=request.tenant,
                target_type='Tenant',
                target_id=request.tenant.id,
                metadata={
                    'key_id': key_id,
                    'key_name': name,
                    'key_preview': plain_key[:8]
                },
                request=request
            )
        
        # Return plain key ONCE using response serializer
        response_data = {
            'message': 'API key generated successfully',
            'api_key': plain_key,  # Plain key shown once
            'key_id': key_id,
            'name': name,
            'key_preview': plain_key[:8],
            'created_at': key_data['created_at'],
            'warning': 'Save this key now. You will not be able to see it again.'
        }
        
        response_serializer = APIKeyResponseSerializer(data=response_data)
        response_serializer.is_valid(raise_exception=True)
        
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=['Settings - API Keys'],
    summary='Revoke API key',
    description='''
Revoke (delete) an API key.

Removes the API key from tenant and logs the action to audit trail.

**Required scope**: `users:manage`
**Rate limit**: 60 requests/minute

**Requirements**: 13.4, 11.5
    ''',
    responses={
        200: OpenApiTypes.OBJECT,
        403: OpenApiTypes.OBJECT,
        404: OpenApiTypes.OBJECT,
        429: OpenApiTypes.OBJECT,
    },
    examples=[
        OpenApiExample(
            'Success Response',
            value={
                'message': 'API key revoked successfully',
                'key_id': 'key_abc123',
                'key_name': 'Production API Key'
            },
            response_only=True
        ),
        OpenApiExample(
            'Not Found',
            value={
                'error': 'API key not found',
                'code': 'NOT_FOUND'
            },
            response_only=True,
            status_codes=['404']
        )
    ]
)
@api_view(['DELETE'])
@permission_classes([HasTenantScopes])
@ratelimit(key='user_or_ip', rate='60/m', method='DELETE')
def api_key_revoke_view(request, key_id):
    """
    Revoke (delete) an API key.
    
    DELETE: Remove API key from tenant
    
    Required scope: users:manage
    
    Requirements: 13.4, 11.5
    """
    # Check scope
    scope_check = check_scope(request, 'users:manage')
    if scope_check:
        return scope_check
    
    # Find the key in tenant's api_keys array
    api_keys = request.tenant.api_keys or []
    key_to_revoke = None
    remaining_keys = []
    
    for key_data in api_keys:
        if key_data.get('id') == key_id:
            key_to_revoke = key_data
        else:
            remaining_keys.append(key_data)
    
    if not key_to_revoke:
        return Response({
            'error': 'API key not found',
            'code': 'NOT_FOUND'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Remove key from tenant
    with transaction.atomic():
        request.tenant.api_keys = remaining_keys
        request.tenant.save(update_fields=['api_keys', 'updated_at'])
        
        # Log to audit trail
        AuditLog.log_action(
            action='api_key_revoked',
            user=request.user,
            tenant=request.tenant,
            target_type='Tenant',
            target_id=request.tenant.id,
            metadata={
                'key_id': key_id,
                'key_name': key_to_revoke.get('name', ''),
                'key_preview': key_to_revoke.get('key_preview', '')
            },
            request=request
        )
    
    return Response({
        'message': 'API key revoked successfully',
        'key_id': key_id,
        'key_name': key_to_revoke.get('name', '')
    }, status=status.HTTP_200_OK)
