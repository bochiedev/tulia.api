# Implementation Plan

- [x] 1. Implement Message Harmonization Service ✅ COMPLETE
  - Create service to detect and buffer rapid messages
  - Add timing logic to wait 3 seconds before processing
  - Implement message combining functionality
  - Add typing indicator support via WhatsApp API
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 1.1 Write property test for message harmonization
  - **Property 4: Message burst harmonization**
  - **Validates: Requirements 4.1, 4.2, 4.3**

- [x] 2. Implement Reference Context Manager
  - Create ReferenceContextManager service class
  - Implement store_list_context() method with TTL
  - Implement resolve_reference() for positional references ("1", "first", "last")
  - Add support for descriptive references ("the blue one")
  - Implement context expiration and cleanup
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 2.1 Write property test for reference resolution
  - **Property 1: Recent context priority**
  - **Validates: Requirements 1.1, 1.2, 1.3**

- [x] 3. Enhance Conversation History Loading
  - Modify ContextBuilderService.get_conversation_history() to load ALL messages
  - Implement ConversationHistoryService.get_full_history()
  - Add conversation summarization for very long histories
  - Update context building to include full history
  - Ensure conversation summary is populated in ConversationContext
  - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

- [x] 3.1 Write property test for conversation history recall
  - **Property 9: Conversation history recall**
  - **Validates: Requirements 11.1, 11.2, 11.3, 11.4, 11.5**

- [x] 4. Implement Language Consistency Manager
  - Create LanguageConsistencyManager service class
  - Implement detect_language() for English, Swahili, mixed detection
  - Implement get_conversation_language() to retrieve established language
  - Implement set_conversation_language() to persist preference
  - Update LanguagePreference model usage
  - Integrate with context builder to enforce consistency
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 4.1 Write property test for language consistency
  - **Property 6: Language consistency**
  - **Validates: Requirements 6.1, 6.2, 6.3, 6.5**

- [x] 5. Implement Smart Product Discovery Service
  - Create SmartProductDiscoveryService class
  - Implement get_immediate_suggestions() to show products without narrowing
  - Add fuzzy matching for product queries
  - Implement get_contextual_recommendations() based on conversation
  - Integrate with existing catalog cache service
  - Update AIAgentService to use proactive suggestions
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 5.1 Write property test for immediate product visibility
  - **Property 2: Immediate product visibility**
  - **Validates: Requirements 2.1, 2.2, 2.3**

- [x] 6. Enhance Rich Message Builder
  - Extend RichMessageBuilder.build_product_list() for WhatsApp lists
  - Implement build_product_card() with action buttons
  - Implement build_service_card() with booking buttons
  - Implement build_checkout_message() with payment links
  - Add fallback to plain text when rich messages fail
  - Store reference context when displaying lists
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 6.1 Write property test for rich message formatting
  - **Property 3: Rich message for product lists**
  - **Validates: Requirements 3.1, 3.2, 3.3, 3.4**

- [x] 7. Implement Branded Persona Builder
  - Create BrandedPersonaBuilder service class
  - Implement build_system_prompt() with tenant branding
  - Use tenant business name in bot identity
  - Add agent_can_do and agent_cannot_do from AgentConfiguration
  - Update AIAgentService to use branded prompts
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 7.1 Write property test for branded identity
  - **Property 7: Branded identity**
  - **Validates: Requirements 7.1, 7.2, 7.3**

- [x] 8. Implement Grounded Response Validator
  - Create GroundedResponseValidator service class
  - Implement extract_claims() to parse factual statements
  - Implement verify_claim() against context data
  - Implement validate_response() to check all claims
  - Integrate with AIAgentService response generation
  - Add logging for validation failures
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 8.1 Write property test for factual grounding
  - **Property 8: Factual grounding**
  - **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5**

- [x] 9. Implement Checkout Guidance Flow
  - Add checkout link generation to payment service
  - Implement complete purchase flow in intent handlers
  - Add product selection confirmation
  - Add quantity confirmation
  - Generate payment links or instructions
  - Update rich message builder for checkout messages
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 9.1 Write property test for checkout guidance
  - **Property 5: Checkout guidance completeness**
  - **Validates: Requirements 5.1, 5.2, 5.3, 5.4**

- [x] 10. Implement Intent Inference from Context
  - Update MultiIntentProcessor to use conversation context
  - Implement context-based intent inference
  - Add fallback to clarifying questions only when context insufficient
  - Update intent detection prompts to include recent messages
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 10.1 Write property test for intent inference
  - **Property 10: Intent inference from context**
  - **Validates: Requirements 10.1, 10.4, 10.5**

- [x] 11. Update Database Models
  - Add last_message_time to ConversationContext
  - Add message_buffer to ConversationContext
  - Add language_locked to ConversationContext
  - Add harmonization fields to AgentConfiguration
  - Add immediate_product_display fields to AgentConfiguration
  - Create MessageHarmonizationLog model
  - Create and run migrations
  - _Requirements: All_

- [x] 12. Integrate All Components
  - Update AIAgentService.process_message() to use message harmonization
  - Update context builder to use reference context manager
  - Update response generation to use branded persona
  - Update response validation to use grounding validator
  - Update rich message detection to use new builder methods
  - Wire up language consistency manager
  - _Requirements: All_

- [ ] 13. Add Feature Flags and Configuration
  - Add enable_message_harmonization to AgentConfiguration
  - Add enable_immediate_product_display to AgentConfiguration
  - Add enable_reference_resolution to AgentConfiguration
  - Add enable_grounded_validation to AgentConfiguration
  - Update admin interface for new configuration options
  - _Requirements: All_

- [x] 14. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 15. Code Cleanup - Remove Unused Code
  - Run code analysis to find unused imports
  - Remove unused functions and classes
  - Remove duplicate code blocks
  - Remove deprecated API usage
  - Update documentation for removed code
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 15.1 Write unit tests for code cleanup analyzer
  - Test unused import detection
  - Test unused function detection
  - Test duplicate code detection

- [x] 16. Performance Optimization
  - Add Redis caching for reference contexts
  - Add database indexes for conversation history queries
  - Optimize product queries with select_related/prefetch_related
  - Implement conversation history pagination
  - Add query performance monitoring
  - _Requirements: All_

- [x] 16.1 Write performance tests
  - Test reference context cache hit rates
  - Test conversation history query performance
  - Test product discovery query performance

- [x] 17. Error Handling and Fallbacks
  - Implement fallback for missing reference context
  - Implement fallback for expired context
  - Implement fallback for ambiguous references
  - Implement fallback for rich message failures
  - Implement fallback for language detection errors
  - Add comprehensive error logging
  - _Requirements: All_

- [x] 17.1 Write unit tests for error handling
  - Test all fallback scenarios
  - Test error logging
  - Test graceful degradation

- [x] 18. Integration Testing
  - Write end-to-end conversation flow tests
  - Test message harmonization in real conversations
  - Test reference resolution across multiple turns
  - Test language consistency across conversation
  - Test product discovery and checkout flow
  - Test WhatsApp rich message rendering
  - _Requirements: All_

- [x] 18.1 Write integration tests
  - Test complete inquiry-to-sale journey
  - Test multi-turn conversations with context
  - Test error recovery scenarios

- [x] 19. Documentation and Deployment
  - Update API documentation
  - Create user guide for new features
  - Create admin guide for configuration
  - Update deployment checklist
  - Create rollback plan
  - _Requirements: All_

- [x] 20. Final Checkpoint - Production Readiness
  - Ensure all tests pass, ask the user if questions arise.
