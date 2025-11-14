#!/usr/bin/env python
"""
Manual test script for /v1/auth/me endpoint.

Run this after starting the development server:
python manage.py runserver

Then in another terminal:
python test_me_endpoint.py
"""
import requests
import json

# Configuration
BASE_URL = "http://localhost:8000"

# Test credentials (use existing user or create one)
EMAIL = "owner@starter.demo"
PASSWORD = "password123"

def test_me_endpoint():
    """Test the /v1/auth/me endpoint."""
    
    print("=" * 80)
    print("Testing /v1/auth/me Endpoint")
    print("=" * 80)
    
    # Step 1: Login to get JWT token
    print("\n1. Logging in...")
    login_response = requests.post(
        f"{BASE_URL}/v1/auth/login",
        json={
            "email": EMAIL,
            "password": PASSWORD
        }
    )
    
    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.status_code}")
        print(login_response.text)
        return
    
    login_data = login_response.json()
    token = login_data.get('token')
    print(f"✅ Login successful")
    print(f"   Token: {token[:50]}...")
    
    # Step 2: Call /v1/auth/me endpoint
    print("\n2. Calling /v1/auth/me...")
    me_response = requests.get(
        f"{BASE_URL}/v1/auth/me",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )
    
    if me_response.status_code != 200:
        print(f"❌ /v1/auth/me failed: {me_response.status_code}")
        print(me_response.text)
        return
    
    me_data = me_response.json()
    print(f"✅ /v1/auth/me successful")
    print("\n" + "=" * 80)
    print("USER PROFILE DATA:")
    print("=" * 80)
    print(json.dumps(me_data, indent=2))
    
    # Verify expected fields
    print("\n" + "=" * 80)
    print("VERIFICATION:")
    print("=" * 80)
    
    expected_fields = [
        'id', 'email', 'first_name', 'last_name', 'full_name',
        'phone', 'is_active', 'is_superuser', 'email_verified',
        'two_factor_enabled', 'tenants', 'total_tenants', 'pending_invites'
    ]
    
    for field in expected_fields:
        if field in me_data:
            print(f"✅ {field}: {me_data[field] if field not in ['tenants', 'pending_invites'] else f'{len(me_data[field])} items'}")
        else:
            print(f"❌ Missing field: {field}")
    
    # Check tenants structure
    if 'tenants' in me_data and len(me_data['tenants']) > 0:
        print("\n" + "=" * 80)
        print("TENANT DETAILS:")
        print("=" * 80)
        for i, tenant in enumerate(me_data['tenants'], 1):
            print(f"\nTenant {i}:")
            print(f"  Name: {tenant.get('tenant', {}).get('name')}")
            print(f"  Slug: {tenant.get('tenant', {}).get('slug')}")
            print(f"  Status: {tenant.get('tenant', {}).get('status')}")
            print(f"  Roles: {[r.get('name') for r in tenant.get('roles', [])]}")
            print(f"  Scopes: {len(tenant.get('scopes', []))} permissions")
            if tenant.get('scopes'):
                print(f"    Sample scopes: {', '.join(tenant['scopes'][:5])}")
    
    print("\n" + "=" * 80)
    print("✅ TEST COMPLETED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    try:
        test_me_endpoint()
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure the development server is running:")
        print("   python manage.py runserver")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
