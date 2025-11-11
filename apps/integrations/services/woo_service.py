"""
WooCommerce integration service for product synchronization.

Handles syncing products from WooCommerce stores to Tulia catalog,
including product variants, pricing, and stock information.
"""
import logging
import requests
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
from requests.auth import HTTPBasicAuth
from django.db import transaction

from apps.catalog.models import Product, ProductVariant
from apps.integrations.models import WebhookLog

logger = logging.getLogger(__name__)


class WooServiceError(Exception):
    """Base exception for WooCommerce service errors."""
    pass


class WooService:
    """
    Service for synchronizing products from WooCommerce stores.
    
    Provides methods for:
    - Authenticating with WooCommerce REST API
    - Fetching products in batches with pagination
    - Transforming WooCommerce product format to Tulia Product
    - Syncing product variants
    - Marking inactive products
    """
    
    def __init__(self, store_url: str, consumer_key: str, consumer_secret: str):
        """
        Initialize WooCommerce service with store credentials.
        
        Args:
            store_url: WooCommerce store URL (e.g., https://example.com)
            consumer_key: WooCommerce REST API consumer key
            consumer_secret: WooCommerce REST API consumer secret
        """
        self.store_url = store_url.rstrip('/')
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.api_base = f"{self.store_url}/wp-json/wc/v3"
        self.auth = HTTPBasicAuth(consumer_key, consumer_secret)
        self.session = requests.Session()
        self.session.auth = self.auth
    
    def sync_products(self, tenant) -> Dict[str, Any]:
        """
        Sync all products from WooCommerce store to Tulia catalog.
        
        Fetches products in batches, transforms them to Tulia format,
        and marks products not in sync as inactive.
        
        Args:
            tenant: Tenant model instance
            
        Returns:
            dict: Sync status with counts
            
        Example:
            >>> service = WooService(url, key, secret)
            >>> result = service.sync_products(tenant)
            >>> print(f"Synced {result['synced_count']} products")
        """
        start_time = None
        synced_ids = set()
        synced_count = 0
        error_count = 0
        page = 1
        per_page = 100
        
        try:
            from django.utils import timezone
            start_time = timezone.now()
            
            logger.info(
                f"Starting WooCommerce product sync",
                extra={
                    'tenant_id': str(tenant.id),
                    'tenant_slug': tenant.slug,
                    'store_url': self.store_url
                }
            )
            
            # Fetch products in batches
            while True:
                try:
                    products_batch = self.fetch_products_batch(page, per_page)
                    
                    if not products_batch:
                        break
                    
                    # Process each product
                    for woo_product in products_batch:
                        try:
                            with transaction.atomic():
                                product = self.transform_product(tenant, woo_product)
                                synced_ids.add(product.id)
                                synced_count += 1
                                
                                logger.debug(
                                    f"Synced product: {product.title}",
                                    extra={
                                        'product_id': str(product.id),
                                        'external_id': product.external_id
                                    }
                                )
                        
                        except Exception as e:
                            error_count += 1
                            logger.error(
                                f"Error syncing product",
                                extra={
                                    'woo_product_id': woo_product.get('id'),
                                    'error': str(e)
                                },
                                exc_info=True
                            )
                    
                    # Check if there are more pages
                    if len(products_batch) < per_page:
                        break
                    
                    page += 1
                
                except WooServiceError as e:
                    logger.error(
                        f"Error fetching products batch",
                        extra={'page': page, 'error': str(e)},
                        exc_info=True
                    )
                    break
            
            # Mark products not in sync as inactive
            inactive_count = self._mark_inactive_products(tenant, synced_ids)
            
            # Calculate sync duration
            end_time = timezone.now()
            duration_seconds = (end_time - start_time).total_seconds()
            
            result = {
                'status': 'success' if error_count == 0 else 'partial',
                'synced_count': synced_count,
                'error_count': error_count,
                'inactive_count': inactive_count,
                'duration_seconds': duration_seconds,
                'store_url': self.store_url
            }
            
            logger.info(
                f"WooCommerce product sync completed",
                extra={
                    'tenant_id': str(tenant.id),
                    **result
                }
            )
            
            # Log sync operation
            self._log_sync_operation(tenant, result)
            
            return result
        
        except Exception as e:
            logger.error(
                f"Fatal error during WooCommerce sync",
                extra={
                    'tenant_id': str(tenant.id),
                    'error': str(e)
                },
                exc_info=True
            )
            
            # Log failed sync
            if start_time:
                from django.utils import timezone
                duration_seconds = (timezone.now() - start_time).total_seconds()
            else:
                duration_seconds = 0
            
            result = {
                'status': 'error',
                'synced_count': synced_count,
                'error_count': error_count + 1,
                'inactive_count': 0,
                'duration_seconds': duration_seconds,
                'error_message': str(e)
            }
            
            self._log_sync_operation(tenant, result, error=str(e))
            
            raise WooServiceError(f"Product sync failed: {str(e)}") from e
    
    def fetch_products_batch(self, page: int = 1, per_page: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch a batch of products from WooCommerce API.
        
        Args:
            page: Page number (1-indexed)
            per_page: Number of products per page (max 100)
            
        Returns:
            list: List of WooCommerce product dictionaries
            
        Raises:
            WooServiceError: If API request fails
        """
        try:
            url = f"{self.api_base}/products"
            params = {
                'page': page,
                'per_page': min(per_page, 100),  # WooCommerce max is 100
                'status': 'publish'  # Only fetch published products
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            products = response.json()
            
            logger.debug(
                f"Fetched WooCommerce products batch",
                extra={
                    'page': page,
                    'count': len(products),
                    'per_page': per_page
                }
            )
            
            return products
        
        except requests.exceptions.HTTPError as e:
            logger.error(
                f"WooCommerce API HTTP error",
                extra={
                    'status_code': e.response.status_code,
                    'response': e.response.text,
                    'page': page
                },
                exc_info=True
            )
            raise WooServiceError(f"HTTP error fetching products: {e.response.status_code}") from e
        
        except requests.exceptions.Timeout as e:
            logger.error(
                f"WooCommerce API timeout",
                extra={'page': page},
                exc_info=True
            )
            raise WooServiceError("Request timeout") from e
        
        except requests.exceptions.RequestException as e:
            logger.error(
                f"WooCommerce API request error",
                extra={'page': page},
                exc_info=True
            )
            raise WooServiceError(f"Request error: {str(e)}") from e
        
        except Exception as e:
            logger.error(
                f"Unexpected error fetching products",
                extra={'page': page},
                exc_info=True
            )
            raise WooServiceError(f"Unexpected error: {str(e)}") from e
    
    def transform_product(self, tenant, woo_product: Dict[str, Any]) -> Product:
        """
        Transform WooCommerce product to Tulia Product model.
        
        Creates or updates Product and ProductVariant records.
        
        Args:
            tenant: Tenant model instance
            woo_product: WooCommerce product dictionary
            
        Returns:
            Product: Created or updated Product instance
        """
        external_id = str(woo_product['id'])
        
        # Extract product data
        product_data = {
            'tenant': tenant,
            'external_source': 'woocommerce',
            'external_id': external_id,
            'title': woo_product.get('name', ''),
            'description': woo_product.get('description', ''),
            'price': Decimal(woo_product.get('price', '0') or '0'),
            'currency': 'USD',  # WooCommerce doesn't include currency in product
            'sku': woo_product.get('sku', ''),
            'stock': self._parse_stock(woo_product),
            'is_active': woo_product.get('status') == 'publish',
            'images': self._extract_images(woo_product),
            'metadata': {
                'woo_permalink': woo_product.get('permalink'),
                'woo_type': woo_product.get('type'),
                'woo_categories': [cat.get('name') for cat in woo_product.get('categories', [])],
                'woo_tags': [tag.get('name') for tag in woo_product.get('tags', [])]
            }
        }
        
        # Create or update product
        product, created = Product.objects.update_or_create(
            tenant=tenant,
            external_source='woocommerce',
            external_id=external_id,
            defaults=product_data
        )
        
        # Sync variations if product is variable
        if woo_product.get('type') == 'variable':
            self.transform_variations(product, woo_product)
        else:
            # For simple products, create a default variant
            self._create_default_variant(product, woo_product)
        
        return product
    
    def transform_variations(self, product: Product, woo_product: Dict[str, Any]) -> List[ProductVariant]:
        """
        Transform WooCommerce variations to ProductVariant models.
        
        Args:
            product: Tulia Product instance
            woo_product: WooCommerce product dictionary
            
        Returns:
            list: List of created/updated ProductVariant instances
        """
        variants = []
        woo_variations = woo_product.get('variations', [])
        
        # If variations are just IDs, we need to fetch them
        if woo_variations and isinstance(woo_variations[0], int):
            woo_variations = self._fetch_variations(woo_product['id'])
        
        # Track synced variant IDs
        synced_variant_ids = set()
        
        for woo_variation in woo_variations:
            try:
                variant_data = {
                    'product': product,
                    'title': self._build_variant_title(woo_variation),
                    'sku': woo_variation.get('sku', ''),
                    'price': Decimal(woo_variation.get('price', '0') or '0') if woo_variation.get('price') else None,
                    'stock': self._parse_stock(woo_variation),
                    'attrs': self._extract_attributes(woo_variation),
                    'metadata': {
                        'woo_variation_id': woo_variation.get('id'),
                        'woo_permalink': woo_variation.get('permalink')
                    }
                }
                
                # Use external variation ID as unique identifier
                external_variant_id = str(woo_variation['id'])
                
                # Find existing variant by metadata
                existing_variant = ProductVariant.objects.filter(
                    product=product,
                    metadata__woo_variation_id=woo_variation['id']
                ).first()
                
                if existing_variant:
                    for key, value in variant_data.items():
                        setattr(existing_variant, key, value)
                    existing_variant.save()
                    variant = existing_variant
                else:
                    variant = ProductVariant.objects.create(**variant_data)
                
                synced_variant_ids.add(variant.id)
                variants.append(variant)
            
            except Exception as e:
                logger.error(
                    f"Error transforming variation",
                    extra={
                        'product_id': str(product.id),
                        'variation_id': woo_variation.get('id'),
                        'error': str(e)
                    },
                    exc_info=True
                )
        
        # Delete variants that are no longer in WooCommerce
        ProductVariant.objects.filter(
            product=product
        ).exclude(
            id__in=synced_variant_ids
        ).delete()
        
        return variants
    
    def _fetch_variations(self, product_id: int) -> List[Dict[str, Any]]:
        """Fetch product variations from WooCommerce API."""
        try:
            url = f"{self.api_base}/products/{product_id}/variations"
            params = {'per_page': 100}
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            return response.json()
        
        except Exception as e:
            logger.error(
                f"Error fetching variations",
                extra={'product_id': product_id},
                exc_info=True
            )
            return []
    
    def _create_default_variant(self, product: Product, woo_product: Dict[str, Any]):
        """Create a default variant for simple products."""
        variant_data = {
            'product': product,
            'title': 'Default',
            'sku': woo_product.get('sku', ''),
            'price': None,  # Use product price
            'stock': None,  # Use product stock
            'attrs': {},
            'metadata': {'is_default': True}
        }
        
        # Check if default variant exists
        existing = ProductVariant.objects.filter(
            product=product,
            metadata__is_default=True
        ).first()
        
        if existing:
            for key, value in variant_data.items():
                setattr(existing, key, value)
            existing.save()
        else:
            ProductVariant.objects.create(**variant_data)
    
    def _parse_stock(self, woo_item: Dict[str, Any]) -> Optional[int]:
        """Parse stock quantity from WooCommerce product/variation."""
        if not woo_item.get('manage_stock', False):
            return None  # Unlimited stock
        
        stock_quantity = woo_item.get('stock_quantity')
        if stock_quantity is not None:
            return max(0, int(stock_quantity))
        
        return 0
    
    def _extract_images(self, woo_product: Dict[str, Any]) -> List[str]:
        """Extract image URLs from WooCommerce product."""
        images = []
        
        for image in woo_product.get('images', []):
            if image.get('src'):
                images.append(image['src'])
        
        return images
    
    def _extract_attributes(self, woo_variation: Dict[str, Any]) -> Dict[str, str]:
        """Extract attributes from WooCommerce variation."""
        attrs = {}
        
        for attr in woo_variation.get('attributes', []):
            name = attr.get('name', '').replace('pa_', '').replace('_', ' ').title()
            value = attr.get('option', '')
            if name and value:
                attrs[name] = value
        
        return attrs
    
    def _build_variant_title(self, woo_variation: Dict[str, Any]) -> str:
        """Build variant title from attributes."""
        attrs = self._extract_attributes(woo_variation)
        
        if attrs:
            return ' / '.join(attrs.values())
        
        return f"Variation {woo_variation.get('id', '')}"
    
    def _mark_inactive_products(self, tenant, synced_ids: set) -> int:
        """Mark products not in sync as inactive."""
        inactive_count = Product.objects.filter(
            tenant=tenant,
            external_source='woocommerce',
            is_active=True
        ).exclude(
            id__in=synced_ids
        ).update(is_active=False)
        
        if inactive_count > 0:
            logger.info(
                f"Marked {inactive_count} WooCommerce products as inactive",
                extra={'tenant_id': str(tenant.id)}
            )
        
        return inactive_count
    
    def _log_sync_operation(self, tenant, result: Dict[str, Any], error: str = None):
        """Log sync operation to WebhookLog."""
        try:
            WebhookLog.objects.create(
                tenant=tenant,
                provider='woocommerce',
                event='product_sync',
                payload={
                    'store_url': self.store_url,
                    'result': result
                },
                status='success' if result['status'] == 'success' else 'error',
                error_message=error,
                processing_time_ms=int(result.get('duration_seconds', 0) * 1000)
            )
        except Exception as e:
            logger.error(
                f"Error logging sync operation",
                extra={'error': str(e)},
                exc_info=True
            )


def create_woo_service_for_tenant(tenant) -> WooService:
    """
    Factory function to create WooService instance for a tenant.
    
    Args:
        tenant: Tenant model instance
        
    Returns:
        WooService: Configured service instance
        
    Raises:
        ValueError: If tenant doesn't have WooCommerce credentials configured
        
    Example:
        >>> from apps.tenants.models import Tenant
        >>> tenant = Tenant.objects.get(slug='acme-corp')
        >>> service = create_woo_service_for_tenant(tenant)
        >>> service.sync_products(tenant)
    """
    # Get WooCommerce credentials from TenantSettings
    try:
        settings = tenant.settings
    except AttributeError:
        raise ValueError("Tenant does not have settings configured")
    
    if not settings.has_woocommerce_configured():
        raise ValueError("Tenant does not have WooCommerce credentials configured")
    
    return WooService(
        store_url=settings.woo_store_url,
        consumer_key=settings.woo_consumer_key,
        consumer_secret=settings.woo_consumer_secret
    )
