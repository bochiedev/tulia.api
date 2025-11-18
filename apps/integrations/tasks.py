"""
Celery tasks for integration services.

Handles scheduled product synchronization from external sources
(WooCommerce, Shopify) with error handling and retry logic.
"""
import logging
from celery import shared_task
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=3600,  # 1 hour
    retry_jitter=True
)
def sync_woocommerce_products(self, tenant_id: str):
    """
    Celery task to sync products from WooCommerce store.
    
    Automatically retries on transient failures with exponential backoff.
    Logs all sync operations to WebhookLog for audit trail.
    
    Args:
        tenant_id: UUID of the tenant to sync products for
        
    Returns:
        dict: Sync result with counts and status
        
    Example:
        >>> from apps.integrations.tasks import sync_woocommerce_products
        >>> result = sync_woocommerce_products.delay(str(tenant.id))
        >>> print(result.get())
    """
    from apps.tenants.models import Tenant
    from apps.integrations.services import create_woo_service_for_tenant
    
    start_time = timezone.now()
    
    try:
        logger.info(
            f"Starting WooCommerce sync task",
            extra={
                'tenant_id': tenant_id,
                'task_id': self.request.id,
                'attempt': self.request.retries + 1
            }
        )
        
        # Get tenant
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            logger.error(
                f"Tenant not found for WooCommerce sync",
                extra={'tenant_id': tenant_id}
            )
            return {
                'status': 'error',
                'error': 'Tenant not found',
                'tenant_id': tenant_id
            }
        
        # Create WooCommerce service
        try:
            woo_service = create_woo_service_for_tenant(tenant)
        except ValueError as e:
            logger.error(
                f"WooCommerce credentials not configured",
                extra={
                    'tenant_id': tenant_id,
                    'error': str(e)
                }
            )
            return {
                'status': 'error',
                'error': 'WooCommerce credentials not configured',
                'tenant_id': tenant_id
            }
        
        # Sync products within transaction
        with transaction.atomic():
            result = woo_service.sync_products(tenant)
        
        # Calculate total duration
        end_time = timezone.now()
        duration_seconds = (end_time - start_time).total_seconds()
        
        logger.info(
            f"WooCommerce sync task completed",
            extra={
                'tenant_id': tenant_id,
                'task_id': self.request.id,
                'duration_seconds': duration_seconds,
                **result
            }
        )
        
        return {
            **result,
            'tenant_id': tenant_id,
            'task_id': self.request.id,
            'total_duration_seconds': duration_seconds
        }
    
    except Exception as e:
        logger.error(
            f"WooCommerce sync task failed",
            extra={
                'tenant_id': tenant_id,
                'task_id': self.request.id,
                'attempt': self.request.retries + 1,
                'error': str(e)
            },
            exc_info=True
        )
        
        # Re-raise to trigger Celery retry
        raise


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=3600,  # 1 hour
    retry_jitter=True
)
def sync_shopify_products(self, tenant_id: str):
    """
    Celery task to sync products from Shopify store.
    
    Automatically retries on transient failures with exponential backoff.
    Logs all sync operations to WebhookLog for audit trail.
    
    Args:
        tenant_id: UUID of the tenant to sync products for
        
    Returns:
        dict: Sync result with counts and status
        
    Example:
        >>> from apps.integrations.tasks import sync_shopify_products
        >>> result = sync_shopify_products.delay(str(tenant.id))
        >>> print(result.get())
    """
    from apps.tenants.models import Tenant
    from apps.integrations.services import create_shopify_service_for_tenant
    
    start_time = timezone.now()
    
    try:
        logger.info(
            f"Starting Shopify sync task",
            extra={
                'tenant_id': tenant_id,
                'task_id': self.request.id,
                'attempt': self.request.retries + 1
            }
        )
        
        # Get tenant
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            logger.error(
                f"Tenant not found for Shopify sync",
                extra={'tenant_id': tenant_id}
            )
            return {
                'status': 'error',
                'error': 'Tenant not found',
                'tenant_id': tenant_id
            }
        
        # Create Shopify service
        try:
            shopify_service = create_shopify_service_for_tenant(tenant)
        except ValueError as e:
            logger.error(
                f"Shopify credentials not configured",
                extra={
                    'tenant_id': tenant_id,
                    'error': str(e)
                }
            )
            return {
                'status': 'error',
                'error': 'Shopify credentials not configured',
                'tenant_id': tenant_id
            }
        
        # Sync products within transaction
        with transaction.atomic():
            result = shopify_service.sync_products(tenant)
        
        # Calculate total duration
        end_time = timezone.now()
        duration_seconds = (end_time - start_time).total_seconds()
        
        logger.info(
            f"Shopify sync task completed",
            extra={
                'tenant_id': tenant_id,
                'task_id': self.request.id,
                'duration_seconds': duration_seconds,
                **result
            }
        )
        
        return {
            **result,
            'tenant_id': tenant_id,
            'task_id': self.request.id,
            'total_duration_seconds': duration_seconds
        }
    
    except Exception as e:
        logger.error(
            f"Shopify sync task failed",
            extra={
                'tenant_id': tenant_id,
                'task_id': self.request.id,
                'attempt': self.request.retries + 1,
                'error': str(e)
            },
            exc_info=True
        )
        
        # Re-raise to trigger Celery retry
        raise


