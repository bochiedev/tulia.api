# RBAC Permission Usage Guide

This guide demonstrates how to use the `HasTenantScopes` permission class and `@requires_scopes` decorator to enforce RBAC permissions on API endpoints.

## Overview

The RBAC system provides two main components:

1. **HasTenantScopes**: A DRF permission class that checks if the user has required scopes
2. **@requires_scopes**: A decorator to declare required scopes on views

## Basic Usage

### Class-Level Scope Requirements

Use the decorator on the entire view class to require the same scopes for all methods:

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from apps.core.permissions import HasTenantScopes, requires_scopes

@requires_scopes('catalog:view')
class ProductListView(APIView):
    permission_classes = [HasTenantScopes]
    
    def get(self, request):
        # Only users with 'catalog:view' scope can access this
        products = Product.objects.filter(tenant=request.tenant)
        return Response({'products': list(products.values())})
```

### Method-Level Scope Requirements

Use the decorator on individual methods to require different scopes per HTTP method:

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from apps.core.permissions import HasTenantScopes, requires_scopes

class ProductListView(APIView):
    permission_classes = [HasTenantScopes]
    
    @requires_scopes('catalog:view')
    def get(self, request):
        # Only users with 'catalog:view' scope can GET
        products = Product.objects.filter(tenant=request.tenant)
        return Response({'products': list(products.values())})
    
    @requires_scopes('catalog:edit')
    def post(self, request):
        # Only users with 'catalog:edit' scope can POST
        product = Product.objects.create(
            tenant=request.tenant,
            **request.data
        )
        return Response({'product': product.id}, status=201)
```

### Multiple Scope Requirements

Require multiple scopes by passing them as separate arguments:

```python
@requires_scopes('catalog:view', 'catalog:edit', 'analytics:view')
class ProductAnalyticsView(APIView):
    permission_classes = [HasTenantScopes]
    
    def get(self, request):
        # User must have ALL three scopes to access this
        # ...
        return Response({'analytics': data})
```

### Manual Scope Declaration

You can also set `required_scopes` directly on the view without using the decorator:

```python
class ProductListView(APIView):
    permission_classes = [HasTenantScopes]
    required_scopes = {'catalog:view', 'catalog:edit'}
    
    def get(self, request):
        # User must have both scopes
        # ...
        return Response({'products': data})
```

## Object-Level Permissions

The `HasTenantScopes` permission class automatically checks that objects belong to the request's tenant:

```python
class ProductDetailView(APIView):
    permission_classes = [HasTenantScopes]
    required_scopes = {'catalog:view'}
    
    def get(self, request, product_id):
        product = Product.objects.get(id=product_id)
        
        # HasTenantScopes.has_object_permission() automatically verifies
        # that product.tenant == request.tenant
        # If not, returns 403 Forbidden
        
        return Response({'product': product.data})
```

## Error Responses

When a user lacks required scopes, the permission class returns a 403 Forbidden response and logs the denial:

```json
{
  "detail": "You do not have permission to perform this action."
}
```

The log entry includes:
- User email
- Tenant slug
- Required scopes
- User's actual scopes
- Missing scopes
- Request path and method
- Request ID for tracing

## Complete Example

Here's a complete example showing different permission patterns:

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from apps.core.permissions import HasTenantScopes, requires_scopes
from apps.catalog.models import Product

class ProductListView(APIView):
    """
    List and create products.
    
    GET requires catalog:view
    POST requires catalog:edit
    """
    permission_classes = [HasTenantScopes]
    
    @requires_scopes('catalog:view')
    def get(self, request):
        """List all products for the tenant."""
        products = Product.objects.filter(
            tenant=request.tenant,
            is_active=True
        )
        return Response({
            'products': [p.to_dict() for p in products]
        })
    
    @requires_scopes('catalog:edit')
    def post(self, request):
        """Create a new product."""
        product = Product.objects.create(
            tenant=request.tenant,
            **request.data
        )
        return Response(
            {'product': product.to_dict()},
            status=status.HTTP_201_CREATED
        )


