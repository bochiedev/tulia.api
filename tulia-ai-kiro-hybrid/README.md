# Tulia AI – Backend Spec for Kiro (Hybrid Layout)

This ZIP contains the **backend specification** for Tulia AI (formerly WabotIQ),
a multi-tenant WhatsApp commerce & customer service platform.

The docs are structured for:
- Kiro (backend automation)
- Human engineers (architecture & flows)
- Future collaborators

## File Layout (Hybrid)

Root:
- `01_system_overview.md` – High-level system architecture
- `02_intent_classification.md` – Intent schema & detection rules
- `FULL_KIRO_BACKEND_PROMPT.md` – Single-file master prompt for Kiro

Folders:
- `business_logic/` – Routers, state machine, core flows
- `ai/` – RAG pipeline, LLM router, minimization strategy
- `flows/` – Product, service, booking, payments & checkout flows
- `infra/` – Deployment, security, monitoring

This spec assumes:
- Django + DRF backend
- Celery + Redis
- PostgreSQL
- Twilio WhatsApp
- LangChain + Pinecone
- Multi-tenant design with strict tenant isolation
