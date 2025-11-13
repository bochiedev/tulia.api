"""
Tenant management API views.

Handles tenant lifecycle operations:
- List user's tenants
- Create new tenant
- Get tenant details
- Update tenant info
- Delete tenant (soft delete)
- Manage tenant members
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
import logging

from apps.tenants.models import Tenant
from apps.tenants.services.tenant_service import TenantService
from apps.tenants.serializers import (
    TenantListSerializer, TenantDetailSerializer,
    TenantCreateSerializer, TenantUpdateSerializer,
    TenantMemberSerializer, TenantMemberInviteSerializer
)
from apps.core.permissions import HasTenantScopes
from apps.rbac.models import TenantUser, AuditLog
from django.core.exceptions import PermissionDenied

logger = logging.getLogger(__name__)


class TenantListView(APIView):
    """
    List all tenants where user has membership.
    
    GET /v1/tenants
    
    Returns all tenants where the authenticated user has an active TenantUser membership.
    Includes tenant name, slug, status, user's role, and onboarding status.
    
    No specific scope required - all authenticated users can list their tenants.
    """
    
    @extend_schema(
        summary="List user's tenants",
        description="""
List all tenants where the authenticated user has membership.

Returns tenant information including:
- Basic tenant details (name, slug, status)
- User's primary role in each tenant
- Onboarding completion status
- Subscription tier

This endpoint does not require any specific scope - all authenticated users
can list the tenants they belong to.