class ProductDetailView(APIView):
    """
    Retrieve, update, or delete a product.
    
    GET requires catalog:view
    PUT/DELETE require catalog:edit
    """
    permission_classes = [HasTenantScopes]
    
    @requires_scopes('catalog:view')
    def get(self, request, product_id):
        """Get product details."""
        try:
            product = Product.objects.get(
                id=product_id,
                tenant=request.tenant
            )
            return Response({'product': product.to_dict()})
        except Product.DoesNotExist:
            return Response(
                {'error': 'Product not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @requires_scopes('catalog:edit')
    def put(self, request, product_id):
        """Update product."""
        try:
            product = Product.objects.get(
                id=product_id,
                tenant=request.tenant
            )
            for key, value in request.data.items():
                setattr(product, key, value)
            product.save()
            return Response({'product': product.to_dict()})
        except Product.DoesNotExist:
            return Response(
                {'error': 'Product not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @requires_scopes('catalog:edit')
    def delete(self, request, product_id):
        """Delete product."""
        try:
            product = Product.objects.get(
                id=product_id,
                tenant=request.tenant
            )
            product.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Product.DoesNotExist:
            return Response(
                {'error': 'Product not found'},
                status=status.HTTP_404_NOT_FOUND
            )


@requires_scopes('finance:withdraw:initiate')
class WithdrawalInitiateView(APIView):
    """
    Initiate a withdrawal request.
    
    Requires finance:withdraw:initiate scope.
    """
    permission_classes = [HasTenantScopes]
    
    def post(self, request):
        """Create a withdrawal request."""
        amount = request.data.get('amount')
        
        # Create withdrawal transaction
        transaction = Transaction.objects.create(
            tenant=request.tenant,
            transaction_type='withdrawal',
            amount=amount,
            status='pending',
            initiated_by=request.user
        )
        
        return Response({
            'transaction_id': str(transaction.id),
            'status': 'pending',
            'message': 'Withdrawal request created. Awaiting approval.'
        }, status=status.HTTP_201_CREATED)


@requires_scopes('finance:withdraw:approve')
class WithdrawalApproveView(APIView):
    """
    Approve a withdrawal request.
    
    Requires finance:withdraw:approve scope.
    Four-eyes validation ensures approver != initiator.
    """
    permission_classes = [HasTenantScopes]
    
    def post(self, request, transaction_id):
        """Approve a withdrawal."""
        transaction = Transaction.objects.get(id=transaction_id)
        
        # Four-eyes validation
        if transaction.initiated_by == request.user:
            return Response({
                'error': 'Cannot approve your own withdrawal request'
            }, status=status.HTTP_409_CONFLICT)
        
        # Process withdrawal
        transaction.status = 'approved'
        transaction.approved_by = request.user
        transaction.save()
        
        return Response({
            'transaction_id': str(transaction.id),
            'status': 'approved'
        })
```

## Canonical Permission Scopes

The following scopes are available in the system:

### Catalog
- `catalog:view` - View products and services
- `catalog:edit` - Create, update, delete products and services

### Services
- `services:view` - View services
- `services:edit` - Create, update, delete services
- `availability:edit` - Manage service availability windows

### Conversations
- `conversations:view` - View customer conversations
- `handoff:perform` - Perform human handoff

### Orders & Appointments
- `orders:view` - View orders
- `orders:edit` - Create, update orders
- `appointments:view` - View appointments
- `appointments:edit` - Create, update, cancel appointments

### Analytics
- `analytics:view` - View analytics and reports

### Finance
- `finance:view` - View wallet balance and transactions
- `finance:withdraw:initiate` - Initiate withdrawal requests
- `finance:withdraw:approve` - Approve withdrawal requests (four-eyes)
- `finance:reconcile` - Perform financial reconciliation

### Integrations
- `integrations:manage` - Manage external integrations (WooCommerce, Shopify, etc.)

### Users
- `users:manage` - Invite users, assign roles, manage permissions

## Testing

When writing tests, you can mock the scopes on the request:

```python
def test_product_list_requires_catalog_view(client, tenant, user):
    """Test that listing products requires catalog:view scope."""
    request = client.get('/v1/products')
    request.tenant = tenant
    request.user = user
    request.scopes = set()  # No scopes
    
    view = ProductListView()
    permission = HasTenantScopes()
    
    # Should deny access
    assert permission.has_permission(request, view) is False
    
    # Add required scope
    request.scopes = {'catalog:view'}
    
    # Should allow access
    assert permission.has_permission(request, view) is True
```

## Best Practices

1. **Always use HasTenantScopes**: Include it in `permission_classes` for all protected endpoints
2. **Declare scopes explicitly**: Use `@requires_scopes` or `required_scopes` attribute
3. **Use method-level decorators**: When different HTTP methods need different scopes
4. **Check object ownership**: The permission class automatically verifies tenant ownership
5. **Log permission denials**: The system automatically logs all denials for debugging
6. **Test scope requirements**: Write tests to verify scope enforcement works correctly

## Troubleshooting

### Permission denied but user should have access

Check the logs for permission denial entries. They include:
- Required scopes
- User's actual scopes
- Missing scopes

### Object permission fails

Ensure the object has a `tenant` attribute that matches `request.tenant`.

### Scopes not set on request

Verify that `TenantContextMiddleware` is properly configured and runs before your view.
