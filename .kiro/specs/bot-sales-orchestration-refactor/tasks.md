# Implementation Plan

- [x] 1. Set up project structure and core models
  - Create new database models: IntentClassificationLog, LLMUsageLog, PaymentRequest
  - Add new fields to ConversationContext model
  - Add new fields to AgentConfiguration model
  - Create and run database migrations
  - Update admin interfaces for new models
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 13.1, 13.2, 13.3, 14.1_

- [x] 2. Implement Intent Detection Engine
  - Create IntentDetectionEngine service class
  - Implement Intent enum with all predefined intents
  - Implement IntentResult dataclass
  - Implement rule-based classification with keyword patterns for EN/SW/Sheng
  - Implement numeric reply detection and resolution
  - Implement WhatsApp button/list payload processing
  - Implement context-aware intent adjustment
  - Implement LLM fallback classification with small models
  - Implement slot extraction with regex patterns
  - Implement confidence scoring and threshold handling
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4, 3.5_

- [ ]* 2.1 Write property test for rule-based classification efficiency
  - **Property 6: Rule-based intent classification efficiency**
  - **Validates: Requirements 2.1**

- [ ]* 2.2 Write property test for numeric selection efficiency
  - **Property 7: Numeric selection efficiency**
  - **Validates: Requirements 2.2, 6.1**

- [ ]* 2.3 Write property test for interactive message efficiency
  - **Property 8: Interactive message efficiency**
  - **Validates: Requirements 2.3, 6.2, 6.3**

- [ ]* 2.4 Write property test for small model constraint
  - **Property 10: Small model constraint**
  - **Validates: Requirements 2.5, 12.5**

- [ ]* 2.5 Write property test for intent schema constraint
  - **Property 11: Intent schema constraint**
  - **Validates: Requirements 3.1**

- [x] 3. Implement Conversation Context Manager
  - Create ConversationContextManager service class
  - Implement load_or_create() method
  - Implement update_from_action() method
  - Implement resolve_menu_reference() for numeric and positional references
  - Implement is_menu_expired() with TTL checking
  - Implement language detection and persistence
  - Implement conversation summary generation
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 19.1, 19.5_

- [ ]* 3.1 Write property test for menu reference resolution
  - **Property 23: Selection resolution**
  - **Validates: Requirements 6.1, 6.4**

- [ ]* 3.2 Write property test for context state updates
  - **Property 18: Context state updates**
  - **Validates: Requirements 4.4, 13.2, 13.3**

- [ ]* 3.3 Write property test for language persistence
  - **Property 56: Language persistence**
  - **Validates: Requirements 19.5**

- [x] 4. Implement Business Logic Router
  - Create BusinessLogicRouter service class
  - Implement BotAction dataclass
  - Implement route() method with intent-to-handler mapping
  - Create handler function signatures for all intents
  - Implement error handling and fallback logic
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [ ]* 4.1 Write property test for deterministic routing
  - **Property 15: Deterministic routing**
  - **Validates: Requirements 4.1**

- [ ]* 4.2 Write property test for handler output structure
  - **Property 16: Handler output structure**
  - **Validates: Requirements 4.2**

- [ ]* 4.3 Write property test for tenant-scoped queries
  - **Property 17: Tenant-scoped queries**
  - **Validates: Requirements 4.3, 15.1, 15.2, 15.3, 15.4**

- [x] 5. Implement Product Browsing Handler
  - Implement handle_browse_products() function
  - Query products with tenant scoping and filters
  - Handle category and budget filters from slots
  - Implement product display limit (10 products)
  - Store last_menu in context with product IDs and positions
  - Handle empty catalog gracefully
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ]* 5.1 Write property test for database-grounded product display
  - **Property 1: Database-grounded product display**
  - **Validates: Requirements 1.1, 5.1, 5.2**

- [ ]* 5.2 Write property test for product display limits
  - **Property 20: Product display limits**
  - **Validates: Requirements 5.2**

- [ ]* 5.3 Write property test for menu storage
  - **Property 21: Menu storage**
  - **Validates: Requirements 5.3, 13.2**

- [x] 6. Implement Product Selection and Order Creation Handler
  - Implement handle_product_details() function
  - Implement handle_place_order() function
  - Resolve product from menu reference
  - Ask for quantity and variants if needed
  - Create Order with PENDING_PAYMENT status
  - Validate product IDs and prices against database
  - Update context with current_flow = "checkout"
  - _Requirements: 6.1, 6.4, 6.5, 7.1, 7.2_

- [ ]* 6.1 Write property test for order integrity
  - **Property 3: Order integrity**
  - **Validates: Requirements 1.3, 7.2**

- [ ]* 6.2 Write property test for order creation flow
  - **Property 25: Order creation flow**
  - **Validates: Requirements 7.2**

