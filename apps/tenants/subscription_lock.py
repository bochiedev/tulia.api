"""
Subscription status locking for critical operations.

Provides utilities to lock tenant records during critical operations
to prevent race conditions where subscription status changes mid-operation.
"""
from django.db import transaction
from typing import Callable, Any
from .models import Tenant


def with_subscription_lock(func: Callable) -> Callable:
    """
    Decorator to lock tenant and re-check subscription status for critical operations.
    
    Use this decorator on views that perform critical operations like:
    - Processing payments
    - Initiating withdrawals
    - Creating orders
    - Booking appointments
    
    The decorator:
    1. Locks the tenant record with select_for_update()
    2. Re-checks subscription status within the transaction
    3. Returns 403 if subscription became inactive
    4. Executes the view function if subscription is active
    
    Example:
        @with_subscription_lock
        def process_payment(request):
            # Tenant is locked and subscription verified
            ...
    """
    def wrapper(request, *args, **kwargs):
        # Get tenant from request (set by TenantContextMiddleware)
        tenant = getattr(request, 'tenant', None)
        
        if not tenant:
            from django.http import JsonResponse
            return JsonResponse({
                'error': 'Tenant context required',
                'code': 'TENANT_REQUIRED'
            }, status=400)
        
        # Lock tenant and re-check subscription status
        with transaction.atomic():
            # Lock the tenant record for this transaction
            locked_tenant = Tenant.objects.select_for_update().get(id=tenant.id)
            
            # Re-check subscription status with locked record
            if not locked_tenant.is_active():
                from django.http import JsonResponse
                return JsonResponse({
                    'error': 'Subscription inactive',
                    'code': 'SUBSCRIPTION_INACTIVE',
                    'details': {
                        'subscription_status': locked_tenant.status,
                        'trial_end_date': (
                            locked_tenant.trial_end_date.isoformat()
                            if locked_tenant.trial_end_date
                            else None
                        )
                    }
                }, status=403)
            
            # Update request.tenant with locked instance
            request.tenant = locked_tenant
            
            # Execute the view function
            return func(request, *args, **kwargs)
    
    return wrapper


def check_subscription_with_lock(tenant_id: str) -> tuple[Tenant, bool]:
    """
    Lock tenant and check subscription status.
    
    Use this in service functions that need to verify subscription
    status before performing critical operations.
    
    Args:
        tenant_id: Tenant UUID
        
    Returns:
        Tuple of (locked_tenant, is_active)
        
    Example:
        with transaction.atomic():
            tenant, is_active = check_subscription_with_lock(tenant_id)
            if not is_active:
                raise ValueError("Subscription inactive")
            # Perform critical operation
            ...
    """
    locked_tenant = Tenant.objects.select_for_update().get(id=tenant_id)
    is_active = locked_tenant.is_active()
    return locked_tenant, is_active


def execute_with_subscription_check(
    tenant_id: str,
    operation: Callable[[Tenant], Any]
) -> Any:
    """
    Execute operation with subscription lock and check.
    
    Wraps the operation in a transaction with tenant lock and
    subscription verification.
    
    Args:
        tenant_id: Tenant UUID
        operation: Function that takes locked tenant and returns result
        
    Returns:
        Result of operation
        
    Raises:
        ValueError: If subscription is inactive
        
    Example:
        def process_withdrawal(tenant):
            # Process withdrawal with locked tenant
            ...
            return withdrawal
        
        withdrawal = execute_with_subscription_check(
            tenant_id,
            process_withdrawal
        )
    """
    with transaction.atomic():
        tenant, is_active = check_subscription_with_lock(tenant_id)
        
        if not is_active:
            raise ValueError(
                f"Subscription inactive: {tenant.status}. "
                f"Cannot perform operation."
            )
        
        return operation(tenant)
