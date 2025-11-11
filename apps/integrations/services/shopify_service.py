"""
Shopify integration service for product synchronization.

Handles syncing products from Shopify stores to Tulia catalog,
including product variants, pricing, and stock information.
"""
import logging
import requests
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
from django.db import transaction

from apps.catalog.models import Product, ProductVariant
from apps.integrations.models import WebhookLog

logger = logging.getLogger(__name__)


class ShopifyServiceError(Exception):
    """Base exception for Shopify service errors."""
    pass


class ShopifyService:
    """
    Service for synchronizing products from Shopify stores.
    
    Provides methods for:
    - Authenticating with Shopify Admin API
    - Fetching products in batches with pagination
    - Transforming Shopify product format to Tulia Product
    - Syncing product variants
    - Marking inactive products
    """
    
    def __init__(self, shop_domain: str, access_token: str):
        """
        Initialize Shopify service with store credentials.
        
        Args:
            shop_domain: Shopify store domain (e.g., mystore.myshopify.com)
            access_token: Shopify Admin API access token
        """
        self.shop_domain = shop_domain.replace('https://', '').replace('http://', '').rstrip('/')
        self.access_token = access_token
        self.api_base = f"https://{self.shop_domain}/admin/api/2024-01"
        self.session = requests.Session()
        self.session.headers.update({
            'X-Shopify-Access-Token': access_token,
            'Content-Type': 'application/json'
        })
    
    def sync_products(self, tenant) -> Dict[str, Any]:
        """
        Sync all products from Shopify store to Tulia catalog.
        
        Fetches products in batches, transforms them to Tulia format,
        and marks products not in sync as inactive.
        
        Args:
            tenant: Tenant model instance
            
        Returns:
            dict: Sync status with counts
            
        Example:
            >>> service = ShopifyService(domain, token)
            >>> result = service.sync_products(tenant)
            >>> print(f"Synced {result['synced_count']} products")
        """
        start_time = None
        synced_ids = set()
        synced_count = 0
        error_count = 0
        page_info = None
        
        try:
            from django.utils import timezone
            start_time = timezone.now()
            
            logger.info(
                f"Starting Shopify product sync",
                extra={
                    'tenant_id': str(tenant.id),
                    'tenant_slug': tenant.slug,
                    'shop_domain': self.shop_domain
                }
            )
            
            # Fetch products in batches using cursor-based pagination
            while True:
                try:
                    products_batch, next_page_info = self.fetch_products_batch(
                        page_info=page_info,
                        limit=100
                    )
                    
                    if not products_batch:
                        break
                    
                    # Process each product
                    for shopify_product in products_batch:
                        try:
                            with transaction.atomic():
                                product = self.transform_product(tenant, shopify_product)
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
                                    'shopify_product_id': shopify_product.get('id'),
                                    'error': str(e)
                                },
                                exc_info=True
                            )
                    
                    # Check if there are more pages
                    if not next_page_info:
                        break
                    
                    page_info = next_page_info
                
                except ShopifyServiceError as e:
                    logger.error(
                        f"Error fetching products batch",
                        extra={'error': str(e)},
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
                'shop_domain': self.shop_domain
            }
            
            logger.info(
                f"Shopify product sync completed",
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
                f"Fatal error during Shopify sync",
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
            
            raise ShopifyServiceError(f"Product sync failed: {str(e)}") from e
    
    def fetch_products_batch(
        self,
        page_info: Optional[str] = None,
        limit: int = 100
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Fetch a batch of products from Shopify Admin API.
        
        Uses cursor-based pagination with page_info parameter.
        
        Args:
            page_info: Cursor for pagination (from previous response)
            limit: Number of products per page (max 250)
            
        Returns:
            tuple: (list of Shopify product dictionaries, next page_info)
            
        Raises:
            ShopifyServiceError: If API request fails
        """
        try:
            url = f"{self.api_base}/products.json"
            params = {
                'limit': min(limit, 250),  # Shopify max is 250
                'status': 'active'  # Only fetch active products
            }
            
            if page_info:
                params['page_info'] = page_info
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            products = data.get('products', [])
            
            # Extract next page_info from Link header
            next_page_info = None
            link_header = response.headers.get('Link', '')
            if 'rel="next"' in link_header:
                # Parse Link header to extract page_info
                for link in link_header.split(','):
                    if 'rel="next"' in link:
                        # Extract page_info from URL
                        import re
                        match = re.search(r'page_info=([^&>]+)', link)
                        if match:
                            next_page_info = match.group(1)
            
            logger.debug(
                f"Fetched Shopify products batch",
                extra={
                    'count': len(products),
                    'has_next': bool(next_page_info)
                }
            )
            
            return products, next_page_info
        
        except requests.exceptions.HTTPError as e:
            logger.error(
                f"Shopify API HTTP error",
                extra={
                    'status_code': e.response.status_code,
                    'response': e.response.text
                },
                exc_info=True
            )
            raise ShopifyServiceError(f"HTTP error fetching products: {e.response.status_code}") from e
        
        except requests.exceptions.Timeout as e:
            logger.error(
                f"Shopify API timeout",
                exc_info=True
            )
            raise ShopifyServiceError("Request timeout") from e
        
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Shopify API request error",
                exc_info=True
            )
            raise ShopifyServiceError(f"Request error: {str(e)}") from e
        
        except Exception as e:
            logger.error(
                f"Unexpected error fetching products",
                exc_info=True
            )
            raise ShopifyServiceError(f"Unexpected error: {str(e)}") from e
    
    def transform_product(self, tenant, shopify_product: Dict[str, Any]) -> Product:
        """
        Transform Shopify product to Tulia Product model.
        
        Creates or updates Product and ProductVariant records.
        
        Args:
            tenant: Tenant model instance
            shopify_product: Shopify product dictionary
            
        Returns:
            Product: Created or updated Product instance
        """
        external_id = str(shopify_product['id'])
        
        # Get first variant for base price (Shopify always has at least one variant)
        variants = shopify_product.get('variants', [])
        first_variant = variants[0] if variants else {}
        
        # Extract product data
        product_data = {
            'tenant': tenant,
            'external_source': 'shopify',
            'external_id': external_id,
            'title': shopify_product.get('title', ''),
            'description': shopify_product.get('body_html', ''),
            'price': Decimal(first_variant.get('price', '0') or '0'),
            'currency': 'USD',  # Shopify uses shop currency, defaulting to USD
            'sku': first_variant.get('sku', ''),
            'stock': self._parse_stock(first_variant),
            'is_active': shopify_product.get('status') == 'active',
            'images': self._extract_images(shopify_product),
            'metadata': {
                'shopify_handle': shopify_product.get('handle'),
                'shopify_product_type': shopify_product.get('product_type'),
                'shopify_vendor': shopify_product.get('vendor'),
                'shopify_tags': shopify_product.get('tags', '').split(',') if shopify_product.get('tags') else []
            }
        }
        
        # Create or update product
        product, created = Product.objects.update_or_create(
            tenant=tenant,
            external_source='shopify',
            external_id=external_id,
            defaults=product_data
        )
        
        # Sync variants
        self.transform_variants(product, shopify_product)
        
        return product
    
    def transform_variants(self, product: Product, shopify_product: Dict[str, Any]) -> List[ProductVariant]:
        """
        Transform Shopify variants to ProductVariant models.
        
        Args:
            product: Tulia Product instance
            shopify_product: Shopify product dictionary
            
        Returns:
            list: List of created/updated ProductVariant instances
        """
        variants = []
        shopify_variants = shopify_product.get('variants', [])
        
        # Track synced variant IDs
        synced_variant_ids = set()
        
        for shopify_variant in shopify_variants:
            try:
                variant_data = {
                    'product': product,
                    'title': self._build_variant_title(shopify_variant),
                    'sku': shopify_variant.get('sku', ''),
                    'price': Decimal(shopify_variant.get('price', '0') or '0') if shopify_variant.get('price') else None,
                    'stock': self._parse_stock(shopify_variant),
                    'attrs': self._extract_attributes(shopify_variant),
                    'metadata': {
                        'shopify_variant_id': shopify_variant.get('id'),
                        'shopify_barcode': shopify_variant.get('barcode'),
                        'shopify_weight': shopify_variant.get('weight'),
                        'shopify_weight_unit': shopify_variant.get('weight_unit')
                    }
                }
                
                # Find existing variant by metadata
                existing_variant = ProductVariant.objects.filter(
                    product=product,
                    metadata__shopify_variant_id=shopify_variant['id']
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
                    f"Error transforming variant",
                    extra={
                        'product_id': str(product.id),
                        'variant_id': shopify_variant.get('id'),
                        'error': str(e)
                    },
                    exc_info=True
                )
        
        # Delete variants that are no longer in Shopify
        ProductVariant.objects.filter(
            product=product
        ).exclude(
            id__in=synced_variant_ids
        ).delete()
        
        return variants
    
    def _parse_stock(self, shopify_variant: Dict[str, Any]) -> Optional[int]:
        """Parse stock quantity from Shopify variant."""
        # Shopify uses inventory_quantity for stock
        inventory_quantity = shopify_variant.get('inventory_quantity')
        
        # Check inventory policy
        inventory_policy = shopify_variant.get('inventory_policy', 'deny')
        
        if inventory_policy == 'continue':
            # Allow overselling - treat as unlimited
            return None
        
        if inventory_quantity is not None:
            return max(0, int(inventory_quantity))
        
        return 0
    
    def _extract_images(self, shopify_product: Dict[str, Any]) -> List[str]:
        """Extract image URLs from Shopify product."""
        images = []
        
        for image in shopify_product.get('images', []):
            if image.get('src'):
                images.append(image['src'])
        
        return images
    
    def _extract_attributes(self, shopify_variant: Dict[str, Any]) -> Dict[str, str]:
        """Extract attributes from Shopify variant."""
        attrs = {}
        
        # Shopify variants have option1, option2, option3
        for i in range(1, 4):
            option_key = f'option{i}'
            option_value = shopify_variant.get(option_key)
            
            if option_value and option_value != 'Default Title':
                # Try to get option name from product (not available in variant alone)
                # For now, use generic names
                option_name = f'Option {i}'
                attrs[option_name] = option_value
        
        return attrs
    
    def _build_variant_title(self, shopify_variant: Dict[str, Any]) -> str:
        """Build variant title from options."""
        title_parts = []
        
        for i in range(1, 4):
            option_value = shopify_variant.get(f'option{i}')
            if option_value and option_value != 'Default Title':
                title_parts.append(option_value)
        
        if title_parts:
            return ' / '.join(title_parts)
        
        return 'Default'
    
    def _mark_inactive_products(self, tenant, synced_ids: set) -> int:
        """Mark products not in sync as inactive."""
        inactive_count = Product.objects.filter(
            tenant=tenant,
            external_source='shopify',
            is_active=True
        ).exclude(
            id__in=synced_ids
        ).update(is_active=False)
        
        if inactive_count > 0:
            logger.info(
                f"Marked {inactive_count} Shopify products as inactive",
                extra={'tenant_id': str(tenant.id)}
            )
        
        return inactive_count
    
    def _log_sync_operation(self, tenant, result: Dict[str, Any], error: str = None):
        """Log sync operation to WebhookLog."""
        try:
            WebhookLog.objects.create(
                tenant=tenant,
                provider='shopify',
                event='product_sync',
                payload={
                    'shop_domain': self.shop_domain,
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


def create_shopify_service_for_tenant(tenant) -> ShopifyService:
    """
    Factory function to create ShopifyService instance for a tenant.
    
    Args:
        tenant: Tenant model instance with Shopify credentials
        
    Returns:
        ShopifyService: Configured service instance
        
    Raises:
        ValueError: If tenant doesn't have Shopify credentials
        
    Example:
        >>> from apps.tenants.models import Tenant
        >>> tenant = Tenant.objects.get(slug='acme-corp')
        >>> service = create_shopify_service_for_tenant(tenant)
        >>> service.sync_products(tenant)
    """
    # Get Shopify credentials from TenantSettings
    try:
        settings = tenant.settings
    except AttributeError:
        raise ValueError("Tenant does not have settings configured")
    
    if not settings.has_shopify_configured():
        raise ValueError("Tenant does not have Shopify credentials configured")
    
    return ShopifyService(
        shop_domain=settings.shopify_shop_domain,
        access_token=settings.shopify_access_token
    )
