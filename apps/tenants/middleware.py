"""
Tenant context middleware for multi-tenant isolation.

Extracts and validates tenant context from request headers,
ensuring all requests are properly scoped to a tenant.
"""
import hashlib
import logging
import uuid
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from .models import Tenant

logger = logging.getLogger(__name__)


class TenantContextMiddleware(MiddlewareMixin):
    """
    Extract and validate tenant context from request headers.
    
    This middleware:
    1. Extracts X-TENANT-ID and X-TENANT-API-KEY headers
    2. Validates the API key against the tenant's stored keys
    3. Injects tenant object into request for use in views
    4. Handles authentication errors with proper responses
    
    Public endpoints (webhooks, health checks) bypass authentication.
    """
    
    # Paths that don't require tenant authentication
    PUBLIC_PATHS = [
        '/v1/webhooks/',
        '/v1/health',
        '/schema',
        '/admin/',
    ]
    
    def process_request(self, request):
        """
        Extract and validate tenant context from headers.
        
        For RBAC-enabled endpoints, this middleware also:
        - Validates TenantUser membership exists
        - Resolves user scopes via RBACService
        - Attaches request.tenant, request.membership, request.scopes
        - Updates last_seen_at timestamp on TenantUser
        - Adds request_id to all audit logs
        """
        # Generate or extract request ID for tracing
        request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
        request.request_id = request_id
        
        # Skip authentication for public paths
        if self._is_public_path(request.path):
            request.tenant = None
            request.membership = None
            request.scopes = set()
            return None
        
        # Extract headers
        tenant_id = request.headers.get('X-TENANT-ID')
        api_key = request.headers.get('X-TENANT-API-KEY')
        
        # Check if headers are present
        if not tenant_id or not api_key:
            return self._error_response(
                'MISSING_CREDENTIALS',
                'X-TENANT-ID and X-TENANT-API-KEY headers are required',
                status=401
            )
        
        # Validate tenant exists
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            logger.warning(
                f"Invalid tenant ID: {tenant_id}",
                extra={'request_id': request_id}
            )
            return self._error_response(
                'INVALID_TENANT',
                'Invalid tenant ID',
                status=401
            )
        
        # Validate API key
        if not self._validate_api_key(tenant, api_key):
            logger.warning(
                f"Invalid API key for tenant: {tenant_id}",
                extra={'request_id': request_id}
            )
            return self._error_response(
                'INVALID_API_KEY',
                'Invalid API key',
                status=401
            )
        
        # Check if tenant is active
        if not tenant.is_active():
            logger.info(
                f"Inactive tenant attempted access: {tenant_id}",
                extra={'request_id': request_id}
            )
            return self._error_response(
                'SUBSCRIPTION_INACTIVE',
                'Your subscription is inactive. Please update your payment method.',
                status=403,
                details={
                    'subscription_status': tenant.status,
                    'trial_end_date': tenant.trial_end_date.isoformat() if tenant.trial_end_date else None,
                }
            )
        
        # Inject tenant into request
        request.tenant = tenant
        
        # Add tenant_id to thread-local storage for logging
        import threading
        threading.current_thread().tenant_id = str(tenant.id)
        
        # RBAC: Validate TenantUser membership and resolve scopes
        # Check if request has authenticated user (from Django auth or JWT)
        if hasattr(request, 'user') and request.user and request.user.is_authenticated:
            # Import here to avoid circular dependency
            from apps.rbac.models import TenantUser
            from apps.rbac.services import RBACService
            
            # Get TenantUser membership
            try:
                membership = TenantUser.objects.get_membership(tenant, request.user)
                
                if not membership:
                    logger.warning(
                        f"User {request.user.email} attempted access to tenant {tenant.slug} without membership",
                        extra={'request_id': request_id, 'tenant_id': str(tenant.id)}
                    )
                    return self._error_response(
                        'FORBIDDEN',
                        'You do not have access to this tenant',
                        status=403
                    )
                
                # Check if membership is accepted
                if membership.invite_status != 'accepted':
                    logger.warning(
                        f"User {request.user.email} attempted access with non-accepted membership: {membership.invite_status}",
                        extra={'request_id': request_id, 'tenant_id': str(tenant.id)}
                    )
                    return self._error_response(
                        'FORBIDDEN',
                        f'Your invitation status is {membership.invite_status}. Please accept your invitation first.',
                        status=403
                    )
                
                # Resolve user scopes
                scopes = RBACService.resolve_scopes(membership)
                
                # Attach to request
                request.membership = membership
                request.scopes = scopes
                
                # Update last_seen_at timestamp (async to avoid blocking)
                try:
                    membership.last_seen_at = timezone.now()
                    membership.save(update_fields=['last_seen_at'])
                except Exception as e:
                    # Log but don't fail request if timestamp update fails
                    logger.warning(
                        f"Failed to update last_seen_at for membership {membership.id}: {e}",
                        extra={'request_id': request_id}
                    )
                
                logger.debug(
                    f"RBAC context set: {request.user.email} @ {tenant.slug} with {len(scopes)} scopes",
                    extra={'request_id': request_id, 'tenant_id': str(tenant.id)}
                )
                
            except Exception as e:
                logger.error(
                    f"Error resolving RBAC context: {e}",
                    extra={'request_id': request_id, 'tenant_id': str(tenant.id)},
                    exc_info=True
                )
                # Set empty membership and scopes on error
                request.membership = None
                request.scopes = set()
        else:
            # No authenticated user - set empty membership and scopes
            request.membership = None
            request.scopes = set()
        
        logger.debug(
            f"Tenant context set: {tenant.slug} ({tenant.id})",
            extra={'request_id': request_id}
        )
        return None
    
    def _is_public_path(self, path):
        """Check if path is public and doesn't require authentication."""
        return any(path.startswith(public_path) for public_path in self.PUBLIC_PATHS)
    
    def _validate_api_key(self, tenant, api_key):
        """
        Validate API key against tenant's stored keys.
        
        API keys are stored as hashed values in tenant.api_keys list.
        Each entry is a dict with: {key_hash, name, created_at}
        """
        if not tenant.api_keys:
            return False
        
        # Hash the provided API key
        api_key_hash = self._hash_api_key(api_key)
        
        # Check if hash matches any stored key
        for key_entry in tenant.api_keys:
            if key_entry.get('key_hash') == api_key_hash:
                return True
        
        return False
    
    def _hash_api_key(self, api_key):
        """Hash API key using SHA-256."""
        return hashlib.sha256(api_key.encode('utf-8')).hexdigest()
    
    def _error_response(self, code, message, status=400, details=None):
        """Generate standardized error response."""
        error_data = {
            'error': {
                'code': code,
                'message': message,
            }
        }
        
        if details:
            error_data['error']['details'] = details
        
        return JsonResponse(error_data, status=status)


