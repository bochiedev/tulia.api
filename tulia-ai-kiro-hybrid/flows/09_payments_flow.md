# 09 — Payments Flow (M-Pesa, Paystack, Stripe, Pesapal)

This file defines how Tulia AI moves from **intent to pay** in a safe,
deterministic way.

## 9.1 Payment Methods

Supported:

- M-Pesa STK Push
- M-Pesa manual paybill/till
- Card payments via:
  - Paystack
  - Stripe
  - Pesapal

Each tenant can enable/disable methods via `TenantSettings`.

## 9.2 High-Level Flow (M-Pesa STK)

1. Customer: “Nataka kununua jacket, nitalipa kwa M-Pesa”
2. Router:
   - Ensure an active order/cart exists (or create one).
   - Ask: “Utalipa kwa hii number ama nyingine?”
3. Customer:
   - Replies with:
     - “Hii number” → use WhatsApp number
     - Or sends alternative `+2547...`
4. Backend:
   - Initiates STK push with tenant’s M-Pesa credentials.
   - Creates `PaymentRequest` record with `PENDING`.
   - Sends message: “Tume-kutumia STK, tafadhali thibitisha.”
5. Callback:
   - Upon success:
     - Mark `PaymentRequest` as `SUCCESS`.
     - Mark `Order` as `PAID`.
     - Send WhatsApp confirmation & receipt.
   - Upon failure:
     - Mark `FAILED`.
     - Send a user-friendly error & options to retry or choose another method.

## 9.3 Card Payments Flow

1. Customer chooses card payment.
2. Backend:
   - Creates `PaymentRequest` with `PENDING`.
   - Calls Paystack / Stripe / Pesapal to generate a payment link.
   - Sends the link as a WhatsApp message.
3. Customer pays in browser.
4. Webhook callback updates status.
5. WhatsApp notification confirms payment and order.

## 9.4 Design Constraints

- No LLM calls in the payment execution path.
- All amounts come from:
  - Product prices
  - Taxes, fees defined in `TenantSettings`
- Currencies come from tenant configuration.
- Any discrepancy → log & request human intervention.
