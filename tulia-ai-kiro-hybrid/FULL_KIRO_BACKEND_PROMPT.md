# FULL Kiro Backend Prompt – Tulia AI

You are Kiro, generating backend code for **Tulia AI**, a multi-tenant
WhatsApp commerce & customer-service engine.

## Objective

Implement a backend that:

- Shortens the path from **enquiry → sale/booking**
- Keeps LLM usage minimal and cheap
- Uses deterministic business logic to avoid hallucinations
- Supports products, services, bookings, payments
- Is fully multi-tenant and secure

## Core Rules

1. **LLM is not the source of truth.**
   - Only DB + RAG (docs) + payment callbacks are authoritative.
2. **Never invent products, services, or policies.**
3. **Use small models only** for NLU and RAG; avoid large models unless
   absolutely necessary.
4. **Use the intent engine + business router** pattern exactly as defined
   in:
   - `02_intent_classification.md`
   - `business_logic/03_business_logic_router.md`
5. **Keep responses short and focused on next action.**

## Implementation Expectations

- Use Django + DRF, Celery, Redis, PostgreSQL.
- Define:
  - Models for Tenant, Customer, ConversationContext, Message, Product,
    Service, Order, Appointment, PaymentRequest, AgentInteraction, etc.
  - Services modules for:
    - Intent detection
    - Business logic routing
    - RAG retrieval
    - Payment orchestration
  - DRF views for:
    - Webhooks (Twilio, payment providers)
    - Admin/tenant dashboards (basic)
  - Celery tasks for async workloads.

- Use the Markdown docs in this folder as **source-of-truth requirements**.
  Don’t invent new flows unless they are small glue pieces.

## Non-Functional Requirements

- Code must be readable and modular.
- Critical flows (payment, bookings, orders) must be unit-testable.
- Avoid vendor lock-in where possible (e.g. payment/LLM providers wrapped
  in adapters).
- Respect rate limits and quiet hours per tenant.

## Output

When generating code, Kiro should:

- Create a Django project with modular apps (`bot`, `catalog`, `services`,
  `orders`, `payments`, `integrations`, `tenants`, etc.).
- Include:
  - Models
  - Serializers
  - Views
  - URLs
  - Services
  - Tasks
  - Basic tests for main paths
- Avoid dumping everything in one giant file; keep responsibilities separate.

This spec, plus the other Markdown files in this ZIP, define the contract
for how the autonomous agent must behave.
