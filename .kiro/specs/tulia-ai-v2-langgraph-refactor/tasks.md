# Implementation Plan

## Phase 1 — Foundations

- [ ] 1. Set up tenant-scoped customer identity model
  - Create enhanced Tenant model with bot persona fields (bot_name, tone_style, default_language, allowed_languages, max_chattiness_level, payment_methods_enabled, escalation_rules)
  - Create tenant-scoped Customer model with composite key (tenant_id, phone_e164) and consent fields
  - Implement customer identification using composite key with no global customer identity
  - Add language preference, marketing opt-in, tags, and consent flags to Customer model
  - _Requirements: 3.2, 6.4, 9.2, 9.4_

- [ ] 2. Implement ConversationState schema and management
  - Create canonical ConversationState dataclass with exact fields from design: tenant_id, conversation_id, request_id, customer_id, phone_e164, tenant_name, bot_name, bot_intro, tone_style, default_language, allowed_languages, max_chattiness_level, catalog_link_base, payments_enabled, compliance, handoff, customer_language_pref, marketing_opt_in, notification_prefs, intent, intent_confidence, journey, response_language, language_confidence, governor_classification, governor_confidence, last_catalog_query, last_catalog_filters, last_catalog_results, catalog_total_matches_estimate, selected_item_ids, cart, order_id, order_totals, payment_request_id, payment_status, kb_snippets, escalation_required, escalation_reason, handoff_ticket_id, turn_count, casual_turns, spam_turns, response_text
  - Implement Intent, Journey, Lang, GovernorClass literal types as specified
  - Implement state serialization/deserialization for persistence
  - Create ConversationSession model for state storage
  - Add state validation to ensure required fields are present
  - _Requirements: 2.2, 2.3, 2.5_

- [ ] 3. Create tool contracts with strict tenant isolation
  - Implement all 15 tool contracts with exact JSON schemas: tenant_get_context, customer_get_or_create, customer_update_preferences, catalog_search, catalog_get_item, order_create, offers_get_applicable, order_apply_coupon, payment_get_methods, payment_get_c2b_instructions, payment_initiate_stk_push, payment_create_pesapal_checkout, order_get_status, kb_retrieve, handoff_create_ticket
  - Ensure all tools require tenant_id, request_id, conversation_id parameters
  - Implement tenant-scoped data access in all tool implementations
  - Add input validation and error handling for all tools
  - _Requirements: 3.1, 3.4, 4.1, 4.2, 4.3_

- [ ]* 3.1 Write property test for tenant isolation
  - **Property 3: Tenant Isolation Enforcement**
  - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

- [ ] 4. Set up vector database with tenant namespaces
  - Configure vector database with tenant-scoped namespaces
  - Implement tenant-scoped document ingestion for PDF, DOCX, text files
  - Create TenantDocument model with vector embeddings and document types
  - Implement kb_retrieve tool with tenant namespace filtering
  - _Requirements: 3.3, 4.2_

- [ ]* 4.1 Write property test for vector DB tenant scoping
  - **Property 3: Tenant Isolation Enforcement (Vector DB component)**
  - **Validates: Requirements 3.3**

## Phase 2 — Orchestration

- [ ] 5. Set up LangGraph core infrastructure
  - Install and configure LangGraph dependencies
  - Create base LangGraph application structure
  - Implement ConversationState as LangGraph state schema
  - Set up node registration and routing infrastructure
  - Create webhook entry point that initializes LangGraph execution
  - _Requirements: 2.1, 1.1_

- [ ]* 5.1 Write property test for LangGraph orchestration
  - **Property 1: LangGraph Orchestration Universality**
  - **Validates: Requirements 1.1, 2.1**

- [ ] 6. Implement intent classification node
  - Create intent_classify LLM node with JSON output schema: {"intent": "...", "confidence": 0-1, "notes": "short", "suggested_journey": "sales|support|orders|offers|prefs|governance"}
  - Implement intent classification with confidence scoring
  - Support exact intents: sales_discovery, product_question, support_question, order_status, discounts_offers, preferences_consent, payment_help, human_request, spam_casual, unknown
  - Add routing logic with EXACT thresholds: IF confidence >= 0.70 THEN route to suggested_journey; IF 0.50 <= confidence < 0.70 THEN ask ONE clarifying question then re-classify; IF confidence < 0.50 THEN route to unknown handler
  - _Requirements: 1.1, 2.1_

