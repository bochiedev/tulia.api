"""
Tests for tenant utility functions.
"""
import pytest
from django.utils import timezone
from apps.tenants.models import Tenant, SubscriptionTier
from apps.tenants.utils import (
    generate_api_key,
    hash_api_key,
    create_api_key_entry,
    add_api_key_to_tenant,
)


@pytest.fixture
def subscription_tier(db):
    """Create a test subscription tier."""
    return SubscriptionTier.objects.create(
        name="Test Tier",
        monthly_price=29.99,
        yearly_price=299.99,
    )


@pytest.fixture
def tenant(db, subscription_tier):
    """Create a test tenant."""
    return Tenant.objects.create(
        name="Test Tenant",
        slug="test-tenant",
        whatsapp_number="+1234567890",
        twilio_sid="test_sid",
        twilio_token="test_token",
        webhook_secret="test_secret",
        subscription_tier=subscription_tier,
    )


@pytest.mark.django_db
class TestAPIKeyGeneration:
    """Test API key generation and hashing."""
    
    def test_generate_api_key_returns_64_char_hex(self):
        """Test that generated API keys are 64 character hex strings."""
        key = generate_api_key()
        
        assert isinstance(key, str)
        assert len(key) == 64  # 32 bytes = 64 hex chars
        # Verify it's valid hex
        int(key, 16)
    
    def test_generate_api_key_is_unique(self):
        """Test that generated API keys are unique."""
        keys = [generate_api_key() for _ in range(100)]
        
        # All keys should be unique
        assert len(keys) == len(set(keys))
    
    def test_hash_api_key_returns_sha256(self):
        """Test that API key hashing produces SHA-256 hash."""
        key = "test_api_key_12345"
        hashed = hash_api_key(key)
        
        assert isinstance(hashed, str)
        assert len(hashed) == 64  # SHA-256 produces 64 hex chars
        # Verify it's valid hex
        int(hashed, 16)
    
    def test_hash_api_key_is_deterministic(self):
        """Test that hashing the same key produces the same hash."""
        key = "test_api_key_12345"
        
        hash1 = hash_api_key(key)
        hash2 = hash_api_key(key)
        
        assert hash1 == hash2
    
    def test_hash_api_key_different_keys_different_hashes(self):
        """Test that different keys produce different hashes."""
        key1 = "test_api_key_1"
        key2 = "test_api_key_2"
        
        hash1 = hash_api_key(key1)
        hash2 = hash_api_key(key2)
        
        assert hash1 != hash2


@pytest.mark.django_db
class TestCreateAPIKeyEntry:
    """Test API key entry creation."""
    
    def test_create_api_key_entry_returns_tuple(self):
        """Test that create_api_key_entry returns (plain_key, entry_dict)."""
        result = create_api_key_entry()
        
        assert isinstance(result, tuple)
        assert len(result) == 2
        
        plain_key, entry = result
        assert isinstance(plain_key, str)
        assert isinstance(entry, dict)
    
    def test_create_api_key_entry_has_required_fields(self):
        """Test that entry dict has all required fields."""
        plain_key, entry = create_api_key_entry(name="Test Key")
        
        assert 'key_hash' in entry
        assert 'name' in entry
        assert 'created_at' in entry
        
        assert entry['name'] == "Test Key"
        assert len(entry['key_hash']) == 64  # SHA-256 hash
    
    def test_create_api_key_entry_hash_matches_plain_key(self):
        """Test that the hash in entry matches the plain key."""
        plain_key, entry = create_api_key_entry()
        
        expected_hash = hash_api_key(plain_key)
        assert entry['key_hash'] == expected_hash
    
    def test_create_api_key_entry_default_name(self):
        """Test that default name is used when not provided."""
        plain_key, entry = create_api_key_entry()
        
        assert entry['name'] == "Default API Key"
    
    def test_create_api_key_entry_created_at_is_iso_format(self):
        """Test that created_at is in ISO format."""
        plain_key, entry = create_api_key_entry()
        
        # Should be parseable as ISO datetime
        from datetime import datetime
        datetime.fromisoformat(entry['created_at'])


