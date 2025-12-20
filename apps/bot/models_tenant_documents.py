"""
Tenant document models for LangGraph RAG implementation.

This module provides the TenantDocument model specifically designed for the
Tulia AI V2 LangGraph refactor, with strict tenant isolation and vector embeddings.
"""
import os
import uuid
from django.db import models
from django.core.validators import FileExtensionValidator
from apps.core.models import BaseModel


class TenantDocumentManager(models.Manager):
    """Manager for tenant document queries with strict tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get documents for a specific tenant."""
        return self.filter(tenant=tenant, is_active=True)
    
    def by_document_type(self, tenant, document_type):
        """Get documents of a specific type within a tenant."""
        return self.filter(tenant=tenant, document_type=document_type, is_active=True)
    
    def processed(self, tenant):
        """Get successfully processed documents for a tenant."""
        return self.filter(tenant=tenant, status='completed', is_active=True)
    
    def pending_processing(self, tenant):
        """Get documents pending processing for a tenant."""
        return self.filter(tenant=tenant, status__in=['pending', 'processing'], is_active=True)


class TenantDocument(BaseModel):
    """
    Tenant-scoped document model for LangGraph RAG implementation.
    
    This model stores documents uploaded by tenants for knowledge base retrieval.
    Each document is processed into chunks with vector embeddings stored in the
    tenant-namespaced vector database.
    
    Document types supported:
    - pdf: PDF documents
    - docx: Microsoft Word documents  
    - txt: Plain text files
    - faq: FAQ entries
    - policy: Business policies
    - manual: User manuals
    
    TENANT SCOPING: All queries MUST filter by tenant to prevent cross-tenant data leakage.
    Vector embeddings are stored in tenant-specific namespaces in the vector database.
    """
    
    DOCUMENT_TYPE_CHOICES = [
        ('pdf', 'PDF Document'),
        ('docx', 'Word Document'),
        ('txt', 'Text File'),
        ('faq', 'FAQ Entry'),
        ('policy', 'Policy Document'),
        ('manual', 'User Manual'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Processing'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='tenant_documents',
        db_index=True,
        help_text="Tenant this document belongs to"
    )
    
    # Document metadata
    title = models.CharField(
        max_length=255,
        help_text="Document title or filename"
    )
    
    document_type = models.CharField(
        max_length=20,
        choices=DOCUMENT_TYPE_CHOICES,
        db_index=True,
        help_text="Type of document"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Optional description of the document content"
    )
    
    # File information
    file_path = models.CharField(
        max_length=500,
        help_text="Path to the stored file"
    )
    
    file_size = models.PositiveIntegerField(
        help_text="File size in bytes"
    )
    
    file_hash = models.CharField(
        max_length=64,
        db_index=True,
        help_text="SHA-256 hash of file content for deduplication"
    )
    
    # Processing status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text="Processing status"
    )
    
    processing_progress = models.PositiveSmallIntegerField(
        default=0,
        help_text="Processing progress percentage (0-100)"
    )
    
    error_message = models.TextField(
        blank=True,
        help_text="Error message if processing failed"
    )
    
    # Content statistics
    chunk_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of chunks created from this document"
    )
    
    total_tokens = models.PositiveIntegerField(
        default=0,
        help_text="Total number of tokens in all chunks"
    )
    
    # Vector embedding information
    embedding_model = models.CharField(
        max_length=100,
        default='text-embedding-3-small',
        help_text="Model used for generating embeddings"
    )
    
    vector_namespace = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Vector database namespace (tenant-scoped)"
    )
    
    # Metadata for search and organization
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Tags for categorization and search"
    )
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (author, source, etc.)"
    )
    
    # Processing timestamps
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the document was uploaded"
    )
    
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When processing was completed"
    )
    
    # Soft delete flag
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this document is active and should be used for retrieval"
    )
    
    # Custom manager
    objects = TenantDocumentManager()
    
    class Meta:
        db_table = 'bot_tenant_documents'
        verbose_name = 'Tenant Document'
        verbose_name_plural = 'Tenant Documents'
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['tenant', 'is_active', 'status']),
            models.Index(fields=['tenant', 'document_type', 'is_active']),
            models.Index(fields=['tenant', 'uploaded_at']),
            models.Index(fields=['vector_namespace']),
            models.Index(fields=['file_hash']),
        ]
        unique_together = [
            ['tenant', 'file_hash'],  # Prevent duplicate files per tenant
        ]
    
    def __str__(self):
        return f"TenantDocument({self.title}) - {self.tenant.name}"
    
    def save(self, *args, **kwargs):
        """Override save to set vector namespace."""
        if not self.vector_namespace:
            self.vector_namespace = f"tenant_{self.tenant_id}"
        super().save(*args, **kwargs)
    
    def get_file_extension(self):
        """Get file extension from file path."""
        return os.path.splitext(self.file_path)[1].lower().lstrip('.')
    
    def is_processed(self):
        """Check if document has been successfully processed."""
        return self.status == 'completed'
    
    def is_processing(self):
        """Check if document is currently being processed."""
        return self.status in ['pending', 'processing']
    
    def has_failed(self):
        """Check if document processing has failed."""
        return self.status == 'failed'
    
    def get_progress_percentage(self):
        """Get processing progress as percentage."""
        return min(max(self.processing_progress, 0), 100)
    
    def mark_processing_started(self):
        """Mark document as processing started."""
        self.status = 'processing'
        self.processing_progress = 0
        self.error_message = ''
        self.save(update_fields=['status', 'processing_progress', 'error_message'])
    
    def mark_processing_completed(self, chunk_count=0, total_tokens=0):
        """Mark document as processing completed."""
        from django.utils import timezone
        
        self.status = 'completed'
        self.processing_progress = 100
        self.chunk_count = chunk_count
        self.total_tokens = total_tokens
        self.processed_at = timezone.now()
        self.error_message = ''
        self.save(update_fields=[
            'status', 'processing_progress', 'chunk_count', 
            'total_tokens', 'processed_at', 'error_message'
        ])
    
    def mark_processing_failed(self, error_message):
        """Mark document as processing failed."""
        self.status = 'failed'
        self.error_message = error_message
        self.save(update_fields=['status', 'error_message'])
    
    def update_progress(self, progress):
        """Update processing progress."""
        self.processing_progress = min(max(progress, 0), 100)
        self.save(update_fields=['processing_progress'])
    
    def soft_delete(self):
        """Soft delete the document."""
        self.is_active = False
        self.save(update_fields=['is_active'])


