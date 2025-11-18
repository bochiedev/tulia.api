"""
Product analysis model for caching AI analysis.
"""
from django.db import models
from apps.core.models import BaseModel


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
        indexes = [
            models.Index(fields=['product']),
            models.Index(fields=['analyzed_at']),
        ]
    
    def __str__(self):
        return f"ProductAnalysis({self.product.name})"
