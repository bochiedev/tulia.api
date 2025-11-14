# QuerySet Chaining Fix

## Problem
The bot was crashing with:
```
AttributeError: 'QuerySet' object has no attribute 'active'
```

When trying to chain manager methods:
```python
products = Product.objects.for_tenant(tenant).active()
```

## Root Cause
The manager methods (`for_tenant()`, `active()`, etc.) were returning filtered QuerySets, but these QuerySets didn't have the custom methods. This prevented method chaining.

**Before (Broken):**
```python
class ProductManager(models.Manager):
    def for_tenant(self, tenant):
        return self.filter(tenant=tenant)  # Returns QuerySet without custom methods
    
    def active(self):
        return self.filter(is_active=True)  # Can't be called on QuerySet
```

## Solution
Implemented custom QuerySet classes with chainable methods following Django best practices:

**After (Fixed):**
```python
class ProductQuerySet(models.QuerySet):
    """Custom QuerySet with chainable methods."""
    
    def for_tenant(self, tenant):
        return self.filter(tenant=tenant)  # Returns ProductQuerySet
    
    def active(self):
        return self.filter(is_active=True)  # Returns ProductQuerySet


class ProductManager(models.Manager):
    def get_queryset(self):
        return ProductQuerySet(self.model, using=self._db)
    
    def for_tenant(self, tenant):
        return self.get_queryset().for_tenant(tenant)
    
    def active(self):
        return self.get_queryset().active()
```

Now all these work:
```python
# Chain in any order
Product.objects.for_tenant(tenant).active()
Product.objects.active().for_tenant(tenant)
Product.objects.for_tenant(tenant).active().filter(price__lt=100)
```

## Files Fixed
1. `apps/catalog/models.py` - Added `ProductQuerySet` and `ProductVariantQuerySet`
2. `apps/services/models.py` - Added `ServiceQuerySet`

## Tests Added
Created comprehensive test suite in `apps/catalog/tests/test_product_models.py`:
- ✅ `test_for_tenant_active_chaining` - The critical test that was failing
- ✅ `test_active_for_tenant_chaining` - Reverse order chaining
- ✅ `test_for_tenant_in_stock_chaining` - Variant chaining
- ✅ All manager methods work correctly

## Why Tests Didn't Catch This
**The problem:** There were NO tests for the Product model manager methods!

The existing tests only covered:
- RBAC permissions on catalog endpoints
- Tenant isolation
- API views

But NOT the underlying model manager methods that the bot handlers use.

## Prevention
1. **Always test manager methods** - Especially custom QuerySet methods
2. **Test method chaining** - If you expect `Model.objects.method1().method2()` to work, test it!
3. **Integration tests** - Test the full flow from API → handler → model
4. **Run tests before deploying** - The bot would have caught this immediately

## Testing
Run the new tests:
```bash
python -m pytest apps/catalog/tests/test_product_models.py -v
```

All tests pass, including the critical chaining test.

## Related Issues
This same pattern was applied to:
- `Product` and `ProductVariant` in catalog app
- `Service` in services app

Any other models with custom manager methods should follow this pattern.

## Django Best Practice
This is the recommended Django pattern for custom QuerySet methods:
https://docs.djangoproject.com/en/4.2/topics/db/managers/#creating-a-manager-with-queryset-methods

Always use custom QuerySet classes when you want chainable methods!
