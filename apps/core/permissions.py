"""
DRF permission classes and decorators for RBAC scope enforcement.

This module provides:
- HasTenantScopes: DRF permission class that enforces scope requirements
- @requires_scopes: Decorator to declare required scopes on views
"""
import logging
from functools import wraps
from rest_framework.permissions import BasePermission

logger = logging.getLogger(__name__)


class HasTenantScopes(BasePermission):
    """
    DRF permission class that enforces scope requirements on API endpoints.
    
    This permission class:
    1. Checks if view has required_scopes attribute
    2. Verifies all required scopes are present in request.scopes
    3. Returns 403 if any required scope is missing
    4. Implements has_object_permission to verify object belongs to request.tenant
    5. Logs permission denials with missing scopes for debugging
    
    Usage in views:
        class MyView(APIView):
            permission_classes = [HasTenantScopes]
            required_scopes = ['catalog:view', 'catalog:edit']
            
            def get(self, request):
                # Will only execute if user has both scopes
                pass
    
    Or use with decorator:
        @requires_scopes('catalog:view', 'catalog:edit')
        class MyView(APIView):
            def get(self, request):
                pass
    """
    
    def has_permission(self, request, view):
        """
        Check if request has all required scopes for the view.
        
        Args:
            request: DRF request object with scopes attribute
            view: DRF view instance with optional required_scopes attribute
            
        Returns:
            bool: True if all required scopes are present, False otherwise
        """
        # Get required scopes from view
        required_scopes = getattr(view, 'required_scopes', None)
        
        # If no scopes required, allow access
        if not required_scopes:
            return True
        
        # Ensure required_scopes is a set or list
        if isinstance(required_scopes, str):
            required_scopes = {required_scopes}
        elif isinstance(required_scopes, (list, tuple)):
            required_scopes = set(required_scopes)
        
        # Get user's scopes from request (set by TenantContextMiddleware)
        user_scopes = getattr(request, 'scopes', set())
        
        # Check if all required scopes are present
        missing_scopes = required_scopes - user_scopes
        
        if missing_scopes:
            # Log permission denial for debugging
            user_email = getattr(request.user, 'email', 'anonymous') if hasattr(request, 'user') else 'anonymous'
            tenant_slug = getattr(request.tenant, 'slug', 'unknown') if hasattr(request, 'tenant') else 'unknown'
            
            logger.warning(
                f"Permission denied: User {user_email} @ {tenant_slug} missing scopes: {missing_scopes}",
                extra={
                    'user_email': user_email,
                    'tenant_slug': tenant_slug,
                    'required_scopes': list(required_scopes),
                    'user_scopes': list(user_scopes),
                    'missing_scopes': list(missing_scopes),
                    'view': view.__class__.__name__,
                    'method': request.method,
                    'path': request.path,
                    'request_id': getattr(request, 'request_id', None),
                }
            )
            
            return False
        
        # All required scopes present
        logger.debug(
            f"Permission granted: User has all required scopes {required_scopes}",
            extra={
                'required_scopes': list(required_scopes),
                'user_scopes': list(user_scopes),
                'view': view.__class__.__name__,
            }
        )
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """
        Verify that the object belongs to the request's tenant.
        
        This method is called after has_permission() passes and provides
        object-level permission checking to ensure tenant isolation.
        
        Args:
            request: DRF request object with tenant attribute
            view: DRF view instance
            obj: The object being accessed
            
        Returns:
            bool: True if object belongs to request.tenant, False otherwise
        """
        # Get tenant from request (set by TenantContextMiddleware)
        request_tenant = getattr(request, 'tenant', None)
        
        if not request_tenant:
            logger.warning(
                "Object permission check failed: No tenant in request",
                extra={
                    'view': view.__class__.__name__,
                    'object_type': obj.__class__.__name__,
                    'object_id': getattr(obj, 'id', None),
                }
            )
            return False
        
        # Check if object has tenant attribute
        if not hasattr(obj, 'tenant'):
            # If object doesn't have tenant attribute, we can't verify ownership
            # Log warning but allow access (scope check already passed)
            logger.debug(
                f"Object {obj.__class__.__name__} has no tenant attribute, skipping tenant check",
                extra={
                    'object_type': obj.__class__.__name__,
                    'object_id': getattr(obj, 'id', None),
                }
            )
            return True
        
        # Verify object belongs to request tenant
        object_tenant = obj.tenant
        
        # Handle both direct tenant objects and tenant IDs
        if hasattr(object_tenant, 'id'):
            object_tenant_id = object_tenant.id
        else:
            object_tenant_id = object_tenant
        
        if hasattr(request_tenant, 'id'):
            request_tenant_id = request_tenant.id
        else:
            request_tenant_id = request_tenant
        
        if object_tenant_id != request_tenant_id:
            # Object belongs to different tenant - deny access
            user_email = getattr(request.user, 'email', 'anonymous') if hasattr(request, 'user') else 'anonymous'
            
            logger.warning(
                f"Object permission denied: Object belongs to different tenant",
                extra={
                    'user_email': user_email,
                    'request_tenant_id': str(request_tenant_id),
                    'object_tenant_id': str(object_tenant_id),
                    'object_type': obj.__class__.__name__,
                    'object_id': getattr(obj, 'id', None),
                    'view': view.__class__.__name__,
                    'request_id': getattr(request, 'request_id', None),
                }
            )
            
            return False
        
        # Object belongs to request tenant
        logger.debug(
            f"Object permission granted: Object belongs to request tenant",
            extra={
                'tenant_id': str(request_tenant_id),
                'object_type': obj.__class__.__name__,
                'object_id': getattr(obj, 'id', None),
            }
        )
        
        return True


def requires_scopes(*scopes):
    """
    Decorator to declare required scopes on view classes or methods.
    
    This decorator sets the required_scopes attribute on the view,
    which is then checked by the HasTenantScopes permission class.
    
    Usage:
        @requires_scopes('catalog:view', 'catalog:edit')
        class ProductListView(APIView):
            permission_classes = [HasTenantScopes]
            
            def get(self, request):
                pass
    
    Or on individual methods:
        class ProductListView(APIView):
            permission_classes = [HasTenantScopes]
            
            @requires_scopes('catalog:view')
            def get(self, request):
                pass
            
            @requires_scopes('catalog:edit')
            def post(self, request):
                pass
    
    Args:
        *scopes: Variable number of scope strings required for access
        
    Returns:
        Decorator function that sets required_scopes attribute
    """
    def decorator(view_or_method):
        # Check if decorating a class or method
        if isinstance(view_or_method, type):
            # Decorating a class
            view_or_method.required_scopes = set(scopes)
            return view_or_method
        else:
            # Decorating a method
            @wraps(view_or_method)
            def wrapped(self, request, *args, **kwargs):
                # Set required_scopes on the view instance
                self.required_scopes = set(scopes)
                return view_or_method(self, request, *args, **kwargs)
            
            # Also set on the function itself for introspection
            wrapped.required_scopes = set(scopes)
            return wrapped
    
    return decorator
