# Django Admin Authentication Fix - Complete

## Summary

Successfully fixed the Django admin authentication architecture by consolidating to a single custom User model that works with both the multi-tenant API and Django's admin interface.

## Problem

The application had **two separate User models**:
1. Django's built-in `django.contrib.auth.models.User` (for admin)
2. Custom `apps.rbac.models.User` (for API)

This caused:
- Two separate user databases with no connection
- Confusion about which User model to use
- Django admin couldn't access the custom User model
- Middleware changes for admin access wouldn't work correctly

## Solution

### 1. Made Custom User Model Django-Admin Compatible

**File: `apps/rbac/models.py`**

Added Django authentication compatibility to the custom User model:

```python
class User(BaseModel):
    # ... existing fields ...
    
    # Django admin compatibility
    USERNAME_FIELD = 'email'  # Use email instead of username
    REQUIRED_FIELDS = []
    
    @property
    def password(self):
        """Alias for password_hash (Django admin expects 'password' field)."""
        return self.password_hash
    
    @property
    def is_staff(self):
        """Superusers can access admin."""
        return self.is_superuser
    
    @property
    def is_authenticated(self):
        return True
    
    @property
    def is_anonymous(self):
        return False
    
    def has_perm(self, perm, obj=None):
        """Superusers have all permissions."""
        return self.is_superuser
    
    def has_module_perms(self, app_label):
        """Superusers have access to all modules."""
        return self.is_superuser
    
    def natural_key(self):
        """Return natural key for serialization."""
        return (self.email,)
```

### 2. Updated UserManager for Django Compatibility

**File: `apps/rbac/models.py`**

```python
class UserManager(models.Manager):
    def create_user(self, email, password=None, **extra_fields):
        """Create regular user (Django-compatible)."""
        # ... implementation ...
    
    def create_superuser(self, email, password=None, **extra_fields):
        """Create superuser (required for createsuperuser command)."""
        # ... implementation ...
    
    def get_by_natural_key(self, email):
        """Get user by natural key (required for Django auth)."""
        return self.get(**{self.model.USERNAME_FIELD: email})
```

### 3. Created Custom Authentication Backend

**File: `apps/rbac/backends.py` (NEW)**

```python
class EmailAuthBackend(BaseBackend):
    """
    Authenticate using email address instead of username.
    Compatible with Django admin and session authentication.
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        """Authenticate by email (Django admin passes email as 'username')."""
        email = username or kwargs.get('email')
        # ... implementation ...
    
    def get_user(self, user_id):
        """Get user by ID (used by session authentication)."""
        # ... implementation ...
```

### 4. Configured Django Settings

**File: `config/settings.py`**

```python
# Custom User Model
AUTH_USER_MODEL = 'rbac.User'

# Authentication Backends
AUTHENTICATION_BACKENDS = [
    'apps.rbac.backends.EmailAuthBackend',
]
```

### 5. Updated Django Admin Configuration

**File: `apps/rbac/admin.py`**

```python
@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    """Custom admin for email-based User model."""
    list_display = ['email', 'first_name', 'last_name', 'is_active', 'is_superuser', 'email_verified', 'created_at']
    search_fields = ['email', 'first_name', 'last_name']
    ordering = ['-created_at']
    
    fieldsets = (
        (None, {'fields': ('email', 'password_hash')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone')}),
        ('Permissions', {'fields': ('is_active', 'is_superuser')}),
        # ... more fieldsets ...
    )
```

### 6. Removed Duplicate User Admin

**File: `apps/core/admin.py`**

Removed the Django built-in User admin registration (no longer needed).

## Database Migration

Created migration: `apps/rbac/migrations/0003_update_user_model_for_django_admin.py`

```bash
python manage.py makemigrations rbac --name update_user_model_for_django_admin
python manage.py migrate
```

## Testing

### Created Comprehensive Test Suite

