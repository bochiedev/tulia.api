"""
RAG (Retrieval-Augmented Generation) models for document management and retrieval.
"""
from django.db import models
from apps.core.models import BaseModel
from apps.tenants.models import Tenant
from apps.messaging.models import Conversation


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
    ]
    
    tenant = models.ForeignKey(
        Tenant,
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
    
    # Metadata
    uploaded_by = models.CharField(max_length=255, blank=True, null=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'bot_documents'
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['status', 'created_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.file_name} ({self.status})"


class DocumentChunk(BaseModel):
    """
    Stores chunks of documents with embeddings for semantic search.
    """
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='chunks'
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='document_chunks'
    )
    
    chunk_index = models.IntegerField(help_text="Position of chunk in document")
    content = models.TextField()
    token_count = models.IntegerField()
    
    # Metadata
    page_number = models.IntegerField(blank=True, null=True)
    section = models.CharField(max_length=255, blank=True, null=True)
    
    # Embedding info (actual embedding stored in vector store)
    embedding_model = models.CharField(max_length=100, default='text-embedding-3-small')
    vector_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="ID in vector store"
    )
    
    class Meta:
        db_table = 'bot_document_chunks'
        indexes = [
            models.Index(fields=['tenant', 'document']),
            models.Index(fields=['document', 'chunk_index']),
            models.Index(fields=['vector_id']),
        ]
        ordering = ['document', 'chunk_index']
        unique_together = [['document', 'chunk_index']]
    
    def __str__(self):
        return f"{self.document.file_name} - Chunk {self.chunk_index}"


class InternetSearchCache(BaseModel):
    """
    Caches internet search results to reduce API calls and costs.
    """
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='search_cache'
    )
    
    query = models.CharField(max_length=500)
    query_hash = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Hash of query for fast lookup"
    )
    
    # Results
    results = models.JSONField(help_text="Cached search results")
    result_count = models.IntegerField()
    
    # Metadata
    expires_at = models.DateTimeField()
    hit_count = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'bot_internet_search_cache'
        indexes = [
            models.Index(fields=['tenant', 'query_hash']),
            models.Index(fields=['expires_at']),
        ]
        unique_together = [['tenant', 'query_hash']]
    
    def __str__(self):
        return f"Cache: {self.query[:50]}"


class RAGRetrievalLog(BaseModel):
    """
    Logs RAG retrieval operations for analytics and debugging.
    """
    SOURCE_CHOICES = [
        ('document', 'Document'),
        ('database', 'Database'),
        ('internet', 'Internet'),
    ]
    
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='rag_logs'
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='rag_logs',
        blank=True,
        null=True
    )
    
    query = models.TextField()
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    
    # Results
    result_count = models.IntegerField()
    results = models.JSONField(help_text="Retrieved results with scores")
    
    # Performance
    retrieval_time_ms = models.IntegerField(help_text="Time taken in milliseconds")
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True, null=True)
    
    # Costs
    embedding_tokens = models.IntegerField(default=0)
    estimated_cost = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=0
    )
    
    class Meta:
        db_table = 'bot_rag_retrieval_logs'
        indexes = [
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['source', 'success']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"RAG {self.source}: {self.query[:50]}"
