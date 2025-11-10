# RBAC Implementation Guide

## Overview
This document explains how RBAC is configured in Tulia AI and when/where to use the seed data.

## 1. Where RBAC Information Lives

### Steering Document (`.kiro/steering/tulia ai steering doc.md`)
Contains the **principles and seed data**:
- Canonical permissions list
- Default roles and their permission mappings
- Acceptance criteria for testing
- RBAC principles and patterns

### Agent Hook (`.kiro/hooks/rbac-automation.kiro.hook`)
Contains the **implementation instructions** for Kiro:
- Complete scaffolding steps
- Model definitions
- Middleware and permission class specs
- Management command requirements
- Test generation requirements
- API endpoint specifications

## 2. Canonical Permissions (When to Seed)

These permissions should be seeded **globally** (not per-tenant) via `seed_permissions` management command:

```python
# Run on initial deployment or when adding new permissions
python manage.py seed_permissions
```

**Permissions List:**
- `catalog:view`, `catalog:edit`
- `services:view`, `services:edit`, `availability:edit`
- `conversations:view`, `handoff:perform`
- `orders:view`, `orders:edit`
- `appointments:view`, `appointments:edit`
- `analytics:view`
- `finance:view`, `finance:withdraw:initiate`, `finance:withdraw:approve`, `finance:reconcile`
- `integrations:manage`
- `users:manage`

## 3. Default Roles (When to Seed)

Roles are **per-tenant** and should be seeded:
- Automatically via signal when a new Tenant is created
- Manually via `seed_tenant_roles` management command for existing tenants

```python
# Run for existing tenants
python manage.py seed_tenant_roles --tenant-id=<uuid>

# Or seed all tenants
python manage.py seed_tenant_roles --all
```

**Role Definitions:**

### Owner
- **Permissions**: ALL
- **Use Case**: Tenant creator, full control

### Admin
- **Permissions**: ALL minus `finance:withdraw:approve`
- **Configurable**: Set `RBAC_ADMIN_CAN_APPROVE=true` to grant approve permission
- **Use Case**: Day-to-day management, cannot approve withdrawals

### Finance Admin
- **Permissions**: `analytics:view`, `finance:*`, `orders:view`
- **Use Case**: Financial operations, can both initiate and approve withdrawals

### Catalog Manager
- **Permissions**: `analytics:view`, `catalog:*`, `services:*`, `availability:edit`
- **Use Case**: Manage products, services, and availability

### Support Lead
- **Permissions**: `conversations:view`, `handoff:perform`, `orders:view`, `appointments:view`
- **Use Case**: Customer support, can view and handoff conversations

### Analyst
- **Permissions**: `analytics:view`, `catalog:view`, `services:view`, `orders:view`, `appointments:view`
- **Use Case**: Read-only access for reporting and analysis

## 4. Where to Use Permissions

### In Views (DRF)
```python
from core.permissions import HasTenantScopes, requires_scopes

@requires_scopes("catalog:view")
class ProductListView(APIView):
    permission_classes = [HasTenantScopes]
    
    def get(self, request):
        # User must have catalog:view scope
        pass

@requires_scopes("catalog:edit")
class ProductCreateView(APIView):
    permission_classes = [HasTenantScopes]
    
    def post(self, request):
        # User must have catalog:edit scope
        pass
```

### In Middleware
```python
# TenantContextMiddleware automatically:
# 1. Resolves tenant from X-TENANT-ID
# 2. Validates TenantUser membership
# 3. Assembles scopes from roles + overrides
# 4. Sets request.scopes
```

### In Services
```python
from rbac.services import resolve_scopes, validate_four_eyes

# Get user's scopes
scopes = resolve_scopes(tenant_user)

# Check four-eyes for finance operations
validate_four_eyes(
    initiator=user_a,
    approver=user_b,
    action="withdraw:approve"
)  # Raises error if same user
```

## 5. Testing Requirements

### Unit Tests
- **Scope Resolution**: Test that roles + overrides correctly assemble scopes
- **Deny Wins**: Test that UserPermission with is_deny=True overrides role grants
- **Missing Scope**: Test that missing scope returns 403
- **Present Scope**: Test that present scope returns 200

### API Tests
- **Catalog**: Test catalog:view for GET, catalog:edit for POST
- **Services**: Test services:edit for create, availability:edit for windows
- **Finance Four-Eyes**: Test that initiator cannot approve, different user can approve
- **Cross-Tenant**: Test that switching tenant without membership returns 403

### Seeder Tests
- **Idempotency**: Test that running seeders multiple times doesn't duplicate data
- **Completeness**: Test that all permissions and roles are created

## 6. Four-Eyes Pattern (Finance Operations)

**Requirement**: Withdrawals require two different users
- User A with `finance:withdraw:initiate` creates withdrawal
- User B with `finance:withdraw:approve` approves withdrawal
- If User A tries to approve their own withdrawal → 409 Conflict

**Implementation**:
```python
# In withdrawal approval endpoint
validate_four_eyes(
    initiator=withdrawal.created_by,
    approver=request.user,
    action="withdraw:approve"
)
```

## 7. Override Pattern

**Deny Wins Over Allow**:
- User has Role "Catalog Manager" which grants `catalog:edit`
- Admin adds UserPermission for user with `catalog:edit` and `is_deny=True`
- Result: User cannot edit catalog (deny wins)

**Use Cases**:
- Temporarily restrict a user without changing their role
- Fine-grained control for specific users
- Compliance requirements (e.g., user on leave)

## 8. Cross-Tenant Isolation

**Key Principle**: Same user can be member of multiple tenants, but data never mixes

**Implementation**:
- Every query filters by `tenant_id` from `request.tenant`
- Middleware validates TenantUser exists for X-TENANT-ID
- Customer records are unique by `(tenant_id, phone_e164)`
- Same phone number in different tenants = different Customer records

**Testing**:
- Create User with TenantUser in Tenant A and Tenant B
- Switch X-TENANT-ID header between requests
- Verify each request only sees that tenant's data

## 9. Triggering RBAC Implementation

To implement the complete RBAC system, trigger the agent hook:

```
"add RBAC" or "implement RBAC"
```

This will:
1. Create `rbac` app with all models
2. Create/update middleware and permission classes
3. Create management commands
4. Wire signals
5. Generate tests
6. Create API endpoints
7. Update OpenAPI schema

## 10. Configuration Settings

Add to Django settings:

```python
# RBAC Configuration
RBAC_ADMIN_CAN_APPROVE = False  # Set True to allow Admin role to approve withdrawals
RBAC_DENY_OVERRIDES_ALLOW = True  # Deny permissions win over role grants
```