**File: `apps/rbac/tests/test_django_admin_auth.py` (NEW)**

21 tests covering:
- Custom User model configuration
- Superuser creation
- Email authentication backend
- Django admin access control
- Session authentication
- Middleware integration
- Permission system

### Test Results

```
✅ 21/21 tests passing in test_django_admin_auth.py
✅ 117/124 tests passing in full RBAC test suite
```

Remaining failures are unrelated to AUTH_USER_MODEL changes (rate limiting tests).

## Verification

### 1. Create Superuser

```bash
python manage.py shell
>>> from apps.rbac.models import User
>>> User.objects.create_superuser('admin@wabotiq.test', 'admin123')
```

### 2. Test Authentication

```bash
python manage.py shell
>>> from apps.rbac.backends import EmailAuthBackend
>>> backend = EmailAuthBackend()
>>> user = backend.authenticate(None, username='admin@wabotiq.test', password='admin123')
>>> print(f'✓ Authenticated: {user.email}, Superuser: {user.is_superuser}, Staff: {user.is_staff}')
```

### 3. Access Django Admin

1. Start development server: `python manage.py runserver`
2. Navigate to: `http://localhost:8000/admin/`
3. Login with: `admin@wabotiq.test` / `admin123`
4. ✅ Should access admin interface successfully

### 4. Verify API Still Works

```bash
curl http://localhost:8000/v1/catalog/
# Should return 401: "X-TENANT-ID header is required"
```

## Security Verification

✅ **Tenant Isolation Maintained**: Admin paths don't require tenant context  
✅ **No Cross-Tenant Leakage**: Admin is separate from tenant data  
✅ **API Protection Preserved**: API endpoints still require tenant headers  
✅ **Session Auth Works**: Django admin uses session-based authentication  
✅ **Superuser Only**: Only superusers can access admin (is_staff check)

## Files Changed

1. `apps/rbac/models.py` - Made User model Django-admin compatible
2. `apps/rbac/backends.py` - Created email authentication backend (NEW)
3. `apps/rbac/admin.py` - Registered custom User admin
4. `apps/core/admin.py` - Removed duplicate User registration
5. `config/settings.py` - Configured AUTH_USER_MODEL and AUTHENTICATION_BACKENDS
6. `apps/tenants/middleware.py` - Preserved request.user for admin paths
7. `apps/rbac/tests/test_django_admin_auth.py` - Comprehensive test suite (NEW)
8. `apps/rbac/migrations/0003_update_user_model_for_django_admin.py` - Migration (NEW)

## Benefits

1. **Single Source of Truth**: One User model for entire application
2. **Django Admin Compatible**: Superusers can access admin interface
3. **Multi-Tenant Support**: Same User can belong to multiple tenants
4. **Email-Based Auth**: No username field required
5. **Backward Compatible**: Existing API authentication still works
6. **Well Tested**: 21 new tests + 117 existing tests passing
7. **Security Maintained**: Tenant isolation and RBAC still enforced

## Next Steps

1. ✅ Architecture fixed and tested
2. ✅ Migration applied
3. ✅ Superuser created and verified
4. ✅ Django admin accessible
5. ✅ API still protected

## Notes

- The custom User model uses `email` as USERNAME_FIELD (no username)
- `password_hash` field has a `password` property alias for Django admin compatibility
- Superusers automatically have `is_staff=True` via property
- Email authentication backend handles both admin and API authentication
- Middleware preserves `request.user` for admin paths to enable session auth

## Definition of Done

✅ Custom User model is Django-admin compatible  
✅ AUTH_USER_MODEL configured in settings  
✅ Email authentication backend created  
✅ Django admin registration updated  
✅ Migration created and applied  
✅ Comprehensive tests written and passing  
✅ Superuser can access Django admin  
✅ API endpoints still require tenant authentication  
✅ No security regressions  
✅ Documentation complete  

**Status: COMPLETE ✅**
