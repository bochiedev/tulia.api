"""
RBAC API URLs.

Provides endpoints for:
- Membership management (invites, role assignments)
- Role management (CRUD, permission assignments)
- Permission management (list, user overrides)
- Audit log viewing
"""
from django.urls import path
from apps.rbac.views import (
    MembershipListView,
    MembershipInviteView,
    MembershipRoleAssignView,
    MembershipRoleRemoveView,
    RoleListView,
    RoleCreateView,
    RoleDetailView,
    RolePermissionsView,
    RolePermissionsAddView,
    UserPermissionsView,
    UserPermissionsManageView,
    PermissionListView,
    AuditLogListView,
)

app_name = 'rbac'

urlpatterns = [
    # Membership endpoints
    path('memberships/me', MembershipListView.as_view(), name='membership-list'),
    path('memberships/<uuid:tenant_id>/invite', MembershipInviteView.as_view(), name='membership-invite'),
    path('memberships/<uuid:tenant_id>/<uuid:user_id>/roles', MembershipRoleAssignView.as_view(), name='membership-role-assign'),
    path('memberships/<uuid:tenant_id>/<uuid:user_id>/roles/<uuid:role_id>', MembershipRoleRemoveView.as_view(), name='membership-role-remove'),
    
    # Role endpoints
    path('roles', RoleListView.as_view(), name='role-list'),
    path('roles/create', RoleCreateView.as_view(), name='role-create'),
    path('roles/<uuid:role_id>', RoleDetailView.as_view(), name='role-detail'),
    path('roles/<uuid:role_id>/permissions', RolePermissionsView.as_view(), name='role-permissions'),
    path('roles/<uuid:role_id>/permissions/add', RolePermissionsAddView.as_view(), name='role-permissions-add'),
    
    # User permission override endpoints
    path('users/<uuid:user_id>/permissions', UserPermissionsView.as_view(), name='user-permissions'),
    path('users/<uuid:user_id>/permissions/manage', UserPermissionsManageView.as_view(), name='user-permissions-manage'),
    
    # Permission list endpoint
    path('permissions', PermissionListView.as_view(), name='permission-list'),
    
    # Audit log endpoint
    path('audit-logs', AuditLogListView.as_view(), name='audit-log-list'),
]
