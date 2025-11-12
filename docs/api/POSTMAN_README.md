# Tulia AI API - Postman Collection

## 📦 What's Included

This directory contains a complete Postman collection for testing the Tulia AI WhatsApp Commerce Platform API.

### Files

| File | Description | Size |
|------|-------------|------|
| `postman_collection.json` | Main Postman collection with 80+ endpoints | 53 KB |
| `postman_environment_template.json` | Environment variable template | 1 KB |
| `POSTMAN_GUIDE.md` | Comprehensive user guide | 13 KB |
| `API_QUICK_REFERENCE.md` | Quick reference card for all endpoints | 11 KB |
| `POSTMAN_TEST_SCENARIOS.md` | Detailed test scenarios documentation | 19 KB |
| `POSTMAN_COLLECTION_SUMMARY.md` | Implementation summary | 11 KB |

## 🚀 Quick Start

### 1. Import Collection

**In Postman Desktop or Web:**
1. Click **Import** button (top left)
2. Drag and drop `postman_collection.json` or click to browse
3. Click **Import**

**Via Postman CLI:**
```bash
# Import collection
postman collection import postman_collection.json
```

### 2. Set Up Environment

**Option A: Manual Setup**
1. Click the gear icon (⚙️) in top right
2. Click **Add** to create new environment
3. Name it "Tulia AI - Development"
4. Add these variables:
   - `base_url` = `http://localhost:8000`
   - `tenant_id` = `your-tenant-uuid`
   - `api_key` = `your-api-key`
5. Click **Save**
6. Select the environment from dropdown

**Option B: Import Template**
1. Click **Import**
2. Select `postman_environment_template.json`
3. Edit the imported environment
4. Fill in your `tenant_id` and `api_key`
5. Save and select

### 3. Run Your First Request

1. Expand the collection in sidebar
2. Navigate to **Health & Status** → **Health Check**
3. Click **Send**
4. You should see: `200 OK` with system health status

✅ **Success!** You're ready to test the API.

## 📚 Documentation

### For New Users
Start with **POSTMAN_GUIDE.md** for:
- Detailed setup instructions
- Authentication configuration
- Running tests
- Common scenarios
- Troubleshooting

### For Quick Reference
Use **API_QUICK_REFERENCE.md** for:
- All endpoint URLs
- Required scopes
- HTTP methods
- Example curl commands
- Status codes

### For Testing
See **POSTMAN_TEST_SCENARIOS.md** for:
- 34 detailed test scenarios
- Step-by-step instructions
- Expected results
- Test assertions

## 🎯 What Can You Test?

### API Endpoints (80+)
- ✅ Products & Catalog
- ✅ Services & Appointments
- ✅ Orders & Payments
- ✅ Messaging & Conversations
- ✅ Campaigns
- ✅ Customers & Preferences
- ✅ Wallet & Finance
- ✅ Analytics
- ✅ RBAC (Roles & Permissions)
- ✅ Admin Operations
- ✅ Webhooks

### Test Scenarios (34)
- ✅ Authentication & Authorization
- ✅ CRUD Operations
- ✅ Business Logic
- ✅ Rate Limiting
- ✅ Pagination
- ✅ Tenant Isolation
- ✅ RBAC Enforcement
- ✅ Four-Eyes Approval
- ✅ Consent Management
- ✅ Integration Tests

### Security Tests
- 🔒 RBAC scope enforcement
- 🔒 Tenant isolation
- 🔒 Four-eyes approval
- 🔒 Cross-tenant access prevention
- 🔒 API key validation

## 🧪 Running Tests

### Individual Request
```
1. Select request from sidebar
2. Click Send
3. View response and test results
```

### Folder of Requests
```
1. Right-click folder
2. Select "Run folder"
3. Review results
```

### Entire Collection
```
1. Click ... next to collection name
2. Select "Run collection"
3. Configure settings
4. Click Run
```

### Command Line (Newman)
```bash
# Install Newman
npm install -g newman

# Run all tests
newman run postman_collection.json \
  --environment postman_environment_template.json

# Run specific folder
newman run postman_collection.json \
  --folder "RBAC - Roles & Permissions"

# Generate HTML report
newman run postman_collection.json \
  --environment postman_environment_template.json \
  --reporters cli,html \
  --reporter-html-export report.html
```

