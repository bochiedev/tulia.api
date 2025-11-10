"""
Core models for Tulia AI.
Provides BaseModel with UUID primary keys, soft delete, and timestamp fields.
"""
import uuid
from django.db import models
from django.utils import timezone


class BaseModelManager(models.Manager):
    """Manager that excludes soft-deleted objects by default."""
    
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class BaseModelQuerySet(models.QuerySet):
    """QuerySet with soft delete support."""
    
    def delete(self):
        """Soft delete all objects in queryset."""
        return self.update(deleted_at=timezone.now())
    
    def hard_delete(self):
        """Permanently delete all objects in queryset."""
        return super().delete()
    
    def with_deleted(self):
        """Include soft-deleted objects."""
        return self.model.objects_with_deleted.all()


class BaseModel(models.Model):
    """
    Abstract base model with UUID primary key, soft delete, and timestamps.
    
    All models in Tulia should inherit from this base model to ensure
    consistent behavior across the platform.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when the record was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        db_index=True,
        help_text="Timestamp when the record was last updated"
    )
    
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Timestamp when the record was soft deleted"
    )
    
    # Default manager excludes soft-deleted objects
    objects = BaseModelManager.from_queryset(BaseModelQuerySet)()
    
    # Manager that includes soft-deleted objects
    objects_with_deleted = models.Manager.from_queryset(BaseModelQuerySet)()
    
    class Meta:
        abstract = True
        ordering = ['-created_at']
    
    def delete(self, using=None, keep_parents=False):
        """Soft delete the object."""
        self.deleted_at = timezone.now()
        self.save(using=using)
    
    def hard_delete(self, using=None, keep_parents=False):
        """Permanently delete the object."""
        super().delete(using=using, keep_parents=keep_parents)
    
    def restore(self):
        """Restore a soft-deleted object."""
        self.deleted_at = None
        self.save()
    
    @property
    def is_deleted(self):
        """Check if the object is soft deleted."""
        return self.deleted_at is not None