- [x] 7. Implement Payment Orchestration Service
  - Create PaymentOrchestrationService class
  - Implement initiate_mpesa_stk() method
  - Implement initiate_card_payment() method for Paystack/Stripe/Pesapal
  - Implement handle_mpesa_callback() method
  - Implement handle_card_callback() method
  - Validate payment amounts against order totals
  - Create PaymentRequest records with proper status tracking
  - Send WhatsApp confirmations on success
  - _Requirements: 7.3, 7.4, 7.5, 8.1, 8.2, 8.3, 8.4, 8.5, 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ]* 7.1 Write property test for payment amount integrity
  - **Property 4: Payment amount integrity**
  - **Validates: Requirements 1.4, 8.2, 9.1**

- [ ]* 7.2 Write property test for payment confirmation
  - **Property 27: Payment confirmation**
  - **Validates: Requirements 7.5, 8.4, 9.4**

- [ ]* 7.3 Write property test for STK push initiation
  - **Property 28: STK push initiation**
  - **Validates: Requirements 8.3**

- [ ]* 7.4 Write property test for payment failure handling
  - **Property 29: Payment failure handling**
  - **Validates: Requirements 8.5, 9.5**

- [x] 8. Implement Payment Help Handler
  - Implement handle_payment_help() function
  - Ask for payment method selection (M-Pesa STK, M-Pesa manual, card)
  - Route to appropriate payment flow based on selection
  - Provide manual paybill/till instructions for M-Pesa manual
  - _Requirements: 7.3, 7.4_

- [ ]* 8.1 Write property test for payment method routing
  - **Property 26: Payment method routing**
  - **Validates: Requirements 7.4**

- [x] 9. Implement Service Browsing and Appointment Booking Handlers
  - Implement handle_browse_services() function
  - Implement handle_service_details() function
  - Implement handle_book_appointment() function
  - Query services with tenant scoping
  - Extract date/time slots from messages
  - Check availability against business hours and existing appointments
  - Create Appointment with PENDING_CONFIRMATION status
  - Ask for confirmation and optionally initiate payment
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [ ]* 9.1 Write property test for database-grounded availability checks
  - **Property 2: Database-grounded availability checks**
  - **Validates: Requirements 1.2, 10.3**

- [ ]* 9.2 Write property test for appointment availability checking
  - **Property 31: Appointment availability checking**
  - **Validates: Requirements 10.3**

- [ ]* 9.3 Write property test for appointment confirmation
  - **Property 32: Appointment confirmation**
  - **Validates: Requirements 10.5**

- [x] 10. Implement Status Checking Handlers
  - Implement handle_check_order_status() function
  - Implement handle_check_appointment_status() function
  - Query orders and appointments with tenant and customer scoping
  - Display most recent order with status, items, tracking
  - Display upcoming appointments with service, date, time, status
  - Handle empty states gracefully
  - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

- [ ]* 10.1 Write property test for order status display
  - **Property 33: Order status display**
  - **Validates: Requirements 11.2**

- [ ]* 10.2 Write property test for appointment status display
  - **Property 34: Appointment status display**
  - **Validates: Requirements 11.4**

- [ ]* 10.3 Write property test for empty status handling
  - **Property 35: Empty status handling**
  - **Validates: Requirements 11.5**

- [x] 11. Implement RAG Pipeline
  - Create RAGPipeline service class
  - Implement answer_question() method
  - Implement _retrieve_chunks() method with Pinecone integration
  - Implement _generate_grounded_answer() method with strict prompts
  - Implement _validate_grounding() method
  - Use tenant-specific Pinecone namespaces
  - Handle low similarity scores with uncertainty responses
  - Offer human handoff when context insufficient
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

- [ ]* 11.1 Write property test for RAG grounding
  - **Property 5: RAG grounding**
  - **Validates: Requirements 1.5, 12.2, 12.3, 12.4**

- [ ]* 11.2 Write property test for RAG retrieval
  - **Property 36: RAG retrieval**
  - **Validates: Requirements 12.1, 15.5**

- [ ]* 11.3 Write property test for RAG uncertainty handling
  - **Property 37: RAG uncertainty handling**
  - **Validates: Requirements 12.4**

- [x] 12. Implement FAQ and Policy Handlers
  - Implement handle_general_faq() function
  - Implement handle_return_policy() function
  - Implement handle_delivery_fees() function
  - Integrate with RAG Pipeline
  - Format answers in detected language
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

- [x] 13. Implement Multi-Model LLM Router
  - Create LLMRouter service class
  - Implement classify_intent() method
  - Implement extract_slots() method
  - Implement generate_rag_answer() method
  - Implement _select_model() with preference order (GPT-4o-mini, Qwen, Gemini Flash)
  - Implement _log_usage() to create LLMUsageLog records
  - Track input/output tokens and estimated costs
  - Implement budget checking and enforcement
  - _Requirements: 2.4, 2.5, 14.1, 14.2, 14.3, 14.4, 14.5_

