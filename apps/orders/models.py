"""
Order and cart models for e-commerce functionality.

Implements shopping cart and order management with:
- Tenant-scoped carts and orders
- Cart persistence per conversation
- Order status tracking
- Payment reference tracking
"""
from django.db import models
from apps.core.models import BaseModel


class CartManager(models.Manager):
    """Manager for cart queries."""
    
    def for_conversation(self, conversation):
        """Get cart for a specific conversation."""
        return self.filter(conversation=conversation).first()
    
    def for_tenant(self, tenant):
        """Get carts for a specific tenant."""
        return self.filter(conversation__tenant=tenant)


class Cart(BaseModel):
    """
    Shopping cart model for temporary item storage.
    
    Each cart:
    - Belongs to a conversation (one cart per conversation)
    - Stores items as JSON with product/variant references
    - Tracks subtotal for quick display
    - Cleared after order creation
    """
    
    conversation = models.OneToOneField(
        'messaging.Conversation',
        on_delete=models.CASCADE,
        related_name='cart',
        help_text="Conversation this cart belongs to"
    )
    
    # Cart Contents
    items = models.JSONField(
        default=list,
        blank=True,
        help_text="List of cart items with product_id, variant_id, quantity, price"
    )
    
    # Pricing
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Cart subtotal (sum of item prices)"
    )
    
    class Meta:
        db_table = 'carts'
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"Cart for {self.conversation.id} ({len(self.items)} items)"
    
    @property
    def item_count(self):
        """Get total number of items in cart."""
        return sum(item.get('quantity', 0) for item in self.items)
    
    def clear(self):
        """Clear all items from cart."""
        self.items = []
        self.subtotal = 0
        self.save(update_fields=['items', 'subtotal'])


class OrderManager(models.Manager):
    """Manager for order queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get orders for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def for_customer(self, tenant, customer):
        """Get orders for a specific customer within tenant."""
        return self.filter(tenant=tenant, customer=customer)
    
    def by_status(self, tenant, status):
        """Get orders by status."""
        return self.filter(tenant=tenant, status=status)
    
    def paid(self, tenant):
        """Get paid orders."""
        return self.filter(tenant=tenant, status__in=['paid', 'fulfilled'])


class Order(BaseModel):
    """
    Order model representing a completed purchase transaction.
    
    Each order:
    - Belongs to a tenant and customer
    - Contains items from cart at time of creation
    - Tracks payment and fulfillment status
    - References external payment system
    """
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending_payment', 'Pending Payment'),
        ('placed', 'Placed'),
        ('paid', 'Paid'),
        ('fulfilled', 'Fulfilled'),
        ('canceled', 'Canceled'),
    ]
    
    # Tenant Scoping
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='orders',
        db_index=True,
        help_text="Tenant this order belongs to"
    )
    customer = models.ForeignKey(
        'tenants.Customer',
        on_delete=models.CASCADE,
        related_name='orders',
        db_index=True,
        help_text="Customer who placed the order"
    )
    
    # Pricing
    currency = models.CharField(
        max_length=3,
        help_text="Currency code (ISO 4217)"
    )
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Order subtotal (sum of item prices)"
    )
    shipping = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Shipping cost"
    )
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Total order amount (subtotal + shipping)"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        db_index=True,
        help_text="Order status"
    )
    
    # Order Contents
    items = models.JSONField(
        default=list,
        help_text="Order items with product_id, variant_id, quantity, price"
    )
    
    # Payment
    payment_ref = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="External payment reference ID"
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when payment was received"
    )
    
    # Fulfillment
    fulfilled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when order was fulfilled"
    )
    tracking_number = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Shipping tracking number"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional order metadata"
    )
    
    # Custom manager
    objects = OrderManager()
    
    class Meta:
        db_table = 'orders'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'customer', 'status']),
            models.Index(fields=['tenant', 'status', 'created_at']),
            models.Index(fields=['payment_ref']),
        ]
    
    def __str__(self):
        return f"Order {self.id} - {self.customer} ({self.status})"
    
    @property
    def item_count(self):
        """Get total number of items in order."""
        return sum(item.get('quantity', 0) for item in self.items)
    
    def mark_paid(self, payment_ref=None):
        """Mark order as paid."""
        from django.utils import timezone
        self.status = 'paid'
        self.paid_at = timezone.now()
        if payment_ref:
            self.payment_ref = payment_ref
        self.save(update_fields=['status', 'paid_at', 'payment_ref'])
    
    def mark_fulfilled(self, tracking_number=None):
        """Mark order as fulfilled."""
        from django.utils import timezone
        self.status = 'fulfilled'
        self.fulfilled_at = timezone.now()
        if tracking_number:
            self.tracking_number = tracking_number
        self.save(update_fields=['status', 'fulfilled_at', 'tracking_number'])
    
    def cancel(self):
        """Cancel the order."""
        self.status = 'canceled'
        self.save(update_fields=['status'])