class WebhookSubscriptionMiddleware(MiddlewareMixin):
    """
    Check subscription status for webhook requests.
    
    For webhook endpoints, this middleware:
    1. Checks if tenant subscription is active
    2. Blocks bot processing if subscription is inactive
    3. Sends "business temporarily unavailable" message to customer
    4. Logs blocked attempts with subscription_inactive status
    """
    
    WEBHOOK_PATHS = [
        '/v1/webhooks/twilio',
    ]
    
    def process_request(self, request):
        """Check subscription status for webhook requests."""
        # Only apply to webhook paths
        if not self._is_webhook_path(request.path):
            return None
        
        # Skip if tenant not resolved yet (will be handled by webhook handler)
        if not hasattr(request, 'tenant') or request.tenant is None:
            return None
        
        tenant = request.tenant
        
        # Check subscription status
        from apps.tenants.services import SubscriptionService
        status = SubscriptionService.check_subscription_status(tenant)
        
        if status not in ['active', 'trial']:
            # Subscription is inactive - block bot processing
            logger.warning(
                f"Webhook blocked for inactive subscription: {tenant.slug} "
                f"(status: {status})"
            )
            
            # Mark request as subscription_inactive for webhook handler
            request.subscription_inactive = True
            request.subscription_status = status
            
            # The webhook handler should:
            # 1. Log the webhook with status "subscription_inactive"
            # 2. Send "business temporarily unavailable" message to customer
            # 3. NOT invoke IntentService or bot processing
            
            # We don't return an error response here because we want to:
            # - Accept the webhook (return 200 to Twilio)
            # - Send a message to the customer
            # - Log the attempt
            return None
        
        # Subscription is active - allow normal processing
        request.subscription_inactive = False
        return None
    
    def _is_webhook_path(self, path):
        """Check if path is a webhook endpoint."""
        return any(path.startswith(webhook_path) for webhook_path in self.WEBHOOK_PATHS)


class RequestIDMiddleware(MiddlewareMixin):
    """
    Inject unique request ID for tracing.
    
    Generates a unique ID for each request to enable request tracing
    across logs, error tracking, and distributed systems.
    
    Note: Request ID is now also generated in TenantContextMiddleware,
    but this middleware ensures it's available for all requests including
    public paths that bypass tenant authentication.
    """
    
    def process_request(self, request):
        """Generate and inject request ID if not already set."""
        if not hasattr(request, 'request_id'):
            request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
            request.request_id = request_id
        
        return None
    
    def process_response(self, request, response):
        """Add request ID to response headers."""
        if hasattr(request, 'request_id'):
            response['X-Request-ID'] = request.request_id
        return response
