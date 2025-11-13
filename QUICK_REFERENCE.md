# Payment System Quick Reference

## Customer Payments (Customers pay for products/services)

### Get Checkout Options
```bash
GET /api/v1/customers/{id}/checkout-options?amount=1000
Scope: conversations:view
```

### Save Payment Method
```bash
POST /api/v1/customers/{id}/payment-methods
Scope: conversations:view
Body: {
  "provider": "mpesa",
  "details": {"phone_number": "254712345678"}
}
```

---

## Tenant Withdrawals (Tenants withdraw earnings)

### Get Withdrawal Options
```bash
GET /api/v1/wallet/withdrawal-options
Scope: finance:view
```

### Initiate Withdrawal
```bash
POST /api/v1/wallet/withdrawals
Scope: finance:withdraw:initiate
Body: {
  "amount": 1000.00,
  "method_type": "mpesa",
  "method_details": {"phone_number": "254712345678"}
}
```

### Approve Withdrawal (Different User!)
```bash
POST /api/v1/wallet/withdrawals/{id}/approve
Scope: finance:withdraw:approve
```

---

## Transaction Fees (Tenant Pays)

| Method | Fee | Minimum |
|--------|-----|---------|
| M-Pesa B2C | KES 33 | KES 10 |
| Bank Transfer | KES 50 | KES 100 |
| Till (B2B) | KES 27 | KES 10 |

**Example**: Request KES 1,000 → Fee KES 33 → Receive KES 967

---

## RBAC Scopes

### Customer Payments
- `conversations:view` - All customer payment endpoints

### Tenant Withdrawals
- `finance:view` - View options and list
- `finance:withdraw:initiate` - Create withdrawal requests
- `finance:withdraw:approve` - Approve withdrawals

---

## Four-Eyes Approval

✅ **CORRECT**:
```
User A initiates → User B approves ✓
```

❌ **WRONG**:
```
User A initiates → User A approves ✗
Error: "four-eyes approval required"
```

---

## Testing

```bash
# Run all payment tests
pytest apps/tenants/tests/test_*payment*.py apps/tenants/tests/test_withdrawal*.py -v

# Run migrations
python manage.py migrate tenants

# Generate API schema
python manage.py spectacular --file schema.yml
```

---

## Key Files

- **Customer Payment Views**: `apps/tenants/views_customer_payment.py`
- **Withdrawal Views**: `apps/tenants/views_withdrawal.py`
- **Customer Service**: `apps/tenants/services/customer_payment_service.py`
- **Withdrawal Service**: `apps/tenants/services/withdrawal_service.py`
- **API Docs**: `docs/API_PAYMENT_ENDPOINTS.md`

---

**Full Documentation**: See `IMPLEMENTATION_COMPLETE.md`
