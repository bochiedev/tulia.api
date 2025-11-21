# Implementation Plan

## Overview

This implementation plan transforms the WabotIQ bot from a conversation that never closes sales into one that completes transactions efficiently. Tasks are organized by priority and dependency, focusing on immediate impact first.

## Task Breakdown

- [-] 1. Set up core infrastructure and models
  - Create new models and modify existing ones
  - Add feature flags to AgentConfiguration
  - Create database migrations
  - _Requirements: 1.1, 5.1, 8.1, 10.1, 13.1, 14.1_

- [x] 1.1 Create CheckoutSession model
  - Add model with state, product, order, payment tracking
  - Add indexes on conversation_id and state
  - _Requirements: 10.1_

- [x] 1.2 Extend ConversationContext model
  - Add checkout_state, selected_product_id, selected_quantity fields
  - Add current_session_start, session_message_count fields
  - Add last_bot_message, last_customer_message fields
  - _Requirements: 8.1, 10.1_

- [x] 1.3 Extend AgentConfiguration model
  - Add enable_echo_prevention, enable_disclaimer_removal flags
  - Add max_response_sentences, max_checkout_messages settings
  - Add force_interactive_messages, fallback_to_text_on_error flags
  - _Requirements: 1.1, 5.1, 12.1_

- [x] 1.4 Create ResponseValidationLog model
  - Add model to track validation results
  - Add fields for echo, disclaimer, length, CTA checks
  - _Requirements: 1.1, 5.5_

- [x] 1.5 Generate and run migrations
  - Create migration files for all model changes
  - Test migrations on development database
  - _Requirements: All_

- [ ] 2. Implement echo prevention system
  - Build filter to remove customer message echoes
  - Integrate into message processing pipeline
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [ ] 2.1 Create EchoPreventionFilter service
  - Implement filter_response() method with verbatim detection
  - Implement contains_echo() with fuzzy matching (difflib)
  - Implement remove_quotes() for quoted text removal
  - Add 100ms timeout for performance
  - _Requirements: 1.1, 1.4_

- [ ]* 2.2 Write property test for echo prevention
  - **Property 1: No message echoes**
  - **Validates: Requirements 1.1, 1.4**

- [ ] 2.3 Integrate echo filter into message pipeline
  - Add filter call after response generation
  - Store customer message in context for comparison
  - Log all echo removals to ResponseValidationLog
  - _Requirements: 1.1_

- [ ]* 2.4 Write unit tests for echo filter
  - Test verbatim echo detection
  - Test partial echo detection (>80% similarity)
  - Test quote removal
  - Test false positive handling
  - Test performance timeout
  - _Requirements: 1.1_

- [ ] 3. Implement disclaimer removal system
  - Remove confidence-undermining phrases
  - Replace with confident alternatives
  - _Requirements: 5.1, 5.2, 5.4, 5.5_

- [ ] 3.1 Create DisclaimerRemover service
  - Define DISCLAIMER_PATTERNS regex list
  - Implement remove_disclaimers() method
  - Implement contains_disclaimers() checker
  - Implement replace_with_confidence() for alternatives
  - _Requirements: 5.5_

- [ ]* 3.2 Write property test for disclaimer removal
  - **Property 12: No disclaimer phrases**
  - **Validates: Requirements 5.1, 5.4, 5.5**

- [ ] 3.3 Integrate disclaimer remover into pipeline
  - Add remover call after response generation
  - Log all disclaimer removals to ResponseValidationLog
  - _Requirements: 5.5_

- [ ]* 3.4 Write unit tests for disclaimer remover
  - Test each disclaimer pattern removal
  - Test replacement with confident alternatives
  - Test preservation of valid uncertainty expressions
  - _Requirements: 5.5_

- [ ] 4. Implement response validation system
  - Validate responses before sending
  - Enforce length, content, and quality rules
  - _Requirements: 1.1, 5.5, 12.1, 12.4_

- [ ] 4.1 Create ResponseValidator service
  - Implement validate() method with all checks
  - Implement count_sentences() helper
  - Implement has_call_to_action() checker
  - Return validation results and issues list
  - _Requirements: 1.1, 5.5, 12.1_

- [ ] 4.2 Integrate validator into pipeline
  - Add validation call before sending
  - Log validation results to ResponseValidationLog
  - Block sending if critical issues found
  - _Requirements: 1.1, 5.5, 12.1_

