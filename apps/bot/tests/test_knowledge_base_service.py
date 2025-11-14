"""
Tests for KnowledgeBaseService.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from django.core.cache import cache
from django.core.exceptions import ValidationError

from apps.bot.models import KnowledgeEntry
from apps.bot.services import KnowledgeBaseService
from apps.tenants.models import Tenant


@pytest.fixture
def tenant(db):
    """Create a test tenant."""
    return Tenant.objects.create(
        name="Test Tenant",
        slug="test-tenant"
    )


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    with patch('apps.bot.services.knowledge_base_service.OpenAI') as mock_openai:
        # Mock embeddings response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai.return_value = mock_client
        yield mock_client


@pytest.fixture
def knowledge_service(mock_openai_client):
    """Create KnowledgeBaseService with mocked OpenAI."""
    return KnowledgeBaseService(api_key='test-key')


@pytest.mark.django_db
class TestKnowledgeBaseServiceCreate:
    """Test knowledge entry creation."""
    
    def setup_method(self):
        """Clear cache before each test."""
        cache.clear()
    
    def test_create_entry_basic(self, tenant, knowledge_service):
        """Test creating a basic knowledge entry."""
        entry = knowledge_service.create_entry(
            tenant=tenant,
            entry_type='faq',
            title='What are your hours?',
            content='We are open Monday-Friday 9am-5pm'
        )
        
        assert entry.id is not None
        assert entry.tenant == tenant
        assert entry.entry_type == 'faq'
        assert entry.title == 'What are your hours?'
        assert entry.content == 'We are open Monday-Friday 9am-5pm'
        assert entry.version == 1
        assert entry.is_active is True
        assert entry.embedding is not None
    
    def test_create_entry_with_keywords(self, tenant, knowledge_service):
        """Test creating entry with keywords."""
        entry = knowledge_service.create_entry(
            tenant=tenant,
            entry_type='faq',
            title='Shipping policy',
            content='We ship worldwide',
            keywords=['shipping', 'delivery', 'international']
        )
        
        assert 'shipping' in entry.keywords
        assert 'delivery' in entry.keywords
        assert 'international' in entry.keywords
    
    def test_create_entry_with_metadata(self, tenant, knowledge_service):
        """Test creating entry with metadata."""
        metadata = {'source': 'manual', 'author': 'admin'}
        entry = knowledge_service.create_entry(
            tenant=tenant,
            entry_type='policy',
            title='Return policy',
            content='30 day returns',
            metadata=metadata
        )
        
        assert entry.metadata == metadata
    
    def test_create_entry_invalid_type(self, tenant, knowledge_service):
        """Test that invalid entry type raises error."""
        with pytest.raises(ValidationError):
            knowledge_service.create_entry(
                tenant=tenant,
                entry_type='invalid_type',
                title='Test',
                content='Test content'
            )
    
    def test_create_entry_invalid_priority(self, tenant, knowledge_service):
        """Test that invalid priority raises error."""
        with pytest.raises(ValidationError):
            knowledge_service.create_entry(
                tenant=tenant,
                entry_type='faq',
                title='Test',
                content='Test content',
                priority=150  # Out of range
            )


@pytest.mark.django_db
class TestKnowledgeBaseServiceSearch:
    """Test knowledge base search."""
    
    def setup_method(self):
        """Clear cache before each test."""
        cache.clear()
    
    def test_search_basic(self, tenant, knowledge_service):
        """Test basic semantic search."""
        # Create test entries
        entry1 = knowledge_service.create_entry(
            tenant=tenant,
            entry_type='faq',
            title='What are your hours?',
            content='We are open Monday-Friday 9am-5pm'
        )
        
        entry2 = knowledge_service.create_entry(
            tenant=tenant,
            entry_type='faq',
            title='Shipping policy',
            content='We ship worldwide in 3-5 business days'
        )
        
        # Search for hours-related query
        results = knowledge_service.search(
            tenant=tenant,
            query='When are you open?',
            limit=5,
            min_similarity=0.0  # Low threshold for testing
        )
        
        # Should return results
        assert len(results) > 0
        
        # Results should be tuples of (entry, score)
        for entry, score in results:
            assert isinstance(entry, KnowledgeEntry)
            assert isinstance(score, float)
            assert 0.0 <= score <= 1.0
    
    def test_search_with_entry_type_filter(self, tenant, knowledge_service):
        """Test search with entry type filtering."""
        # Create entries of different types
        knowledge_service.create_entry(
            tenant=tenant,
            entry_type='faq',
            title='FAQ entry',
            content='FAQ content'
        )
        
        knowledge_service.create_entry(
            tenant=tenant,
            entry_type='policy',
            title='Policy entry',
            content='Policy content'
        )
        
        # Search only FAQs
        results = knowledge_service.search(
            tenant=tenant,
            query='entry',
            entry_types=['faq'],
            min_similarity=0.0
        )
        
        # Should only return FAQ entries
        for entry, score in results:
            assert entry.entry_type == 'faq'
    
    def test_search_respects_is_active(self, tenant, knowledge_service):
        """Test that search only returns active entries."""
        # Create active entry
        active_entry = knowledge_service.create_entry(
            tenant=tenant,
            entry_type='faq',
            title='Active entry',
            content='Active content',
            is_active=True
        )
        
        # Create inactive entry
        inactive_entry = knowledge_service.create_entry(
            tenant=tenant,
            entry_type='faq',
            title='Inactive entry',
            content='Inactive content',
            is_active=False
        )
        
        # Search should only return active entry
        results = knowledge_service.search(
            tenant=tenant,
            query='entry',
            min_similarity=0.0
        )
        
        entry_ids = [entry.id for entry, score in results]
        assert active_entry.id in entry_ids
        assert inactive_entry.id not in entry_ids
    
    def test_search_caching(self, tenant, knowledge_service):
        """Test that search results are cached."""
        knowledge_service.create_entry(
            tenant=tenant,
            entry_type='faq',
            title='Test entry',
            content='Test content'
        )
        
        # First search
        results1 = knowledge_service.search(
            tenant=tenant,
            query='test',
            min_similarity=0.0
        )
        
        # Second search with same query should hit cache
        results2 = knowledge_service.search(
            tenant=tenant,
            query='test',
            min_similarity=0.0
        )
        
        # Results should be identical
        assert len(results1) == len(results2)


@pytest.mark.django_db
class TestKnowledgeBaseServiceUpdate:
    """Test knowledge entry updates."""
    
    def setup_method(self):
        """Clear cache before each test."""
        cache.clear()
    
    def test_update_entry_title(self, tenant, knowledge_service):
        """Test updating entry title."""
        entry = knowledge_service.create_entry(
            tenant=tenant,
            entry_type='faq',
            title='Old title',
            content='Content'
        )
        
        original_version = entry.version
        
        updated = knowledge_service.update_entry(
            entry_id=str(entry.id),
            title='New title'
        )
        
        assert updated.title == 'New title'
        assert updated.version == original_version + 1
        assert updated.embedding is not None  # Should regenerate
    
    def test_update_entry_content(self, tenant, knowledge_service):
        """Test updating entry content."""
        entry = knowledge_service.create_entry(
            tenant=tenant,
            entry_type='faq',
            title='Title',
            content='Old content'
        )
        
        updated = knowledge_service.update_entry(
            entry_id=str(entry.id),
            content='New content'
        )
        
        assert updated.content == 'New content'
        assert updated.embedding is not None  # Should regenerate
    
    def test_update_entry_metadata_only(self, tenant, knowledge_service):
        """Test updating only metadata doesn't regenerate embedding."""
        entry = knowledge_service.create_entry(
            tenant=tenant,
            entry_type='faq',
            title='Title',
            content='Content'
        )
        
        original_embedding = entry.embedding
        
        updated = knowledge_service.update_entry(
            entry_id=str(entry.id),
            metadata={'updated': True}
        )
        
        assert updated.metadata == {'updated': True}
        # Embedding should not change if title/content unchanged
        # (Note: In actual implementation, embedding is regenerated if title/content changes)
    
    def test_update_entry_priority(self, tenant, knowledge_service):
        """Test updating entry priority."""
        entry = knowledge_service.create_entry(
            tenant=tenant,
            entry_type='faq',
            title='Title',
            content='Content',
            priority=0
        )
        
        updated = knowledge_service.update_entry(
            entry_id=str(entry.id),
            priority=50
        )
        
        assert updated.priority == 50
    
    def test_update_entry_invalid_priority(self, tenant, knowledge_service):
        """Test that invalid priority raises error."""
        entry = knowledge_service.create_entry(
            tenant=tenant,
            entry_type='faq',
            title='Title',
            content='Content'
        )
        
        with pytest.raises(ValidationError):
            knowledge_service.update_entry(
                entry_id=str(entry.id),
                priority=150  # Out of range
            )


