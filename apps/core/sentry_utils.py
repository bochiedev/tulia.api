"""
Sentry utilities for adding context and breadcrumbs.
"""
import sentry_sdk
from django.conf import settings


def set_tenant_context(tenant):
    """
    Set tenant context in Sentry for error tracking.
    
    Args:
        tenant: Tenant model instance
    """
    if not settings.SENTRY_DSN:
        return
    
    sentry_sdk.set_context("tenant", {
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "status": tenant.status,
        "subscription_tier": tenant.subscription_tier.name if tenant.subscription_tier else None,
    })
    
    # Also set as tag for easier filtering
    sentry_sdk.set_tag("tenant_id", str(tenant.id))
    sentry_sdk.set_tag("tenant_slug", tenant.slug)


def set_customer_context(customer):
    """
    Set customer context in Sentry for error tracking.
    Note: We don't include PII like phone numbers.
    
    Args:
        customer: Customer model instance
    """
    if not settings.SENTRY_DSN:
        return
    
    sentry_sdk.set_context("customer", {
        "id": str(customer.id),
        "tenant_id": str(customer.tenant_id),
        "has_name": bool(customer.name),
        "timezone": customer.timezone,
        "tags": customer.tags,
    })
    
    sentry_sdk.set_tag("customer_id", str(customer.id))


def set_user_context(user, tenant_user=None):
    """
    Set user context in Sentry for error tracking.
    
    Args:
        user: User model instance
        tenant_user: Optional TenantUser instance for additional context
    """
    if not settings.SENTRY_DSN:
        return
    
    user_data = {
        "id": str(user.id),
        "email": user.email,
        "is_active": user.is_active,
    }
    
    if tenant_user:
        user_data["tenant_id"] = str(tenant_user.tenant_id)
        user_data["roles"] = [role.name for role in tenant_user.roles.all()]
        user_data["invite_status"] = tenant_user.invite_status
    
    sentry_sdk.set_user(user_data)


def add_breadcrumb(category, message, level="info", data=None):
    """
    Add a breadcrumb to Sentry for debugging.
    
    Args:
        category: Category of the breadcrumb (e.g., "webhook", "intent", "payment")
        message: Human-readable message
        level: Severity level (debug, info, warning, error)
        data: Optional dictionary of additional data
    """
    if not settings.SENTRY_DSN:
        return
    
    sentry_sdk.add_breadcrumb(
        category=category,
        message=message,
        level=level,
        data=data or {}
    )


def capture_exception(exception, **kwargs):
    """
    Capture an exception in Sentry with optional context.
    
    Args:
        exception: The exception to capture
        **kwargs: Additional context to attach
    """
    if not settings.SENTRY_DSN:
        return
    
    with sentry_sdk.push_scope() as scope:
        for key, value in kwargs.items():
            scope.set_context(key, value)
        sentry_sdk.capture_exception(exception)


def capture_message(message, level="info", **kwargs):
    """
    Capture a message in Sentry with optional context.
    
    Args:
        message: The message to capture
        level: Severity level (debug, info, warning, error, fatal)
        **kwargs: Additional context to attach
    """
    if not settings.SENTRY_DSN:
        return
    
    with sentry_sdk.push_scope() as scope:
        for key, value in kwargs.items():
            scope.set_context(key, value)
        sentry_sdk.capture_message(message, level=level)


def start_transaction(name, op):
    """
    Start a Sentry transaction for performance monitoring.
    
    Args:
        name: Transaction name (e.g., "webhook.twilio.process")
        op: Operation type (e.g., "webhook", "task", "http.server")
    
    Returns:
        Transaction object or None if Sentry is not configured
    """
    if not settings.SENTRY_DSN:
        return None
    
    return sentry_sdk.start_transaction(name=name, op=op)


def start_span(transaction, op, description):
    """
    Start a span within a transaction for detailed performance tracking.
    
    Args:
        transaction: Parent transaction
        op: Operation type (e.g., "db.query", "http.client", "ai.inference")
        description: Human-readable description
    
    Returns:
        Span object or None if transaction is None
    """
    if not transaction:
        return None
    
    return transaction.start_child(op=op, description=description)
