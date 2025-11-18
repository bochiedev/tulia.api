#!/usr/bin/env python3
"""
Generate a secure encryption key for the ENCRYPTION_KEY setting.

This script generates a cryptographically secure 32-byte (256-bit) key
suitable for AES-256-GCM encryption.

Usage:
    python scripts/generate_encryption_key.py

The generated key will be base64-encoded and can be directly used in .env:
    ENCRYPTION_KEY=<generated_key>
"""
import os
import base64


def generate_encryption_key() -> str:
    """
    Generate a secure 32-byte encryption key.
    
    Returns:
        str: Base64-encoded 32-byte key
    """
    # Generate 32 random bytes (256 bits)
    key_bytes = os.urandom(32)
    
    # Encode as base64 for storage in .env
    key_b64 = base64.b64encode(key_bytes).decode('utf-8')
    
    return key_b64


def main():
    """Generate and display encryption key."""
    print("=" * 80)
    print("Encryption Key Generator")
    print("=" * 80)
    print()
    print("Generating secure 32-byte (256-bit) encryption key...")
    print()
    
    key = generate_encryption_key()
    
    print("Generated Key:")
    print("-" * 80)
    print(key)
    print("-" * 80)
    print()
    print("Add this to your .env file:")
    print(f"ENCRYPTION_KEY={key}")
    print()
    print("IMPORTANT:")
    print("- Store this key securely")
    print("- NEVER commit it to version control")
    print("- Use different keys for different environments")
    print("- Keep a backup in a secure location")
    print()
    print("For key rotation:")
    print("1. Generate a new key with this script")
    print("2. Add the old key to ENCRYPTION_OLD_KEYS in .env:")
    print(f"   ENCRYPTION_OLD_KEYS={key}")
    print("3. Set the new key as ENCRYPTION_KEY")
    print("4. Re-encrypt data with the new key (optional)")
    print("5. Remove old key from ENCRYPTION_OLD_KEYS once all data is re-encrypted")
    print()


if __name__ == '__main__':
    main()
