# 02 — Intent Classification

This file defines the **intent schema** and how Tulia AI detects intents
cheaply and reliably, with minimal use of LLMs.

## 2.1 Intent Schema

A compact, business-oriented intent set:

- `GREET` – greetings, check-ins
- `BROWSE_PRODUCTS` – view products, categories, availability
- `BROWSE_SERVICES` – view services, menus, packages
- `PRODUCT_DETAILS` – ask for more info about a product
- `SERVICE_DETAILS` – ask for more info about a service
- `PLACE_ORDER` – buy a product
- `BOOK_APPOINTMENT` – book a service at a time
- `CHECK_ORDER_STATUS` – “order imefika?”, “order status?”
- `CHECK_APPOINTMENT_STATUS` – appointment follow-up
- `ASK_DELIVERY_FEES` – shipping / delivery questions
- `ASK_RETURN_POLICY` – refunds, exchanges
- `PAYMENT_HELP` – how to pay, payment issues
- `REQUEST_HUMAN` – ask to talk to a person
- `GENERAL_FAQ` – generic questions answerable via RAG
- `SMALL_TALK` – “rada msee”, “uko aje?”, non-business chat
- `UNKNOWN` – unclassified / noise

## 2.2 Slot Extraction

For some intents we need **slots** (structured attributes), e.g.:

- `BROWSE_PRODUCTS`: `category`, `budget_min`, `budget_max`, `brand`
- `PLACE_ORDER`: `product_id`, `quantity`, `variant`, `color`, `size`
- `BOOK_APPOINTMENT`: `service_id`, `date`, `time`, `duration`
- `PAYMENT_HELP`: `payment_method` (mpesa, card)

Slot extraction should be mostly rule/regex based:

- Detect numbers (“1”, “2”) → menu choices
- Detect words like “kes 5000”, “50k”, “under 10k”
- Detect dates: “leo”, “kesho”, “Saturday”, etc.
- Detect time: “sa kumi”, “4pm”, “6:30”

If ambiguous, use a small LLM to map text → structured fields.

## 2.3 Rule-Based Detection First

1. **Hard-coded keywords & patterns** (EN/SW/Sheng):
   - `BROWSE_PRODUCTS`: “browse products”, “naona nini?”, “what do you sell”
   - `BROWSE_SERVICES`: “nataka service”, “services ziko?”, “book salon”
   - `BOOK_APPOINTMENT`: “book”, “appointment”, “slot”, “time kuja”
   - `PLACE_ORDER`: “order”, “nunua”, “buy”, “weka kwa cart”
   - `PAYMENT_HELP`: “how do I pay”, “mpesa details”, “paybill”, “till”
   - `REQUEST_HUMAN`: “ongea na mtu”, “human”, “agent”, “representative”

2. **Numeric replies**:
   - If last turn offered a numbered list and user replies with `1`, `2`,
     map to a `SELECT_MENU_OPTION` pseudo-intent handled entirely by
     the Business Logic Router (no LLM).

3. **WhatsApp interactive messages**:
   - If the message has `button_payload` or `list_reply_id`, treat that as
     a *direct action*, not a free-form NLU task.

Only if these fail do we call a small LLM.

## 2.4 Lightweight LLM NLU (Fallback)

When rules are insufficient (long, messy, mixed-language phrases), use
a **small model** (e.g., GPT-4o-mini or Qwen 2.5 7B) with a constrained
JSON output format:

```jsonc
{
  "intent": "BROWSE_PRODUCTS",
  "confidence": 0.86,
  "slots": {
    "category": "electronics",
    "budget_max": 50000
  },
  "language": ["sw", "sheng"],
  "needs_clarification": false
}
```

The prompt must:

- List all allowed intents
- Explicitly forbid inventing any products or policies
- Treat phone numbers, OTP-like codes, and payment confirmations carefully
- Prefer `UNKNOWN` over guessing

## 2.5 Context-Aware Intent Adjustment

The Intent Engine has access to:

- Last intent
- `ConversationContext.current_flow` (e.g., `booking`, `checkout`)
- `awaiting_response` flag
- `last_question`

Examples:

- If the bot just asked, “Which of these services do you want?”, and the user
  says “Pedicure” → treat as `SERVICE_DETAILS` or selection, not a new flow.
- If the bot asked “Do you want to pay by M-Pesa or card?” and user says
  “M-Pesa” → treat as `PAYMENT_HELP` with `payment_method="mpesa"`.

## 2.6 Anti-Hallucination Guardrails

- If the LLM returns an intent that would require products/services but
  the tenant has **none**, the router should:
  - Respond with a graceful message (“This store has no products yet”)
  - Offer human handoff
- If LLM confidence < threshold (e.g. 0.65):
  - Either ask a clarification question
  - Or route to `UNKNOWN` / `REQUEST_HUMAN` depending on tenant config

## 2.7 Output API

Provide a clear Python API:

```python
@dataclass
class IntentResult:
    intent: str
    confidence: float
    slots: dict
    language: list[str]
    needs_clarification: bool

def detect_intent(message: str, context: "ConversationContext") -> IntentResult:
    ...
```

The Business Logic Router will use this `IntentResult` to drive all flows.
