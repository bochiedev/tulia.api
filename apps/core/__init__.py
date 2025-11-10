default_app_config = 'apps.core.apps.CoreConfig'

# Export RBAC permission classes and decorators for easy importing
from apps.core.permissions import HasTenantScopes, requires_scopes

__all__ = ['HasTenantScopes', 'requires_scopes']
