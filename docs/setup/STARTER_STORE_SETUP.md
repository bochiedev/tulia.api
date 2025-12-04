# Starter Store Setup Guide

Quick setup script to create a demo tenant with sample data for testing and development.

## What It Creates

- **Tenant**: "Starter Store" (retail business in Nairobi)
- **Owner User**: `owner@starterstore.com` with Owner role
- **Agent**: "Stella" - friendly AI assistant configured with GPT-4o
- **Products**: 5 sample products (coffee, honey, basket, lotion, t-shirt)
- **Services**: 3 sample services (shopping assistant, gift wrapping, consultation)
- **FAQs**: 6 knowledge base entries (hours, delivery, payment, returns, location, rewards)
- **Twilio**: Pre-configured with sandbox credentials

## Usage

```bash
python setup_starter_store.py
```

## Output

The script will display:
- Tenant ID (save this for API calls)
- Owner credentials (email + password)
- Agent configuration
- Counts of created entities
- Next steps

## Security Notes

⚠️ **IMPORTANT**: 
- Default password is `ChangeMe123!` - change immediately in production
- Twilio credentials are sandbox credentials - replace with your own
- This is for development/testing only

## Next Steps

1. **Change Password**
   ```bash
   python manage.py changepassword owner@starterstore.com
   ```

2. **Generate API Key**
   ```bash
   python manage.py generate_api_key --tenant-id <TENANT_ID>
   ```

3. **Test WhatsApp**
   - Join sandbox: https://www.twilio.com/console/sms/whatsapp/sandbox
   - Send message to: `+14155238886`
   - Try: "Hi", "Show me products", "What are your hours?"

4. **Access Django Admin**
   - URL: http://localhost:8000/admin
   - Login with owner credentials
   - Browse tenant data

## API Testing

Use the generated API key with these headers:

```bash
curl -X GET http://localhost:8000/v1/products \
  -H "X-TENANT-ID: <TENANT_ID>" \
  -H "X-TENANT-API-KEY: <API_KEY>"
```

## Cleanup

To remove the starter store:

```bash
python manage.py shell
>>> from apps.tenants.models import Tenant
>>> Tenant.objects.filter(name="Starter Store").delete()
```

## Customization

Edit `setup_starter_store.py` to:
- Change business details (name, timezone, currency)
- Add more products/services
- Modify agent personality
- Add custom FAQs
- Configure different integrations
