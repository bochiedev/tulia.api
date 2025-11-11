---
inclusion: always
---

# RBAC Quick Reference Card

## 🚨 SECURITY REQUIREMENT: All API Views MUST Enforce RBAC

## Quick Copy-Paste Templates

### Template 1: Single Scope (Most Common)
```python
from apps.core.permissions import HasTenantScopes

class MyView(APIView):
    """
    Description.
    
    Required scope: my:scope
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'my:scope'}
```

### Template 2: Method-Based Scopes
```python
from apps.core.permissions import HasTenantScopes

class MyView(APIView):
    """
    Description.
    
    Required scopes:
    - GET: my:view
    - POST/PUT/DELETE: my:edit
    """
    permission_classes = [HasTenantScopes]
    
    def check_permissions(self, request):
        if request.method == 'GET':
            self.required_scopes = {'my:view'}
        else:
            self.required_scopes = {'my:edit'}
        super().check_permissions(request)
```

### Template 3: ViewSet with Decorator
```python
from apps.core.permissions import requires_scopes

@requires_scopes('my:view', 'my:edit')
class MyViewSet(viewsets.ModelViewSet):
    """
    Description.
    
    Required scopes: my:view, my:edit
    """
    pass
```

## Standard Permission Scopes

| Scope | Use For |
|-------|---------|
| `catalog:view` | View products/variants |
| `catalog:edit` | Create/update/delete products |
| `orders:view` | View orders |
| `orders:edit` | Create/update orders |
| `services:view` | View services |
| `services:edit` | Manage services |
| `appointments:view` | View appointments |
| `appointments:edit` | Manage appointments |
| `finance:view` | View wallet/transactions |
| `finance:withdraw:initiate` | Request withdrawals |
| `finance:withdraw:approve` | Approve withdrawals |
| `conversations:view` | View messages |
| `analytics:view` | View reports |
| `integrations:manage` | Manage integrations |
| `users:manage` | Manage users/roles |

## Pre-Commit Checklist

Before committing a new view:
- [ ] Added `permission_classes = [HasTenantScopes]`
- [ ] Defined `required_scopes` or `check_permissions()`
- [ ] Documented scope in docstring
- [ ] Added 403 response to OpenAPI schema
- [ ] Wrote test for 403 without scope
- [ ] Wrote test for 200 with scope

## Common Mistakes

❌ **WRONG:** No permission class
```python
class MyView(APIView):
    def get(self, request):
        pass  # SECURITY ISSUE!
```

✅ **CORRECT:** With RBAC
```python
class MyView(APIView):
    permission_classes = [HasTenantScopes]
    required_scopes = {'my:scope'}
    
    def get(self, request):
        pass
```

## Testing Pattern

```python
def test_requires_scope(self, tenant, user):
    # User without scope
    tenant_user = TenantUser.objects.create(tenant=tenant, user=user)
    
    response = client.get('/v1/endpoint', headers={
        'X-TENANT-ID': str(tenant.id),
        'X-TENANT-API-KEY': 'key'
    })
    
    assert response.status_code == 403  # Must be forbidden
```

## Need Help?

See full documentation: `.kiro/steering/rbac-enforcement-checklist.md`
