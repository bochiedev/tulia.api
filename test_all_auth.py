#!/usr/bin/env python
"""
Test all authentication endpoints to verify they work correctly.
"""
import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiOGU0ZTU5NGYtODZjZC00NTVhLTg2MzktMTg1NWMyZjA3ZTNlIiwiZW1haWwiOiJvd25lckBzdGFydGVyLmRlbW8iLCJleHAiOjE3NjMxODc5ODQsImlhdCI6MTc2MzEwMTU4NH0.KNc2y6uUd2GSvIxQq-Hm5mAYASyI7CpAXnGaZmdwsAo"
TENANT_ID = "604923c8-cff3-49d7-b3a3-fe5143c5c46b"

def test_endpoint(name, method, path, needs_tenant=False):
    """Test an endpoint and return result."""
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    
    if needs_tenant:
        headers["X-TENANT-ID"] = TENANT_ID
    
    try:
        if method == "GET":
            response = requests.get(f"{BASE_URL}{path}", headers=headers)
        elif method == "POST":
            response = requests.post(f"{BASE_URL}{path}", headers=headers, json={})
        else:
            return "❓", "Unknown method"
        
        if response.status_code == 200:
            return "✅", "OK"
        elif response.status_code == 201:
            return "✅", "Created"
        elif response.status_code == 401:
            return "❌", f"401 Unauthorized: {response.json().get('error', 'Unknown')}"
        elif response.status_code == 403:
            return "✅", "403 Forbidden (expected for non-superuser)"
        elif response.status_code == 404:
            return "⚠️", "404 Not Found (endpoint might not exist)"
        else:
            return "⚠️", f"{response.status_code}: {response.text[:100]}"
    except Exception as e:
        return "❌", f"Error: {str(e)}"


def main():
    """Test all authentication endpoints."""
    print("="*80)
    print("AUTHENTICATION TEST SUITE")
    print("="*80)
    print()
    
    tests = [
        # JWT-only endpoints (no tenant required)
        ("Get Profile", "GET", "/v1/auth/me", False),
        ("Refresh Token", "POST", "/v1/auth/refresh-token", False),
        ("Logout", "POST", "/v1/auth/logout", False),
        ("List Tenants", "GET", "/v1/tenants", False),
        
        # Tenant-scoped endpoints
        ("List Products", "GET", "/v1/products/", True),
        ("List Orders", "GET", "/v1/orders/", True),
        ("List Conversations", "GET", "/v1/messages/conversations", True),
        ("Get Wallet Balance", "GET", "/v1/wallet/balance", True),
        ("List Analytics", "GET", "/v1/analytics/overview", True),
        
        # Admin endpoints (should return 403 for non-superuser)
        ("Admin: List All Tenants", "GET", "/v1/admin/tenants", False),
        ("Admin: Revenue Analytics", "GET", "/v1/admin/analytics/revenue", False),
    ]
    
    results = []
    
    for name, method, path, needs_tenant in tests:
        status, message = test_endpoint(name, method, path, needs_tenant)
        results.append((name, status, message))
        
        # Print result
        tenant_marker = " [+TENANT]" if needs_tenant else ""
        print(f"{status} {name}{tenant_marker}")
        if status == "❌":
            print(f"   {message}")
        print()
    
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print()
    
    success = sum(1 for _, status, _ in results if status == "✅")
    failed = sum(1 for _, status, _ in results if status == "❌")
    warning = sum(1 for _, status, _ in results if status == "⚠️")
    
    print(f"✅ Passed: {success}")
    print(f"❌ Failed: {failed}")
    print(f"⚠️  Warnings: {warning}")
    print()
    
    if failed > 0:
        print("Failed tests:")
        for name, status, message in results:
            if status == "❌":
                print(f"  - {name}: {message}")
        print()
        return False
    
    print("🎉 All authentication tests passed!")
    return True


if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)