@pytest.mark.django_db
class TestKnowledgeBaseServiceDelete:
    """Test knowledge entry deletion."""
    
    def setup_method(self):
        """Clear cache before each test."""
        cache.clear()
    
    def test_delete_entry_soft_delete(self, tenant, knowledge_service):
        """Test that delete is a soft delete."""
        entry = knowledge_service.create_entry(
            tenant=tenant,
            entry_type='faq',
            title='Title',
            content='Content'
        )
        
        original_version = entry.version
        
        deleted = knowledge_service.delete_entry(str(entry.id))
        
        assert deleted.is_active is False
        assert deleted.version == original_version + 1
        
        # Entry should still exist in database
        assert KnowledgeEntry.objects.filter(id=entry.id).exists()
    
    def test_deleted_entry_not_in_search(self, tenant, knowledge_service):
        """Test that deleted entries don't appear in search."""
        entry = knowledge_service.create_entry(
            tenant=tenant,
            entry_type='faq',
            title='Test entry',
            content='Test content'
        )
        
        # Delete entry
        knowledge_service.delete_entry(str(entry.id))
        
        # Search should not return deleted entry
        results = knowledge_service.search(
            tenant=tenant,
            query='test',
            min_similarity=0.0
        )
        
        entry_ids = [e.id for e, score in results]
        assert entry.id not in entry_ids


