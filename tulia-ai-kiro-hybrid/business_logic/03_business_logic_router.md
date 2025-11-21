# 03 — Business Logic Router

The Business Logic Router is where **all real decisions** happen. It:

- Accepts: `IntentResult` + `ConversationContext` + tenant data
- Produces: `BotAction` + `next_state`
- Never uses LLM internally
- Guarantees **no hallucination**

## 3.1 Responsibilities

- Map `intent` → handler function
- Respect `ConversationContext.current_flow` and `awaiting_response`
- Manage multi-step flows (browse → select → confirm → pay)
- Update context (summary, key facts, last question)
- Trigger side effects:
  - Order creation
  - Appointment creation
  - Payment initiation
  - Hand-off to human

## 3.2 Example Routing Table

```python
INTENT_HANDLERS = {
    "GREET": handle_greet,
    "BROWSE_PRODUCTS": handle_browse_products,
    "BROWSE_SERVICES": handle_browse_services,
    "PRODUCT_DETAILS": handle_product_details,
    "SERVICE_DETAILS": handle_service_details,
    "PLACE_ORDER": handle_place_order,
    "BOOK_APPOINTMENT": handle_book_appointment,
    "CHECK_ORDER_STATUS": handle_check_order_status,
    "CHECK_APPOINTMENT_STATUS": handle_check_appointment_status,
    "ASK_DELIVERY_FEES": handle_delivery_fees,
    "ASK_RETURN_POLICY": handle_return_policy,
    "PAYMENT_HELP": handle_payment_help,
    "REQUEST_HUMAN": handle_request_human,
    "GENERAL_FAQ": handle_general_faq,
    "SMALL_TALK": handle_small_talk,
    "UNKNOWN": handle_unknown,
}
```

Each handler is deterministic and should be easy to test.

## 3.3 BotAction Model

Router returns a structured action:

```python
@dataclass
class BotAction:
    type: str  # "TEXT", "LIST", "BUTTONS", "PRODUCT_CARDS", "HANDOFF"
    text: str | None = None
    rich_payload: dict | None = None
    new_context: dict | None = None
```

The **WhatsApp formatter** takes this and builds Twilio-compatible messages.

## 3.4 Example: Browse Products Flow

1. Intent: `BROWSE_PRODUCTS` (slots: `category="jackets"`, `budget_max=50000`)
2. `handle_browse_products`:
   - Query Products for tenant with category/price filter
   - If zero:
     - Reply: “Hatujapata jackets kwa budget hii…” + maybe offer full list
   - If 1–10:
     - Return `PRODUCT_CARDS` action with list of products
     - Store in context: `last_menu = {"type": "products", "ids": [...]}`

3. If user replies `1` or clicks a button:
   - Router recognizes `SELECT_MENU_OPTION`
   - Resolves product id from `last_menu`
   - Transitions to `PLACE_ORDER` or `PRODUCT_DETAILS` as appropriate

All of this is pure Python logic, no LLM.

## 3.5 Example: Book Appointment Flow

- Step 1: Customer says “Nataka pedicure leo 6pm”
  - Intent: `BOOK_APPOINTMENT`
  - Slots: `service="pedicure"`, `date="today"`, `time="18:00"`

- Step 2: Handler:
  - Resolve service from DB
  - Normalize date/time to tenant timezone
  - Check availability in `Appointment` / `AvailabilityWindow`
  - If free:
    - Create appointment `PENDING_CONFIRMATION`
    - Ask confirmation: “Niku-book pedicure leo saa kumi na mbili?”
  - If not:
    - Suggest alternative slots

- Step 3: On “Yes”:
  - Finalize appointment `CONFIRMED`
  - Send confirmation & optional payment

Again, no LLM inside the handler.

## 3.6 Error & Fallback Strategy

- If handler fails (e.g., DB error):
  - Log with Sentry
  - Send a simple apology message
  - Optionally trigger `REQUEST_HUMAN`

- If router receives unknown intent:
  - Route to `handle_unknown`, which:
    - Asks clarification
    - Or offers a main menu
    - Or triggers human handoff depending on tenant settings
