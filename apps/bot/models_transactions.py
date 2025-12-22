"""
Transaction and workflow models for bot interactions.

Consolidates models related to checkout, payments, escalation,
and other transactional workflows.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import BaseModel


class BrowseSession(BaseModel):
    """
    Tracks pagination state for catalog browsing.
    
    Allows customers to browse large catalogs with pagination,
    maintaining state across multiple messages.
    
    TENANT SCOPING: Inherits tenant from conversation relationship.
    All queries MUST filter by tenant to prevent cross-tenant data leakage.
    """
    
    CATALOG_TYPE_CHOICES = [
        ('products', 'Products'),
        ('services', 'Services'),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='browse_sessions',
        db_index=True,
        help_text="Tenant this browse session belongs to"
    )
    conversation = models.ForeignKey(
        'messaging.Conversation',
        on_delete=models.CASCADE,
        related_name='browse_sessions',
        db_index=True,
        help_text="Conversation this browse session belongs to"
    )
    catalog_type = models.CharField(
        max_length=20,
        choices=CATALOG_TYPE_CHOICES,
        help_text="Type of catalog being browsed"
    )
    current_page = models.IntegerField(
        default=1,
        help_text="Current page number (1-indexed)"
    )
    items_per_page = models.IntegerField(
        default=5,
        help_text="Number of items per page"
    )
    total_items = models.IntegerField(
        help_text="Total number of items in result set"
    )
    filters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Applied filters (category, price range, etc.)"
    )
    search_query = models.TextField(
        blank=True,
        help_text="Search query if applicable"
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether session is still active"
    )
    expires_at = models.DateTimeField(
        help_text="When session expires (10 minutes from last activity)"
    )
    
    class Meta:
        db_table = 'bot_browse_sessions'
        verbose_name = 'Browse Session'
        verbose_name_plural = 'Browse Sessions'
        indexes = [
            models.Index(fields=['tenant', 'conversation', 'is_active']),
            models.Index(fields=['expires_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"BrowseSession({self.catalog_type}, page {self.current_page}/{self.total_pages})"
    
    @property
    def total_pages(self):
        """Calculate total number of pages."""
        if self.total_items == 0:
            return 0
        return (self.total_items + self.items_per_page - 1) // self.items_per_page
    
    @property
    def has_next_page(self):
        """Check if there's a next page."""
        return self.current_page < self.total_pages
    
    @property
    def has_previous_page(self):
        """Check if there's a previous page."""
        return self.current_page > 1
    
    @property
    def start_index(self):
        """Get start index for current page (0-indexed)."""
        return (self.current_page - 1) * self.items_per_page
    
    @property
    def end_index(self):
        """Get end index for current page (0-indexed, exclusive)."""
        return min(self.start_index + self.items_per_page, self.total_items)
    
    def save(self, *args, **kwargs):
        """Override save to ensure tenant consistency with conversation."""
        if self.conversation_id and not self.tenant_id:
            # Auto-populate tenant from conversation
            self.tenant = self.conversation.tenant
        
        # Validate tenant consistency
        if self.conversation_id and self.tenant_id:
            if self.conversation.tenant_id != self.tenant_id:
                raise ValueError(
                    f"BrowseSession tenant ({self.tenant_id}) must match "
                    f"Conversation tenant ({self.conversation.tenant_id})"
                )
        
        super().save(*args, **kwargs)


