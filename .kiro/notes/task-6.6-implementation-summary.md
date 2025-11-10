# Task 6.6 Implementation Summary: Wire RBAC Signals for Automatic Role Seeding

## Overview
Implemented Django signals to automatically seed default RBAC roles when a new tenant is created, and optionally assign the Owner role to the creating user.

## Requirements Addressed
- **Requirement 58.1**: Automatically seed default Role records when a new Tenant is created
- **Requirement 59.4**: Automatically assign Owner role to creating user if specified

## Implementation Details

### 1. Signal Handler (`apps/rbac/signals.py`)

Created `seed_roles_on_tenant_creation` signal that:
- Listens to `post_save` signal on the `Tenant` model
- Only runs for newly created tenants (not updates)
- Seeds all 6 default roles: Owner, Admin, Finance Admin, Catalog Manager, Support Lead, Analyst
- Assigns permissions to each role based on the canonical definitions
- Logs the seeding completion to the audit log
- Optionally assigns Owner role to creating user if `_created_by_user` attribute is set

### 2. Helper Functions

**`_sync_role_permissions(role, permissions)`**
- Ensures a role has exactly the specified permissions
- Adds missing permissions and removes extra ones
- Idempotent operation

**`_assign_owner_role(tenant, user)`**
- Creates or retrieves TenantUser membership
- Assigns the Owner role to the user
- Logs the assignment to the audit log
- Handles edge cases gracefully

### 3. Usage Pattern

To create a tenant with an owner:

```python
# Create tenant with owner assignment
tenant = Tenant(
    name='My Business',
    slug='my-business',
    whatsapp_number='+1234567890',
    twilio_sid='...',
    twilio_token='...',
    webhook_secret='...',
    subscription_tier=tier
)
tenant._created_by_user = user  # Set before save
tenant.save()  # Signal runs and assigns Owner role
```

### 4. Audit Trail

The signal creates two types of audit log entries:

1. **tenant_roles_seeded**: Logs when roles are seeded for a tenant
   - Includes list of roles created
   - Total number of roles
   - Trigger source (post_save_signal)

2. **owner_role_assigned**: Logs when Owner role is assigned to a user
   - User email
   - Role name
   - Trigger source (tenant_creation)

## Testing

Created comprehensive test suite in `apps/rbac/tests/test_signals.py`:

1. **test_roles_seeded_on_tenant_creation**: Verifies all 6 default roles are created
2. **test_owner_role_has_all_permissions**: Verifies Owner role has all canonical permissions
3. **test_audit_log_created_on_seeding**: Verifies audit log entry is created
4. **test_owner_role_assigned_to_creating_user**: Verifies Owner role assignment works
5. **test_signal_idempotent_on_update**: Verifies signal doesn't run on tenant updates

All tests pass successfully.

## Key Design Decisions

1. **Atomic Operations**: Used `transaction.atomic()` to ensure all role seeding happens atomically
2. **Idempotent**: Signal is safe to run multiple times (though it only runs on creation)
3. **Graceful Degradation**: If permissions don't exist, roles are still created (just without permissions)
4. **Optional Owner Assignment**: Owner assignment only happens if `_created_by_user` is explicitly set
5. **System Actions**: Audit logs mark these as system actions (user=None) since they're automatic

## Integration

The signal is automatically registered via `apps/rbac/apps.py`:

```python
def ready(self):
    """Import signals when app is ready."""
    import apps.rbac.signals  # noqa
```

## Benefits

1. **Automatic Setup**: New tenants get roles automatically without manual intervention
2. **Consistency**: All tenants have the same default role structure
3. **Audit Trail**: Complete audit trail of role seeding and Owner assignments
4. **Developer Experience**: Simple pattern for creating tenants with owners
5. **Testability**: Comprehensive test coverage ensures reliability

## Future Enhancements

Potential improvements for future iterations:
- Support for custom role templates per tenant type
- Configurable default roles via settings
- Webhook notifications when roles are seeded
- Bulk tenant creation with role seeding optimization