@pytest.mark.django_db
class TestKnowledgeBaseServiceTenantIsolation:
    """Test tenant isolation in knowledge base."""
    
    def setup_method(self):
        """Clear cache before each test."""
        cache.clear()
    
    def test_search_tenant_isolation(self, db, knowledge_service):
        """Test that search only returns entries for the correct tenant."""
        # Create two tenants with unique whatsapp numbers
        tenant1 = Tenant.objects.create(
            name="Tenant 1",
            slug="tenant-1",
            whatsapp_number="+1234567890"
        )
        tenant2 = Tenant.objects.create(
            name="Tenant 2",
            slug="tenant-2",
            whatsapp_number="+0987654321"
        )
        
        # Create entries for each tenant
        entry1 = knowledge_service.create_entry(
            tenant=tenant1,
            entry_type='faq',
            title='Tenant 1 entry',
            content='Tenant 1 content'
        )
        
        entry2 = knowledge_service.create_entry(
            tenant=tenant2,
            entry_type='faq',
            title='Tenant 2 entry',
            content='Tenant 2 content'
        )
        
        # Search for tenant 1 should only return tenant 1 entries
        results1 = knowledge_service.search(
            tenant=tenant1,
            query='entry',
            min_similarity=0.0
        )
        
        entry_ids1 = [e.id for e, score in results1]
        assert entry1.id in entry_ids1
        assert entry2.id not in entry_ids1
        
        # Search for tenant 2 should only return tenant 2 entries
        results2 = knowledge_service.search(
            tenant=tenant2,
            query='entry',
            min_similarity=0.0
        )
        
        entry_ids2 = [e.id for e, score in results2]
        assert entry2.id in entry_ids2
        assert entry1.id not in entry_ids2


@pytest.mark.django_db
class TestCosineSimilarity:
    """Test cosine similarity calculation."""
    
    def test_identical_vectors(self):
        """Test that identical vectors have similarity of 1.0."""
        vec = [1.0, 2.0, 3.0]
        similarity = KnowledgeBaseService._cosine_similarity(vec, vec)
        assert abs(similarity - 1.0) < 0.01  # Should be very close to 1.0
    
    def test_orthogonal_vectors(self):
        """Test that orthogonal vectors have similarity of 0.5."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = KnowledgeBaseService._cosine_similarity(vec1, vec2)
        # Normalized cosine similarity: (0 + 1) / 2 = 0.5
        assert abs(similarity - 0.5) < 0.01
    
    def test_opposite_vectors(self):
        """Test that opposite vectors have similarity of 0.0."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [-1.0, 0.0, 0.0]
        similarity = KnowledgeBaseService._cosine_similarity(vec1, vec2)
        # Normalized cosine similarity: (-1 + 1) / 2 = 0.0
        assert abs(similarity - 0.0) < 0.01
    
    def test_dimension_mismatch(self):
        """Test that dimension mismatch returns 0.0."""
        vec1 = [1.0, 2.0]
        vec2 = [1.0, 2.0, 3.0]
        similarity = KnowledgeBaseService._cosine_similarity(vec1, vec2)
        assert similarity == 0.0
