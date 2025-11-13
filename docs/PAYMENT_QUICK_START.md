# Payment Integration Quick Start Guide

## For Developers

### Setup Payment Providers

#### 1. Configure Environment Variables

Copy from `.env.example` and fill in your credentials:

```bash
# Stripe (for international cards and subscriptions)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Paystack (for African card payments)
PAYSTACK_SECRET_KEY=sk_test_...
PAYSTACK_PUBLIC_KEY=pk_test_...

# M-Pesa (for Kenya mobile money)
MPESA_CONSUMER_KEY=...
MPESA_CONSUMER_SECRET=...
MPESA_SHORTCODE=174379
MPESA_PASSKEY=...
MPESA_ENVIRONMENT=sandbox

# Pesapal (for East Africa)
PESAPAL_CONSUMER_KEY=...
PESAPAL_CONSUMER_SECRET=...
PESAPAL_IPN_ID=...
```

#### 2. Register Webhook URLs

**Stripe Dashboard** → Developers → Webhooks:
```
https://yourdomain.com/api/v1/webhooks/stripe
```
Events to listen: `checkout.session.completed`, `payment_intent.payment_failed`

**Paystack Dashboard** → Settings → Webhooks:
```
https://yourdomain.com/api/v1/webhooks/paystack
```

**Pesapal** - Register IPN programmatically:
```python
from apps.integrations.services.pesapal_service import PesapalService

PesapalService.register_ipn(
    url='https://yourdomain.com/api/v1/webhooks/pesapal',
    ipn_notification_type='POST'
)
```

**M-Pesa** - Register C2B URLs:
```python
from apps.integrations.services.mpesa_service import MpesaService

MpesaService.c2b_register_urls(
    confirmation_url='https://yourdomain.com/api/v1/webhooks/mpesa/callback',
    validation_url='https://yourdomain.com/api/v1/webhooks/mpesa/validate'
)
```

### Usage Examples

#### Generate Payment Checkout Link

```python
from apps.integrations.services.payment_service import PaymentService
from apps.orders.models import Order

# Get order
order = Order.objects.get(id=order_id)

# Generate checkout link (automatically selects best provider)
checkout = PaymentService.generate_checkout_link(order)

# Returns:
# {
#     'checkout_url': 'https://...',  # or None for M-Pesa STK
#     'provider': 'mpesa',
#     'payment_ref': 'ws_...',
#     'stk_push_initiated': True  # for M-Pesa only
# }
```

#### M-Pesa STK Push (Direct)

```python
from apps.integrations.services.mpesa_service import MpesaService

result = MpesaService.stk_push(
    phone_number='254712345678',
    amount=Decimal('100.00'),
    account_reference='ORD123',
    transaction_desc='Order payment',
    callback_url='https://yourdomain.com/api/v1/webhooks/mpesa/callback'
)

# Customer receives STK push on their phone
# Result: {'checkout_request_id': '...', 'customer_message': '...'}
```

#### Paystack Payment

```python
from apps.integrations.services.paystack_service import PaystackService

result = PaystackService.initialize_transaction(
    email='customer@example.com',
    amount=Decimal('1000.00'),
    currency='KES',
    reference='order_123',
    callback_url='https://yourdomain.com/orders/123/success',
    metadata={'order_id': '123', 'tenant_id': '456'}
)

# Redirect customer to: result['authorization_url']
```

#### Pesapal Payment

```python
from apps.integrations.services.pesapal_service import PesapalService

result = PesapalService.submit_order(
    merchant_reference='order_123',
    amount=Decimal('5000.00'),
    currency='KES',
    description='Order payment',
    callback_url='https://yourdomain.com/orders/123/success',
    notification_id=settings.PESAPAL_IPN_ID,
    billing_address={
        'country_code': 'KE',
        'first_name': 'John',
        'email_address': 'john@example.com',
        'phone_number': '254712345678'
    },
    customer_email='john@example.com'
)

# Redirect customer to: result['redirect_url']
```

### Tenant Withdrawals

#### M-Pesa B2C (Withdraw to M-Pesa)

```python
from apps.integrations.services.mpesa_service import MpesaService

result = MpesaService.b2c_payment(
    phone_number='254712345678',
    amount=Decimal('5000.00'),
    occasion='Withdrawal',
    remarks='Tenant withdrawal',
    command_id='BusinessPayment'
)

# Money sent to customer's M-Pesa wallet
```

#### Paystack Transfer (Withdraw to Bank)

