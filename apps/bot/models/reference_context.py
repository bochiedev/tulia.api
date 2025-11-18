"""
Reference context model for storing list contexts.
"""
from django.db import models
from apps.core.models import BaseModel


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