- [ ] 7. Implement language policy node
  - Create language_policy LLM node with JSON output schema: {"response_language": "en|sw|sheng|mixed", "confidence": 0-1, "should_ask_language_question": true|false}
  - Implement language detection with confidence scoring
  - Support exact languages: English (default), Swahili, Sheng
  - Add language switching logic with EXACT threshold: IF confidence >= 0.75 AND language in allowed_languages THEN switch; IF confidence < 0.75 THEN use tenant.default_language
  - Respect customer language preferences (override if explicitly set) and tenant defaults
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [ ]* 7.1 Write property test for language policy compliance
  - **Property 8: Language Policy Compliance**
  - **Validates: Requirements 6.2, 6.3**

- [ ] 8. Implement conversation governor node
  - Create governor_spam_casual LLM node with JSON output schema: {"classification": "business|casual|spam|abuse", "confidence": 0-1, "recommended_action": "proceed|redirect|limit|stop|handoff"}
  - Implement business vs casual/spam classification
  - Add chattiness control with EXACT levels: Level 0 (strictly business), Level 1 (1 short greeting), Level 2 (max 2 casual turns - DEFAULT), Level 3 (max 4 casual turns)
  - Implement EXACT routing: IF classification == "business" THEN proceed; IF "casual" THEN increment casual_turns, allow max per level before redirect; IF "spam" THEN increment spam_turns, after 2 turns disengage; IF "abuse" THEN stop immediately
  - Implement rate limiting per customer per tenant
  - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [ ]* 8.1 Write property test for conversation governance
  - **Property 9: Conversation Governance**
  - **Validates: Requirements 8.1, 8.2, 8.3, 8.4**

- [ ] 9. Create journey router with exact routing conditions
  - Implement journey routing based on intent classification results
  - Add routing to sales, support, orders, offers, preferences, governance subgraphs
  - Implement unknown intent handler with clarification prompts
  - Add journey transition logic with state updates
  - _Requirements: 2.1, 2.3_

## Phase 3 — Core Journeys

- [ ] 10. Implement Sales Journey subgraph
  - Create sales_narrow_query LLM node for catalog search or clarification
  - Implement catalog_search tool integration with semantic search and filters
  - Create catalog_present_options LLM node with WhatsApp formatting (max 6 items)
  - Implement product selection and catalog_get_item tool integration
  - Create product_disambiguate LLM node for order preparation
  - Integrate order_create tool with cart management
  - _Requirements: 1.2, 5.1, 5.4, 5.5, 13.1_

- [ ]* 10.1 Write property test for complete sales journey
  - **Property 5: Complete Sales Journey Execution**
  - **Validates: Requirements 1.2, 13.1**

- [ ]* 10.2 Write property test for product discovery constraints
  - **Property 6: Product Discovery Constraints**
  - **Validates: Requirements 5.1, 5.5**

- [ ] 11. Implement Orders Journey subgraph
  - Create order_get_status tool integration
  - Implement order_status_response LLM node for status summaries
  - Add order lookup by reference and customer
  - Handle multiple orders with disambiguation
  - _Requirements: 4.3, 13.1_

- [ ] 12. Implement Support Journey subgraph with RAG
  - Create kb_retrieve tool integration with tenant-scoped vector search
  - Implement support_rag_answer LLM node with strict grounding
  - Add escalation logic when information is insufficient
  - Integrate handoff_create_ticket tool for human escalation
  - Create handoff_message LLM node for escalation communication
  - _Requirements: 4.2, 4.5, 10.2_

- [ ]* 12.1 Write property test for escalation context preservation
  - **Property 12: Escalation Context Preservation**
  - **Validates: Requirements 4.5, 10.2**

- [ ] 13. Implement Preferences & Consent Journey subgraph
  - Create preference parsing logic for language, marketing, notifications
  - Implement customer_update_preferences tool with audit trail
  - Create prefs_consent_response LLM node for confirmation messages
  - Add immediate STOP/UNSUBSCRIBE processing
  - Implement consent flag enforcement across all interactions
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ]* 13.1 Write property test for immediate consent processing
  - **Property 10: Immediate Consent Processing**
  - **Validates: Requirements 9.1, 9.3**

- [ ]* 13.2 Write property test for consent enforcement consistency
  - **Property 11: Consent Enforcement Consistency**
  - **Validates: Requirements 9.4, 9.5**

## Phase 4 — UX & Cost Controls

- [ ] 14. Implement product narrowing logic and catalog fallback
  - Add catalog link generation with EXACT conditions: Show catalog link when ANY is true: (catalog_total_matches_estimate >= 50 AND user still vague after 1 clarifying question) OR user asks "see all items/catalog/list everything" OR results are low confidence (no clear top 3) OR product selection requires visuals/variants beyond WhatsApp UX OR repeated loop (user rejects 2 shortlists in a row)
  - Implement deep-linking capability for web catalog returns with tenant_id + product_id
  - Create fallback logic for low confidence results
  - Enforce WhatsApp shortlist rule: NEVER show more than 6 items in single reply
  - Handle "see all items" requests with catalog links
  - _Requirements: 5.2, 5.3_

