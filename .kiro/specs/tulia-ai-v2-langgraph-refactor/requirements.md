# Requirements Document

## Introduction

Tulia AI V2 is a complete architectural transformation of the existing WhatsApp Sales & Support Agent system. The system must be rebuilt as a LangGraph-orchestrated, tool-driven, stateful commerce agent with strict tenant isolation, predictable behavior, and safe autonomy. The primary purpose is to convert conversations into revenue while handling customer support, order enquiries, preferences, and consent. This is explicitly NOT a chatbot - it is a journey-driven commerce agent with no backward compatibility requirements. The system must be implemented following a specific 5-phase build order with absolute non-negotiables that cannot be violated.

## Glossary

- **Tulia_AI_System**: The complete LangGraph-orchestrated WhatsApp commerce agent
- **LangGraph_Orchestrator**: The core state machine that manages all conversation flows and business logic
- **Conversation_State**: The explicit shared state object that tracks all conversation context and progress
- **Journey**: A specific business workflow (Sales, Support, Orders, Preferences) with defined steps and outcomes
- **Tool_Contract**: Backend service interfaces that provide authoritative business data and operations
- **Tenant_Scope**: Strict data isolation ensuring no cross-tenant data leakage
- **Commerce_Agent**: A stateful agent focused on business outcomes, not general conversation
- **Conversation_Governor**: The component responsible for cost control, spam detection, and conversation boundaries

## Requirements

### Requirement 1

**User Story:** As a business owner, I want a WhatsApp agent that converts conversations into sales autonomously, so that I can generate revenue without manual intervention.

#### Acceptance Criteria

1. WHEN a customer initiates a WhatsApp conversation, THE Tulia_AI_System SHALL route the message through LangGraph_Orchestrator to determine appropriate journey
2. WHEN the system identifies sales intent, THE Tulia_AI_System SHALL guide the customer through product discovery, selection, order creation, and payment completion
3. WHEN payment is required, THE Tulia_AI_System SHALL initiate payment via backend tools and confirm completion before order fulfillment
4. WHEN an order is completed, THE Tulia_AI_System SHALL update order status and provide confirmation to the customer
5. THE Tulia_AI_System SHALL never invent prices, discounts, or payment statuses

### Requirement 2

**User Story:** As a system architect, I want all conversation logic orchestrated through LangGraph, so that behavior is predictable and maintainable.

#### Acceptance Criteria

1. THE Tulia_AI_System SHALL process every incoming WhatsApp message through LangGraph_Orchestrator state machine
2. THE Tulia_AI_System SHALL maintain explicit Conversation_State containing tenant_id, customer_id, journey, step, intent, language, selected_items, cart, order_id, payment_status, consent_flags, and escalation_required
3. WHEN transitioning between conversation steps, THE LangGraph_Orchestrator SHALL update Conversation_State explicitly
4. THE Tulia_AI_System SHALL never rely on implicit context or prompt engineering for business logic
5. IF state information is not explicitly tracked, THE Tulia_AI_System SHALL treat it as unknown

### Requirement 3

**User Story:** As a tenant, I want complete data isolation from other tenants, so that my customer data and business information remains private and secure.

#### Acceptance Criteria

1. THE Tulia_AI_System SHALL enforce tenant isolation at the architectural level through data scoping
2. WHEN identifying customers, THE Tulia_AI_System SHALL use composite key (tenant_id, phone_e164) with no global customer identity
3. WHEN accessing vector databases, THE Tulia_AI_System SHALL use tenant-scoped namespaces
4. WHEN calling backend tools, THE Tulia_AI_System SHALL always include tenant_id parameter
5. THE Tulia_AI_System SHALL never mix tenant data in memory, storage, or processing

### Requirement 4

**User Story:** As a customer, I want the agent to provide accurate business information from authoritative sources, so that I can make informed purchasing decisions.

#### Acceptance Criteria

1. WHEN providing product information, THE Tulia_AI_System SHALL retrieve data exclusively from backend Tool_Contracts
2. WHEN answering support questions, THE Tulia_AI_System SHALL use tenant-scoped RAG from approved documents
3. WHEN checking order status, THE Tulia_AI_System SHALL query backend systems for current information
4. THE Tulia_AI_System SHALL never generate or hallucinate business facts, prices, availability, or order details
5. IF authoritative information is unavailable, THE Tulia_AI_System SHALL escalate to human support

### Requirement 5

**User Story:** As a customer with a large product catalog, I want efficient product discovery without overwhelming information, so that I can find relevant items quickly.

#### Acceptance Criteria

1. WHEN presenting product options, THE Tulia_AI_System SHALL return maximum 3-6 options per response
2. WHEN catalog narrowing fails, THE Tulia_AI_System SHALL provide tenant-hosted catalog link with deep-linking capability
3. WHEN customer returns from web catalog, THE Tulia_AI_System SHALL resume conversation with selected product context
4. THE Tulia_AI_System SHALL use semantic search combined with structured filters for product discovery
5. THE Tulia_AI_System SHALL never dump complete catalogs into WhatsApp messages

### Requirement 6

**User Story:** As a customer, I want to interact in my preferred language, so that I can communicate naturally and understand responses clearly.

#### Acceptance Criteria

