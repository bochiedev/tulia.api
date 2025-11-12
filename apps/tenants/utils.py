"""
Utility functions for tenant management.

This module provides secure API key generation and management for tenants.

Key Features:
- Cryptographically secure random key generation using secrets module
- SHA-256 hashing for secure storage
- Integration with TenantContextMiddleware for authentication
- Automatic initial key generation via post_save signal (see signals.py)

Security Notes:
- API keys are 64-character hexadecimal strings (32 bytes)
- Keys are hashed with SHA-256 before storage
- Plain keys are only returned once during generation
- Middleware validates requests by comparing hashed keys
"""
import hashlib
import secrets
from datetime import datetime
from django.utils import timezone


def generate_api_key():
    """
    Generate a secure random API key.
    
    Returns:
        str: A 32-character hexadecimal API key
    """
    return secrets.token_hex(32)


def hash_api_key(api_key):
    """
    Hash an API key using SHA-256.
    
    Args:
        api_key (str): The plain text API key
        
    Returns:
        str: The SHA-256 hash of the API key
    """
    return hashlib.sha256(api_key.encode('utf-8')).hexdigest()


def create_api_key_entry(name="Default API Key"):
    """
    Create a new API key entry with hash and metadata.
    
    Args:
        name (str): Human-readable name for the API key
        
    Returns:
        tuple: (plain_api_key, api_key_entry_dict)
            - plain_api_key: The unhashed API key (show this to user ONCE)
            - api_key_entry_dict: The entry to store in tenant.api_keys
    """
    plain_key = generate_api_key()
    key_hash = hash_api_key(plain_key)
    
    entry = {
        'key_hash': key_hash,
        'name': name,
        'created_at': timezone.now().isoformat(),
    }
    
    return plain_key, entry


def add_api_key_to_tenant(tenant, name="API Key"):
    """
    Generate and add a new API key to a tenant.
    
    Args:
        tenant: The Tenant instance
        name (str): Human-readable name for the API key
        
    Returns:
        str: The plain text API key (show this to user ONCE)
    """
    plain_key, entry = create_api_key_entry(name)
    
    if tenant.api_keys is None:
        tenant.api_keys = []
    
    tenant.api_keys.append(entry)
    tenant.save(update_fields=['api_keys'])
    
    return plain_key
