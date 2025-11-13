"""
Tenant Management API URLs.

Endpoints for:
- Listing user's tenants
- Creating new tenants
- Viewing/updating tenant details
- Managing tenant members
- Deleting tenants
"""
from django.urls import path
from apps.tenants.views_tenant_management import (
    TenantListView,
    TenantCreateView,
    TenantDetailView,
    TenantUpdateView,
    TenantDeleteView,
    TenantMembersView,
    TenantMemberInviteView,
    TenantMemberRemoveView,
)

app_name = 'tenant_management'

urlpatterns = [
    # Tenant CRUD
    path('tenants', TenantListView.as_view(), name='tenant-list'),
    path('tenants/create', TenantCreateView.as_view(), name='tenant-create'),
    path('tenants/<uuid:tenant_id>', TenantDetailView.as_view(), name='tenant-detail'),
    path('tenants/<uuid:tenant_id>/update', TenantUpdateView.as_view(), name='tenant-update'),
    path('tenants/<uuid:tenant_id>/delete', TenantDeleteView.as_view(), name='tenant-delete'),
    
    # Member management
    path('tenants/<uuid:tenant_id>/members', TenantMembersView.as_view(), name='tenant-members'),
    path('tenants/<uuid:tenant_id>/members/invite', TenantMemberInviteView.as_view(), name='tenant-member-invite'),
    path('tenants/<uuid:tenant_id>/members/<uuid:user_id>', TenantMemberRemoveView.as_view(), name='tenant-member-remove'),
]