```python
from apps.integrations.services.paystack_service import PaystackService

# First, create recipient
recipient = PaystackService.create_transfer_recipient(
    account_number='1234567890',
    bank_code='063',  # Access Bank Kenya
    name='John Doe',
    currency='KES'
)

# Then initiate transfer
transfer = PaystackService.initiate_transfer(
    recipient_code=recipient['recipient_code'],
    amount=Decimal('10000.00'),
    currency='KES',
    reference='withdrawal_123',
    reason='Tenant withdrawal'
)
```

### Webhook Processing

Webhooks are automatically processed by the views. To manually process:

```python
from apps.integrations.services.payment_service import PaymentService

# Process webhook
result = PaymentService.process_payment_webhook(
    provider='paystack',  # or 'stripe', 'mpesa', 'pesapal'
    payload=webhook_payload,
    signature=signature_header
)
```

### Query Transaction Status

#### M-Pesa STK Status

```python
from apps.integrations.services.mpesa_service import MpesaService

status = MpesaService.query_stk_status(checkout_request_id)
# Returns: {'ResultCode': 0, 'ResultDesc': 'Success', ...}
```

#### Paystack Verification

```python
from apps.integrations.services.paystack_service import PaystackService

transaction = PaystackService.verify_transaction(reference)
# Returns: {'status': 'success', 'amount': 100000, ...}
```

#### Pesapal Status

```python
from apps.integrations.services.pesapal_service import PesapalService

status = PesapalService.get_transaction_status(order_tracking_id)
# Returns: {'payment_status_description': 'Completed', ...}
```

### Testing

#### Test with Sandbox Credentials

All services support sandbox/test environments. Use test credentials from `.env.example`.

#### M-Pesa Test Phone Numbers

```python
# Success
phone = '254708374149'

# Insufficient funds
phone = '254708374150'

# Invalid account
phone = '254708374151'
```

#### Paystack Test Cards

```
Card: 4084084084084081
CVV: 408
Expiry: Any future date
PIN: 0000
OTP: 123456
```

### Error Handling

All services raise specific exceptions:

```python
from apps.integrations.services.paystack_service import PaystackError
from apps.integrations.services.mpesa_service import MpesaError
from apps.integrations.services.pesapal_service import PesapalError

try:
    result = PaystackService.initialize_transaction(...)
except PaystackError as e:
    logger.error(f"Paystack error: {str(e)}")
    # Handle error
```

### Logging

All payment operations are logged with structured data:

```python
logger.info(
    "Payment processed",
    extra={
        'order_id': str(order.id),
        'amount': float(amount),
        'provider': 'mpesa',
        'reference': payment_ref
    }
)
```

### Security Best Practices

1. **Never log sensitive data**: Card numbers, full phone numbers, API keys
2. **Always verify webhooks**: Use signature verification
3. **Use HTTPS**: All webhook URLs must use HTTPS
4. **Validate amounts**: Check amounts match before processing
5. **Idempotency**: Handle duplicate webhooks gracefully

### Common Issues

#### M-Pesa "Invalid Access Token"
- Token expired (cached for 55 minutes)
- Solution: Token auto-refreshes, check credentials

#### Paystack "Invalid Signature"
- Webhook secret mismatch
- Solution: Update `PAYSTACK_SECRET_KEY` in settings

#### Pesapal "Transaction Not Found"
- IPN received before transaction created
- Solution: Query status after delay, or use metadata

#### Stripe "Webhook Signature Verification Failed"
- Wrong webhook secret
- Solution: Get secret from Stripe Dashboard → Webhooks

### Performance Tips

1. **Cache OAuth tokens**: M-Pesa and Pesapal tokens are cached automatically
2. **Async webhooks**: Webhook processing is synchronous, consider Celery for heavy operations
3. **Batch queries**: Use bulk operations when querying multiple transactions
4. **Rate limiting**: Respect provider rate limits (usually 100-300 req/min)

### Monitoring

Check webhook logs:

```python
from apps.integrations.models import WebhookLog

# Recent webhooks
recent = WebhookLog.objects.filter(
    provider='mpesa',
    status='error'
).order_by('-created_at')[:10]

# Success rate
from django.db.models import Count
stats = WebhookLog.objects.filter(
    provider='paystack'
).values('status').annotate(count=Count('id'))
```

### Support

- **M-Pesa**: https://developer.safaricom.co.ke/support
- **Paystack**: support@paystack.com
- **Pesapal**: support@pesapal.com
- **Stripe**: https://support.stripe.com

---

**Quick Links**:
- [Full Documentation](./PAYMENT_INTEGRATION_SUMMARY.md)
- [API Reference](../apps/integrations/services/)
- [Webhook Handlers](../apps/integrations/views_payment.py)