@pytest.mark.django_db
class TestAddAPIKeyToTenant:
    """Test adding API keys to tenants."""
    
    def test_add_api_key_to_tenant_returns_plain_key(self, tenant):
        """Test that add_api_key_to_tenant returns the plain key."""
        plain_key = add_api_key_to_tenant(tenant, name="Test Key")
        
        assert isinstance(plain_key, str)
        assert len(plain_key) == 64
    
    def test_add_api_key_to_tenant_stores_entry(self, tenant):
        """Test that API key entry is stored in tenant.api_keys."""
        # Tenant already has 1 key from signal (Initial API Key)
        initial_count = len(tenant.api_keys)
        
        plain_key = add_api_key_to_tenant(tenant, name="Test Key")
        
        tenant.refresh_from_db()
        
        # Should have one more key now
        assert len(tenant.api_keys) == initial_count + 1
        
        # Find the new key
        new_entry = [e for e in tenant.api_keys if e['name'] == "Test Key"][0]
        
        assert new_entry['name'] == "Test Key"
        assert 'key_hash' in new_entry
        assert 'created_at' in new_entry
    
    def test_add_api_key_to_tenant_hash_is_correct(self, tenant):
        """Test that stored hash matches the plain key."""
        plain_key = add_api_key_to_tenant(tenant, name="Test Key")
        
        tenant.refresh_from_db()
        
        # Find the new key by name
        new_entry = [e for e in tenant.api_keys if e['name'] == "Test Key"][0]
        stored_hash = new_entry['key_hash']
        expected_hash = hash_api_key(plain_key)
        
        assert stored_hash == expected_hash
    
    def test_add_api_key_to_tenant_multiple_keys(self, tenant):
        """Test adding multiple API keys to the same tenant."""
        initial_count = len(tenant.api_keys)
        
        key1 = add_api_key_to_tenant(tenant, name="Key 1")
        key2 = add_api_key_to_tenant(tenant, name="Key 2")
        key3 = add_api_key_to_tenant(tenant, name="Key 3")
        
        tenant.refresh_from_db()
        
        # Should have 3 more keys
        assert len(tenant.api_keys) == initial_count + 3
        assert key1 != key2 != key3
        
        names = [entry['name'] for entry in tenant.api_keys]
        assert "Key 1" in names
        assert "Key 2" in names
        assert "Key 3" in names
    
    def test_add_api_key_to_tenant_with_signal_generated_key(self, subscription_tier):
        """Test that signal-generated initial key exists and new keys are added."""
        # Create tenant - signal will auto-generate an initial API key
        tenant = Tenant.objects.create(
            name="Test Tenant Signal",
            slug="test-tenant-signal",
            whatsapp_number="+1234567891",
            twilio_sid="test_sid",
            twilio_token="test_token",
            webhook_secret="test_secret",
            subscription_tier=subscription_tier,
        )
        
        tenant.refresh_from_db()
        
        # Should have initial key from signal
        assert tenant.api_keys is not None
        assert len(tenant.api_keys) == 1
        assert tenant.api_keys[0]['name'] == "Initial API Key"
        
        # Add another key
        plain_key = add_api_key_to_tenant(tenant, name="Second Key")
        tenant.refresh_from_db()
        
        # Should now have 2 keys
        assert len(tenant.api_keys) == 2
        names = [e['name'] for e in tenant.api_keys]
        assert "Initial API Key" in names
        assert "Second Key" in names
    
    def test_add_api_key_to_tenant_preserves_existing_keys(self, tenant):
        """Test that adding a new key preserves existing keys."""
        initial_count = len(tenant.api_keys)
        
        # Add first key
        key1 = add_api_key_to_tenant(tenant, name="Key 1")
        tenant.refresh_from_db()
        
        # Add second key
        key2 = add_api_key_to_tenant(tenant, name="Key 2")
        tenant.refresh_from_db()
        
        # Should have initial + 2 new keys
        assert len(tenant.api_keys) == initial_count + 2
        
        # Verify first key is still valid
        hash1 = hash_api_key(key1)
        hashes = [entry['key_hash'] for entry in tenant.api_keys]
        assert hash1 in hashes


@pytest.mark.django_db
class TestAPIKeyIntegrationWithMiddleware:
    """Test that generated API keys work with middleware validation."""
    
    def test_generated_key_validates_in_middleware_style(self, tenant):
        """Test that generated keys can be validated using middleware logic."""
        # Generate and add key
        plain_key = add_api_key_to_tenant(tenant, name="Test Key")
        tenant.refresh_from_db()
        
        # Simulate middleware validation
        api_key_hash = hash_api_key(plain_key)
        
        # Check if hash matches any stored key (middleware logic)
        is_valid = False
        for key_entry in tenant.api_keys:
            if key_entry.get('key_hash') == api_key_hash:
                is_valid = True
                break
        
        assert is_valid
    
    def test_wrong_key_does_not_validate(self, tenant):
        """Test that wrong keys don't validate."""
        # Generate and add key
        plain_key = add_api_key_to_tenant(tenant, name="Test Key")
        tenant.refresh_from_db()
        
        # Try with wrong key
        wrong_key = "wrong_key_12345"
        wrong_hash = hash_api_key(wrong_key)
        
        # Check if hash matches any stored key
        is_valid = False
        for key_entry in tenant.api_keys:
            if key_entry.get('key_hash') == wrong_hash:
                is_valid = True
                break
        
        assert not is_valid
