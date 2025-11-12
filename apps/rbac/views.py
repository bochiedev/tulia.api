"""
RBAC REST API views.

Implements endpoints for:
- Membership management (invites, role assignments)
- Role management (CRUD, permission assignments)
- Permission management (list, user overrides)
- Audit log viewing
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.core.mail import send_mail
from django.conf import settings
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from apps.core.permissions import requires_scopes, HasTenantScopes
from apps.rbac.models import (
    User, TenantUser, Permission, Role, RolePermission,
    TenantUserRole, UserPermission, AuditLog
)
from apps.rbac.services import RBACService
from apps.rbac.serializers import (
    UserSerializer, TenantUserSerializer, MembershipDetailSerializer,
    PermissionSerializer, RoleSerializer, RoleDetailSerializer,
    RoleCreateSerializer, TenantUserRoleSerializer,
    UserPermissionSerializer, AuditLogSerializer,
    InviteMemberSerializer, AssignRolesSerializer,
    RolePermissionSerializer, UserPermissionCreateSerializer
)


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for list endpoints."""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100


@extend_schema_view(
    get=extend_schema(
        tags=['RBAC - Memberships'],
        summary='List user memberships',
        description='''
List all tenant memberships for the authenticated user.
Returns tenants where the user has an active TenantUser record with roles.

**No scope required** - users can always see their own memberships.

This endpoint is typically used for:
- Workspace switcher in the UI
- Determining which tenants a user can access
- Displaying user's roles per tenant
        ''',
        responses={
            200: MembershipDetailSerializer(many=True),
        },
        examples=[
            OpenApiExample(
                'Success Response',
                value={
                    'count': 2,
                    'memberships': [
                        {
                            'id': '123e4567-e89b-12d3-a456-426614174000',
                            'tenant': {
                                'id': '123e4567-e89b-12d3-a456-426614174001',
                                'name': 'Acme Corp',
                                'slug': 'acme-corp'
                            },
                            'user': {
                                'id': '123e4567-e89b-12d3-a456-426614174002',
                                'email': 'user@example.com'
                            },
                            'roles': [
                                {'id': 'role-1', 'name': 'Owner'},
                                {'id': 'role-2', 'name': 'Admin'}
                            ],
                            'invite_status': 'accepted',
                            'joined_at': '2025-01-01T00:00:00Z'
                        }
                    ]
                },
                response_only=True
            )
        ]
    )
)
class MembershipListView(APIView):
    """
    GET /v1/memberships/me
    
    List all tenant memberships for the authenticated user.
    Returns tenants where the user has an active TenantUser record with roles.
    
    No scope required - users can always see their own memberships.
    """
    
    def get(self, request):
        """List user's tenant memberships."""
        user = request.user
        
        # Get all active memberships for this user
        memberships = TenantUser.objects.filter(
            user=user,
            is_active=True,
            invite_status='accepted'
        ).select_related('tenant', 'invited_by').prefetch_related('user_roles__role')
        
        serializer = MembershipDetailSerializer(memberships, many=True)
        
        return Response({
            'count': memberships.count(),
            'memberships': serializer.data
        })


