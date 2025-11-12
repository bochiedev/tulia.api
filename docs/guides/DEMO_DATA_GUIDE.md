# Demo Data Guide

This guide explains how to use the demo data seeding functionality for the Tulia AI platform.

## Overview

The `seed_demo_data` management command creates comprehensive demo data for testing and demonstrations, including:

- **3 demo tenants** (one per subscription tier: Starter, Growth, Enterprise)
- **50 products per tenant** with realistic categories and variants
- **10 services per tenant** with availability windows
- **100 customers per tenant** with varied consent preferences
- **Historical messages and orders** for analytics testing
- **Appointments** with scheduled reminders

## Quick Start

### Basic Usage

```bash
python manage.py seed_demo_data
```

This will create all demo data with default settings.

### Command Options

```bash
# Skip subscription tier seeding (if already exists)
python manage.py seed_demo_data --skip-tiers

# Skip permission seeding (if already exists)
python manage.py seed_demo_data --skip-permissions

# Only create tenants, skip products/services/customers
python manage.py seed_demo_data --tenants-only
```

## What Gets Created

### Tenants

Three demo tenants are created, one for each subscription tier:

| Tenant | Slug | Tier | Phone | Owner Email |
|--------|------|------|-------|-------------|
| Starter Store | starter-store | Starter | +15555551001 | owner@starter.demo |
| Growth Business | growth-business | Growth | +15555551002 | owner@growth.demo |
| Enterprise Corp | enterprise-corp | Enterprise | +15555551003 | owner@enterprise.demo |

All owner accounts have the password: `demo123!`

### Products (50 per tenant)

Products are distributed across 5 categories:
- **Electronics**: Headphones, smart watches, speakers, etc.
- **Clothing**: T-shirts, jeans, sneakers, etc.
- **Home & Kitchen**: Coffee makers, blenders, cookware, etc.
- **Beauty & Personal Care**: Face cream, shampoo, perfume, etc.
- **Sports & Outdoors**: Yoga mats, dumbbells, water bottles, etc.

Approximately 50% of products have variants (different sizes, colors, storage options).

### Services (10 per tenant)

Services are distributed across 3 categories:
- **Beauty & Wellness**: Haircuts, massages, facials, etc.
- **Professional Services**: Consultations, legal advice, coaching, etc.
- **Home Services**: Cleaning, lawn care, repairs, etc.

Each service has:
- 1-2 variants with different durations
- 5 availability windows (Monday-Friday, 9am-5pm)
- Capacity of 2-5 concurrent bookings

### Customers (100 per tenant)

Customers are created with:
- Realistic names (first + last)
- Unique phone numbers
- Varied consent preferences:
  - **Transactional**: 100% (always true)
  - **Reminder**: ~80% opt-in
  - **Promotional**: ~40% opt-in
- Random tags for segmentation
- Last seen dates within past 30 days

### Historical Data

For each tenant:
- **30 customers** have conversation history (3-10 messages each)
- **20 customers** have 1-3 orders each
- **15 customers** have 1-2 appointments each
- Orders include realistic product selections and pricing
- Appointments are scheduled in the next 30 days with reminder messages

## Verifying Demo Data

After running the seed command, you can verify the data:

```bash
# Check counts
python manage.py shell -c "
from apps.tenants.models import Tenant
from apps.catalog.models import Product
from apps.services.models import Service
from apps.tenants.models import Customer
from apps.orders.models import Order
from apps.services.models import Appointment

print(f'Tenants: {Tenant.objects.count()}')
print(f'Products: {Product.objects.count()}')
print(f'Services: {Service.objects.count()}')
print(f'Customers: {Customer.objects.count()}')
print(f'Orders: {Order.objects.count()}')
print(f'Appointments: {Appointment.objects.count()}')
"

# Check consent distribution
python manage.py shell -c "
from apps.messaging.models import CustomerPreferences
total = CustomerPreferences.objects.count()
promo = CustomerPreferences.objects.filter(promotional_messages=True).count()
reminder = CustomerPreferences.objects.filter(reminder_messages=True).count()
print(f'Total preferences: {total}')
print(f'Promotional opt-in: {promo} ({promo/total*100:.1f}%)')
print(f'Reminder opt-in: {reminder} ({reminder/total*100:.1f}%)')
"
```

## Using Demo Data

### API Testing

Use the tenant IDs and owner credentials to test API endpoints:

```bash
# Get tenant ID
TENANT_ID=$(python manage.py shell -c "from apps.tenants.models import Tenant; print(Tenant.objects.get(slug='starter-store').id)")

# Login and get token
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "owner@starter.demo", "password": "demo123!"}'

# Use token in API requests
curl -X GET http://localhost:8000/v1/products \
  -H "X-TENANT-ID: $TENANT_ID" \
  -H "Authorization: Bearer <token>"
```

### Testing Different Tiers

Each tenant has different subscription tier limits:

**Starter Tier:**
- 1,000 messages/month
- 100 max products
- 10 max services
- No payment facilitation

**Growth Tier:**
- 10,000 messages/month
- 1,000 max products
- 50 max services
- Payment facilitation (3.5% fee)

**Enterprise Tier:**
- Unlimited messages
- Unlimited products
- Unlimited services
- Payment facilitation (2.5% fee)

### Testing RBAC

Each tenant has the following roles pre-configured:
- Owner (all permissions)
- Admin (all except finance:withdraw:approve)
- Finance Admin (finance + analytics)
- Catalog Manager (catalog + services)
- Support Lead (conversations + orders)
- Analyst (read-only analytics)

## Resetting Demo Data

To reset and recreate demo data:

```bash
# Delete existing demo tenants
python manage.py shell -c "
from apps.tenants.models import Tenant
Tenant.objects.filter(slug__in=['starter-store', 'growth-business', 'enterprise-corp']).delete()
"

# Recreate demo data
python manage.py seed_demo_data
```

## Idempotency

The seed command is designed to be idempotent:
- If tenants already exist, they are reused (not duplicated)
- Subscription tiers and permissions are only created if missing
- Running the command multiple times is safe

## Notes

- All demo data uses fake/placeholder information
- Phone numbers use the +1555 prefix (reserved for testing)
- Twilio credentials are randomly generated UUIDs (not real)
- All tenants start with a 14-day free trial
- Historical data dates are relative to the current date

## Troubleshooting

### "no such table" errors

Run migrations first:
```bash
python manage.py migrate
```

### Duplicate tenant errors

Use `--skip-if-exists` flag or delete existing tenants first.

### Missing permissions

Ensure RBAC permissions are seeded:
```bash
python manage.py seed_permissions
```

## Related Commands

- `seed_subscription_tiers` - Create subscription tier definitions
- `seed_permissions` - Create RBAC permission definitions
- `seed_tenant_roles` - Create default roles for a tenant
- `seed_demo` - Create a single demo tenant with users (simpler version)
