# 24 — Security Model

- All sensitive keys encrypted at rest:
  - Twilio
  - Payment providers
  - LLM providers
- Strict tenant scoping on every query.
- JWT / API-key-based authentication for dashboards & APIs.
- No direct cross-tenant joins.
- Audit logging for:
  - Payment events
  - Role/permission changes
  - LLM usage per tenant.