1. THE Tulia_AI_System SHALL support English (default), Swahili, and Sheng languages
2. WHEN detecting language preference, THE Tulia_AI_System SHALL switch only with high confidence
3. WHEN language confidence is low, THE Tulia_AI_System SHALL maintain tenant's default language
4. THE Tulia_AI_System SHALL store and respect customer language preferences across conversations
5. THE Tulia_AI_System SHALL allow controlled language mixing within conversations

### Requirement 7

**User Story:** As a business owner, I want the agent to handle payments securely through established providers, so that transactions are reliable and compliant.

#### Acceptance Criteria

1. WHEN initiating payments, THE Tulia_AI_System SHALL support MPESA C2B instructions, MPESA STK push, and card payments via PesaPal
2. WHEN processing payments, THE Tulia_AI_System SHALL use backend Tool_Contracts exclusively
3. WHEN confirming payment amounts, THE Tulia_AI_System SHALL verify with customer before initiating payment
4. WHEN checking payment status, THE Tulia_AI_System SHALL query backend systems for authoritative status
5. THE Tulia_AI_System SHALL never simulate or guess payment outcomes

### Requirement 8

**User Story:** As a business owner, I want the agent to control conversation costs and prevent abuse, so that operational expenses remain manageable.

#### Acceptance Criteria

1. WHEN detecting casual or spam intent, THE Conversation_Governor SHALL politely redirect to business purposes
2. WHEN spam persists, THE Conversation_Governor SHALL gracefully disengage from conversation
3. WHEN rate limits are exceeded, THE Tulia_AI_System SHALL enforce per-customer per-tenant limits
4. THE Conversation_Governor SHALL detect and limit chatty behavior while maintaining friendliness
5. THE Tulia_AI_System SHALL use cost-effective models for intent classification and language detection

### Requirement 9

**User Story:** As a customer, I want to manage my communication preferences and consent, so that I control how the business contacts me.

#### Acceptance Criteria

1. WHEN customer requests opt-out, THE Tulia_AI_System SHALL immediately process STOP/UNSUBSCRIBE commands
2. WHEN managing preferences, THE Tulia_AI_System SHALL handle language, marketing opt-in/out, and notification settings
3. WHEN consent is withdrawn, THE Tulia_AI_System SHALL update tenant-scoped consent flags immediately
4. THE Tulia_AI_System SHALL maintain auditable consent records for compliance
5. THE Tulia_AI_System SHALL respect consent flags in all future interactions

### Requirement 10

**User Story:** As a system administrator, I want comprehensive observability and error handling, so that I can monitor system health and resolve issues quickly.

#### Acceptance Criteria

1. WHEN errors occur, THE Tulia_AI_System SHALL log detailed context including tenant_id, customer_id, journey, and step
2. WHEN escalation is required, THE Tulia_AI_System SHALL provide clear escalation reasons and conversation context
3. WHEN system components fail, THE Tulia_AI_System SHALL gracefully degrade and maintain conversation continuity
4. THE Tulia_AI_System SHALL provide metrics on journey completion rates, payment success, and escalation frequency
5. THE Tulia_AI_System SHALL integrate with monitoring systems for real-time alerting

### Requirement 11

**User Story:** As a system architect, I want the system built in a specific phased approach, so that foundational components are solid before building dependent features.

#### Acceptance Criteria

1. WHEN implementing Phase 1 Foundations, THE Tulia_AI_System SHALL establish tenant-scoped customer identity model, tool contracts, vector DB namespaces, and ConversationState schema
2. WHEN implementing Phase 2 Orchestration, THE Tulia_AI_System SHALL set up LangGraph with intent classification, journey routing, and governance nodes
3. WHEN implementing Phase 3 Core Journeys, THE Tulia_AI_System SHALL build Sales, Orders, Support, and Preferences journeys in sequence
4. WHEN implementing Phase 4 UX Controls, THE Tulia_AI_System SHALL add product narrowing, catalog fallbacks, and rate limiting
5. WHEN implementing Phase 5 Hardening, THE Tulia_AI_System SHALL complete escalation rules, error handling, and observability

### Requirement 12

**User Story:** As a developer, I want explicit removal of legacy chatbot patterns, so that the new system maintains architectural integrity.

#### Acceptance Criteria

1. THE Tulia_AI_System SHALL remove all direct LLM calls that bypass LangGraph orchestration
2. THE Tulia_AI_System SHALL remove all prompt-only logic flows and replace with tool-driven workflows
3. THE Tulia_AI_System SHALL remove all implicit tenant context and enforce explicit tenant_id parameters
4. THE Tulia_AI_System SHALL remove all cross-tenant memory or data sharing mechanisms
5. THE Tulia_AI_System SHALL remove all features not supporting sales, support, orders, payments, or consent management

### Requirement 13

**User Story:** As a business owner, I want the system to demonstrate autonomous commerce capability, so that I can validate the transformation success.

#### Acceptance Criteria

1. THE Tulia_AI_System SHALL complete full order workflows autonomously from intent to payment confirmation
2. THE Tulia_AI_System SHALL never invent or hallucinate prices, offers, or payment states
3. THE Tulia_AI_System SHALL respect tenant isolation and consent across all interactions
4. THE Tulia_AI_System SHALL behave predictably and consistently across all conversations
5. THE Tulia_AI_System SHALL escalate to humans only when necessary and with clear context