- [ ]* 4.3 Write unit tests for response validator
  - Test sentence counting
  - Test call-to-action detection
  - Test length validation
  - Test combined validation
  - _Requirements: 12.1_

- [ ] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Fix interactive message routing
  - Ensure all product displays use WhatsApp interactive elements
  - Add proper fallback handling
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 9.1, 9.2, 9.3, 9.4_

- [ ] 6.1 Create InteractiveMessageRouter service
  - Implement format_product_list() for WhatsApp list messages
  - Implement format_checkout_confirmation() with buttons
  - Implement format_payment_methods() with buttons
  - Add fallback to numbered text on API failure
  - _Requirements: 2.1, 2.4_

- [ ]* 6.2 Write property test for interactive messages
  - **Property 4: Interactive message format**
  - **Validates: Requirements 2.1, 2.2**

- [ ] 6.3 Wire interactive router into bot response flow
  - Replace plain text product displays with interactive messages
  - Add product images to media payload
  - Store list context for reference resolution
  - Log all interactive message sends
  - _Requirements: 2.1, 2.5, 9.1, 9.4_

- [ ] 6.4 Implement WhatsApp message format builders
  - Build list message format (3-10 items)
  - Build button message format (1-3 options)
  - Build media message format with images
  - Add unique selectable IDs for each item
  - _Requirements: 2.2, 9.1_

- [ ]* 6.5 Write unit tests for message formatting
  - Test list message structure
  - Test button message structure
  - Test unique ID generation
  - Test image inclusion
  - Test fallback to text
  - _Requirements: 2.1, 2.2, 9.1_

- [ ] 7. Implement session-aware context loading
  - Load full conversation history with session detection
  - Prioritize current session messages
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 8.1, 8.2, 8.3, 8.4, 8.5_

- [ ] 7.1 Create SessionAwareContextLoader service
  - Implement load_context() with session detection
  - Implement detect_session_boundary() (24-hour gaps)
  - Implement summarize_session() for older messages
  - Return structured context with current + summary
  - _Requirements: 3.1, 8.2, 8.3_

- [ ]* 7.2 Write property test for context loading
  - **Property 6: Full history loading**
  - **Validates: Requirements 3.1, 3.2**

- [ ]* 7.3 Write property test for session detection
  - **Property 18: Session boundary detection**
  - **Validates: Requirements 8.2**

- [ ] 7.4 Integrate session loader into context building
  - Replace existing context loader with session-aware version
  - Load last 20 messages from current session
  - Add session summary for older messages
  - Store session_start in ConversationContext
  - _Requirements: 3.3, 8.3, 8.4_

- [ ] 7.5 Implement "haven't talked" phrase prevention
  - Add check for conversation history before responding
  - Remove phrases like "we haven't talked" from responses
  - _Requirements: 3.5_

- [ ]* 7.6 Write unit tests for session loading
  - Test session boundary detection with various gaps
  - Test context structure (20 messages + summary)
  - Test multi-day conversation handling
  - _Requirements: 3.1, 3.3, 8.2_

- [ ] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.


- [ ] 9. Implement checkout state machine
  - Create deterministic checkout flow
  - Limit to 3 messages from selection to payment
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 7.1, 7.2, 7.3, 7.4, 7.5, 10.1, 10.2, 10.3_

- [ ] 9.1 Create CheckoutStateMachine service
  - Define CheckoutState enum (7 states)
  - Implement process_message() state router
  - Implement transition_state() with validation
  - Implement create_order() with PENDING_PAYMENT status
  - _Requirements: 4.1, 10.1_

- [ ]* 9.2 Write property test for quick checkout
  - **Property 9: Quick checkout flow**
  - **Validates: Requirements 4.2, 4.4**

- [ ]* 9.3 Write property test for order creation
  - **Property 24: Order creation on confirmation**
  - **Validates: Requirements 10.1**

- [ ]* 9.4 Write property test for order totals
  - **Property 25: Accurate order totals**
  - **Validates: Requirements 10.2**

- [ ] 9.2 Implement state transition handlers
  - Handle BROWSING → PRODUCT_SELECTED (on selection)
  - Handle PRODUCT_SELECTED → QUANTITY_CONFIRMED (ask quantity)
  - Handle QUANTITY_CONFIRMED → PAYMENT_METHOD_SELECTED (create order)
  - Handle PAYMENT_METHOD_SELECTED → PAYMENT_INITIATED (initiate payment)
  - _Requirements: 4.1, 4.2, 4.3_