- [ ]* 14.1 Write property test for catalog fallback behavior
  - **Property 15: Catalog Fallback Behavior**
  - **Validates: Requirements 5.2, 5.3**

- [ ] 15. Implement payment processing with secure handling
  - Create payment_get_methods tool integration
  - Implement payment_router_prompt LLM node for method selection
  - Add payment_initiate_stk_push tool for MPESA STK
  - Implement payment_get_c2b_instructions tool for C2B payments
  - Create payment_create_pesapal_checkout tool for card payments
  - Add amount confirmation before all payment initiations
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ]* 15.1 Write property test for secure payment processing
  - **Property 7: Secure Payment Processing**
  - **Validates: Requirements 7.2, 7.3, 7.4, 7.5**

- [ ] 16. Implement offers and coupons handling
  - Create offers_get_applicable tool integration
  - Implement offers_answer LLM node without offer invention
  - Add order_apply_coupon tool for coupon application
  - Integrate with payment flow for discounted orders
  - _Requirements: 4.4, 13.2_

- [ ] 17. Add chattiness limits and rate limiting
  - Implement per-customer per-tenant rate limiting
  - Add casual turn counting and redirect logic
  - Create business re-anchoring responses
  - Implement spam turn limits with graceful disengagement
  - _Requirements: 8.1, 8.2, 8.3, 8.4_

## Phase 5 — Hardening

- [ ] 18. Implement comprehensive error handling
  - Add graceful degradation for tool failures
  - Implement circuit breaker pattern for external services
  - Create retry logic with exponential backoff
  - Add conversation continuity during component failures
  - Implement fallback responses for all error scenarios
  - _Requirements: 10.1, 10.3_

- [ ]* 18.1 Write property test for graceful failure handling
  - **Property 13: Graceful Failure Handling**
  - **Validates: Requirements 10.1, 10.3**

- [ ] 19. Add escalation rules and human handoff
  - Implement EXACT escalation triggers (escalate immediately if ANY is true): user explicitly asks for human ("agent", "human", "call me") OR payment disputes ("I paid but..."), chargebacks, refunds, delivery complaints beyond policy OR missing authoritative info after RAG/tool attempts (unclear order lookup) OR repeated failures (2 consecutive tool errors OR 3 clarification loops) OR sensitive/legal/medical content (tenant policy) OR user frustration detected + failure to resolve in 2 turns
  - Create handoff_create_ticket tool with context snapshots including tenant_id, customer_id, journey, step
  - Add escalation reason tracking and context preservation
  - Implement handoff_message responses with expected timelines
  - _Requirements: 4.5, 10.2, 13.5_

- [ ] 20. Implement comprehensive logging and observability
  - Add structured logging with tenant_id, customer_id, journey, step context
  - Implement request_id tracking throughout conversation flow
  - Create metrics collection for journey completion rates, payment success, escalation frequency
  - Add performance monitoring for LLM nodes and tool calls
  - Integrate with monitoring systems for real-time alerting
  - _Requirements: 10.1, 10.4, 10.5_

- [ ]* 20.1 Write property test for behavioral consistency
  - **Property 14: Behavioral Consistency**
  - **Validates: Requirements 13.4**

- [ ] 21. Remove legacy chatbot patterns
  - Remove all direct LLM calls that bypass LangGraph orchestration
  - Replace prompt-only logic flows with tool-driven workflows
  - Remove implicit tenant context and enforce explicit tenant_id parameters
  - Remove cross-tenant memory and data sharing mechanisms
  - Remove features not supporting sales, support, orders, payments, or consent
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

- [ ]* 21.1 Write property test for no data hallucination
  - **Property 2: No Data Hallucination**
  - **Validates: Requirements 1.5, 4.1, 4.4, 7.2, 7.5, 13.2**

- [ ] 22. Final integration testing and validation
  - Test complete order workflows from intent to payment confirmation
  - Validate tenant isolation across all data paths
  - Test consent and preference enforcement
  - Verify catalog handling with large product sets
  - Validate payment processing with all supported methods
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

- [ ] 23. Checkpoint - Ensure all tests pass and system meets success criteria
  - Ensure all tests pass, ask the user if questions arise
  - Verify system can complete full order autonomously
  - Confirm system never invents prices, offers, or payment states
  - Validate tenant isolation and consent respect
  - Test predictable behavior across conversations
  - Confirm appropriate escalation with clear context