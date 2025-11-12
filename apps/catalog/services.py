"""
Catalog service for product operations.

Handles product search, retrieval, and feature limit enforcement
with strict tenant scoping.
"""
import hashlib
import json
from django.db.models import Q, Prefetch
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from apps.catalog.models import Product, ProductVariant
from apps.tenants.services.subscription_service import SubscriptionService
from apps.core.exceptions import FeatureLimitExceeded
from apps.core.cache import (
    CacheService, CacheKeys, CacheTTL, TenantCacheInvalidator
)


class CatalogService:
    """Service for catalog operations with tenant scoping."""
    
    @staticmethod
    def search_products(tenant, query=None, filters=None, limit=50):
        """
        Search products with full-text search and filtering.
        
        Args:
            tenant: Tenant instance
            query: Search query string (searches title and description)
            filters: Dict of filters (e.g., {'is_active': True, 'min_price': 10})
            limit: Maximum number of results
            
        Returns:
            QuerySet: Filtered and ordered products
        """
        # Start with tenant-scoped queryset with optimized joins
        products = Product.objects.for_tenant(tenant).select_related('tenant').prefetch_related(
            Prefetch(
                'variants',
                queryset=ProductVariant.objects.order_by('title')
            )
        )
        
        # Apply search query
        if query:
            # Use PostgreSQL full-text search if available
            from django.db import connection
            if connection.vendor == 'postgresql':
                try:
                    search_query = SearchQuery(query)
                    search_vector = SearchVector('title', weight='A') + SearchVector('description', weight='B')
                    products = products.annotate(
                        rank=SearchRank(search_vector, search_query)
                    ).filter(rank__gte=0.01).order_by('-rank')
                except Exception:
                    # Fallback to simple icontains search
                    products = products.filter(
                        Q(title__icontains=query) | Q(description__icontains=query)
                    )
            else:
                # Fallback to simple icontains search for non-PostgreSQL databases
                products = products.filter(
                    Q(title__icontains=query) | Q(description__icontains=query)
                )
        
        # Apply filters
        if filters:
            if 'is_active' in filters:
                products = products.filter(is_active=filters['is_active'])
            
            if 'min_price' in filters:
                products = products.filter(price__gte=filters['min_price'])
            
            if 'max_price' in filters:
                products = products.filter(price__lte=filters['max_price'])
            
            if 'external_source' in filters:
                products = products.filter(external_source=filters['external_source'])
            
            if 'in_stock' in filters and filters['in_stock']:
                products = products.filter(Q(stock__isnull=True) | Q(stock__gt=0))
        
        # Limit results
        return products[:limit]
    
    @staticmethod
    def get_product(tenant, product_id, include_variants=True):
        """
        Get a single product with optional variant loading.
        
        Args:
            tenant: Tenant instance
            product_id: Product UUID
            include_variants: Whether to prefetch variants
            
        Returns:
            Product: Product instance or None
        """
        # Try cache first
        cache_key = CacheKeys.format(
            CacheKeys.PRODUCT_DETAIL,
            tenant_id=str(tenant.id),
            product_id=str(product_id)
        )
        
        cached_product = CacheService.get(cache_key)
        if cached_product is not None:
            return cached_product
        
        # Cache miss - fetch from database
        queryset = Product.objects.for_tenant(tenant).select_related('tenant')
        
        if include_variants:
            queryset = queryset.prefetch_related(
                Prefetch(
                    'variants',
                    queryset=ProductVariant.objects.order_by('title')
                )
            )
        
        try:
            product = queryset.get(id=product_id)
            # Cache the result
            CacheService.set(cache_key, product, CacheTTL.CATALOG)
            return product
        except Product.DoesNotExist:
            return None
    
    @staticmethod
    def get_product_by_external_id(tenant, external_source, external_id, include_variants=True):
        """
        Get product by external source and ID.
        
        Args:
            tenant: Tenant instance
            external_source: Source system ('woocommerce', 'shopify', 'manual')
            external_id: External product ID
            include_variants: Whether to prefetch variants
            
        Returns:
            Product: Product instance or None
        """
        queryset = Product.objects.for_tenant(tenant).select_related('tenant')
        
        if include_variants:
            queryset = queryset.prefetch_related(
                Prefetch(
                    'variants',
                    queryset=ProductVariant.objects.order_by('title')
                )
            )
        
        return queryset.filter(
            external_source=external_source,
            external_id=external_id
        ).first()
    
    @staticmethod
    def create_product(tenant, product_data, check_limits=True):
        """
        Create a new product with feature limit enforcement.
        
        Args:
            tenant: Tenant instance
            product_data: Dict of product fields
            check_limits: Whether to enforce feature limits
            
        Returns:
            Product: Created product instance
            
        Raises:
            FeatureLimitExceeded: If product limit is exceeded
        """
        if check_limits:
            CatalogService.check_feature_limit(tenant, 'max_products')
        
        # Ensure tenant is set
        product_data['tenant'] = tenant
        
        # Create product
        product = Product.objects.create(**product_data)
        
        # Invalidate catalog cache
        TenantCacheInvalidator.invalidate_product_catalog(str(tenant.id))
        
        return product
    
    @staticmethod
    def update_product(tenant, product_id, product_data):
        """
        Update an existing product.
        
        Args:
            tenant: Tenant instance
            product_id: Product UUID
            product_data: Dict of fields to update
            
        Returns:
            Product: Updated product instance or None
        """
        product = CatalogService.get_product(tenant, product_id, include_variants=False)
        
        if not product:
            return None
        
        # Update fields
        for field, value in product_data.items():
            if field != 'tenant' and hasattr(product, field):
                setattr(product, field, value)
        
        product.save()
        
        # Invalidate cache for this product
        TenantCacheInvalidator.invalidate_product_catalog(str(tenant.id), str(product_id))
        
        return product
    
    @staticmethod
    def delete_product(tenant, product_id, soft_delete=True):
        """
        Delete a product (soft delete by default).
        
        Args:
            tenant: Tenant instance
            product_id: Product UUID
            soft_delete: Whether to soft delete (True) or hard delete (False)
            
        Returns:
            bool: True if deleted, False if not found
        """
        product = CatalogService.get_product(tenant, product_id, include_variants=False)
        
        if not product:
            return False
        
        if soft_delete:
            product.delete()  # Soft delete via BaseModel
        else:
            product.hard_delete()
        
        # Invalidate cache for this product
        TenantCacheInvalidator.invalidate_product_catalog(str(tenant.id), str(product_id))
        
        return True
    
    @staticmethod
    def check_feature_limit(tenant, feature_name='max_products'):
        """
        Check if tenant can create more products based on tier limits.
        
        Args:
            tenant: Tenant instance
            feature_name: Feature to check (default: 'max_products')
            
        Raises:
            FeatureLimitExceeded: If limit is exceeded
        """
        # Get current product count
        current_count = Product.objects.filter(
            tenant=tenant,
            is_active=True
        ).count()
        
        # Use subscription service to enforce limit
        SubscriptionService.enforce_feature_limit(
            tenant,
            feature_name,
            current_count
        )
    
    @staticmethod
    def get_variant(tenant, variant_id):
        """
        Get a product variant.
        
        Args:
            tenant: Tenant instance
            variant_id: ProductVariant UUID
            
        Returns:
            ProductVariant: Variant instance or None
        """
        try:
            return ProductVariant.objects.select_related('product').get(
                id=variant_id,
                product__tenant=tenant
            )
        except ProductVariant.DoesNotExist:
            return None
    
    @staticmethod
    def create_variant(tenant, product_id, variant_data):
        """
        Create a product variant.
        
        Args:
            tenant: Tenant instance
            product_id: Product UUID
            variant_data: Dict of variant fields
            
        Returns:
            ProductVariant: Created variant or None if product not found
        """
        product = CatalogService.get_product(tenant, product_id, include_variants=False)
        
        if not product:
            return None
        
        variant_data['product'] = product
        variant = ProductVariant.objects.create(**variant_data)
        
        return variant
    
    @staticmethod
    def update_variant(tenant, variant_id, variant_data):
        """
        Update a product variant.
        
        Args:
            tenant: Tenant instance
            variant_id: ProductVariant UUID
            variant_data: Dict of fields to update
            
        Returns:
            ProductVariant: Updated variant or None
        """
        variant = CatalogService.get_variant(tenant, variant_id)
        
        if not variant:
            return None
        
        # Update fields
        for field, value in variant_data.items():
            if field != 'product' and hasattr(variant, field):
                setattr(variant, field, value)
        
        variant.save()
        return variant
    
    @staticmethod
    def delete_variant(tenant, variant_id, soft_delete=True):
        """
        Delete a product variant.
        
        Args:
            tenant: Tenant instance
            variant_id: ProductVariant UUID
            soft_delete: Whether to soft delete (True) or hard delete (False)
            
        Returns:
            bool: True if deleted, False if not found
        """
        variant = CatalogService.get_variant(tenant, variant_id)
        
        if not variant:
            return False
        
        if soft_delete:
            variant.delete()  # Soft delete via BaseModel
        else:
            variant.hard_delete()
        
        return True
    
    @staticmethod
    def bulk_upsert_products(tenant, products_data, external_source):
        """
        Bulk upsert products from external source (for sync operations).
        
        Args:
            tenant: Tenant instance
            products_data: List of product dicts with external_id
            external_source: Source system ('woocommerce', 'shopify')
            
        Returns:
            dict: {'created': count, 'updated': count, 'errors': []}
        """
        created_count = 0
        updated_count = 0
        errors = []
        
        # Get all external IDs from the sync
        synced_external_ids = set()
        
        for product_data in products_data:
            try:
                external_id = product_data.get('external_id')
                if not external_id:
                    errors.append({'error': 'Missing external_id', 'data': product_data})
                    continue
                
                synced_external_ids.add(external_id)
                
                # Try to find existing product
                existing = Product.objects.filter(
                    tenant=tenant,
                    external_source=external_source,
                    external_id=external_id
                ).first()
                
                # Ensure tenant and source are set
                product_data['tenant'] = tenant
                product_data['external_source'] = external_source
                
                if existing:
                    # Update existing product
                    for field, value in product_data.items():
                        if field != 'id' and hasattr(existing, field):
                            setattr(existing, field, value)
                    existing.save()
                    updated_count += 1
                else:
                    # Create new product (skip limit check for sync)
                    Product.objects.create(**product_data)
                    created_count += 1
                    
            except Exception as e:
                errors.append({
                    'error': str(e),
                    'data': product_data
                })
        
        # Mark products not in sync as inactive
        if synced_external_ids:
            Product.objects.filter(
                tenant=tenant,
                external_source=external_source
            ).exclude(
                external_id__in=synced_external_ids
            ).update(is_active=False)
        
        return {
            'created': created_count,
            'updated': updated_count,
            'errors': errors
        }