**Example curl:**
```bash
curl -X GET https://api.tulia.ai/v1/tenants \\
  -H "Authorization: Bearer {jwt_token}"
```
        """,
        responses={
            200: TenantListSerializer(many=True),
            401: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                },
                'description': 'Unauthorized - Invalid or missing JWT token'
            }
        },
        tags=['Tenant Management']
    )
    def get(self, request):
        """List user's tenants."""
        user = request.user
        
        try:
            # Get all tenants where user has membership
            tenants = TenantService.get_user_tenants(user)
            
            # Serialize
            serializer = TenantListSerializer(
                tenants,
                many=True,
                context={'request': request}
            )
            
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error listing tenants for user {user.email}: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Failed to retrieve tenants',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(ratelimit(key='user_or_ip', rate='60/m', method='POST', block=True), name='dispatch')
class TenantCreateView(APIView):
    """
    Create a new tenant.
    
    POST /v1/tenants
    
    Creates a new tenant with the authenticated user as Owner.
    Automatically:
    - Creates Tenant record with trial status
    - Creates TenantSettings with defaults
    - Creates TenantUser membership with Owner role
    - Initializes onboarding status tracking
    
    No specific scope required - all authenticated users can create tenants.
    Rate limited to 60 requests per minute per user.
    """
    
    @extend_schema(
        summary="Create new tenant",
        description="""
Create a new tenant with the authenticated user as Owner.

The system automatically:
1. Creates a Tenant record with 'trial' status
2. Generates a unique slug from the business name (if not provided)
3. Creates TenantSettings with default configuration
4. Creates TenantUser membership with Owner role and all permissions
5. Initializes onboarding status tracking

The user becomes the Owner of the new tenant with full access to all features.

**Example curl:**
```bash
curl -X POST https://api.tulia.ai/v1/tenants \\
  -H "Authorization: Bearer {jwt_token}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "Acme Corp",
    "slug": "acme-corp",
    "whatsapp_number": "+1234567890"
  }'
```
        """,
        request=TenantCreateSerializer,
        responses={
            201: TenantDetailSerializer,
            400: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'},
                    'details': {'type': 'object'}
                },
                'description': 'Bad Request - Invalid input data'
            },
            401: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                },
                'description': 'Unauthorized - Invalid or missing JWT token'
            }
        },
        examples=[
            OpenApiExample(
                'Create Tenant Request',
                value={
                    'name': 'Acme Corp',
                    'slug': 'acme-corp',
                    'whatsapp_number': '+1234567890'
                },
                request_only=True
            ),
            OpenApiExample(
                'Success Response',
                value={
                    'id': '123e4567-e89b-12d3-a456-426614174000',
                    'name': 'Acme Corp',
                    'slug': 'acme-corp',
                    'status': 'trial',
                    'whatsapp_number': '+1234567890',
                    'role': 'Owner',
                    'roles': ['Owner'],
                    'onboarding_status': {
                        'completed': False,
                        'completion_percentage': 0,
                        'pending_steps': [
                            'twilio_configured',
                            'payment_method_added',
                            'business_settings_configured'
                        ]
                    },
                    'created_at': '2025-11-12T10:00:00Z'
                },
                response_only=True
            )
        ],
        tags=['Tenant Management']
    )
    def post(self, request):
        """Create new tenant."""
        user = request.user
        
        # Validate request data
        serializer = TenantCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Invalid request data',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = serializer.validated_data
        
        try:
            # Create tenant with user as Owner
            tenant = TenantService.create_tenant(
                user=user,
                name=data['name'],
                slug=data.get('slug'),
                whatsapp_number=data.get('whatsapp_number')
            )
            
            # Serialize response
            response_serializer = TenantDetailSerializer(
                tenant,
                context={'request': request}
            )
            
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
        
        except ValueError as e:
            return Response(
                {
                    'error': str(e),
                    'details': {'message': 'Validation error'}
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        except Exception as e:
            logger.error(f"Error creating tenant: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Failed to create tenant',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TenantDetailView(APIView):
    """
    Get tenant details.
    
    GET /v1/tenants/{id}
    
    Returns full tenant details including onboarding status.
    User must have membership in the tenant to access.
    
    No specific scope required - all tenant members can view tenant details.
    """
    
    @extend_schema(
        summary="Get tenant details",
        description="""
Retrieve full details for a specific tenant.

Returns comprehensive tenant information including:
- Basic tenant details
- User's roles in the tenant
- Detailed onboarding status with pending steps
- Subscription information
- Contact information
- Business settings

User must have an active membership in the tenant to access this endpoint.

**Example curl:**
```bash
curl -X GET https://api.tulia.ai/v1/tenants/{tenant_id} \\
  -H "Authorization: Bearer {jwt_token}"
```
        """,
        responses={
            200: TenantDetailSerializer,
            403: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                },
                'description': 'Forbidden - User does not have access to this tenant'
            },
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                },
                'description': 'Not Found - Tenant does not exist'
            }
        },
        tags=['Tenant Management']
    )
    def get(self, request, tenant_id):
        """Get tenant details."""
        user = request.user
        
        try:
            # Get tenant
            tenant = Tenant.objects.get(id=tenant_id, deleted_at__isnull=True)
        except Tenant.DoesNotExist:
            return Response(
                {'error': 'Tenant not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            # Validate user has access
            TenantService.validate_tenant_access(user, tenant)
            
            # Serialize response
            serializer = TenantDetailSerializer(
                tenant,
                context={'request': request}
            )
            
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        except PermissionDenied as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        
        except Exception as e:
            logger.error(f"Error getting tenant details: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Failed to retrieve tenant details',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(ratelimit(key='user_or_ip', rate='60/m', method='PUT', block=True), name='dispatch')
class TenantUpdateView(APIView):
    """
    Update tenant information.
    
    PUT /v1/tenants/{id}
    
    Updates basic tenant information.
    Requires users:manage scope.
    Rate limited to 60 requests per minute per user.
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'users:manage'}
    
    @extend_schema(
        summary="Update tenant information",
        description="""
Update basic tenant information such as name, contact details, and timezone.

**Required scope:** `users:manage`

Only users with the users:manage scope can update tenant information.
Typically this is limited to Owners and Admins.

**Example curl:**
```bash
curl -X PUT https://api.tulia.ai/v1/tenants/{tenant_id} \\
  -H "Authorization: Bearer {jwt_token}" \\
  -H "X-TENANT-ID: {tenant_id}" \\
  -H "X-TENANT-API-KEY: {api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "Acme Corporation",
    "contact_email": "contact@acme.com",
    "timezone": "America/New_York"
  }'
```
        """,
        request=TenantUpdateSerializer,
        responses={
            200: TenantDetailSerializer,
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
                },
                'description': 'Forbidden - Missing required scope: users:manage'
            },
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Tenant Management']
    )
    def put(self, request, tenant_id):
        """Update tenant information."""
        user = request.user
        
        try:
            # Get tenant
            tenant = Tenant.objects.get(id=tenant_id, deleted_at__isnull=True)
        except Tenant.DoesNotExist:
            return Response(
                {'error': 'Tenant not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Validate request data
        serializer = TenantUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Invalid request data',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = serializer.validated_data
        
        try:
            # Track changes for audit log
            changes = {}
            
            # Update fields
            if 'name' in data and data['name'] != tenant.name:
                changes['name'] = {'old': tenant.name, 'new': data['name']}
                tenant.name = data['name']
            
            if 'contact_email' in data and data['contact_email'] != tenant.contact_email:
                changes['contact_email'] = {'old': tenant.contact_email, 'new': data['contact_email']}
                tenant.contact_email = data['contact_email']
            
            if 'contact_phone' in data and data['contact_phone'] != tenant.contact_phone:
                changes['contact_phone'] = {'old': tenant.contact_phone, 'new': data['contact_phone']}
                tenant.contact_phone = data['contact_phone']
            
            if 'timezone' in data and data['timezone'] != tenant.timezone:
                changes['timezone'] = {'old': tenant.timezone, 'new': data['timezone']}
                tenant.timezone = data['timezone']
            
            # Save if there are changes
            if changes:
                tenant.save()
                
                # Log to audit trail
                AuditLog.log_action(
                    action='tenant_updated',
                    user=user,
                    tenant=tenant,
                    target_type='Tenant',
                    target_id=tenant.id,
                    diff=changes,
                    request=request
                )
            
            # Serialize response
            response_serializer = TenantDetailSerializer(
                tenant,
                context={'request': request}
            )
            
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error updating tenant: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Failed to update tenant',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(ratelimit(key='user_or_ip', rate='60/m', method='DELETE', block=True), name='dispatch')
class TenantDeleteView(APIView):
    """
    Delete tenant (soft delete).
    
    DELETE /v1/tenants/{id}
    
    Soft deletes the tenant and cascades to all related records.
    Requires users:manage scope and Owner role.
    Rate limited to 60 requests per minute per user.
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'users:manage'}
    
    @extend_schema(
        summary="Delete tenant",
        description="""
Soft delete a tenant and cascade to all related records.

**Required scope:** `users:manage`
**Required role:** `Owner`

This operation:
1. Marks the tenant as deleted (soft delete)
2. Sets tenant status to 'canceled'
3. Revokes all API keys
4. Deactivates all tenant user memberships
5. Cascades soft delete to related records

Only tenant Owners can delete tenants. This is a destructive operation
that cannot be easily undone.

**Example curl:**
```bash
curl -X DELETE https://api.tulia.ai/v1/tenants/{tenant_id} \\
  -H "Authorization: Bearer {jwt_token}" \\
  -H "X-TENANT-ID: {tenant_id}" \\
  -H "X-TENANT-API-KEY: {api_key}"
```
        """,
        responses={
            204: {
                'description': 'No Content - Tenant successfully deleted'
            },
            403: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                },
                'description': 'Forbidden - Missing required scope or not an Owner'
            },
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Tenant Management']
    )
    def delete(self, request, tenant_id):
        """Delete tenant (soft delete)."""
        user = request.user
        
        try:
            # Get tenant
            tenant = Tenant.objects.get(id=tenant_id, deleted_at__isnull=True)
        except Tenant.DoesNotExist:
            return Response(
                {'error': 'Tenant not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            # Soft delete tenant (validates permissions internally)
            TenantService.soft_delete_tenant(tenant, user)
            
            return Response(status=status.HTTP_204_NO_CONTENT)
        
        except PermissionDenied as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        
        except Exception as e:
            logger.error(f"Error deleting tenant: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Failed to delete tenant',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TenantMembersView(APIView):
    """
    List tenant members.
    
    GET /v1/tenants/{id}/members
    
    Returns all active members of the tenant with their roles.
    User must have membership in the tenant to access.
    """
    
    @extend_schema(
        summary="List tenant members",
        description="""
List all active members of a tenant with their roles and status.

Returns information about each member including:
- User details (email, name)
- Assigned roles
- Invitation status
- Join date and last activity

User must have an active membership in the tenant to access this endpoint.

**Example curl:**
```bash
curl -X GET https://api.tulia.ai/v1/tenants/{tenant_id}/members \\
  -H "Authorization: Bearer {jwt_token}"
```
        """,
        responses={
            200: TenantMemberSerializer(many=True),
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
        tags=['Tenant Management']
    )
    def get(self, request, tenant_id):
        """List tenant members."""
        user = request.user
        
        try:
            # Get tenant
            tenant = Tenant.objects.get(id=tenant_id, deleted_at__isnull=True)
        except Tenant.DoesNotExist:
            return Response(
                {'error': 'Tenant not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            # Validate user has access
            TenantService.validate_tenant_access(user, tenant)
            
            # Get all tenant members
            members = TenantUser.objects.for_tenant(tenant).select_related(
                'user'
            ).prefetch_related(
                'user_roles__role'
            ).order_by('-joined_at')
            
            # Serialize
            serializer = TenantMemberSerializer(members, many=True)
            
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        except PermissionDenied as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        
        except Exception as e:
            logger.error(f"Error listing tenant members: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Failed to retrieve tenant members',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(ratelimit(key='user_or_ip', rate='60/m', method='POST', block=True), name='dispatch')
class TenantMemberInviteView(APIView):
    """
    Invite user to tenant.
    
    POST /v1/tenants/{id}/members
    
    Invites a user to the tenant with specified roles.
    Requires users:manage scope.
    Rate limited to 60 requests per minute per user.
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'users:manage'}
    
    @extend_schema(
        summary="Invite user to tenant",
        description="""
Invite a user to join the tenant with specified roles.

**Required scope:** `users:manage`

If the user doesn't exist, creates a new user account with pending status.
If the user exists, creates a TenantUser membership with pending invitation.

The invited user will receive an email invitation to join the tenant.

**Example curl:**
```bash
curl -X POST https://api.tulia.ai/v1/tenants/{tenant_id}/members \\
  -H "Authorization: Bearer {jwt_token}" \\
  -H "X-TENANT-ID: {tenant_id}" \\
  -H "X-TENANT-API-KEY: {api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "email": "newuser@example.com",
    "roles": ["Admin", "Catalog Manager"]
  }'
```
        """,
        request=TenantMemberInviteSerializer,
        responses={
            201: TenantMemberSerializer,
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
        tags=['Tenant Management']
    )
    def post(self, request, tenant_id):
        """Invite user to tenant."""
        user = request.user
        
        try:
            # Get tenant
            tenant = Tenant.objects.get(id=tenant_id, deleted_at__isnull=True)
        except Tenant.DoesNotExist:
            return Response(
                {'error': 'Tenant not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Validate request data
        serializer = TenantMemberInviteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Invalid request data',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = serializer.validated_data
        
        try:
            # Invite user
            tenant_user = TenantService.invite_user(
                tenant=tenant,
                email=data['email'],
                role_names=data['roles'],
                invited_by=user
            )
            
            # Serialize response
            response_serializer = TenantMemberSerializer(tenant_user)
            
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
        
        except PermissionDenied as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        
        except ValueError as e:
            return Response(
                {
                    'error': str(e),
                    'details': {'message': 'Validation error'}
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        except Exception as e:
            logger.error(f"Error inviting user: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Failed to invite user',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(ratelimit(key='user_or_ip', rate='60/m', method='DELETE', block=True), name='dispatch')
class TenantMemberRemoveView(APIView):
    """
    Remove member from tenant.
    
    DELETE /v1/tenants/{id}/members/{user_id}
    
    Removes a user's membership from the tenant.
    Requires users:manage scope.
    Rate limited to 60 requests per minute per user.
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'users:manage'}
    
    @extend_schema(
        summary="Remove member from tenant",
        description="""
Remove a user's membership from the tenant.

**Required scope:** `users:manage`

This deactivates the user's TenantUser membership, revoking their access
to the tenant. The user account itself is not deleted.

**Example curl:**
```bash
curl -X DELETE https://api.tulia.ai/v1/tenants/{tenant_id}/members/{user_id} \\
  -H "Authorization: Bearer {jwt_token}" \\
  -H "X-TENANT-ID: {tenant_id}" \\
  -H "X-TENANT-API-KEY: {api_key}"
```
        """,
        responses={
            204: {
                'description': 'No Content - Member successfully removed'
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
        tags=['Tenant Management']
    )
    def delete(self, request, tenant_id, user_id):
        """Remove member from tenant."""
        current_user = request.user
        
        try:
            # Get tenant
            tenant = Tenant.objects.get(id=tenant_id, deleted_at__isnull=True)
        except Tenant.DoesNotExist:
            return Response(
                {'error': 'Tenant not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            # Get the membership to remove
            from apps.rbac.models import User
            target_user = User.objects.get(id=user_id)
            tenant_user = TenantUser.objects.get_membership(tenant, target_user)
            
            if not tenant_user:
                return Response(
                    {'error': 'User is not a member of this tenant'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Deactivate membership
            tenant_user.is_active = False
            tenant_user.save(update_fields=['is_active', 'updated_at'])
            
            # Log to audit trail
            AuditLog.log_action(
                action='member_removed',
                user=current_user,
                tenant=tenant,
                target_type='TenantUser',
                target_id=tenant_user.id,
                metadata={
                    'removed_user_email': target_user.email,
                    'removed_by_email': current_user.email,
                },
                request=request
            )
            
            return Response(status=status.HTTP_204_NO_CONTENT)
        
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        except PermissionDenied as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        
        except Exception as e:
            logger.error(f"Error removing member: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Failed to remove member',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
