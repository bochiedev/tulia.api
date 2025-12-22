"""
Knowledge base and RAG models for document management and retrieval.

Consolidates all knowledge-related models including documents, embeddings,
and retrieval systems.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import BaseModel


class KnowledgeEntryManager(models.Manager):
    """Manager for knowledge entry queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get active knowledge entries for a specific tenant."""
        return self.filter(tenant=tenant, is_active=True)
    
    def by_category(self, tenant, category):
        """Get entries for a specific category within a tenant."""
        return self.filter(tenant=tenant, category=category, is_active=True)
    
    def by_type(self, tenant, entry_type):
        """Get entries of a specific type within a tenant."""
        return self.filter(tenant=tenant, entry_type=entry_type, is_active=True)
    
    def search_by_keywords(self, tenant, keywords):
        """Search entries by keywords within a tenant."""
        query = self.filter(tenant=tenant, is_active=True)
        for keyword in keywords:
            query = query.filter(keywords__icontains=keyword)
        return query


class KnowledgeEntry(BaseModel):
    """
    Knowledge base entry for AI agent context.
    
    Stores information that the AI agent can reference when responding
    to customer queries. Supports semantic search via embeddings for
    intelligent context retrieval.
    
    Entry types:
    - faq: Frequently asked questions and answers
    - policy: Business policies (returns, shipping, etc.)
    - product_info: Detailed product information
    - service_info: Detailed service information
    - procedure: Step-by-step procedures
    - general: General knowledge
    
    TENANT SCOPING: All queries MUST filter by tenant to prevent cross-tenant data leakage.
    """
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='knowledge_entries',
        db_index=True,
        help_text="Tenant this knowledge entry belongs to"
    )
    
    # Entry Classification
    entry_type = models.CharField(
        max_length=20,
        choices=[
            ('faq', 'FAQ'),
            ('policy', 'Policy'),
            ('product_info', 'Product Information'),
            ('service_info', 'Service Information'),
            ('procedure', 'Procedure'),
            ('general', 'General Knowledge'),
        ],
        default='general',
        db_index=True,
        help_text="Type of knowledge entry"
    )
    
    category = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Category for organizing entries (e.g., 'shipping', 'returns', 'technical')"
    )
    
    # Content
    title = models.CharField(
        max_length=255,
        help_text="Title or question for this entry"
    )
    
    content = models.TextField(
        help_text="Full content or answer for this entry"
    )
    
    # Search Optimization
    keywords = models.TextField(
        blank=True,
        help_text="Comma-separated keywords for search optimization"
    )
    
    embedding = models.JSONField(
        null=True,
        blank=True,
        help_text="Vector embedding for semantic search (generated from title + content)"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (source, author, related_entries, etc.)"
    )
    
    # Priority and Status
    priority = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Priority for ranking search results (0-100, higher = more important)"
    )
    
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this entry is active and should be used by the agent"
    )
    
    # Versioning
    version = models.IntegerField(
        default=1,
        help_text="Version number for tracking updates"
    )
    
    # Custom manager
    objects = KnowledgeEntryManager()
    
    class Meta:
        db_table = 'knowledge_entries'
        verbose_name = 'Knowledge Entry'
        verbose_name_plural = 'Knowledge Entries'
        ordering = ['-priority', '-created_at']
        indexes = [
            models.Index(fields=['tenant', 'is_active', 'priority']),
            models.Index(fields=['tenant', 'entry_type', 'is_active']),
            models.Index(fields=['tenant', 'category', 'is_active']),
            models.Index(fields=['tenant', 'created_at']),
        ]
    
    def __str__(self):
        return f"KnowledgeEntry {self.id} - {self.title} ({self.tenant.name})"
    
    def get_keywords_list(self):
        """Get keywords as a list."""
        if not self.keywords:
            return []
        return [k.strip() for k in self.keywords.split(',') if k.strip()]
    
    def set_keywords_list(self, keywords_list):
        """Set keywords from a list."""
        self.keywords = ', '.join(keywords_list)
    
    def increment_version(self):
        """Increment version number."""
        self.version += 1
    
    def get_metadata_field(self, field_name, default=None):
        """Get a specific metadata field value."""
        return self.metadata.get(field_name, default)
    
    def save(self, *args, **kwargs):
        """Override save to validate tenant consistency."""
        super().save(*args, **kwargs)


class Document(BaseModel):
    """
    Stores uploaded documents for RAG retrieval.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    FILE_TYPE_CHOICES = [
        ('pdf', 'PDF'),
        ('txt', 'Text'),
        ('docx', 'Word Document'),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='documents'
    )
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES)
    file_path = models.CharField(max_length=500)
    file_size = models.IntegerField(help_text="File size in bytes")
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    processing_progress = models.IntegerField(
        default=0,
        help_text="Processing progress percentage (0-100)"
    )
    error_message = models.TextField(blank=True, null=True)
    
    # Statistics
    chunk_count = models.IntegerField(default=0)
    total_tokens = models.IntegerField(default=0)
    
    # Processing timestamps
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When processing was completed"
    )
    
    class Meta:
        db_table = 'bot_documents'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Document {self.file_name} ({self.tenant.name})"


class DocumentChunk(BaseModel):
    """
    Stores document chunks for RAG retrieval.
    """
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='chunks'
    )
    chunk_index = models.IntegerField()
    content = models.TextField()
    token_count = models.IntegerField(default=0)
    
    # Context information
    page_number = models.IntegerField(
        null=True,
        blank=True,
        help_text="Page number in source document (if applicable)"
    )
    section = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Section or heading title (if applicable)"
    )
    
    # Embedding
    embedding = models.JSONField(null=True, blank=True)
    embedding_model = models.CharField(
        max_length=100,
        default='text-embedding-3-small',
        help_text="Embedding model used for this chunk"
    )
    
    class Meta:
        db_table = 'bot_document_chunks'
        ordering = ['document', 'chunk_index']
        unique_together = ['document', 'chunk_index']
    
    def __str__(self):
        return f"Chunk {self.chunk_index} of {self.document.file_name}"


# Note: Additional RAG models would be implemented here as needed