## 🔑 Authentication

All API requests (except health check and webhooks) require:

```http
X-TENANT-ID: your-tenant-uuid
X-TENANT-API-KEY: your-api-key
```

These headers are automatically added by the collection using environment variables.

## 📊 Test Coverage

- **Total Endpoints:** 80+
- **Test Assertions:** 200+
- **Success Tests:** 100+
- **Error Tests:** 80+
- **Security Tests:** 20+
- **Coverage:** 100% of REST API

## 🎨 Collection Features

### Automatic Authentication
- Headers added automatically from environment
- No need to manually add auth to each request

### Request Chaining
- Variables saved between requests
- Create → Update → Delete workflows
- IDs automatically captured

### Comprehensive Tests
- Success scenarios (200, 201)
- Error scenarios (400, 403, 404, 409, 429)
- Security validations
- Business logic checks

### Documentation
- Every request documented
- Required scopes listed
- Query parameters explained
- Example responses included

## 🔧 Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `base_url` | API base URL | `http://localhost:8000` |
| `tenant_id` | Your tenant UUID | `550e8400-e29b-41d4-a716-446655440000` |
| `api_key` | Your API key | `test-api-key-12345` |

### Auto-Saved Variables

These are automatically saved during test execution:
- `created_product_id`
- `created_service_id`
- `created_appointment_id`
- `created_campaign_id`
- `withdrawal_id`

## 🐛 Troubleshooting

### 401 Unauthorized
- ✓ Check `api_key` is set in environment
- ✓ Verify API key is valid
- ✓ Ensure environment is selected

### 403 Forbidden
- ✓ Check required scope in request description
- ✓ Verify your user has the scope
- ✓ Confirm `tenant_id` is correct

### 429 Too Many Requests
- ✓ Check `Retry-After` header
- ✓ Wait before retrying
- ✓ Consider upgrading tier

### Tests Failing
- ✓ Check response body in console
- ✓ Verify test data exists
- ✓ Review server logs
- ✓ Ensure clean database state

## 📖 Additional Resources

### API Documentation
- **Swagger UI:** `http://localhost:8000/schema/swagger/`
- **OpenAPI Schema:** `http://localhost:8000/schema/`

### Project Documentation
- **Main README:** `../README.md`
- **Deployment Guide:** `../DEPLOYMENT.md`
- **Quick Start:** `../QUICKSTART.md`

### Support
- **GitHub Issues:** Report bugs and feature requests
- **API Status:** Check `/v1/health/` endpoint

## 🚢 CI/CD Integration

### GitHub Actions
```yaml
- name: Run API Tests
  run: |
    npm install -g newman
    newman run postman_collection.json \
      --environment postman_environment_template.json
```

### Jenkins
```groovy
sh 'newman run postman_collection.json \
    --environment postman_environment_template.json'
```

### GitLab CI
```yaml
test:
  script:
    - npm install -g newman
    - newman run postman_collection.json
```

## 📝 Version History

- **v1.0.0** (2025-11-12): Initial release
  - 80+ endpoints
  - 200+ test assertions
  - 34 test scenarios
  - Complete documentation

## 📄 License

This Postman collection is part of the Tulia AI platform and follows the same license as the main project.

## 🤝 Contributing

To add new tests or improve existing ones:

1. Add/modify requests in Postman
2. Write test assertions
3. Update documentation
4. Export collection
5. Submit pull request

## ⭐ Quick Tips

1. **Use environments** - Create separate environments for dev/staging/prod
2. **Run tests often** - Catch issues early
3. **Review test results** - Don't just look at pass/fail counts
4. **Chain requests** - Use saved variables for workflows
5. **Document changes** - Update descriptions when modifying requests

## 🎓 Learning Resources

- **Postman Learning Center:** https://learning.postman.com/
- **Newman Documentation:** https://learning.postman.com/docs/running-collections/using-newman-cli/
- **API Testing Best Practices:** See POSTMAN_GUIDE.md

---

**Ready to start testing?** Import the collection and run your first request! 🚀
