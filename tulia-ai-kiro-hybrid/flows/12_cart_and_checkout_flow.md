# 12 — Cart & Checkout Flow

## 12.1 Adding to Cart / Direct Order

Tulia can use either:
- Simple “direct order” (no cart, one item per order)
- Or a multi-item cart (future extension)

Default Starter: direct order.

Steps:
1. User selects product.
2. Bot asks quantity / variant if needed.
3. Create `Order` with `PENDING_PAYMENT`.
4. Move to payment method selection.

## 12.2 Payment Selection

- Ask: “Utapenda kulipa kwa M-Pesa ama card?”
- Map responses to:
  - `PAYMENT_HELP` with `payment_method` slot.
  - Then use Payment Flow (see `09_payments_flow.md`).