- [ ] 9.3 Wire state machine into message processing
  - Check checkout_state in ConversationContext
  - Route to state machine if in checkout flow
  - Update checkout_state after each transition
  - Create CheckoutSession record on start
  - _Requirements: 4.1, 10.1_

- [ ] 9.4 Implement order creation logic
  - Calculate total from database product prices
  - Create Order with PENDING_PAYMENT status
  - Store order_id in ConversationContext
  - Validate product availability before creating
  - _Requirements: 10.1, 10.2_

- [ ] 9.5 Implement message count enforcement
  - Track message count in CheckoutSession
  - Ensure ≤3 messages from selection to payment
  - Skip unnecessary confirmation steps
  - _Requirements: 4.4_

- [ ]* 9.6 Write unit tests for state machine
  - Test each state transition
  - Test invalid transitions
  - Test order creation
  - Test message count tracking
  - _Requirements: 4.1, 4.4, 10.1_

- [ ] 10. Implement payment integration
  - Wire M-Pesa STK push into checkout flow
  - Handle payment callbacks
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 10.3, 10.4, 10.5, 14.1, 14.2, 14.3, 14.4, 14.5_

- [ ] 10.1 Create BotPaymentService
  - Implement initiate_mpesa_stk() with phone validation
  - Implement handle_payment_callback() with status updates
  - Implement generate_payment_message() in correct language
  - Use tenant credentials from TenantSettings
  - _Requirements: 6.1, 6.3, 10.4_

- [ ]* 10.2 Write property test for payment amounts
  - **Property 26: Payment amount accuracy**
  - **Validates: Requirements 10.3**

- [ ]* 10.3 Write property test for payment credentials
  - **Property 27: Correct payment credentials**
  - **Validates: Requirements 10.4**

- [ ]* 10.4 Write property test for order status update
  - **Property 28: Order status update on payment**
  - **Validates: Requirements 10.5**

- [ ] 10.2 Integrate payment into checkout flow
  - Call initiate_mpesa_stk() when payment method selected
  - Create PaymentRequest with PENDING status
  - Send STK push confirmation message
  - Update checkout_state to PAYMENT_INITIATED
  - _Requirements: 6.1, 6.3, 14.1_

- [ ] 10.3 Implement payment callback handler
  - Update PaymentRequest with callback data
  - Update Order status to PAID on success
  - Send order confirmation message
  - Offer retry/alternatives on failure
  - _Requirements: 6.4, 6.5, 10.5, 14.2_

- [ ] 10.4 Implement payment logging
  - Log all payment initiations
  - Log callback data
  - Log failures with error details
  - Log successes with transaction reference
  - Send errors to Sentry with full context
  - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_

- [ ] 10.5 Implement post-payment message control
  - Stop sending messages after payment initiation
  - Wait for callback or customer response
  - Send only one confirmation message
  - _Requirements: 4.5, 7.5_

- [ ]* 10.6 Write unit tests for payment service
  - Test STK push initiation
  - Test phone number validation
  - Test callback handling (success/failure)
  - Test payment message generation
  - Test credential usage
  - _Requirements: 6.1, 6.3, 6.4, 6.5, 10.4_

- [ ] 11. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 12. Implement enhanced reference resolution
  - Handle "this one", "1", "first", etc.
  - Support multiple reference types
  - _Requirements: 1.3, 11.1, 11.2, 11.3, 11.4, 11.5_

- [ ] 12.1 Create ReferenceResolutionService
  - Implement resolve_reference() for all reference types
  - Support numeric references ("1", "2")
  - Support ordinal references ("first", "last")
  - Support demonstrative references ("this one", "that one")
  - Support descriptive references ("the blue one")
  - _Requirements: 11.1, 11.2_

- [ ]* 12.2 Write property test for reference resolution
  - **Property 29: Reference resolution accuracy**
  - **Validates: Requirements 11.1, 11.2**

- [ ]* 12.3 Write property test for reference confirmation
  - **Property 3: Reference resolution with names**
  - **Validates: Requirements 1.3, 11.3**

