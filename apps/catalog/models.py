"""
Catalog models for products and services.

Implements multi-tenant product catalog with support for:
- External source synchronization (WooCommerce, Shopify)
- Product variants with SKU, price, and stock tracking
- Full-text search capabilities
- Tenant isolation
"""
from django.db import models
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex
from apps.core.models import BaseModel


class ProductQuerySet(models.QuerySet):
    """Custom QuerySet for Product with chainable methods."""
    
    def for_tenant(self, tenant):
        """Get products for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def active(self):
        """Get only active products."""
        return self.filter(is_active=True)
    
    def search(self, query):
        """Search products by title or description."""
        return self.filter(
            models.Q(title__icontains=query) |
            models.Q(description__icontains=query)
        )


class ProductManager(models.Manager):
    """Manager for product queries with tenant scoping."""
    
    def get_queryset(self):
        """Return custom QuerySet."""
        return ProductQuerySet(self.model, using=self._db)
    
    def for_tenant(self, tenant):
        """Get products for a specific tenant."""
        return self.get_queryset().for_tenant(tenant)
    
    def active(self):
        """
        Get only active products.
        
        WARNING: This method does NOT filter by tenant. 
        Always chain with .for_tenant(tenant) or use in tenant-scoped context.
        """
        return self.get_queryset().active()
    
    def by_external_id(self, tenant, external_source, external_id):
        """Find product by external source and ID."""
        return self.get_queryset().filter(
            tenant=tenant,
            external_source=external_source,
            external_id=external_id
        ).first()
    
    def search(self, tenant, query):
        """Search products by title or description."""
        return self.get_queryset().for_tenant(tenant).active().search(query)


class Product(BaseModel):
    """
    Product model representing a physical item for sale.
    
    Products can be:
    - Synchronized from external sources (WooCommerce, Shopify)
    - Manually created by tenant
    - Have multiple variants with different SKUs, prices, attributes
    
    Each product is strictly scoped to a tenant with unique constraint
    on (tenant, external_source, external_id) for sync deduplication.
    """
    
    EXTERNAL_SOURCE_CHOICES = [
        ('woocommerce', 'WooCommerce'),
        ('shopify', 'Shopify'),
        ('manual', 'Manual'),
    ]
    
    # Tenant Scoping
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='products',
        db_index=True,
        help_text="Tenant this product belongs to"
    )
    
    # External Source Tracking
    external_source = models.CharField(
        max_length=20,
        choices=EXTERNAL_SOURCE_CHOICES,
        null=True,
        blank=True,
        help_text="Source system for synchronized products"
    )
    external_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Product ID in external system"
    )
    
    # Basic Information
    title = models.CharField(
        max_length=500,
        db_index=True,
        help_text="Product title"
    )
    description = models.TextField(
        null=True,
        blank=True,
        help_text="Product description"
    )
    images = models.JSONField(
        default=list,
        blank=True,
        help_text="List of image URLs"
    )
    
    # Pricing
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Base price"
    )
    currency = models.CharField(
        max_length=3,
        default='USD',
        help_text="Currency code (ISO 4217)"
    )
    
    # Inventory
    sku = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Stock Keeping Unit"
    )
    stock = models.IntegerField(
        null=True,
        blank=True,
        help_text="Available stock quantity (null = unlimited)"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether product is active and visible"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional product metadata"
    )
    
    # Search
    search_vector = SearchVectorField(
        null=True,
        blank=True,
        help_text="Full-text search vector"
    )
    
    # Custom manager
    objects = ProductManager()
    
    class Meta:
        db_table = 'products'
        ordering = ['-created_at']
        unique_together = [('tenant', 'external_source', 'external_id')]
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['tenant', 'title']),
            models.Index(fields=['tenant', 'external_source', 'external_id']),
            models.Index(fields=['tenant', 'created_at']),
            GinIndex(fields=['search_vector'], name='product_search_idx'),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.tenant.slug})"
    
    def has_stock(self, quantity=1):
        """Check if product has sufficient stock."""
        if self.stock is None:
            return True  # Unlimited stock
        return self.stock >= quantity
    
    def reduce_stock(self, quantity):
        """Reduce stock by specified quantity."""
        if self.stock is not None:
            self.stock = max(0, self.stock - quantity)
            self.save(update_fields=['stock'])
    
    def increase_stock(self, quantity):
        """Increase stock by specified quantity."""
        if self.stock is not None:
            self.stock += quantity
            self.save(update_fields=['stock'])
    
    @property
    def is_in_stock(self):
        """Check if product is in stock."""
        return self.stock is None or self.stock > 0
    
    @property
    def variant_count(self):
        """Get number of variants."""
        return self.variants.count()


class ProductVariantQuerySet(models.QuerySet):
    """Custom QuerySet for ProductVariant with chainable methods."""
    
    def for_product(self, product):
        """Get variants for a specific product."""
        return self.filter(product=product)
    
    def for_tenant(self, tenant):
        """Get variants for a specific tenant."""
        return self.filter(product__tenant=tenant)
    
    def in_stock(self):
        """Get only variants with stock."""
        return self.filter(
            models.Q(stock__isnull=True) | models.Q(stock__gt=0)
        )


class ProductVariantManager(models.Manager):
    """Manager for product variant queries."""
    
    def get_queryset(self):
        """Return custom QuerySet."""
        return ProductVariantQuerySet(self.model, using=self._db)
    
    def for_product(self, product):
        """Get variants for a specific product."""
        return self.get_queryset().for_product(product)
    
    def for_tenant(self, tenant):
        """Get variants for a specific tenant."""
        return self.get_queryset().for_tenant(tenant)
    
    def by_sku(self, tenant, sku):
        """Find variant by SKU within tenant."""
        return self.get_queryset().for_tenant(tenant).filter(sku=sku).first()
    
    def in_stock(self):
        """
        Get only variants with stock.
        
        WARNING: This method does NOT filter by tenant.
        Always chain with .for_tenant(tenant) or use in tenant-scoped context.
        """
        return self.get_queryset().in_stock()


class ProductVariant(BaseModel):
    """
    Product variant representing a specific configuration of a product.
    
    Variants allow products to have multiple options with different:
    - SKUs
    - Prices
    - Stock levels
    - Attributes (size, color, etc.)
    
    Example: A t-shirt product might have variants for different sizes and colors.
    """
    
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants',
        db_index=True,
        help_text="Product this variant belongs to"
    )
    
    # Basic Information
    title = models.CharField(
        max_length=255,
        help_text="Variant title (e.g., 'Large / Red')"
    )
    
    # Inventory
    sku = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Stock Keeping Unit for this variant"
    )
    stock = models.IntegerField(
        null=True,
        blank=True,
        help_text="Available stock quantity (null = unlimited)"
    )
    
    # Pricing (overrides product price if set)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Variant-specific price (null = use product price)"
    )
    
    # Attributes
    attrs = models.JSONField(
        default=dict,
        blank=True,
        help_text="Variant attributes (e.g., {'size': 'L', 'color': 'red'})"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional variant metadata"
    )
    
    # Custom manager
    objects = ProductVariantManager()
    
    class Meta:
        db_table = 'product_variants'
        ordering = ['title']
        indexes = [
            models.Index(fields=['product', 'created_at']),
            models.Index(fields=['sku']),
        ]
    
    def __str__(self):
        return f"{self.product.title} - {self.title}"
    
    @property
    def effective_price(self):
        """Get effective price (variant price or product price)."""
        return self.price if self.price is not None else self.product.price
    
    @property
    def currency(self):
        """Get currency from product."""
        return self.product.currency
    
    def has_stock(self, quantity=1):
        """Check if variant has sufficient stock."""
        if self.stock is None:
            return True  # Unlimited stock
        return self.stock >= quantity
    
    def reduce_stock(self, quantity):
        """Reduce stock by specified quantity."""
        if self.stock is not None:
            self.stock = max(0, self.stock - quantity)
            self.save(update_fields=['stock'])
    
    def increase_stock(self, quantity):
        """Increase stock by specified quantity."""
        if self.stock is not None:
            self.stock += quantity
            self.save(update_fields=['stock'])
    
    @property
    def is_in_stock(self):
        """Check if variant is in stock."""
        return self.stock is None or self.stock > 0