@extend_schema_view(
    post=extend_schema(
        tags=['RBAC - Memberships'],
        summary='Invite user to tenant',
        description='''
Invite a user to join a tenant.
Creates a TenantUser record with invite_status='pending' and optionally assigns roles.

**Required scope:** `users:manage`

The invited user will receive an email with an acceptance link.
If the user doesn't exist, a new User account is created.

**Example curl:**
```bash
curl -X POST https://api.tulia.ai/v1/memberships/{tenant_id}/invite \\
  -H "X-TENANT-ID: {tenant_id}" \\
  -H "X-TENANT-API-KEY: {api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "email": "newuser@example.com",
    "role_ids": ["role-uuid-1", "role-uuid-2"]
  }'
```
        ''',
        request=InviteMemberSerializer,
        responses={
            201: MembershipDetailSerializer,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                'Invite Request',
                value={
                    'email': 'newuser@example.com',
                    'role_ids': ['123e4567-e89b-12d3-a456-426614174000']
                },
                request_only=True
            ),
            OpenApiExample(
                'Success Response',
                value={
                    'id': '123e4567-e89b-12d3-a456-426614174000',
                    'tenant': {
                        'id': '123e4567-e89b-12d3-a456-426614174001',
                        'name': 'Acme Corp'
                    },
                    'user': {
                        'id': '123e4567-e89b-12d3-a456-426614174002',
                        'email': 'newuser@example.com'
                    },
                    'roles': [
                        {'id': 'role-1', 'name': 'Catalog Manager'}
                    ],
                    'invite_status': 'pending'
                },
                response_only=True
            )
        ]
    )
)
@requires_scopes('users:manage')
class MembershipInviteView(APIView):
    """
    POST /v1/memberships/{tenant_id}/invite
    
    Invite a user to join a tenant.
    Creates a TenantUser record with invite_status='pending' and optionally assigns roles.
    
    Required scope: users:manage
    """
    
    permission_classes = [HasTenantScopes]
    
    @transaction.atomic
    def post(self, request, tenant_id):
        """Invite a user to the tenant."""
        tenant = request.tenant
        inviting_user = request.user
        
        # Validate request data
        serializer = InviteMemberSerializer(
            data=request.data,
            context={'tenant': tenant}
        )
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        role_ids = serializer.validated_data.get('role_ids', [])
        
        # Get or create user
        user, user_created = User.objects.get_or_create(
            email=email,
            defaults={
                'is_active': True,
                'password_hash': User.objects.make_random_password()  # Temporary password
            }
        )
        
        # Check if membership already exists
        existing_membership = TenantUser.objects.filter(
            tenant=tenant,
            user=user
        ).first()
        
        if existing_membership:
            if existing_membership.is_active and existing_membership.invite_status == 'accepted':
                return Response(
                    {'error': 'User is already a member of this tenant'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            elif existing_membership.invite_status == 'pending':
                return Response(
                    {'error': 'User already has a pending invitation'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            else:
                # Reactivate revoked membership
                existing_membership.is_active = True
                existing_membership.invite_status = 'pending'
                existing_membership.invited_by = inviting_user
                existing_membership.save()
                tenant_user = existing_membership
        else:
            # Create new membership
            tenant_user = TenantUser.objects.create(
                tenant=tenant,
                user=user,
                invite_status='pending',
                invited_by=inviting_user
            )
        
        # Assign roles if provided
        if role_ids:
            roles = Role.objects.filter(tenant=tenant, id__in=role_ids)
            for role in roles:
                RBACService.assign_role(
                    tenant_user=tenant_user,
                    role=role,
                    assigned_by=inviting_user,
                    request=request
                )
        
        # Send invitation email
        self._send_invitation_email(user, tenant, inviting_user)
        
        # Log action
        AuditLog.log_action(
            action='user_invited',
            user=inviting_user,
            tenant=tenant,
            target_type='TenantUser',
            target_id=tenant_user.id,
            diff={
                'invited_user': email,
                'roles': list(roles.values_list('name', flat=True)) if role_ids else [],
            },
            metadata={
                'user_created': user_created,
            },
            request=request
        )
        
        serializer = MembershipDetailSerializer(tenant_user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def _send_invitation_email(self, user, tenant, inviting_user):
        """Send invitation email to user."""
        try:
            subject = f"You've been invited to join {tenant.name} on Tulia AI"
            message = f"""
Hello,

{inviting_user.get_full_name()} has invited you to join {tenant.name} on Tulia AI.

Please log in to accept your invitation: {settings.FRONTEND_URL}/accept-invite

Best regards,
The Tulia AI Team
            """
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=True
            )
        except Exception:
            # Don't fail the request if email fails
            pass


@extend_schema_view(
    post=extend_schema(
        tags=['RBAC - Memberships'],
        summary='Assign roles to user',
        description='''
Assign roles to a tenant user. Adds the specified roles to the user's existing roles.

**Required scope:** `users:manage`

**Example curl:**
```bash
curl -X POST https://api.tulia.ai/v1/memberships/{tenant_id}/{user_id}/roles \\
  -H "X-TENANT-ID: {tenant_id}" \\
  -H "X-TENANT-API-KEY: {api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{"role_ids": ["role-uuid-1", "role-uuid-2"]}'
```
        ''',
        request=AssignRolesSerializer,
        responses={
            200: MembershipDetailSerializer,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        }
    )
)
@requires_scopes('users:manage')
class MembershipRoleAssignView(APIView):
    """
    POST /v1/memberships/{tenant_id}/{user_id}/roles
    
    Assign roles to a tenant user.
    Adds the specified roles to the user's existing roles.
    
    Required scope: users:manage
    """
    
    permission_classes = [HasTenantScopes]
    
    @transaction.atomic
    def post(self, request, tenant_id, user_id):
        """Assign roles to a user."""
        tenant = request.tenant
        assigning_user = request.user
        
        # Validate request data
        serializer = AssignRolesSerializer(
            data=request.data,
            context={'tenant': tenant}
        )
        serializer.is_valid(raise_exception=True)
        
        role_ids = serializer.validated_data['role_ids']
        
        # Get target user and membership
        target_user = get_object_or_404(User, id=user_id)
        tenant_user = get_object_or_404(
            TenantUser,
            tenant=tenant,
            user=target_user,
            is_active=True
        )
        
        # Assign roles
        roles = Role.objects.filter(tenant=tenant, id__in=role_ids)
        assigned_roles = []
        
        for role in roles:
            user_role = RBACService.assign_role(
                tenant_user=tenant_user,
                role=role,
                assigned_by=assigning_user,
                request=request
            )
            assigned_roles.append(user_role)
        
        # Return updated membership
        serializer = MembershipDetailSerializer(tenant_user)
        return Response(serializer.data)


@extend_schema_view(
    delete=extend_schema(
        tags=['RBAC - Memberships'],
        summary='Remove role from user',
        description='''
Remove a role from a tenant user.

**Required scope:** `users:manage`
        ''',
        responses={
            204: None,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        }
    )
)
@requires_scopes('users:manage')
class MembershipRoleRemoveView(APIView):
    """
    DELETE /v1/memberships/{tenant_id}/{user_id}/roles/{role_id}
    
    Remove a role from a tenant user.
    
    Required scope: users:manage
    """
    
    permission_classes = [HasTenantScopes]
    
    @transaction.atomic
    def delete(self, request, tenant_id, user_id, role_id):
        """Remove a role from a user."""
        tenant = request.tenant
        removing_user = request.user
        
        # Get target user, membership, and role
        target_user = get_object_or_404(User, id=user_id)
        tenant_user = get_object_or_404(
            TenantUser,
            tenant=tenant,
            user=target_user,
            is_active=True
        )
        role = get_object_or_404(Role, tenant=tenant, id=role_id)
        
        # Remove role
        removed = RBACService.remove_role(
            tenant_user=tenant_user,
            role=role,
            removed_by=removing_user,
            request=request
        )
        
        if not removed:
            return Response(
                {'error': 'User does not have this role'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    get=extend_schema(
        tags=['RBAC - Roles'],
        summary='List tenant roles',
        description='''
List all roles for the authenticated tenant. Returns both system and custom roles.

**No specific scope required** - all authenticated users can view roles.

Query parameters:
- `type`: Filter by 'system' or 'custom'
- `include_permissions`: Set to 'true' to include permission details
        ''',
        parameters=[
            OpenApiParameter('type', OpenApiTypes.STR, description='Filter by role type: system or custom'),
            OpenApiParameter('include_permissions', OpenApiTypes.BOOL, description='Include permission details'),
        ],
        responses={
            200: RoleSerializer(many=True),
        }
    )
)
class RoleListView(APIView):
    """
    GET /v1/roles
    
    List all roles for the authenticated tenant.
    Returns both system and custom roles.
    
    No specific scope required - all authenticated users can view roles.
    """
    pagination_class = StandardResultsSetPagination
    
    def get(self, request):
        """List roles for the tenant."""
        tenant = request.tenant
        
        # Get all roles for this tenant
        roles = Role.objects.filter(tenant=tenant).order_by('is_system', 'name')
        
        # Filter by type if requested
        role_type = request.query_params.get('type')
        if role_type == 'system':
            roles = roles.filter(is_system=True)
        elif role_type == 'custom':
            roles = roles.filter(is_system=False)
        
        # Paginate
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(roles, request)
        
        serializer = RoleSerializer(
            page if page is not None else roles,
            many=True,
            context={'include_permissions': request.query_params.get('include_permissions') == 'true'}
        )
        
        if page is not None:
            return paginator.get_paginated_response(serializer.data)
        
        return Response({
            'count': roles.count(),
            'roles': serializer.data
        })


@extend_schema_view(
    post=extend_schema(
        tags=['RBAC - Roles'],
        summary='Create custom role',
        description='''
Create a new custom role for the tenant. System roles cannot be created via API.

**Required scope:** `users:manage`

After creating a role, use the `/v1/roles/{id}/permissions` endpoint to add permissions.
        ''',
        request=RoleCreateSerializer,
        responses={
            201: RoleSerializer,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        }
    )
)
@requires_scopes('users:manage')
class RoleCreateView(APIView):
    """
    POST /v1/roles
    
    Create a new custom role for the tenant.
    System roles cannot be created via API.
    
    Required scope: users:manage
    """
    
    permission_classes = [HasTenantScopes]
    
    @transaction.atomic
    def post(self, request):
        """Create a new role."""
        tenant = request.tenant
        creating_user = request.user
        
        # Validate request data
        serializer = RoleCreateSerializer(
            data=request.data,
            context={'tenant': tenant}
        )
        serializer.is_valid(raise_exception=True)
        
        # Create role
        role = Role.objects.create(
            tenant=tenant,
            name=serializer.validated_data['name'],
            description=serializer.validated_data.get('description', ''),
            is_system=False
        )
        
        # Log action
        AuditLog.log_action(
            action='role_created',
            user=creating_user,
            tenant=tenant,
            target_type='Role',
            target_id=role.id,
            diff={
                'name': role.name,
                'description': role.description,
            },
            request=request
        )
        
        serializer = RoleSerializer(role)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(
        tags=['RBAC - Roles'],
        summary='Get role details',
        description='''
Get detailed information about a role including all permissions.

**No specific scope required** - all authenticated users can view roles.
        ''',
        responses={
            200: RoleDetailSerializer,
            404: OpenApiTypes.OBJECT,
        }
    )
)
class RoleDetailView(APIView):
    """
    GET /v1/roles/{id}
    
    Get detailed information about a role including all permissions.
    
    No specific scope required - all authenticated users can view roles.
    """
    
    def get(self, request, role_id):
        """Get role details."""
        tenant = request.tenant
        
        role = get_object_or_404(Role, tenant=tenant, id=role_id)
        
        serializer = RoleDetailSerializer(role)
        return Response(serializer.data)


@extend_schema_view(
    get=extend_schema(
        tags=['RBAC - Roles'],
        summary='List role permissions',
        description='''
List all permissions for a role.

**No specific scope required** - all authenticated users can view role permissions.
        ''',
        responses={
            200: PermissionSerializer(many=True),
            404: OpenApiTypes.OBJECT,
        }
    )
)
class RolePermissionsView(APIView):
    """
    GET /v1/roles/{id}/permissions
    
    List all permissions for a role.
    
    No specific scope required - all authenticated users can view role permissions.
    """
    
    def get(self, request, role_id):
        """List permissions for a role."""
        tenant = request.tenant
        
        role = get_object_or_404(Role, tenant=tenant, id=role_id)
        
        permissions = Permission.objects.filter(
            role_permissions__role=role
        ).order_by('category', 'code')
        
        serializer = PermissionSerializer(permissions, many=True)
        
        return Response({
            'role_id': str(role.id),
            'role_name': role.name,
            'count': permissions.count(),
            'permissions': serializer.data
        })


@extend_schema_view(
    post=extend_schema(
        tags=['RBAC - Roles'],
        summary='Add permissions to role',
        description='''
Add permissions to a role. Creates RolePermission records for the specified permission codes.

**Required scope:** `users:manage`

This immediately affects all users assigned to this role. Their scope cache is invalidated.

**Example curl:**
```bash
curl -X POST https://api.tulia.ai/v1/roles/{role_id}/permissions \\
  -H "X-TENANT-ID: {tenant_id}" \\
  -H "X-TENANT-API-KEY: {api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "permission_codes": ["catalog:view", "catalog:edit", "orders:view"]
  }'
```
        ''',
        request=RolePermissionSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        }
    )
)
@requires_scopes('users:manage')
class RolePermissionsAddView(APIView):
    """
    POST /v1/roles/{id}/permissions
    
    Add permissions to a role.
    Creates RolePermission records for the specified permission codes.
    
    Required scope: users:manage
    """
    
    permission_classes = [HasTenantScopes]
    
    @transaction.atomic
    def post(self, request, role_id):
        """Add permissions to a role."""
        tenant = request.tenant
        modifying_user = request.user
        
        role = get_object_or_404(Role, tenant=tenant, id=role_id)
        
        # Validate request data
        serializer = RolePermissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        permission_codes = serializer.validated_data['permission_codes']
        
        # Get permissions
        permissions = Permission.objects.filter(code__in=permission_codes)
        
        # Add permissions to role
        added_permissions = []
        for permission in permissions:
            role_perm, created = RolePermission.objects.grant_permission(role, permission)
            if created:
                added_permissions.append(permission.code)
        
        # Invalidate cache for all users with this role
        tenant_users = TenantUser.objects.filter(
            user_roles__role=role,
            is_active=True
        )
        for tenant_user in tenant_users:
            RBACService.invalidate_scope_cache(tenant_user)
        
        # Log action
        AuditLog.log_action(
            action='role_permissions_added',
            user=modifying_user,
            tenant=tenant,
            target_type='Role',
            target_id=role.id,
            diff={
                'role': role.name,
                'added_permissions': added_permissions,
            },
            request=request
        )
        
        return Response({
            'role_id': str(role.id),
            'role_name': role.name,
            'added_permissions': added_permissions,
            'total_permissions': role.role_permissions.count()
        })


@extend_schema_view(
    get=extend_schema(
        tags=['RBAC - Permissions'],
        summary='List user permission overrides',
        description='''
List all permission overrides for a user. Shows both grants and denies.

**No specific scope required** - users can view their own overrides.
Users with `users:manage` scope can view others' overrides.
        ''',
        responses={
            200: UserPermissionSerializer(many=True),
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        }
    )
)
class UserPermissionsView(APIView):
    """
    GET /v1/users/{id}/permissions
    
    List all permission overrides for a user.
    Shows both grants and denies.
    
    No specific scope required - users can view their own overrides,
    users with users:manage can view others.
    """
    
    def get(self, request, user_id):
        """List permission overrides for a user."""
        tenant = request.tenant
        requesting_user = request.user
        
        # Get target user
        target_user = get_object_or_404(User, id=user_id)
        
        # Check permissions: users can view their own, or need users:manage for others
        if target_user.id != requesting_user.id:
            if 'users:manage' not in request.scopes:
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Get tenant user
        tenant_user = get_object_or_404(
            TenantUser,
            tenant=tenant,
            user=target_user,
            is_active=True
        )
        
        # Get permission overrides
        overrides = UserPermission.objects.filter(
            tenant_user=tenant_user
        ).select_related('permission').order_by('permission__category', 'permission__code')
        
        serializer = UserPermissionSerializer(overrides, many=True)
        
        return Response({
            'user_id': str(target_user.id),
            'user_email': target_user.email,
            'count': overrides.count(),
            'overrides': serializer.data
        })


@extend_schema_view(
    post=extend_schema(
        tags=['RBAC - Permissions'],
        summary='Grant or deny user permission',
        description='''
Grant or deny a permission to a specific user.
Creates a UserPermission override that takes precedence over role permissions.

**Required scope:** `users:manage`

**Deny overrides always win:** If a user has a permission from a role but a UserPermission
denies it, the user will NOT have that permission.

**Example curl (grant):**
```bash
curl -X POST https://api.tulia.ai/v1/users/{user_id}/permissions \\
  -H "X-TENANT-ID: {tenant_id}" \\
  -H "X-TENANT-API-KEY: {api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "permission_code": "finance:reconcile",
    "granted": true,
    "reason": "Temporary access for Q4 audit"
  }'
```

**Example curl (deny):**
```bash
curl -X POST https://api.tulia.ai/v1/users/{user_id}/permissions \\
  -H "X-TENANT-ID: {tenant_id}" \\
  -H "X-TENANT-API-KEY: {api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "permission_code": "catalog:edit",
    "granted": false,
    "reason": "Suspended pending investigation"
  }'
```
        ''',
        request=UserPermissionCreateSerializer,
        responses={
            201: UserPermissionSerializer,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        }
    )
)
@requires_scopes('users:manage')
class UserPermissionsManageView(APIView):
    """
    POST /v1/users/{id}/permissions
    
    Grant or deny a permission to a specific user.
    Creates a UserPermission override that takes precedence over role permissions.
    
    Required scope: users:manage
    """
    
    permission_classes = [HasTenantScopes]
    
    @transaction.atomic
    def post(self, request, user_id):
        """Grant or deny a permission to a user."""
        tenant = request.tenant
        granting_user = request.user
        
        # Get target user
        target_user = get_object_or_404(User, id=user_id)
        
        # Get tenant user
        tenant_user = get_object_or_404(
            TenantUser,
            tenant=tenant,
            user=target_user,
            is_active=True
        )
        
        # Validate request data
        serializer = UserPermissionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        permission_code = serializer.validated_data['permission_code']
        granted = serializer.validated_data['granted']
        reason = serializer.validated_data.get('reason', '')
        
        # Grant or deny permission
        if granted:
            user_perm = RBACService.grant_permission(
                tenant_user=tenant_user,
                permission_code=permission_code,
                reason=reason,
                granted_by=granting_user,
                request=request
            )
        else:
            user_perm = RBACService.deny_permission(
                tenant_user=tenant_user,
                permission_code=permission_code,
                reason=reason,
                granted_by=granting_user,
                request=request
            )
        
        serializer = UserPermissionSerializer(user_perm)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(
        tags=['RBAC - Permissions'],
        summary='List all permissions',
        description='''
List all available permissions in the system. Returns the canonical permission set.

**No specific scope required** - all authenticated users can view available permissions.

Query parameters:
- `category`: Filter by permission category (e.g., 'Catalog', 'Finance')
- `group_by_category`: Set to 'true' to group permissions by category

This endpoint is useful for:
- Building role permission assignment UIs
- Displaying available permissions to administrators
- Understanding the permission model
        ''',
        parameters=[
            OpenApiParameter('category', OpenApiTypes.STR, description='Filter by permission category'),
            OpenApiParameter('group_by_category', OpenApiTypes.BOOL, description='Group results by category'),
        ],
        responses={
            200: PermissionSerializer(many=True),
        },
        examples=[
            OpenApiExample(
                'Permissions List',
                value={
                    'count': 17,
                    'permissions': [
                        {
                            'id': '123e4567-e89b-12d3-a456-426614174000',
                            'code': 'catalog:view',
                            'label': 'View Catalog',
                            'description': 'View products and catalog',
                            'category': 'Catalog'
                        },
                        {
                            'id': '123e4567-e89b-12d3-a456-426614174001',
                            'code': 'finance:withdraw:approve',
                            'label': 'Approve Withdrawals',
                            'description': 'Approve withdrawal requests (four-eyes)',
                            'category': 'Finance'
                        }
                    ]
                },
                response_only=True
            )
        ]
    )
)
class PermissionListView(APIView):
    """
    GET /v1/permissions
    
    List all available permissions in the system.
    Returns the canonical permission set.
    
    No specific scope required - all authenticated users can view available permissions.
    """
    pagination_class = StandardResultsSetPagination
    
    def get(self, request):
        """List all permissions."""
        # Get all permissions
        permissions = Permission.objects.all().order_by('category', 'code')
        
        # Filter by category if requested
        category = request.query_params.get('category')
        if category:
            permissions = permissions.filter(category=category)
        
        # Group by category if requested (skip pagination for grouped view)
        if request.query_params.get('group_by_category') == 'true':
            serializer = PermissionSerializer(permissions, many=True)
            grouped = {}
            for perm in serializer.data:
                cat = perm['category']
                if cat not in grouped:
                    grouped[cat] = []
                grouped[cat].append(perm)
            
            return Response({
                'count': permissions.count(),
                'permissions_by_category': grouped
            })
        
        # Paginate
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(permissions, request)
        
        serializer = PermissionSerializer(page if page is not None else permissions, many=True)
        
        if page is not None:
            return paginator.get_paginated_response(serializer.data)
        
        return Response({
            'count': permissions.count(),
            'permissions': serializer.data
        })


@extend_schema_view(
    get=extend_schema(
        tags=['RBAC - Audit'],
        summary='List audit logs',
        description='''
List audit logs for the tenant. Supports filtering by action, target_type, user, and date range.

**Required scope:** `analytics:view`

Audit logs track all RBAC changes and sensitive operations including:
- User invitations and role assignments
- Permission grants and denials
- Role modifications
- Financial operations (withdrawals, approvals)
- Catalog changes

Query parameters:
- `action`: Filter by action type (e.g., 'user_invited', 'role_assigned')
- `target_type`: Filter by target type (e.g., 'TenantUser', 'Role')
- `user_id`: Filter by user who performed the action
- `from_date`: Filter by date range start (ISO 8601)
- `to_date`: Filter by date range end (ISO 8601)
        ''',
        parameters=[
            OpenApiParameter('action', OpenApiTypes.STR, description='Filter by action type'),
            OpenApiParameter('target_type', OpenApiTypes.STR, description='Filter by target type'),
            OpenApiParameter('user_id', OpenApiTypes.UUID, description='Filter by user ID'),
            OpenApiParameter('from_date', OpenApiTypes.DATETIME, description='Filter from date'),
            OpenApiParameter('to_date', OpenApiTypes.DATETIME, description='Filter to date'),
        ],
        responses={
            200: AuditLogSerializer(many=True),
            403: OpenApiTypes.OBJECT,
        }
    )
)
@requires_scopes('analytics:view')
class AuditLogListView(APIView):
    """
    GET /v1/audit-logs
    
    List audit logs for the tenant.
    Supports filtering by action, target_type, user, and date range.
    
    Required scope: analytics:view
    """
    
    permission_classes = [HasTenantScopes]
    pagination_class = StandardResultsSetPagination
    
    def get(self, request):
        """List audit logs."""
        tenant = request.tenant
        
        # Get audit logs for this tenant
        logs = AuditLog.objects.filter(tenant=tenant).select_related('user', 'tenant')
        
        # Filter by action
        action = request.query_params.get('action')
        if action:
            logs = logs.filter(action=action)
        
        # Filter by target_type
        target_type = request.query_params.get('target_type')
        if target_type:
            logs = logs.filter(target_type=target_type)
        
        # Filter by user
        user_id = request.query_params.get('user_id')
        if user_id:
            logs = logs.filter(user_id=user_id)
        
        # Filter by date range
        from_date = request.query_params.get('from_date')
        if from_date:
            logs = logs.filter(created_at__gte=from_date)
        
        to_date = request.query_params.get('to_date')
        if to_date:
            logs = logs.filter(created_at__lte=to_date)
        
        # Paginate
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(logs, request)
        
        serializer = AuditLogSerializer(page, many=True)
        
        return paginator.get_paginated_response(serializer.data)