- [ ] 12.2 Implement reference context management
  - Implement get_recent_lists() (last 5, max 5 minutes old)
  - Implement store_list_context() with expiration
  - Store context when displaying products/services
  - _Requirements: 11.1_

- [ ] 12.3 Integrate reference resolution into intent detection
  - Check for reference patterns in customer message
  - Resolve reference before intent classification
  - Confirm resolved item in response
  - Ask for clarification if ambiguous
  - Ask for specification if no recent list
  - _Requirements: 11.3, 11.4, 11.5_

- [ ]* 12.4 Write unit tests for reference resolution
  - Test numeric reference resolution
  - Test ordinal reference resolution
  - Test demonstrative reference resolution
  - Test expired context handling
  - Test ambiguous reference handling
  - Test missing context handling
  - _Requirements: 11.1, 11.2, 11.4, 11.5_

- [ ] 13. Implement response brevity controls
  - Enforce maximum 3 sentences
  - Limit product displays to 5 items
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

- [ ] 13.1 Add sentence counting to ResponseValidator
  - Count sentences in non-list responses
  - Enforce max_response_sentences from config
  - Truncate or summarize if too long
  - _Requirements: 12.1, 12.4_

- [ ]* 13.2 Write property test for response brevity
  - **Property 32: Response brevity**
  - **Validates: Requirements 12.1, 12.4**

- [ ] 13.2 Add product list size limiting
  - Limit to max_products_to_show from config (default 5)
  - Show "View more" option if more products available
  - _Requirements: 12.2_

- [ ]* 13.3 Write property test for product list size
  - **Property 33: Product list size limit**
  - **Validates: Requirements 12.2**

- [ ] 13.3 Implement concise response prompting
  - Update LLM prompts to request brief responses
  - Add "Keep response to 3 sentences max" instruction
  - Add "Focus on next action" instruction
  - _Requirements: 12.1, 12.5_

- [ ]* 13.4 Write unit tests for brevity controls
  - Test sentence counting
  - Test truncation logic
  - Test product list limiting
  - _Requirements: 12.1, 12.2_

- [ ] 14. Implement tenant branding
  - Use business name in messages
  - Support custom greetings
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

- [ ] 14.1 Create BrandedPersonaBuilder service
  - Implement build_system_prompt() with business name
  - Include bot name from config or business name + "Assistant"
  - Add brand voice from AgentConfiguration
  - _Requirements: 13.1, 13.2_

- [ ]* 14.2 Write property test for business name in introduction
  - **Property 34: Business name in introduction**
  - **Validates: Requirements 13.1**

- [ ] 14.2 Integrate branding into message generation
  - Use business name in introductions
  - Use business name in order confirmations
  - Use business name in handoff messages
  - Use custom greeting if configured
  - _Requirements: 13.1, 13.3, 13.4, 13.5_

- [ ]* 14.3 Write unit tests for branding
  - Test business name inclusion
  - Test custom greeting usage
  - Test handoff identification
  - _Requirements: 13.1, 13.3, 13.4, 13.5_

- [ ] 15. Implement language handling
  - Detect and match customer language
  - Support English, Swahili, mixed
  - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_

- [ ] 15.1 Create LanguageConsistencyManager service
  - Implement detect_language() for EN/SW/mixed
  - Implement get_conversation_language() from context
  - Implement set_conversation_language() to context
  - Detect dominant language in mixed messages
  - _Requirements: 15.1, 15.2, 15.3_

- [ ]* 15.2 Write property test for language matching
  - **Property 43: Language matching**
  - **Validates: Requirements 15.1, 15.2**

- [ ]* 15.3 Write property test for language storage
  - **Property 45: Language preference storage**
  - **Validates: Requirements 15.4**

- [ ] 15.2 Integrate language detection into pipeline
  - Detect language from customer message
  - Store in ConversationContext
  - Pass to response generation
  - Adapt immediately on language switch
  - _Requirements: 15.4, 15.5_

- [ ]* 15.3 Write unit tests for language handling
  - Test English detection
  - Test Swahili detection
  - Test mixed language detection
  - Test language switching
  - Test language persistence
  - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_

- [ ] 16. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 17. Integration testing and bug fixes
  - Test end-to-end flows
  - Fix any issues found
  - _Requirements: All_