class TenantDocumentChunkManager(models.Manager):
    """Manager for tenant document chunk queries with strict tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get chunks for a specific tenant."""
        return self.filter(document__tenant=tenant, document__is_active=True)
    
    def for_document(self, document):
        """Get chunks for a specific document."""
        return self.filter(document=document).order_by('chunk_index')
    
    def by_vector_ids(self, tenant, vector_ids):
        """Get chunks by vector IDs within a tenant."""
        return self.filter(
            document__tenant=tenant,
            document__is_active=True,
            vector_id__in=vector_ids
        )


class TenantDocumentChunk(BaseModel):
    """
    Chunks of tenant documents with vector embeddings for semantic search.
    
    Each document is split into chunks for better retrieval granularity.
    Vector embeddings are stored in the tenant-namespaced vector database.
    
    TENANT SCOPING: Inherits tenant from document relationship.
    All queries MUST filter by document__tenant to prevent cross-tenant data leakage.
    """
    
    document = models.ForeignKey(
        TenantDocument,
        on_delete=models.CASCADE,
        related_name='chunks',
        db_index=True,
        help_text="Document this chunk belongs to"
    )
    
    # Chunk positioning
    chunk_index = models.PositiveIntegerField(
        help_text="Position of chunk within document (0-based)"
    )
    
    # Content
    content = models.TextField(
        help_text="Text content of the chunk"
    )
    
    token_count = models.PositiveIntegerField(
        help_text="Number of tokens in this chunk"
    )
    
    # Source location within document
    page_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Page number in source document (if applicable)"
    )
    
    section_title = models.CharField(
        max_length=255,
        blank=True,
        help_text="Section or heading title (if applicable)"
    )
    
    # Vector embedding information
    vector_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Unique ID in vector database"
    )
    
    embedding_model = models.CharField(
        max_length=100,
        default='text-embedding-3-small',
        help_text="Model used for generating embedding"
    )
    
    # Chunk metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional chunk metadata"
    )
    
    # Custom manager
    objects = TenantDocumentChunkManager()
    
    class Meta:
        db_table = 'bot_tenant_document_chunks'
        verbose_name = 'Tenant Document Chunk'
        verbose_name_plural = 'Tenant Document Chunks'
        ordering = ['document', 'chunk_index']
        indexes = [
            models.Index(fields=['document', 'chunk_index']),
            models.Index(fields=['vector_id']),
            models.Index(fields=['document', 'page_number']),
        ]
        unique_together = [
            ['document', 'chunk_index'],  # Ensure unique chunk ordering per document
        ]
    
    def __str__(self):
        return f"Chunk {self.chunk_index} of {self.document.title}"
    
    def save(self, *args, **kwargs):
        """Override save to generate vector_id if not set."""
        if not self.vector_id:
            self.vector_id = f"doc_{self.document_id}_chunk_{self.chunk_index}_{uuid.uuid4().hex[:8]}"
        super().save(*args, **kwargs)
    
    def get_tenant(self):
        """Get the tenant this chunk belongs to."""
        return self.document.tenant
    
    def get_vector_namespace(self):
        """Get the vector namespace for this chunk."""
        return self.document.vector_namespace
    
    def get_preview(self, max_length=100):
        """Get a preview of the chunk content."""
        if len(self.content) <= max_length:
            return self.content
        return self.content[:max_length] + "..."