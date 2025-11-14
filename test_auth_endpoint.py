#!/usr/bin/env python
"""
Test authentication endpoint directly.
"""
import requests

token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiOGU0ZTU5NGYtODZjZC00NTVhLTg2MzktMTg1NWMyZjA3ZTNlIiwiZW1haWwiOiJvd25lckBzdGFydGVyLmRlbW8iLCJleHAiOjE3NjMxODc5ODQsImlhdCI6MTc2MzEwMTU4NH0.KNc2y6uUd2GSvIxQq-Hm5mAYASyI7CpAXnGaZmdwsAo"

print("Testing /v1/auth/me endpoint...")
print()

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

print("Headers:")
for key, value in headers.items():
    if key == "Authorization":
        print(f"  {key}: Bearer {value[7:30]}...")
    else:
        print(f"  {key}: {value}")
print()

try:
    response = requests.get(
        "http://localhost:8000/v1/auth/me",
        headers=headers
    )
    
    print(f"Status Code: {response.status_code}")
    print()
    print("Response:")
    print(response.text)
    print()
    
    if response.status_code == 200:
        print("✅ SUCCESS! Authentication working!")
    else:
        print("❌ FAILED! Check Django logs for details")
        print()
        print("Common issues:")
        print("1. Token expired - login again")
        print("2. Middleware not setting request.user")
        print("3. User object missing is_authenticated property")
        
except Exception as e:
    print(f"❌ Error: {e}")
    print()
    print("Is Django running?")
    print("  python manage.py runserver")
