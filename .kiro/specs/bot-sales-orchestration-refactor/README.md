# Bot Sales Orchestration Refactor

## Overview

This spec defines a fundamental refactor of the Tulia AI (Tulia AI) conversational bot from a hallucination-prone, LLM-heavy system into a deterministic, sales-oriented agent. The new architecture implements a hybrid approach where deterministic business logic handles all critical decisions, and LLMs serve only as a thin NLU (Natural Language Understanding) and formatting layer.

## Key Objectives

1. **Eliminate hallucinations** - Never invent products, prices, or policies
2. **Minimize LLM costs** - Keep usage under $10/tenant/month
3. **Improve conversion rates** - Shorten path from enquiry to sale/booking
4. **Ensure predictability** - Use deterministic business logic for all critical flows
5. **Maintain quality** - Provide accurate, grounded information from actual data

## Architecture Highlights

### Hybrid Approach
- **Deterministic business logic** for products, orders, payments, bookings
- **Rule-based intent classification** for 60-80% of messages
- **Small LLMs only** (GPT-4o-mini, Qwen 2.5 7B, Gemini Flash) for NLU and formatting
- **RAG pipeline** for grounded FAQ answers from tenant documents

### Core Components
1. **Intent Detection Engine** - Rule-first classification with LLM fallback
2. **Business Logic Router** - Maps intents to deterministic handlers
3. **Conversation Context Manager** - Tracks flow state and references
4. **Payment Orchestration** - M-Pesa STK, manual M-Pesa, card payments
5. **RAG Pipeline** - Grounded answers from Pinecone-indexed documents
6. **Multi-Model LLM Router** - Cost-optimized model selection
7. **WhatsApp Message Formatter** - Rich interactive messages

### Intent Schema
- GREET, BROWSE_PRODUCTS, BROWSE_SERVICES
- PRODUCT_DETAILS, SERVICE_DETAILS
- PLACE_ORDER, BOOK_APPOINTMENT
- CHECK_ORDER_STATUS, CHECK_APPOINTMENT_STATUS
- ASK_DELIVERY_FEES, ASK_RETURN_POLICY
- PAYMENT_HELP, REQUEST_HUMAN
- GENERAL_FAQ, SMALL_TALK, UNKNOWN

## Key Features

### Product & Service Flows
- Immediate product display without narrowing
- Numeric menu selection (1, 2, 3...)
- WhatsApp rich messages (lists, buttons, cards)
- Complete purchase flow: browse → select → order → pay
- Service appointment booking with availability checking

### Payment Support
- M-Pesa STK Push
- M-Pesa Manual (Paybill/Till)
- Card payments (Paystack, Stripe, Pesapal)
- Webhook callback processing
- Payment confirmation messages

### Intelligence Layer
- Rule-based intent classification (60-80% of messages)
- Small LLM fallback for ambiguous messages
- RAG-powered FAQ answers from tenant documents
- Language detection (English, Swahili, Sheng)
- Conversation context tracking

### Cost Optimization
- Rule-first approach minimizes LLM calls
- Small models only (GPT-4o-mini, Qwen, Gemini Flash)
- Conversation summaries instead of full history
- Cached FAQ answers
- Budget enforcement and throttling

## Implementation Phases

### Phase 1: Foundation (Weeks 1-2)
- Database models and migrations
- Intent Detection Engine
- Conversation Context Manager
- Business Logic Router framework

### Phase 2: Core Flows (Weeks 3-4)
- Product browsing and selection
- Order creation and payment
- Appointment booking
- Status checking

### Phase 3: Intelligence Layer (Weeks 5-6)
- Multi-Model LLM Router
- RAG Pipeline
- Language detection
- Slot extraction

### Phase 4: Polish & Optimization (Weeks 7-8)
- WhatsApp rich messages
- Error handling
- Business hours
- Cost tracking
- Performance optimization
- Testing and documentation

## Testing Strategy

### Unit Tests
- Intent classification (rule-based and LLM)
- Business logic handlers
- Payment flows
- RAG pipeline
- Context management

### Property-Based Tests (56 properties)
- Database grounding
- Rule-based efficiency
- Tenant isolation
- Payment integrity
- RAG grounding
- Language consistency
- And 50 more...

### Integration Tests
- End-to-end product purchase flow
- End-to-end appointment booking flow
- FAQ with RAG
- Multi-tenant isolation
- Payment callbacks

### Performance Tests
- Response time <1.5s for rule-based flows
- Response time <3s for LLM-based flows
- Database query performance
- Cache hit rates

### Cost Tests
- LLM usage under $10/tenant/month
- Token counting accuracy
- Budget enforcement

## Success Metrics

- **Hallucination rate**: 0% (all data from database/RAG)
- **LLM cost**: <$10/tenant/month on Starter tier
- **Rule-based classification**: 60-80% of messages
- **Response time**: <1.5s for rule-based, <3s for LLM-based
- **Conversion rate**: Measurable improvement in enquiry → sale
- **Payment success rate**: >95%

## Getting Started

1. Review the [requirements document](requirements.md) for detailed acceptance criteria
2. Study the [design document](design.md) for architecture and component interfaces
3. Follow the [implementation plan](tasks.md) for step-by-step coding tasks
4. Run tests frequently to ensure correctness
5. Monitor LLM costs and optimize as needed

## Key Principles

1. **LLM is not the source of truth** - Only database and RAG documents are authoritative
2. **Never invent data** - Products, prices, policies must come from actual sources
3. **Small models only** - Use GPT-4o-mini, Qwen, or Gemini Flash exclusively
4. **Intent-driven routing** - Use constrained intent schema with deterministic handlers
5. **Short, focused responses** - Guide customers to next action quickly
6. **Tenant isolation** - All queries are tenant-scoped

## Documentation

- [Requirements](requirements.md) - User stories and acceptance criteria
- [Design](design.md) - Architecture, components, and correctness properties
- [Tasks](tasks.md) - Implementation plan with 32 tasks

## Status

**Spec Status**: ✅ Complete and ready for implementation

**Next Steps**:
1. Review and approve the spec
2. Begin Phase 1 implementation
3. Set up monitoring and cost tracking
4. Execute tasks incrementally
5. Test thoroughly at each checkpoint

---

**Created**: 2025-11-21
**Feature Name**: bot-sales-orchestration-refactor
**Estimated Duration**: 8 weeks
**Priority**: High
**Dependencies**: Existing Django/DRF backend, Celery, Redis, PostgreSQL, Twilio, Pinecone
