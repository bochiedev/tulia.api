---
inclusion: always
---

# RBAC Enforcement Checklist for Tulia AI

## CRITICAL: All API Views MUST Enforce RBAC

Every API endpoint in this application MUST enforce Role-Based Access Control (RBAC) using scope-based permissions. This is a **SECURITY REQUIREMENT** and must never be bypassed.

## Mandatory RBAC Patterns

### Pattern 1: Fixed Scope (Single Permission)

Use when an endpoint requires only one permission regardless of HTTP method:

```python
from apps.core.permissions import HasTenantScopes

class MyView(APIView):
    """
    My view description.
    
    Required scope: my:scope
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'my:scope'}
    
    def get(self, request):
        # Implementation
        pass
```

### Pattern 2: Dynamic Scopes (Method-Based Permissions)

Use when different HTTP methods require different permissions:

```python
from apps.core.permissions import HasTenantScopes

class MyView(APIView):
    """
    My view description.
    
    Required scopes:
    - GET: my:view
    - POST: my:edit
    """
    permission_classes = [HasTenantScopes]
    
    def check_permissions(self, request):
        """Set required scopes based on HTTP method."""
        if request.method == 'GET':
            self.required_scopes = {'my:view'}
        elif request.method == 'POST':
            self.required_scopes = {'my:edit'}
        elif request.method in ['PUT', 'PATCH', 'DELETE']:
            self.required_scopes = {'my:edit'}
        super().check_permissions(request)
    
    def get(self, request):
        # Implementation
        pass
    
    def post(self, request):
        # Implementation
        pass
```

### Pattern 3: Class Decorator (ViewSets)

Use for ViewSets that need the same scopes for all actions:

```python
from apps.core.permissions import requires_scopes

@requires_scopes('my:view', 'my:edit')
class MyViewSet(viewsets.ModelViewSet):
    """
    My viewset description.
    
    Required scopes: my:view, my:edit
    """
    # Implementation
    pass
```

### Pattern 4: Function-Based Views

Use for function-based views:

```python
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from apps.core.permissions import HasTenantScopes, requires_scopes

@api_view(['GET'])
@permission_classes([IsAuthenticated, HasTenantScopes])
@requires_scopes('my:view')
def my_view(request):
    """
    My view description.
    
    Required scope: my:view
    """
    # Implementation
    pass
```

## Canonical Permission Scopes

These are the standard permission scopes used throughout the application:

### Catalog & Products
- `catalog:view` - View products and catalog
- `catalog:edit` - Create, update, delete products

### Services & Appointments
- `services:view` - View services
- `services:edit` - Create, update, delete services
- `availability:edit` - Manage availability windows
- `appointments:view` - View appointments
- `appointments:edit` - Create, update, cancel appointments

### Orders
- `orders:view` - View orders
- `orders:edit` - Create, update orders

### Conversations & Messaging
- `conversations:view` - View conversations and messages
- `handoff:perform` - Perform human handoff

### Finance & Wallet
- `finance:view` - View wallet balance and transactions
- `finance:withdraw:initiate` - Initiate withdrawal requests
- `finance:withdraw:approve` - Approve withdrawals (four-eyes)
- `finance:reconcile` - Reconcile transactions

### Analytics
- `analytics:view` - View analytics and reports

### Integrations
- `integrations:manage` - Manage integrations (WooCommerce, Shopify, Twilio)

### User Management
- `users:manage` - Manage users, roles, and permissions

## Exceptions (Public Endpoints)

Only these endpoints are allowed to be public (no RBAC):

1. **Health Check** (`/v1/health`)
   ```python
   class HealthCheckView(APIView):
       authentication_classes = []
       permission_classes = []
   ```

2. **Webhook Endpoints** (External services)
   - Twilio webhooks (verified by signature)
   - WooCommerce webhooks (verified by signature)
   - Shopify webhooks (verified by signature)

All other endpoints MUST enforce RBAC.

## Pre-Deployment Checklist

Before deploying any new view or endpoint:

- [ ] Does the view have `permission_classes = [HasTenantScopes]`?
- [ ] Does the view define `required_scopes` or implement `check_permissions()`?
- [ ] Are the required scopes documented in the docstring?
- [ ] Are 403 responses documented in the OpenAPI schema?
- [ ] Have you tested that the endpoint returns 403 without the required scope?
- [ ] Have you tested that the endpoint works WITH the required scope?

## Testing RBAC Enforcement

Every view MUST have tests that verify:

1. **403 without scope** - User without required scope gets 403
2. **200/201 with scope** - User with required scope can access
3. **Tenant isolation** - User cannot access another tenant's data

Example test:

```python
def test_endpoint_requires_scope(self, tenant, user):
    """Test that endpoint requires proper scope."""
    # Create user WITHOUT required scope
    tenant_user = TenantUser.objects.create(tenant=tenant, user=user)
    
    # Make request
    response = client.get('/v1/my-endpoint', headers={
        'X-TENANT-ID': str(tenant.id),
        'X-TENANT-API-KEY': 'test-key'
    })
    
    # Should return 403
    assert response.status_code == 403
```

## Common Mistakes to Avoid

### ❌ WRONG: No permission class
```python
class MyView(APIView):
    def get(self, request):
        # SECURITY ISSUE: Anyone can access!
        pass
```

### ❌ WRONG: Only authentication, no RBAC
```python
class MyView(APIView):
    permission_classes = [IsAuthenticated]  # Not enough!
    def get(self, request):
        pass
```

### ❌ WRONG: Checking roles instead of scopes
```python
# DON'T check role names in code
if request.membership.roles.filter(name='Owner').exists():
    # This violates RBAC principles
```

### ✅ CORRECT: Check scopes
```python
# DO check scopes
from apps.rbac.services import RBACService

if RBACService.has_scope(request.membership, 'my:scope'):
    # This is the correct way
```

## Audit History

- **2025-11-11**: Initial RBAC enforcement audit completed
  - Fixed 4 views missing RBAC: WalletBalanceView, WalletTransactionsView, ProductVariantListView, ProductVariantDetailView
  - All other views confirmed to have proper RBAC enforcement
  - Created this checklist to prevent future regressions

## When Adding New Views

1. Copy one of the patterns above
2. Replace `my:scope` with the appropriate canonical scope
3. Add the required scope to the docstring
4. Add 403 response to OpenAPI schema
5. Write tests for both 403 (without scope) and 200 (with scope)
6. Run the full test suite to ensure no regressions

## Enforcement

This is a **MANDATORY** security requirement. Code reviews MUST verify RBAC enforcement before merging. Any PR that adds a view without proper RBAC enforcement will be rejected.
