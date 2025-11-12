# Tenant API Key Management

## Overview

Every tenant requires an API key for authentication when accessing the API. API keys are automatically generated when a new tenant is created.

## Automatic Generation

When a new tenant is created, an initial API key is automatically generated and logged. The key is shown in the logs during tenant creation:

```
NEW TENANT API KEY (save this, it won't be shown again): <api-key>
```

**Important:** API keys are only shown once during generation. They are stored as SHA-256 hashes and cannot be retrieved later.

## Manual API Key Generation

### Generate a new API key for a tenant

```bash
python manage.py generate_api_key <tenant-slug> --name "Key Name"
```

Example:
```bash
python manage.py generate_api_key starter-store --name "Production API Key"
```

This will output:
- The plain text API key (save this immediately!)
- Tenant ID
- Instructions for using the key

### List existing API keys for a tenant

```bash
python manage.py list_api_keys <tenant-slug>
```

Example:
```bash
python manage.py list_api_keys starter-store
```

This shows:
- Number of API keys
- Key names and creation dates
- Key hash previews (not the actual keys)

## Using API Keys

All API requests (except public paths like `/admin/`, `/v1/health`, `/schema`) require two headers:

```http
X-TENANT-ID: <tenant-uuid>
X-TENANT-API-KEY: <api-key>
```

Example with curl:
```bash
curl -H "X-TENANT-ID: 604923c8-cff3-49d7-b3a3-fe5143c5c46b" \
     -H "X-TENANT-API-KEY: edaee3e5a4305ace873a20c4d7aac9112169ef7ec9563d4f0dd8fb00de626250" \
     https://api.example.com/v1/products
```

## Public Paths (No API Key Required)

The following paths do NOT require tenant authentication:
- `/admin/` - Django admin interface
- `/v1/health` - Health check endpoint
- `/v1/webhooks/` - External webhook callbacks (verified by signature)
- `/schema` - OpenAPI schema documentation

## Security Best Practices

1. **Never commit API keys to version control**
2. **Store API keys securely** (environment variables, secrets manager)
3. **Rotate keys regularly** by generating new ones and removing old ones
4. **Use descriptive names** for keys to track their usage
5. **Generate separate keys** for different environments (dev, staging, prod)

## Programmatic API Key Management

You can also manage API keys programmatically:

```python
from apps.tenants.models import Tenant
from apps.tenants.utils import add_api_key_to_tenant

# Get tenant
tenant = Tenant.objects.get(slug='my-tenant')

# Generate new API key
plain_key = add_api_key_to_tenant(tenant, name="My API Key")

# Save the plain_key securely - it won't be accessible again!
print(f"New API key: {plain_key}")
```

## Troubleshooting

### "MISSING_CREDENTIALS" error
- Ensure you're sending both `X-TENANT-ID` and `X-TENANT-API-KEY` headers
- Check that you're not accessing a public path that doesn't need authentication

### "INVALID_API_KEY" error
- Verify the API key is correct (no extra spaces or characters)
- Check that the key belongs to the specified tenant
- Generate a new key if the old one was lost

### "INVALID_TENANT" error
- Verify the tenant ID is correct
- Check that the tenant exists and is active

## Migration for Existing Tenants

If you have existing tenants without API keys, generate them:

```bash
# List all tenants
python manage.py shell -c "from apps.tenants.models import Tenant; [print(t.slug) for t in Tenant.objects.all()]"

# Generate key for each tenant
python manage.py generate_api_key <tenant-slug>
```
