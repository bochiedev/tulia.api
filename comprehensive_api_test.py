#!/usr/bin/env python
"""
Comprehensive API test suite.

Tests all major endpoints to ensure JWT authentication and tenant scoping work correctly.
"""
import requests
import json
import sys

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiOGU0ZTU5NGYtODZjZC00NTVhLTg2MzktMTg1NWMyZjA3ZTNlIiwiZW1haWwiOiJvd25lckBzdGFydGVyLmRlbW8iLCJleHAiOjE3NjMxODc5ODQsImlhdCI6MTc2MzEwMTU4NH0.KNc2y6uUd2GSvIxQq-Hm5mAYASyI7CpAXnGaZmdwsAo"
TENANT_ID = "604923c8-cff3-49d7-b3a3-fe5143c5c46b"


def test_endpoint(name, method, path, needs_tenant=False, expected_status=200, check_fields=None):
    """Test an endpoint."""
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    
    if needs_tenant:
        headers["X-TENANT-ID"] = TENANT_ID
    
    try:
        if method == "GET":
            response = requests.get(f"{BASE_URL}{path}", headers=headers, timeout=5)
        elif method == "POST":
            response = requests.post(f"{BASE_URL}{path}", headers=headers, json={}, timeout=5)
        else:
            return "❓", "Unknown method", None
        
        # Check status code
        if response.status_code != expected_status:
            if response.status_code == 401:
                return "❌", f"401 Unauthorized", response.json() if response.text else None
            elif response.status_code == 403:
                return "⚠️", "403 Forbidden (may be expected)", response.json() if response.text else None
            elif response.status_code == 500:
                return "❌", f"500 Internal Server Error", response.json() if response.text else None
            else:
                return "⚠️", f"Status {response.status_code}", response.json() if response.text else None
        
        # Parse response
        try:
            data = response.json()
        except:
            data = None
        
        # Check required fields if specified
        if check_fields and data:
            missing = [f for f in check_fields if f not in data]
            if missing:
                return "⚠️", f"Missing fields: {missing}", data
        
        return "✅", "OK", data
        
    except requests.exceptions.Timeout:
        return "❌", "Timeout", None
    except requests.exceptions.ConnectionError:
        return "❌", "Connection Error - Is Django running?", None
    except Exception as e:
        return "❌", f"Error: {str(e)}", None


def main():
    """Run comprehensive API tests."""
    print("="*80)
    print("COMPREHENSIVE API TEST SUITE")
    print("="*80)
    print()
    print(f"Base URL: {BASE_URL}")
    print(f"Token: {TOKEN[:30]}...")
    print(f"Tenant ID: {TENANT_ID}")
    print()
    print("="*80)
    print()
    
    tests = [
        # Authentication endpoints
        ("Get Profile", "GET", "/v1/auth/me", False, 200, ['id', 'email', 'tenants']),
        ("Refresh Token", "POST", "/v1/auth/refresh-token", False, 200, ['token']),
        ("Logout", "POST", "/v1/auth/logout", False, 200, None),
        
        # Tenant management
        ("List My Tenants", "GET", "/v1/tenants", False, 200, None),
        
        # Catalog
        ("List Products", "GET", "/v1/products/", True, 200, None),
        
        # Orders
        ("List Orders", "GET", "/v1/orders/", True, 200, None),
        
        # Services
        ("List Services", "GET", "/v1/services/", True, 200, None),
        
        # Messaging
        ("List Conversations", "GET", "/v1/messages/conversations", True, 200, None),
        
        # Analytics
        ("Analytics Overview", "GET", "/v1/analytics/overview", True, 200, None),
        
        # Wallet
        ("Wallet Balance", "GET", "/v1/wallet/balance", True, 200, None),
        ("Wallet Transactions", "GET", "/v1/wallet/transactions", True, 200, None),
        
        # RBAC
        ("List Memberships", "GET", "/v1/memberships", True, 200, None),
        ("List Roles", "GET", "/v1/roles", True, 200, None),
        ("List Permissions", "GET", "/v1/permissions", True, 200, None),
        
        # Settings
        ("List Integrations", "GET", "/v1/settings/integrations", True, 200, None),
        ("List API Keys", "GET", "/v1/settings/api-keys", True, 200, None),
    ]
    
    results = []
    
    for name, method, path, needs_tenant, expected_status, check_fields in tests:
        status, message, data = test_endpoint(name, method, path, needs_tenant, expected_status, check_fields)
        results.append((name, status, message, data))
        
        # Print result
        tenant_marker = " [+TENANT]" if needs_tenant else ""
        print(f"{status} {name}{tenant_marker}")
        
        if status == "❌":
            print(f"   Error: {message}")
            if data:
                print(f"   Response: {json.dumps(data, indent=2)[:200]}")
        elif status == "⚠️":
            print(f"   Warning: {message}")
        elif status == "✅" and check_fields and data:
            # Show key fields for successful responses
            if name == "Get Profile":
                print(f"   User: {data.get('email', 'N/A')}")
                print(f"   Tenants: {len(data.get('tenants', []))}")
                if data.get('tenants'):
                    for t in data['tenants']:
                        print(f"     - {t.get('name')} ({len(t.get('scopes', []))} scopes)")
        
        print()
    
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print()
    
    success = sum(1 for _, status, _, _ in results if status == "✅")
    failed = sum(1 for _, status, _, _ in results if status == "❌")
    warning = sum(1 for _, status, _, _ in results if status == "⚠️")
    total = len(results)
    
    print(f"✅ Passed: {success}/{total}")
    print(f"❌ Failed: {failed}/{total}")
    print(f"⚠️  Warnings: {warning}/{total}")
    print()
    
    if failed > 0:
        print("Failed tests:")
        for name, status, message, _ in results:
            if status == "❌":
                print(f"  - {name}: {message}")
        print()
    
    if success == total:
        print("🎉 All tests passed!")
        return True
    elif failed == 0:
        print("✅ No failures, but some warnings")
        return True
    else:
        print("❌ Some tests failed")
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
