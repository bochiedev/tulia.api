# RBAC Quick Reference Card

## Import

```python
from apps.core.permissions import HasTenantScopes, requires_scopes
```

## Basic Patterns

### Pattern 1: Class-Level Scopes (Same for all methods)

```python
@requires_scopes('catalog:view')
class ProductListView(APIView):
    permission_classes = [HasTenantScopes]
    
    def get(self, request):
        # Requires catalog:view
        pass
```

### Pattern 2: Method-Level Scopes (Different per method)

```python
class ProductListView(APIView):
    permission_classes = [HasTenantScopes]
    
    @requires_scopes('catalog:view')
    def get(self, request):
        # Requires catalog:view
        pass
    
    @requires_scopes('catalog:edit')
    def post(self, request):
        # Requires catalog:edit
        pass
```

### Pattern 3: Multiple Scopes

```python
@requires_scopes('catalog:view', 'analytics:view', 'orders:view')
class DashboardView(APIView):
    permission_classes = [HasTenantScopes]
    
    def get(self, request):
        # Requires ALL three scopes
        pass
```

### Pattern 4: Manual Declaration

```python
class ProductListView(APIView):
    permission_classes = [HasTenantScopes]
    required_scopes = {'catalog:view', 'catalog:edit'}
    
    def get(self, request):
        # Requires both scopes
        pass
```

## Available Scopes

| Scope | Description |
|-------|-------------|
| `catalog:view` | View products and services |
| `catalog:edit` | Create, update, delete products |
| `services:view` | View services |
| `services:edit` | Manage services |
| `availability:edit` | Manage availability windows |
| `conversations:view` | View conversations |
| `handoff:perform` | Perform human handoff |
| `orders:view` | View orders |
| `orders:edit` | Manage orders |
| `appointments:view` | View appointments |
| `appointments:edit` | Manage appointments |
| `analytics:view` | View analytics |
| `finance:view` | View wallet/transactions |
| `finance:withdraw:initiate` | Initiate withdrawals |
| `finance:withdraw:approve` | Approve withdrawals |
| `finance:reconcile` | Financial reconciliation |
| `integrations:manage` | Manage integrations |
| `users:manage` | Manage users and roles |

## Common Use Cases

### Read-Only Endpoint
```python
@requires_scopes('catalog:view')
class ProductListView(APIView):
    permission_classes = [HasTenantScopes]
```

### Read-Write Endpoint
```python
class ProductListView(APIView):
    permission_classes = [HasTenantScopes]
    
    @requires_scopes('catalog:view')
    def get(self, request):
        pass
    
    @requires_scopes('catalog:edit')
    def post(self, request):
        pass
```

### Admin-Only Endpoint
```python
@requires_scopes('users:manage', 'analytics:view')
class AdminDashboardView(APIView):
    permission_classes = [HasTenantScopes]
```

### Four-Eyes Financial Operation
```python
class WithdrawalInitiateView(APIView):
    permission_classes = [HasTenantScopes]
    
    @requires_scopes('finance:withdraw:initiate')
    def post(self, request):
        # User A initiates
        pass

class WithdrawalApproveView(APIView):
    permission_classes = [HasTenantScopes]
    
    @requires_scopes('finance:withdraw:approve')
    def post(self, request, transaction_id):
        # User B approves (must be different from initiator)
        pass
```

## Error Response

When user lacks required scopes:

**HTTP 403 Forbidden**
```json
{
  "detail": "You do not have permission to perform this action."
}
```

**Log Entry** (for debugging):
```
WARNING: Permission denied: User test@example.com @ test-tenant missing scopes: {'catalog:edit'}
```

## Testing

```python
def test_requires_scope(client, tenant, user):
    request = client.get('/v1/products')
    request.tenant = tenant
    request.user = user
    request.scopes = {'catalog:view'}  # Set user scopes
    
    view = ProductListView()
    permission = HasTenantScopes()
    
    assert permission.has_permission(request, view) is True
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Always getting 403 | Check that `TenantContextMiddleware` is configured |
| Scopes not set | Verify `RBACService.resolve_scopes()` is called in middleware |
| Object permission fails | Ensure object has `tenant` attribute |
| Decorator not working | Ensure `permission_classes = [HasTenantScopes]` is set |

## Best Practices

1. ✅ Always include `HasTenantScopes` in `permission_classes`
2. ✅ Use method-level decorators when methods need different scopes
3. ✅ Use class-level decorator when all methods need same scopes
4. ✅ Check logs when debugging permission issues
5. ✅ Write tests to verify scope enforcement
6. ✅ Document required scopes in API documentation