- [ ] 17.1 Test end-to-end checkout flow
  - Test complete flow from browse to payment
  - Verify interactive messages sent
  - Verify no echoes or disclaimers
  - Verify ≤3 messages to payment
  - Verify payment initiation works
  - _Requirements: 2.1, 4.4, 6.1_

- [ ] 17.2 Test multi-day conversation flow
  - Test conversation spanning multiple days
  - Verify session detection works
  - Verify context continuity maintained
  - Verify no "haven't talked" messages
  - _Requirements: 3.1, 3.5, 8.2_

- [ ] 17.3 Test language switching flow
  - Test conversation starting in English
  - Test switching to Swahili mid-conversation
  - Verify bot adapts immediately
  - _Requirements: 15.1, 15.2, 15.5_

- [ ] 17.4 Test reference resolution flow
  - Test "I want this one" after product list
  - Test numeric references "1", "2"
  - Test ordinal references "first", "last"
  - Verify correct product resolved
  - _Requirements: 11.1, 11.2, 11.3_

- [ ] 17.5 Test payment callback handling
  - Test successful payment callback
  - Test failed payment callback
  - Verify order status updates
  - Verify confirmation messages sent
  - _Requirements: 6.4, 6.5, 10.5_

- [ ] 17.6 Fix bugs found during integration testing
  - Document all bugs found
  - Prioritize by severity
  - Fix critical bugs
  - Retest after fixes
  - _Requirements: All_

- [ ] 18. Performance optimization
  - Optimize slow operations
  - Add caching where appropriate
  - _Requirements: All_

- [ ] 18.1 Optimize echo detection performance
  - Add timeout (100ms max)
  - Use simple string matching first
  - Only use fuzzy matching if needed
  - Cache customer message for comparison
  - _Requirements: 1.1_

- [ ] 18.2 Optimize context loading performance
  - Add database indexes on (conversation_id, created_at)
  - Use select_related for related objects
  - Cache session summaries in Redis (1 hour TTL)
  - Limit to 50 messages max
  - _Requirements: 3.1, 8.1_

- [ ] 18.3 Optimize interactive message generation
  - Pre-build message templates
  - Cache product images
  - Batch product queries with prefetch_related
  - Use connection pooling for WhatsApp API
  - _Requirements: 2.1, 9.1_

- [ ] 18.4 Optimize checkout state management
  - Store state in ConversationContext (no extra query)
  - Use database transactions for order creation
  - Cache payment credentials in Redis
  - _Requirements: 10.1, 10.4_

- [ ] 19. Monitoring and observability
  - Add metrics tracking
  - Set up alerts
  - _Requirements: All_

- [ ] 19.1 Add metrics tracking
  - Track echo detection rate
  - Track disclaimer removal rate
  - Track interactive message success rate
  - Track checkout completion rate
  - Track average messages to payment
  - Track payment success rate
  - _Requirements: 1.1, 2.1, 4.4, 5.5, 6.1_

- [ ] 19.2 Set up alerts
  - Alert if echo detection rate >10%
  - Alert if interactive message failure rate >10%
  - Alert if checkout abandonment rate >50%
  - Alert if payment failure rate >30%
  - Alert if response validation failure rate >5%
  - _Requirements: 1.1, 2.1, 4.4, 5.5, 6.1_

- [ ] 19.3 Add logging for debugging
  - Log all echo removals
  - Log all disclaimer removals
  - Log all interactive message sends
  - Log all checkout state transitions
  - Log all payment attempts
  - _Requirements: 1.1, 2.5, 5.5, 10.1, 14.1_

- [ ] 20. Documentation and deployment
  - Document new features
  - Create deployment plan
  - _Requirements: All_

- [ ] 20.1 Document new services and components
  - Document EchoPreventionFilter usage
  - Document DisclaimerRemover usage
  - Document CheckoutStateMachine states
  - Document InteractiveMessageRouter formats
  - Document BotPaymentService integration
  - _Requirements: All_

- [ ] 20.2 Create deployment plan
  - Define canary rollout (1 test tenant)
  - Define beta rollout (10 tenants)
  - Define gradual rollout (25% of tenants)
  - Define full rollout (all tenants)
  - Define rollback procedure
  - _Requirements: All_

- [ ] 20.3 Update configuration documentation
  - Document new AgentConfiguration flags
  - Document feature flag usage
  - Document monitoring metrics
  - Document alert thresholds
  - _Requirements: All_

- [ ] 21. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

