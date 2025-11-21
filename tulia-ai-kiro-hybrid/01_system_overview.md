# 01 — System Overview

Tulia AI is a **multi-tenant WhatsApp commerce & service platform** that gives
businesses an autonomous agent which:

- Shortens the path from *enquiry → sale/booking*
- Works 24/7 in **English, Swahili, and Sheng**
- Does **not hallucinate** products, prices, or policies
- Handles orders, bookings, and payments (M-Pesa, Paystack, Stripe, Pesapal)
- Stays under **$10/month LLM cost per tenant** on the Starter tier

## 1.1 Core Principle

> Use deterministic business logic wherever possible, and use LLMs *only* as
> a thin NLU and language-formatting layer, never as the source of truth.

### LLM is allowed for:
- Intent & slot extraction when rules are not enough
- Language normalization / tone (EN/SW/Sheng mix)
- Free-form FAQ answers backed by RAG-only contexts

### LLM is *not* allowed for:
- Creating products, services, prices, discounts
- Inventing return/delivery policies
- Guessing timeslots or capacity
- Marking payments or orders as complete

## 1.2 High-Level Flow

```text
Customer (WhatsApp)
    ↓
Twilio Webhook → Tulia API (/v1/webhooks/twilio/inbound)
    ↓
Message Normalizer (language, noise filtering)
    ↓
Intent Engine (rules + optional small LLM)
    ↓
Business Logic Router
    ├─ Product / Service browse
    ├─ Order + Cart flows
    ├─ Appointment booking
    ├─ Order / appointment status
    ├─ Payment initiation & confirmation
    └─ FAQ / RAG responses
    ↓
Response Formatter (language, style, Sheng)
    ↓
WhatsApp Rich Message Builder (lists, buttons, cards)
    ↓
Twilio API → Customer
```

## 1.3 Key Components

- **Intent Engine** – Classifies messages into a constrained set of intents.
- **Business Logic Router** – Pure Python/DRF services mapping intent+context
  to deterministic actions.
- **RAG Pipeline** – Uses Pinecone + LangChain with tenant-specific
  namespaces for FAQs and business docs.
- **Multi-Model LLM Router** – Chooses the cheapest viable model for NLU /
  formatting (e.g., GPT-4o-mini, Qwen 2.5, Gemini Flash).
- **Payments Layer** – Implements M-Pesa STK, manual paybill/till flows,
  card payments (Paystack, Stripe, Pesapal) and processes callbacks.
- **Conversation Memory** – Tracks last N messages, key facts, and current
  flow state, expiring after 30 minutes of inactivity.

## 1.4 Tenant Isolation

- All DB queries are **tenant-scoped** (`tenant_id` FK everywhere).
- Pinecone uses **per-tenant namespaces** (`tenant_{uuid}`).
- Cache keys are prefixed by `tenant:{tenant_id}:...`.
- API keys, Twilio/M-Pesa/Stripe/Pesapal credentials are stored encrypted.

## 1.5 Non-Goals

- No per-tenant finetuning or large dedicated models.
- No generic chatbot behavior. Every response must stay inside the
  tenant’s business domain.
- No heavy conversation design tools like Rasa; Tulia relies on code-driven
  flows and a small, well-defined intent space.

## 1.6 Success Metrics

- Median reply latency < 1.5s (excluding payment callbacks).
- < 1% of messages require large LLMs; majority use rule-based or small NLU.
- Clear, short journeys from **“I want X” → payment link / STK**.
- Businesses see visible uplift in:
  - Conversion rate
  - Average order value
  - Repeat customers / appointments
