# 11 — Products & Services Flow

## 11.1 Browsing Products

- Intents: `BROWSE_PRODUCTS`, `PRODUCT_DETAILS`
- Flow:
  1. Detect category / interest.
  2. Query DB for matching products.
  3. Return up to N items as:
     - Text list
     - Or WhatsApp product-like cards (rich messages).
  4. Store `last_menu` in `ConversationContext`.

## 11.2 Selecting a Product

- If user replies with `1`, `2`, `3`:
  - Resolve from `last_menu`.
  - Show details or go straight to add-to-cart.

## 11.3 Services

- Same pattern as products, but using `Service` model:
  - Show name, price, duration, brief description.