- [ ]* 13.1 Write property test for LLM usage logging
  - **Property 41: LLM usage logging**
  - **Validates: Requirements 14.1**

- [ ]* 13.2 Write property test for small model preference
  - **Property 42: Small model preference**
  - **Validates: Requirements 14.2**

- [ ]* 13.3 Write property test for context window optimization
  - **Property 43: Context window optimization**
  - **Validates: Requirements 14.3**

- [ ]* 13.4 Write property test for budget enforcement
  - **Property 44: Budget enforcement**
  - **Validates: Requirements 14.5**

- [x] 14. Implement WhatsApp Message Formatter
  - Create WhatsAppMessageFormatter service class
  - Implement format_action() method
  - Implement build_product_list() for WhatsApp list messages
  - Implement build_button_message() for confirmation buttons
  - Implement build_payment_message() with order summary and links
  - Implement fallback to plain text when rich messages fail
  - Format messages in detected language
  - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5_

- [ ]* 14.1 Write property test for rich message formatting
  - **Property 45: Rich message formatting**
  - **Validates: Requirements 16.1**

- [ ]* 14.2 Write property test for confirmation button formatting
  - **Property 46: Confirmation button formatting**
  - **Validates: Requirements 16.3**

- [ ]* 14.3 Write property test for rich message fallback
  - **Property 47: Rich message fallback**
  - **Validates: Requirements 16.4**

- [x] 15. Implement Language Detection and Consistency
  - Implement language detection for EN/SW/Sheng/mixed
  - Store detected language in ConversationContext
  - Ensure all responses use consistent language
  - Implement language fallback to tenant primary language
  - Pass language to LLM prompts
  - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5_

- [ ]* 15.1 Write property test for language detection
  - **Property 53: Language detection**
  - **Validates: Requirements 19.1**

- [ ]* 15.2 Write property test for language consistency
  - **Property 54: Language consistency**
  - **Validates: Requirements 19.2**

- [ ]* 15.3 Write property test for language fallback
  - **Property 55: Language fallback**
  - **Validates: Requirements 19.4**

- [x] 16. Implement Remaining Intent Handlers
  - Implement handle_greet() function
  - Implement handle_small_talk() function
  - Implement handle_request_human() function
  - Implement handle_unknown() function
  - Tag conversations for human handoff
  - Stop automated responses when needs_human is set
  - _Requirements: 17.5_

- [ ]* 16.1 Write property test for human handoff tagging
  - **Property 50: Human handoff tagging**
  - **Validates: Requirements 17.5**

- [x] 17. Implement Business Hours and Quiet Hours
  - Add business hours checking to appointment booking
  - Add quiet hours checking to message processing
  - Implement quiet hours response message
  - Implement conversation queueing for quiet hours
  - Suggest alternative times within business hours
  - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5_

- [ ]* 17.1 Write property test for quiet hours handling
  - **Property 51: Quiet hours handling**
  - **Validates: Requirements 18.1**

- [ ]* 17.2 Write property test for business hours enforcement
  - **Property 52: Business hours enforcement**
  - **Validates: Requirements 18.2, 18.3**

- [x] 18. Implement Main Message Processing Pipeline
  - Update process_inbound_message Celery task
  - Integrate IntentDetectionEngine
  - Integrate BusinessLogicRouter
  - Integrate ConversationContextManager
  - Integrate WhatsAppMessageFormatter
  - Handle message deduplication
  - Implement error handling and logging
  - _Requirements: All_

- [x] 19. Implement Error Handling and Fallbacks
  - Implement graceful error handling for all handlers
  - Log all errors to Sentry with full context
  - Implement fallback messages for database failures
  - Implement fallback for LLM timeouts
  - Implement fallback for payment API failures
  - Implement fallback for RAG failures
  - Implement fallback for WhatsApp API failures
  - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_

- [ ]* 19.1 Write property test for graceful error handling
  - **Property 19: Graceful error handling**
  - **Validates: Requirements 4.5, 17.1, 17.4**

- [ ]* 19.2 Write property test for LLM timeout fallback
  - **Property 48: LLM timeout fallback**
  - **Validates: Requirements 17.2**

- [ ]* 19.3 Write property test for payment API error handling
  - **Property 49: Payment API error handling**
  - **Validates: Requirements 17.3**

- [x] 20. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 21. Implement Webhook Endpoints
  - Update Twilio webhook endpoint to use new pipeline
  - Implement M-Pesa callback webhook endpoint
  - Implement Paystack callback webhook endpoint
  - Implement Stripe callback webhook endpoint
  - Implement Pesapal callback webhook endpoint
  - Verify webhook signatures
  - Handle webhook errors gracefully
  - _Requirements: 8.4, 8.5, 9.4, 9.5_

