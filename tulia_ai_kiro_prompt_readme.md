# Tulia AI Conversational Agent Refactor – Kiro Backend Prompt

## 1. Project Context
You are working on **Tulia AI** (codebase may still use the name `WabotIQ`), a **multi-tenant WhatsApp commerce & services platform** built with Django + DRF, Celery, Redis, PostgreSQL, Twilio WhatsApp, LangChain & Pinecone.

The current bot behavior is hallucination-heavy and not optimized for sales/booking flows.  
This document instructs Kiro to refactor the system into a deterministic, sales-oriented agent.

---

## 2. Primary Objective
Transform the current WhatsApp AI agent into a **conversion-focused digital salesperson** that:

- Shortens the path from *enquiry → sale/booking*
- Uses deterministic logic first; LLM only when needed
- Never hallucinates products/services/prices
- Supports payments (M-Pesa, Paystack, Stripe, Pesapal)
- Uses per-tenant configuration without per-tenant model training
- Maintains cost < **$10 per tenant per month** on Starter tier

---

## 3. Core Design Principles

### 3.1 Orchestration > LLM  
LLM is only for:
- Intent & slot extraction
- Natural language formatting (EN/SW/Sheng)
- FAQ + RAG answer generation

Business logic must be deterministic.

### 3.2 Avoid LLM When Possible
Use rules for:
- Numeric selection (“1”, “2”, etc.)
- Yes/No responses
- WhatsApp button/list payloads
- Standard confirmations

### 3.3 LLM Must Be Grounded  
No invented catalog or policies.  
All data must come from:
- Database (products, services, appointments)
- RAG chunks (Tenant docs)
- Payment provider configurations
- Business rules

### 3.4 No Per-Tenant Big Model Training  
Use shared small models.  
Customize via:
- `TenantSettings`
- `AgentConfiguration`
- Pinecone namespace

### 3.5 Token & Cost Efficiency
- Use small models by default (GPT-4o-mini / Gemini Flash / Qwen 7B)
- Use conversation summaries, not full history
- Cache FAQ responses where possible
- Limit LLM usage to only required steps

---

## 4. Intent Schema & Slots

### Supported Intents
```
BROWSE_PRODUCTS
BROWSE_SERVICES
BOOK_APPOINTMENT
PLACE_ORDER
CHECK_ORDER_STATUS
CHECK_APPOINTMENT_STATUS
ASK_DELIVERY_FEES
ASK_RETURN_POLICY
GENERAL_FAQ
PAYMENT_HELP
REQUEST_HUMAN
SMALL_TALK
UNKNOWN
```

### Slot Examples
- `BROWSE_PRODUCTS`: category, brand, budget_min, budget_max, size, color  
- `BOOK_APPOINTMENT`: service_name, date, time  
- `PLACE_ORDER`: product_id, quantity, variant, location  
- `PAYMENT_HELP`: payment_method

Implement:

```python
def classify_intent_and_extract_slots(tenant, context, message, language) -> IntentResult:
    ...
```

---

## 5. Conversation Orchestration & State Machine

Use `ConversationContext` to store:

- `current_intent`
- `last_question`
- `awaiting_response`
- `state_machine_state`
- `metadata` (e.g., pending product IDs)

Implement:

```python
def handle_inbound_message(tenant, customer, message: Message) -> BotResponse:
    ...
```

Flow:

1. If conversation is inside an active flow → handle deterministically  
2. Else → run NLU to determine new intent  
3. Route to business logic handler  
4. Update `ConversationContext`  
5. Return structured response

---

## 6. Deterministic Menu Handling

### Numeric Selection
If user replies `1`, `2`, etc.:
- Map directly to `metadata.last_menu`
- No LLM call

### Yes/No Matching
Use rule-based EN/SW/Sheng synonyms.

### Interactive Messages
Use Twilio payload → exact product/service/time slot selection.

---

## 7. Product → Order → Payment Flow

### 1. Browse Products
- Query DB filtered by tenant  
- Return 5–10 best matches  
- Store `last_menu`

### 2. Product Selection
- Resolve via number/text/button  
- Collect required fields (size/color)

### 3. Create Order
Status: `pending_payment`

### 4. Payment Options
Show:

1. M-Pesa STK  
2. M-Pesa manual (paybill/till)  
3. Card payment link (Paystack/Stripe/Pesapal)

### 5. Payment Flow
- STK: ask number → initiate → await callback  
- Manual: share details  
- Card: generate link  

### 6. Callbacks
On payment success:
- Mark order as `paid`
- Notify customer via WhatsApp

---

## 8. Service → Appointment Flow

### Browse Services  
- Show list  
- Store menu  

### Select Service  
- Ask for time slot  
- Confirm appointment  

### Optional Payment  
Reuse product payment flow.

---

## 9. RAG & FAQ Behavior

For intents like `ASK_RETURN_POLICY`:
- Retrieve tenant documents
- Provide answer **only** from retrieved chunks  
- If unknown → admit uncertainty + offer human help

---

## 10. LLM Efficiency Strategy

- Use smallest model that meets accuracy  
- Cap context  
- Use summary + last N messages  
- Cache reusable results  
- Log token usage per tenant  

---

## 11. Technical Deliverables

Implement or refactor:

### NLU Module
- Intent classification  
- Slot extraction  

### Orchestration Engine
- State machine  
- Flow control  

### Business Handlers
- Product browsing  
- Service listing  
- Appointment booking  
- Order creation  
- Payment initiation  
- FAQ retrieval  

### Payment Integration
Unified interface for:
- M-Pesa  
- Paystack  
- Stripe  
- Pesapal  

### Tests
- NLU accuracy  
- Menu selection logic  
- Order & payment flow  
- Appointment flow  
- FAQ grounding tests  
- Anti-hallucination tests  

---

## 12. Acceptance Criteria

The bot must:

- Never hallucinate products/services/prices  
- Correctly handle “I want to buy X” end-to-end  
- Correctly handle “Nataka pedicure leo” end-to-end  
- Use LLM *only* for NLU + natural language  
- Use deterministic logic for menus & confirmations  
- Send correct payment links / STK prompts  
- Confirm payment via callback  
- Maintain cost < $10/tenant/month on Starter  

If all above pass, the refactor is **done**.

---

This document is the authoritative specification for Kiro.  
It defines exactly what to build and how the system must behave.