class ReferenceContext(BaseModel):
    """
    Stores list contexts for positional reference resolution.
    
    Allows customers to say "1", "the first one", "last", etc.
    to refer to items in recently displayed lists.
    """
    
    LIST_TYPE_CHOICES = [
        ('products', 'Products'),
        ('services', 'Services'),
        ('appointments', 'Appointments'),
        ('orders', 'Orders'),
    ]
    
    conversation = models.ForeignKey(
        'messaging.Conversation',
        on_delete=models.CASCADE,
        related_name='reference_contexts'
    )
    context_id = models.CharField(
        max_length=50,
        help_text="Unique identifier for this context"
    )
    list_type = models.CharField(
        max_length=20,
        choices=LIST_TYPE_CHOICES,
        help_text="Type of items in the list"
    )
    items = models.JSONField(
        help_text="List of items with IDs and display info"
    )
    expires_at = models.DateTimeField(
        help_text="When context expires (5 minutes from creation)"
    )
    
    class Meta:
        db_table = 'bot_reference_contexts'
        verbose_name = 'Reference Context'
        verbose_name_plural = 'Reference Contexts'
        indexes = [
            models.Index(fields=['conversation', 'expires_at']),
            models.Index(fields=['context_id']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"ReferenceContext({self.list_type}, {len(self.items)} items)"
    
    def get_item_by_position(self, position):
        """
        Get item by position (1-indexed).
        
        Args:
            position: 1-indexed position
        
        Returns:
            Item dict or None
        """
        if 1 <= position <= len(self.items):
            return self.items[position - 1]
        return None
    
    def get_first_item(self):
        """Get first item in list."""
        return self.items[0] if self.items else None
    
    def get_last_item(self):
        """Get last item in list."""
        return self.items[-1] if self.items else None


class ProductAnalysis(BaseModel):
    """
    Stores AI-generated product analysis for intelligent recommendations.
    
    Caches LLM analysis of products to enable semantic matching
    and intelligent recommendations without repeated API calls.
    """
    
    product = models.OneToOneField(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='ai_analysis'
    )
    key_features = models.JSONField(
        default=list,
        help_text="List of key product features"
    )
    use_cases = models.JSONField(
        default=list,
        help_text="Common use cases for this product"
    )
    target_audience = models.JSONField(
        default=list,
        help_text="Target customer segments"
    )
    embedding = models.JSONField(
        null=True,
        blank=True,
        help_text="Semantic embedding vector for similarity search"
    )
    summary = models.TextField(
        help_text="AI-generated product summary"
    )
    ai_categories = models.JSONField(
        default=list,
        help_text="AI-inferred categories beyond formal taxonomy"
    )
    ai_tags = models.JSONField(
        default=list,
        help_text="AI-generated tags for search and matching"
    )
    analyzed_at = models.DateTimeField(
        auto_now=True,
        help_text="When analysis was last updated"
    )
    
    class Meta:
        db_table = 'bot_product_analyses'
        verbose_name = 'Product Analysis'
        verbose_name_plural = 'Product Analyses'
        indexes = [
            models.Index(fields=['product']),
            models.Index(fields=['analyzed_at']),
        ]
    
    def __str__(self):
        return f"ProductAnalysis({self.product.name})"


class LanguagePreference(BaseModel):
    """
    Tracks language preferences and usage patterns for customers.
    
    Supports multi-language conversations with code-switching
    between English, Swahili, and Sheng.
    """
    
    conversation = models.OneToOneField(
        'messaging.Conversation',
        on_delete=models.CASCADE,
        related_name='language_preference'
    )
    primary_language = models.CharField(
        max_length=10,
        default='en',
        help_text="Primary language code (en, sw, mixed)"
    )
    language_usage = models.JSONField(
        default=dict,
        help_text="Usage statistics per language"
    )
    common_phrases = models.JSONField(
        default=list,
        help_text="Commonly used phrases by this customer"
    )
    
    class Meta:
        db_table = 'bot_language_preferences'
        verbose_name = 'Language Preference'
        verbose_name_plural = 'Language Preferences'
        indexes = [
            models.Index(fields=['conversation']),
        ]
    
    def __str__(self):
        return f"LanguagePreference({self.primary_language})"
    
    def record_language_usage(self, language_code):
        """Record usage of a language."""
        if language_code not in self.language_usage:
            self.language_usage[language_code] = 0
        self.language_usage[language_code] += 1
        self.save(update_fields=['language_usage'])
    
    def get_preferred_language(self):
        """Get most frequently used language."""
        if not self.language_usage:
            return self.primary_language
        
        return max(self.language_usage.items(), key=lambda x: x[1])[0]


# Note: Transaction models would be imported here when implemented