- [x] 22. Implement Caching Layer
  - Cache product catalogs per tenant (Redis, 5-minute TTL)
  - Cache service lists per tenant (Redis, 5-minute TTL)
  - Cache tenant settings (Redis, 10-minute TTL)
  - Cache menu contexts (Redis, 5-minute TTL)
  - Cache popular FAQ answers (Redis, 1-hour TTL)
  - Implement cache invalidation on data updates
  - _Requirements: All (Performance)_

- [x] 23. Implement Database Optimizations
  - Add indexes on tenant_id for all models
  - Add indexes on customer_id for orders and appointments
  - Add indexes on created_at for time-based queries
  - Add indexes on status for filtering
  - Optimize queries with select_related and prefetch_related
  - _Requirements: All (Performance)_

- [x] 24. Implement Monitoring and Analytics
  - Set up Sentry error tracking with context
  - Implement structured JSON logging
  - Log intent classification method distribution
  - Log LLM usage per tenant
  - Log conversion rates (enquiry → order → payment)
  - Log payment success/failure rates
  - Log response times by handler
  - Log error rates by type
  - Create analytics dashboard views
  - _Requirements: All (Observability)_

- [x] 25. Implement Feature Flags
  - Add enable_rule_based_intent to AgentConfiguration
  - Add enable_mpesa_stk to AgentConfiguration
  - Add enable_card_payments to AgentConfiguration
  - Add monthly_llm_budget_usd to AgentConfiguration
  - Add llm_budget_exceeded_action to AgentConfiguration
  - Add business_hours_start/end to AgentConfiguration
  - Add quiet_hours_start/end to AgentConfiguration
  - Update admin interface for configuration
  - _Requirements: All (Configuration)_

- [ ] 26. Write Integration Tests
  - Write end-to-end test for product purchase flow
  - Write end-to-end test for appointment booking flow
  - Write end-to-end test for FAQ flow
  - Write end-to-end test for error recovery flow
  - Write multi-tenant isolation tests
  - Write payment callback tests
  - Write webhook signature verification tests
  - _Requirements: All_

- [ ]* 26.1 Write integration test for complete product purchase journey
  - Test: Customer browses → selects → orders → pays → receives confirmation
  - Validates: Requirements 5.1, 6.1, 7.1, 7.2, 7.3, 7.4, 7.5

- [ ]* 26.2 Write integration test for complete appointment booking journey
  - Test: Customer browses services → selects → books → confirms → pays
  - Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5

- [ ]* 26.3 Write integration test for FAQ with RAG
  - Test: Customer asks policy question → receives grounded answer
  - Validates: Requirements 12.1, 12.2, 12.3, 12.4

- [ ]* 26.4 Write integration test for multi-tenant isolation
  - Test: Tenant A queries don't return Tenant B data
  - Validates: Requirements 15.1, 15.2, 15.3, 15.4, 15.5

- [ ] 27. Write Performance Tests
  - Test response time for rule-based flows (<1.5s)
  - Test response time for LLM-based flows (<3s)
  - Test concurrent message processing
  - Test database query performance
  - Test Pinecone query performance
  - Test cache hit rates
  - _Requirements: All (Performance)_

- [ ]* 27.1 Write performance test for rule-based classification
  - Test: Rule-based classification completes in <100ms
  - Validates: Requirements 2.1, 2.2, 2.3

- [ ]* 27.2 Write performance test for database queries
  - Test: Product/service queries complete in <200ms
  - Validates: Requirements 5.1, 10.1

- [ ] 28. Write Cost Tests
  - Test LLM usage stays under $10/tenant/month
  - Test token counting accuracy
  - Test cost estimation accuracy
  - Test budget enforcement and throttling
  - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_

- [ ]* 28.1 Write cost test for LLM budget enforcement
  - Test: System throttles when budget exceeded
  - Validates: Requirements 14.5

- [ ] 29. Create Documentation
  - Document intent schema and slot definitions
  - Document handler function signatures and behaviors
  - Document payment flow diagrams
  - Document RAG pipeline configuration
  - Document LLM model selection logic
  - Document error handling strategies
  - Document deployment procedures
  - Create admin user guide for configuration
  - _Requirements: All_

- [ ] 30. Create Migration Guide
  - Document migration from old bot to new bot
  - Create feature flag rollout plan
  - Create tenant communication templates
  - Create rollback procedures
  - Document breaking changes
  - _Requirements: All_

- [ ] 31. Security Audit
  - Review tenant isolation in all queries
  - Review credential encryption
  - Review webhook signature verification
  - Review input validation and sanitization
  - Review rate limiting implementation
  - Review audit logging coverage
  - Review PII protection
  - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_

- [ ] 32. Final Checkpoint - Production Readiness
  - Ensure all tests pass, ask the user if questions arise.