@shared_task
def sync_all_woocommerce_stores():
    """
    Celery task to sync products from all tenants with WooCommerce configured.
    
    Schedules individual sync tasks for each tenant.
    Useful for scheduled periodic syncs (e.g., daily at 2 AM).
    
    Returns:
        dict: Summary of scheduled sync tasks
        
    Example:
        >>> from apps.integrations.tasks import sync_all_woocommerce_stores
        >>> result = sync_all_woocommerce_stores.delay()
    """
    from apps.tenants.models import Tenant
    
    logger.info("Starting batch WooCommerce sync for all tenants")
    
    # Find all tenants with WooCommerce configured
    tenants_with_woo = Tenant.objects.filter(
        metadata__woocommerce__isnull=False,
        status='active'
    )
    
    scheduled_count = 0
    
    for tenant in tenants_with_woo:
        # Check if WooCommerce credentials are present
        woo_config = tenant.metadata.get('woocommerce', {})
        if all([
            woo_config.get('store_url'),
            woo_config.get('consumer_key'),
            woo_config.get('consumer_secret')
        ]):
            # Schedule sync task
            sync_woocommerce_products.delay(str(tenant.id))
            scheduled_count += 1
            
            logger.info(
                f"Scheduled WooCommerce sync",
                extra={
                    'tenant_id': str(tenant.id),
                    'tenant_slug': tenant.slug
                }
            )
    
    logger.info(
        f"Batch WooCommerce sync scheduled",
        extra={'scheduled_count': scheduled_count}
    )
    
    return {
        'status': 'success',
        'scheduled_count': scheduled_count
    }


@shared_task
def sync_all_shopify_stores():
    """
    Celery task to sync products from all tenants with Shopify configured.
    
    Schedules individual sync tasks for each tenant.
    Useful for scheduled periodic syncs (e.g., daily at 2 AM).
    
    Returns:
        dict: Summary of scheduled sync tasks
        
    Example:
        >>> from apps.integrations.tasks import sync_all_shopify_stores
        >>> result = sync_all_shopify_stores.delay()
    """
    from apps.tenants.models import Tenant
    
    logger.info("Starting batch Shopify sync for all tenants")
    
    # Find all tenants with Shopify configured
    tenants_with_shopify = Tenant.objects.filter(
        metadata__shopify__isnull=False,
        status='active'
    )
    
    scheduled_count = 0
    
    for tenant in tenants_with_shopify:
        # Check if Shopify credentials are present
        shopify_config = tenant.metadata.get('shopify', {})
        if all([
            shopify_config.get('shop_domain'),
            shopify_config.get('access_token')
        ]):
            # Schedule sync task
            sync_shopify_products.delay(str(tenant.id))
            scheduled_count += 1
            
            logger.info(
                f"Scheduled Shopify sync",
                extra={
                    'tenant_id': str(tenant.id),
                    'tenant_slug': tenant.slug
                }
            )
    
    logger.info(
        f"Batch Shopify sync scheduled",
        extra={'scheduled_count': scheduled_count}
    )
    
    return {
        'status': 'success',
        'scheduled_count': scheduled_count
    }
