#!/bin/bash
# Test script to verify API fixes

BASE_URL="http://localhost:8000"
TENANT_ID="604923c8-cff3-49d7-b3a3-fe5143c5c46b"
API_KEY="a96b73152af3e755424b11a6dad39a44bbebb553c7608f0b138a48ba95e54d68"

echo "🧪 Testing API Fixes"
echo "===================="
echo ""

# Test 1: Health check (no auth)
echo "1️⃣  Testing health check (no auth required)..."
curl -s -o /dev/null -w "Status: %{http_code}\n" \
  "$BASE_URL/v1/health/"
echo ""

# Test 2: List integrations (API key auth)
echo "2️⃣  Testing list integrations (API key auth)..."
curl -s -o /dev/null -w "Status: %{http_code}\n" \
  -H "X-TENANT-ID: $TENANT_ID" \
  -H "X-TENANT-API-KEY: $API_KEY" \
  "$BASE_URL/v1/settings/integrations"
echo ""

# Test 3: Get Twilio credentials (API key auth)
echo "3️⃣  Testing get Twilio credentials (API key auth)..."
curl -s -o /dev/null -w "Status: %{http_code}\n" \
  -H "X-TENANT-ID: $TENANT_ID" \
  -H "X-TENANT-API-KEY: $API_KEY" \
  "$BASE_URL/v1/settings/integrations/twilio"
echo ""

# Test 4: Analytics overview (API key auth)
echo "4️⃣  Testing analytics overview (API key auth)..."
curl -s -o /dev/null -w "Status: %{http_code}\n" \
  -H "X-TENANT-ID: $TENANT_ID" \
  -H "X-TENANT-API-KEY: $API_KEY" \
  "$BASE_URL/v1/analytics/overview"
echo ""

echo "✅ All tests completed!"
echo ""
echo "Expected results:"
echo "  - All should return 200 (or 403 if missing RBAC scope)"
echo "  - None should return 401 CSRF errors"
echo ""
echo "To test JWT endpoints, first login:"
echo "  curl -X POST $BASE_URL/v1/auth/login \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"email\":\"your@email.com\",\"password\":\"yourpass\"}'"
