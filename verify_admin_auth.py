#!/usr/bin/env python
"""
Verification script for Django admin authentication fix.

Tests:
1. Custom User model is configured
2. Superuser can be created
3. Authentication backend works
4. User has correct permissions
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.rbac.backends import EmailAuthBackend

User = get_user_model()

def test_user_model():
    """Test that custom User model is configured."""
    print("1. Testing User Model Configuration...")
    assert User.__module__ == 'apps.rbac.models', f"❌ Wrong module: {User.__module__}"
    assert User.__name__ == 'User', f"❌ Wrong name: {User.__name__}"
    assert User.USERNAME_FIELD == 'email', f"❌ Wrong USERNAME_FIELD: {User.USERNAME_FIELD}"
    print("   ✅ Custom User model configured correctly")
    return True

def test_create_superuser():
    """Test creating a superuser."""
    print("\n2. Testing Superuser Creation...")
    
    # Clean up any existing test user
    User.objects.filter(email='test-admin@wabotiq.test').delete()
    
    user = User.objects.create_superuser(
        email='test-admin@wabotiq.test',
        password='testpass123'
    )
    
    assert user.email == 'test-admin@wabotiq.test', "❌ Email mismatch"
    assert user.is_superuser is True, "❌ Not superuser"
    assert user.is_active is True, "❌ Not active"
    assert user.is_staff is True, "❌ Not staff"
    assert user.email_verified is True, "❌ Email not verified"
    
    print(f"   ✅ Superuser created: {user.email}")
    print(f"   ✅ is_superuser: {user.is_superuser}")
    print(f"   ✅ is_staff: {user.is_staff}")
    print(f"   ✅ is_active: {user.is_active}")
    
    return user

def test_authentication(user):
    """Test email authentication backend."""
    print("\n3. Testing Authentication Backend...")
    
    backend = EmailAuthBackend()
    
    # Test successful authentication
    authenticated_user = backend.authenticate(
        None,
        username='test-admin@wabotiq.test',
        password='testpass123'
    )
    
    assert authenticated_user is not None, "❌ Authentication failed"
    assert authenticated_user.email == user.email, "❌ Wrong user returned"
    print(f"   ✅ Authentication successful: {authenticated_user.email}")
    
    # Test wrong password
    wrong_auth = backend.authenticate(
        None,
        username='test-admin@wabotiq.test',
        password='wrongpassword'
    )
    assert wrong_auth is None, "❌ Should fail with wrong password"
    print("   ✅ Wrong password correctly rejected")
    
    # Test get_user
    retrieved_user = backend.get_user(user.id)
    assert retrieved_user is not None, "❌ get_user failed"
    assert retrieved_user.id == user.id, "❌ Wrong user retrieved"
    print(f"   ✅ get_user works: {retrieved_user.email}")
    
    return True

def test_permissions(user):
    """Test Django admin permissions."""
    print("\n4. Testing Django Admin Permissions...")
    
    assert user.has_perm('any.permission') is True, "❌ Superuser should have all perms"
    assert user.has_perms(['perm1', 'perm2']) is True, "❌ Superuser should have all perms"
    assert user.has_module_perms('any_app') is True, "❌ Superuser should have module perms"
    
    print("   ✅ has_perm: True")
    print("   ✅ has_perms: True")
    print("   ✅ has_module_perms: True")
    
    # Test authentication properties
    assert user.is_authenticated is True, "❌ Should be authenticated"
    assert user.is_anonymous is False, "❌ Should not be anonymous"
    
    print("   ✅ is_authenticated: True")
    print("   ✅ is_anonymous: False")
    
    return True

def test_natural_key(user):
    """Test natural key methods."""
    print("\n5. Testing Natural Key Methods...")
    
    natural_key = user.natural_key()
    assert natural_key == ('test-admin@wabotiq.test',), f"❌ Wrong natural key: {natural_key}"
    print(f"   ✅ natural_key: {natural_key}")
    
    retrieved_user = User.objects.get_by_natural_key('test-admin@wabotiq.test')
    assert retrieved_user.id == user.id, "❌ get_by_natural_key failed"
    print(f"   ✅ get_by_natural_key: {retrieved_user.email}")
    
    return True

def cleanup():
    """Clean up test data."""
    print("\n6. Cleaning Up...")
    User.objects.filter(email='test-admin@wabotiq.test').delete()
    print("   ✅ Test user deleted")

def main():
    """Run all tests."""
    print("=" * 60)
    print("Django Admin Authentication Verification")
    print("=" * 60)
    
    try:
        test_user_model()
        user = test_create_superuser()
        test_authentication(user)
        test_permissions(user)
        test_natural_key(user)
        cleanup()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print("\nDjango admin authentication is working correctly.")
        print("\nTo access Django admin:")
        print("1. Create a superuser: python manage.py shell")
        print("   >>> from apps.rbac.models import User")
        print("   >>> User.objects.create_superuser('admin@example.com', 'password')")
        print("2. Start server: python manage.py runserver")
        print("3. Navigate to: http://localhost:8000/admin/")
        print("4. Login with your superuser credentials")
        print("=" * 60)
        
        return 0
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        cleanup()
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        cleanup()
        return 1

if __name__ == '__main__':
    sys.exit(main())
