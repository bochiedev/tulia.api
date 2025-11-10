"""
Tests for core models.
"""
from django.test import TestCase
from apps.core.models import BaseModel
from django.db import models


class DummyModel(BaseModel):
    """Test model for BaseModel functionality."""
    name = models.CharField(max_length=100)
    
    class Meta:
        app_label = 'core'


class TestBaseModel(TestCase):
    """Test BaseModel functionality."""
    
    def test_uuid_primary_key(self):
        """Test that BaseModel uses UUID as primary key."""
        obj = DummyModel.objects.create(name="Test")
        self.assertIsNotNone(obj.id)
        self.assertEqual(len(str(obj.id)), 36)  # UUID format
    
    def test_timestamps(self):
        """Test that created_at and updated_at are set automatically."""
        obj = DummyModel.objects.create(name="Test")
        self.assertIsNotNone(obj.created_at)
        self.assertIsNotNone(obj.updated_at)
        self.assertLessEqual(obj.created_at, obj.updated_at)
    
    def test_soft_delete(self):
        """Test soft delete functionality."""
        obj = DummyModel.objects.create(name="Test")
        obj_id = obj.id
        
        # Soft delete
        obj.delete()
        
        # Should not be in default queryset
        self.assertFalse(DummyModel.objects.filter(id=obj_id).exists())
        
        # Should be in with_deleted queryset
        self.assertTrue(DummyModel.objects_with_deleted.filter(id=obj_id).exists())
        
        # Should have deleted_at timestamp
        obj_deleted = DummyModel.objects_with_deleted.get(id=obj_id)
        self.assertIsNotNone(obj_deleted.deleted_at)
        self.assertTrue(obj_deleted.is_deleted)
    
    def test_restore(self):
        """Test restoring a soft-deleted object."""
        obj = DummyModel.objects.create(name="Test")
        obj_id = obj.id
        
        # Soft delete
        obj.delete()
        self.assertFalse(DummyModel.objects.filter(id=obj_id).exists())
        
        # Restore
        obj_deleted = DummyModel.objects_with_deleted.get(id=obj_id)
        obj_deleted.restore()
        
        # Should be back in default queryset
        self.assertTrue(DummyModel.objects.filter(id=obj_id).exists())
        obj_restored = DummyModel.objects.get(id=obj_id)
        self.assertIsNone(obj_restored.deleted_at)
        self.assertFalse(obj_restored.is_deleted)
    
    def test_hard_delete(self):
        """Test permanent deletion."""
        obj = DummyModel.objects.create(name="Test")
        obj_id = obj.id
        
        # Hard delete
        obj.hard_delete()
        
        # Should not exist in any queryset
        self.assertFalse(DummyModel.objects.filter(id=obj_id).exists())
        self.assertFalse(DummyModel.objects_with_deleted.filter(id=obj_id).exists())
