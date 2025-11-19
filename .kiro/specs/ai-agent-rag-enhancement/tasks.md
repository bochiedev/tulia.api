# Implementation Plan

This implementation plan breaks down the RAG enhancement into discrete, manageable coding tasks. Each task builds incrementally, starting with core infrastructure and progressing to advanced features. The plan prioritizes delivering a working MVP quickly while maintaining production quality.

## Task List

- [x] 1. Set up RAG infrastructure and dependencies ✅ COMPLETE
  - [x] 1.1 Install and configure LangChain
    - Add langchain, langchain-openai, langchain-community to requirements.txt
    - Install PDF processing libraries (pypdf2, pdfplumber)
    - Install text processing libraries (tiktoken, nltk)
    - Configure LangChain settings in Django settings
    - _Requirements: 7.1, 7.2_
  
  - [x] 1.2 Set up vector store integration
    - Choose vector store provider (Pinecone recommended for MVP)
    - Add vector store client library to requirements
    - Configure API keys in environment variables
    - Create vector store connection service
    - Test connection and basic operations
    - _Requirements: 2.1, 2.2, 17.1, 17.2_
  
  - [x] 1.3 Create database models for RAG
    - Create Document model with file metadata and status
    - Create DocumentChunk model with content and embedding references
    - Create InternetSearchCache model for caching search results
    - Create RAGRetrievalLog model for analytics
    - Create and run database migrations
    - Add indexes for tenant_id, status, and timestamps
    - _Requirements: 1.5, 9.1, 13.5, 19.1_

- [x] 2. Implement document upload and management ✅ COMPLETE
  - [x] 2.1 Create document upload API endpoint
    - Create DocumentSerializer with validation
    - Create DocumentUploadView with file handling
    - Validate file types (PDF, TXT) and size limits (10MB)
    - Store files in tenant-specific directories
    - Add RBAC enforcement with required scope "integrations:manage"
    - Return document ID and processing status
    - _Requirements: 1.1, 1.2, 9.2, 9.3, 17.1_
  
  - [x] 2.2 Create document management API endpoints
    - Create DocumentListView for viewing uploaded documents
    - Create DocumentDetailView for document details
    - Create DocumentDeleteView for removing documents
    - Add filtering by status and file type
    - Add pagination for large document lists
    - _Requirements: 9.1, 9.3, 9.4_
  
  - [x] 2.3 Build document status tracking
    - Implement status updates (pending → processing → completed/failed)
    - Add processing progress tracking
    - Create webhook/notification for completion
    - Track chunk count and token statistics
    - _Requirements: 9.5, 16.5_

- [x] 3. Build document processing pipeline ✅ COMPLETE
  - [x] 3.1 Implement text extraction service
    - Create TextExtractionService class
    - Implement PDF text extraction using pypdf2
    - Add OCR fallback using pdfplumber for scanned PDFs
    - Implement text file extraction with encoding detection
    - Handle extraction errors gracefully
    - _Requirements: 1.1, 16.2_
  
  - [x] 3.2 Implement text chunking service
    - Create ChunkingService using LangChain's RecursiveCharacterTextSplitter
    - Configure chunk size (300-500 tokens) and overlap (50 tokens)
    - Preserve sentence boundaries in chunks
    - Add metadata to chunks (page number, section)
    - Track chunk statistics
    - _Requirements: 1.3, 16.3_
  
  - [x] 3.3 Create Celery task for document processing
    - Create process_document Celery task
    - Orchestrate extraction → chunking → embedding → indexing
    - Update document status at each stage
    - Handle errors and mark documents as failed
    - Log processing time and statistics
    - _Requirements: 16.1, 16.4, 16.5_

- [x] 4. Implement embedding service ✅ COMPLETE
  - [x] 4.1 Create embedding service with OpenAI integration
    - Create EmbeddingService class
    - Implement embed_text() for single text
    - Implement embed_batch() for batch processing
    - Support text-embedding-3-small (default) and text-embedding-3-large
    - Add error handling and retry logic
    - _Requirements: 10.1, 10.2_
  
  - [x] 4.2 Add embedding caching
    - Cache embeddings in Redis (5 min TTL for queries)
    - Use content hash as cache key
    - Track cache hit rate
    - Implement cache invalidation
    - _Requirements: 15.1_
  
  - [x] 4.3 Integrate embeddings into document processing
    - Generate embeddings for all chunks in batch
    - Store embedding model name with chunks
    - Track embedding generation time
    - Calculate embedding costs
    - _Requirements: 16.4_

- [x] 5. Implement vector store integration ✅ COMPLETE
  - [x] 5.1 Create vector store abstraction layer
    - Create VectorStore abstract base class
    - Define interface: upsert(), search(), delete()
    - Implement PineconeVectorStore class
    - Add tenant isolation using namespaces
    - Test basic operations
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 17.2_
  
  - [x] 5.2 Implement vector indexing
    - Create method to upsert document chunks to vector store
    - Include tenant_id in metadata
    - Store chunk references (document_id, chunk_index)
    - Handle batch upsert for efficiency
    - Track indexing success/failure
    - _Requirements: 2.2, 17.3_
  
  - [x] 5.3 Implement vector search
    - Create method to search vector store by query embedding
    - Filter results by tenant_id
    - Return top K results with similarity scores
    - Include chunk metadata in results
    - Handle search errors gracefully
    - _Requirements: 2.3, 2.4, 17.2_
  
  - [x] 5.4 Add vector deletion
    - Implement method to delete vectors by document_id
    - Clean up all chunks when document deleted
    - Verify deletion success
    - _Requirements: 2.5, 9.3_

- [x] 6. Build document store service ✅ COMPLETE
  - [x] 6.1 Create DocumentStoreService class
    - Implement upload_document() method
    - Implement search_documents() method
    - Implement delete_document() method
    - Implement get_document_status() method
    - Add comprehensive error handling
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_
  
  - [x] 6.2 Implement semantic search
    - Generate query embedding
    - Search vector store
    - Retrieve matching chunks from database
    - Return results with similarity scores
    - _Requirements: 2.3, 2.4_
  
  - [ ] 6.3 Implement keyword search (DEFERRED - not needed for MVP)
    - Use PostgreSQL full-text search or BM25
    - Create text search index on chunk content
    - Search by keywords with ranking
    - Return results with relevance scores
    - _Requirements: 5.2_

- [x] 7. Implement hybrid search engine ✅ COMPLETE
  - [x] 7.1 Create HybridSearchEngine class
    - Implement search() method combining semantic and keyword
    - Execute semantic and keyword searches in parallel
    - Merge results with configurable weights (70% semantic, 30% keyword)
    - Normalize and rank combined results
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
  
  - [x] 7.2 Add search optimization
    - Implement early termination for high-confidence results
    - Add query expansion with synonyms
    - Implement result deduplication
    - Track search performance metrics
    - _Requirements: 15.1, 15.2_

- [x] 8. Implement database store service ✅ COMPLETE
  - [x] 8.1 Create DatabaseStoreService class
    - Implement get_product_context() method
    - Implement get_service_context() method
    - Implement get_appointment_availability() method
    - Implement needs_enrichment() method
    - Add tenant filtering to all queries
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 12.1, 12.2, 12.3_
  
  - [x] 8.2 Add product/service search
    - Implement fuzzy matching for product names
    - Search by category and tags
    - Include pricing and availability
    - Return structured context
    - _Requirements: 3.1, 3.2_
  
  - [x] 8.3 Add real-time availability queries
    - Query appointment slots in real-time
    - Filter by date range and service
    - Include booking status
    - Return available time slots
    - _Requirements: 3.3, 12.3_
  
  - [x] 8.4 Implement enrichment detection
    - Check if product description is minimal (< 50 chars)
    - Check if product is a known brand/item
    - Flag products needing internet enrichment
    - Track enrichment candidates
    - _Requirements: 3.4, 4.1_

- [x] 9. Implement internet search service ✅ COMPLETE
  - [x] 9.1 Create InternetSearchService class
    - Integrate with Google Custom Search API
    - Implement search_product_info() method
    - Implement extract_product_details() method
    - Add error handling for API failures
    - _Requirements: 13.1, 13.2, 13.3_
  
  - [x] 9.2 Build search query construction
    - Construct effective queries from product name and category
    - Add context terms (specifications, features)
    - Handle special characters and formatting
    - _Requirements: 13.2_
  
  - [x] 9.3 Implement result extraction
    - Parse search results for relevant information
    - Extract product features and specifications
    - Filter out advertisements and irrelevant content
    - Use LLM to structure extracted information
    - _Requirements: 13.3, 4.2_
  
  - [x] 9.4 Add search result caching
    - Cache search results for 24 hours
    - Use query hash as cache key
    - Implement cache lookup before API call
    - Track cache hit rate
    - _Requirements: 13.4_
  
  - [x] 9.5 Handle search failures gracefully
    - Return empty results on API failure
    - Log errors without blocking response
    - Fall back to cached results if available
    - Track failure rate
    - _Requirements: 13.5, 18.3_

- [x] 10. Build RAG retriever service ✅ COMPLETE
  - [x] 10.1 Create RAGRetrieverService class
    - Implement retrieve() method as main orchestrator
    - Implement retrieve_from_documents() method
    - Implement retrieve_from_database() method
    - Implement retrieve_from_internet() method
    - Implement rank_results() method
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_
  
  - [x] 10.2 Implement parallel retrieval
    - Execute document, database, and internet queries in parallel
    - Use asyncio or threading for concurrency
    - Set timeouts for each source (300ms target)
    - Handle partial failures gracefully
    - _Requirements: 8.2, 15.2_
  
  - [x] 10.3 Add query analysis
    - Analyze query to determine relevant sources
    - Extract entities (product names, dates)
    - Determine query type (product, service, general)
    - Route to appropriate sources
    - _Requirements: 8.1_
  
  - [x] 10.4 Implement result ranking
    - Rank results by relevance score
    - Prioritize based on source reliability
    - Consider recency for time-sensitive info
    - Return top N results
    - _Requirements: 8.3_

- [x] 11. Implement context synthesizer ✅ COMPLETE
  - [x] 11.1 Create ContextSynthesizer class
    - Implement synthesize() method
    - Implement resolve_conflicts() method
    - Implement format_for_llm() method
    - Merge information from multiple sources
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_
  
  - [x] 11.2 Add conflict resolution
    - Prioritize tenant-provided data over external sources
    - Prioritize database over documents for real-time data
    - Note discrepancies when sources conflict
    - Track conflict resolution decisions
    - _Requirements: 14.2_
  
  - [x] 11.3 Format context for LLM
    - Structure context with clear sections
    - Include source metadata
    - Optimize for token efficiency
    - Add relevance indicators
    - _Requirements: 14.4_

- [x] 12. Implement attribution handler ✅ COMPLETE
  - [x] 12.1 Create AttributionHandler class
    - Implement add_attribution() method
    - Implement format_citation() method
    - Implement should_attribute() method
    - Support multiple citation styles (inline, endnote)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_
  
  - [x] 12.2 Add citation formatting
    - Format document citations with name and section
    - Format database citations as "our catalog"
    - Format internet citations with source indication
    - List all sources at end of response
    - _Requirements: 6.1, 6.2, 6.3, 6.4_
  
  - [x] 12.3 Respect tenant attribution settings
    - Check tenant configuration for attribution enabled/disabled
    - Omit citations when disabled
    - Still track sources internally for analytics
    - _Requirements: 6.6_

- [ ] 13. Integrate RAG into AI agent
  - [x] 13.1 Update AgentConfiguration model ✅ COMPLETE
    - Add enable_document_retrieval field
    - Add enable_database_retrieval field
    - Add enable_internet_enrichment field
    - Add enable_source_attribution field
    - Add max_document_results, max_database_results, max_internet_results fields
    - Add semantic_search_weight and keyword_search_weight fields
    - Add embedding_model field
    - Add agent_can_do and agent_cannot_do text fields
    - Create and run migration
    - _Requirements: 21.1, 21.2, 21.3, 21.4_
  
  - [ ] 13.2 Update AI agent service to use RAG
    - Integrate RAGRetrieverService into agent workflow
    - Retrieve context before LLM generation
    - Pass retrieved context to context builder
    - Include RAG context in prompts
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_
  
  - [ ] 13.3 Update prompt engineering for RAG
    - Add section for retrieved information
    - Include source attribution instructions
    - Add instructions for using agent_can_do and agent_cannot_do
    - Format retrieved context clearly
    - _Requirements: 14.4, 21.3, 21.4_
  
  - [ ] 13.4 Add attribution to responses
    - Use AttributionHandler after LLM generation
    - Add citations based on tenant settings
    - Track which sources were used
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [ ] 14. Implement contextual retrieval
  - [ ] 14.1 Add conversation context to retrieval
    - Include conversation history in retrieval query
    - Consider customer preferences
    - Filter by current topic
    - _Requirements: 11.1, 11.2, 11.3_
  
  - [ ] 14.2 Implement query expansion
    - Expand queries with synonyms
    - Add related terms
    - Use conversation context for expansion
    - _Requirements: 11.4_
  
  - [ ] 14.3 Add contextual re-ranking
    - Re-rank results based on conversation context
    - Boost results matching customer preferences
    - Consider previous interactions
    - _Requirements: 11.5_

- [ ] 15. Build RAG analytics and monitoring
  - [ ] 15.1 Implement retrieval logging
    - Log every RAG retrieval operation
    - Track sources queried and results returned
    - Track retrieval time and performance
    - Track success/failure
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5_
  
  - [ ] 15.2 Create RAG analytics API endpoints
    - Create endpoint for retrieval success rate by source
    - Create endpoint for most retrieved documents/chunks
    - Create endpoint for queries with no results
    - Create endpoint for performance metrics
    - Create endpoint for source attribution breakdown
    - Add RBAC enforcement with required scope "analytics:view"
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5_
  
  - [ ] 15.3 Add cost tracking
    - Track embedding API costs
    - Track vector store costs
    - Track internet search costs
    - Calculate cost per retrieval
    - Aggregate costs per tenant
    - _Requirements: 19.4_

- [ ] 16. Implement performance optimizations
  - [ ] 16.1 Add caching layers
    - Cache query embeddings (5 min TTL)
    - Cache search results (1 min TTL)
    - Cache frequently accessed chunks
    - Use Redis for distributed caching
    - _Requirements: 15.1, 15.2, 15.3_
  
  - [ ] 16.2 Optimize database queries
    - Add indexes for tenant_id and status
    - Use select_related for foreign keys
    - Implement query result caching
    - Batch database operations
    - _Requirements: 15.2_
  
  - [ ] 16.3 Implement batch processing
    - Batch embedding generation (up to 100 texts)
    - Batch vector store operations
    - Process documents in background
    - Use Celery for async tasks
    - _Requirements: 16.4_
  
  - [ ] 16.4 Add performance monitoring
    - Track retrieval latency (p50, p95, p99)
    - Track cache hit rates
    - Track source query times
    - Alert on slow performance
    - _Requirements: 15.1, 15.4_

- [ ] 17. Implement security and tenant isolation
  - [ ] 17.1 Audit tenant isolation
    - Verify all document queries filter by tenant
    - Verify vector store uses tenant namespaces
    - Verify file storage is tenant-specific
    - Add automated tests for isolation
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_
  
  - [ ] 17.2 Add input validation
    - Sanitize file uploads
    - Validate file types and sizes
    - Prevent path traversal attacks
    - Sanitize search queries
    - _Requirements: 9.2_
  
  - [ ] 17.3 Implement encryption
    - Encrypt documents at rest
    - Encrypt API keys in database
    - Use HTTPS for all API calls
    - Implement secure key rotation
    - _Requirements: 17.1_
  
  - [ ] 17.4 Add rate limiting
    - Rate limit document uploads per tenant
    - Rate limit search queries per tenant
    - Rate limit internet searches globally
    - Track rate limit violations
    - _Requirements: 15.2_

- [ ] 18. Create demo and testing data
  - [ ] 18.1 Create sample documents
    - Generate Business FAQ PDF (20 Q&As)
    - Generate Product Catalog Guide PDF
    - Generate Business Policies text file
    - Generate Service Guide PDF
    - Upload to demo tenant
    - _Requirements: 22.1_
  
  - [ ] 18.2 Create sample products
    - Create well-described products (200+ char descriptions)
    - Create minimally-described products (< 50 char descriptions)
    - Create brand products (books, perfumes with model numbers)
    - Add to demo tenant catalog
    - _Requirements: 22.2_
  
  - [ ] 18.3 Create sample services
    - Create services with detailed descriptions
    - Add availability windows
    - Create booking scenarios
    - Add to demo tenant
    - _Requirements: 22.3_
  
  - [ ] 18.4 Create sample conversations
    - Create conversation with document-based query
    - Create conversation with product query
    - Create conversation with service query
    - Create conversation with appointment query
    - Create conversation with multi-source query
    - _Requirements: 22.4_
  
  - [ ] 18.5 Create sample agent configurations
    - Create config with full attribution enabled
    - Create config with attribution disabled
    - Create config with internet enrichment enabled
    - Create config with internet enrichment disabled
    - Create config with custom agent_can_do and agent_cannot_do
    - _Requirements: 22.5_

- [ ] 19. Testing and quality assurance
  - [ ] 19.1 Write unit tests for document processing
    - Test PDF text extraction
    - Test text chunking with overlap
    - Test embedding generation
    - Test error handling
    - _Requirements: All document processing requirements_
  
  - [ ] 19.2 Write unit tests for retrieval services
    - Test semantic search
    - Test keyword search
    - Test hybrid search merging
    - Test result ranking
    - Test parallel retrieval
    - _Requirements: All retrieval requirements_
  
  - [ ] 19.3 Write unit tests for synthesis and attribution
    - Test conflict resolution
    - Test source prioritization
    - Test context formatting
    - Test citation formatting
    - Test attribution toggle
    - _Requirements: All synthesis and attribution requirements_
  
  - [ ] 19.4 Write integration tests
    - Test end-to-end document upload and retrieval
    - Test multi-source retrieval
    - Test RAG integration with AI agent
    - Test tenant isolation
    - _Requirements: All requirements_
  
  - [ ] 19.5 Write performance tests
    - Test retrieval latency under load
    - Test concurrent document processing
    - Test large document handling (100+ pages)
    - Verify 95th percentile < 300ms
    - _Requirements: 15.1, 15.2, 15.3, 15.4_

- [ ] 20. Documentation and deployment
  - [ ] 20.1 Update API documentation
    - Document document upload endpoints
    - Document document management endpoints
    - Document RAG configuration options
    - Add example requests and responses
    - Update OpenAPI schema
    - _Requirements: All requirements_
  
  - [ ] 20.2 Create RAG setup guide
    - Document vector store setup
    - Document embedding model configuration
    - Document internet search API setup
    - Provide troubleshooting guide
    - _Requirements: All requirements_
  
  - [ ] 20.3 Create tenant onboarding guide
    - Explain document upload process
    - Explain RAG configuration options
    - Provide best practices for document organization
    - Explain source attribution settings
    - Include examples of agent_can_do and agent_cannot_do
    - _Requirements: 21.1, 21.2, 21.3, 21.4, 21.5_
  
  - [ ] 20.4 Create deployment checklist
    - Environment variable configuration
    - Vector store setup verification
    - Database migration steps
    - Demo data seeding
    - Performance testing
    - Rollback procedures
    - _Requirements: All requirements_

---

## Phase 2: Multi-Provider Support & Continuous Learning

This phase adds multi-provider LLM support (Gemini), feedback collection, and continuous learning capabilities to improve bot performance over time without degrading quality.

- [ ] 21. Implement multi-provider LLM support
  - [ ] 21.1 Add Gemini provider integration
    - Install google-generativeai SDK to requirements.txt
    - Create GeminiProvider class extending LLMProvider base
    - Implement generate() method with Gemini API
    - Support gemini-1.5-pro and gemini-1.5-flash models
    - Add error handling and retry logic
    - Configure Gemini API key in tenant settings
    - _Requirements: Cost optimization, provider redundancy_
  
  - [ ] 21.2 Implement smart provider routing
    - Create ProviderRouter class for intelligent model selection
    - Implement complexity scoring for queries (0.0-1.0)
    - Route simple queries to Gemini Flash (cost optimization)
    - Route large context (>100K tokens) to Gemini Pro (1M context window)
    - Route complex reasoning to OpenAI o1-preview
    - Default to OpenAI GPT-4o for balanced performance
    - Add routing configuration to AgentConfiguration model
    - _Requirements: Cost optimization, performance optimization_
  
  - [ ] 21.3 Add provider failover mechanism
    - Implement automatic failover on provider errors
    - Try fallback providers in order of preference
    - Track provider availability and success rates
    - Log failover events for monitoring
    - Set timeout limits per provider (30s default)
    - _Requirements: Reliability, uptime_
  
  - [ ] 21.4 Implement cost tracking per provider
    - Track token usage per provider (OpenAI, Gemini)
    - Calculate costs using provider-specific pricing
    - Aggregate costs per tenant per day/month
    - Create cost analytics dashboard
    - Set cost alerts and limits per tenant
    - _Requirements: Cost monitoring, budget management_
  
  - [ ] 21.5 Add provider performance monitoring
    - Track latency per provider (p50, p95, p99)
    - Track success/failure rates per provider
    - Track quality metrics per provider (feedback scores)
    - Create provider comparison dashboard
    - Alert on provider performance degradation
    - _Requirements: Performance monitoring, quality assurance_

- [ ] 22. Implement feedback collection system
  - [ ] 22.1 Create feedback database models
    - Create InteractionFeedback model for user ratings
    - Add rating field (helpful/not_helpful)
    - Add feedback_text field for optional comments
    - Add implicit signals (user_continued, completed_action, requested_human)
    - Add response_time_seconds for engagement tracking
    - Create HumanCorrection model for agent takeover scenarios
    - Add indexes for tenant_id, interaction_id, created_at
    - Create and run migrations
    - _Requirements: Feedback collection, quality improvement_
  
  - [ ] 22.2 Add feedback API endpoints
    - Create FeedbackSubmitView for thumbs up/down
    - Create FeedbackListView for viewing feedback history
    - Create FeedbackAnalyticsView for aggregated metrics
    - Add RBAC enforcement with required scope "analytics:view"
    - Validate feedback data and prevent spam
    - Return feedback confirmation to user
    - _Requirements: User feedback, API access_
  
  - [ ] 22.3 Implement WhatsApp feedback collection
    - Add thumbs up/down buttons after bot responses
    - Handle button click events in webhook
    - Store feedback with interaction reference
    - Send confirmation message to user
    - Respect user preferences (can disable feedback prompts)
    - Track feedback collection rate
    - _Requirements: User experience, feedback collection_
  
  - [ ] 22.4 Track implicit feedback signals
    - Track conversation continuation (user replied within 5 min)
    - Track action completion (product purchased, service booked)
    - Track human handoff requests (negative signal)
    - Track response time (fast response = engaged user)
    - Track message abandonment (user stopped replying)
    - Calculate implicit satisfaction score
    - _Requirements: Behavioral analytics, quality metrics_
  
  - [ ] 22.5 Implement human correction capture
    - Detect when human agent takes over conversation
    - Capture bot's last response before handoff
    - Capture human agent's corrected response
    - Store correction reason and category
    - Flag corrections for training approval
    - Create correction review dashboard
    - _Requirements: Quality improvement, training data_

- [ ] 23. Build continuous learning pipeline
  - [ ] 23.1 Create evaluation dataset
    - Create EvaluationCase model for test cases
    - Store customer_message, expected_response, context
    - Add quality_score from human ratings
    - Add intent and category labels
    - Import validated human corrections as test cases
    - Maintain minimum 500 test cases for validation
    - Version evaluation dataset for tracking
    - _Requirements: Model evaluation, quality assurance_
  
  - [ ] 23.2 Implement training data generation
    - Create TrainingDataGenerator service
    - Filter feedback for high-quality corrections (rating >4.0)
    - Require human approval before including in training set
    - Format data for OpenAI fine-tuning API
    - Format data for Gemini tuning API
    - Generate training/validation split (80/20)
    - Track training data statistics
    - _Requirements: Fine-tuning, model improvement_
  
  - [ ] 23.3 Create model evaluation framework
    - Implement ModelEvaluator class
    - Run evaluation on test set before deployment
    - Calculate quality metrics (BLEU, ROUGE, exact match)
    - Calculate business metrics (handoff rate, satisfaction)
    - Compare new model vs baseline model
    - Generate evaluation report with recommendations
    - Require minimum quality threshold to pass
    - _Requirements: Quality assurance, safe deployment_
  
  - [ ] 23.4 Implement A/B testing framework
    - Create ABTest model for experiment tracking
    - Implement traffic splitting (10/50/100% rollout)
    - Assign users to control/treatment groups consistently
    - Track metrics per group (quality, cost, latency)
    - Calculate statistical significance
    - Provide early stopping for bad experiments
    - Create A/B test dashboard
    - _Requirements: Safe deployment, data-driven decisions_
  
  - [ ] 23.5 Build fine-tuning job scheduler
    - Create FineTuningJob model for job tracking
    - Implement Celery task for fine-tuning orchestration
    - Submit fine-tuning jobs to OpenAI/Gemini APIs
    - Monitor job progress and status
    - Download and validate fine-tuned models
    - Run evaluation before marking as ready
    - Schedule monthly retraining automatically
    - _Requirements: Automation, continuous improvement_
  
  - [ ] 23.6 Implement model rollback mechanism
    - Track model versions and deployment history
    - Monitor quality metrics in real-time post-deployment
    - Automatic rollback if metrics drop >5%
    - Manual rollback via admin dashboard
    - Preserve previous model versions (keep last 3)
    - Log all rollback events with reasons
    - Alert team on automatic rollbacks
    - _Requirements: Safety, reliability_

- [ ] 24. Implement advanced performance monitoring
  - [ ] 24.1 Create quality metrics dashboard
    - Track response quality score (human-rated, 1-5 scale)
    - Track feedback positive rate (target >70%)
    - Track handoff rate (target <15%)
    - Track conversation completion rate
    - Track average response time
    - Visualize trends over time (daily/weekly/monthly)
    - Compare metrics across models and providers
    - _Requirements: Quality monitoring, insights_
  
  - [ ] 24.2 Implement business metrics tracking
    - Track customer satisfaction (CSAT) score
    - Track conversion rate (product purchases, bookings)
    - Track cost per conversation
    - Track agent productivity (time saved)
    - Track revenue impact (attributed sales)
    - Calculate ROI of AI agent
    - Create executive dashboard
    - _Requirements: Business value, ROI tracking_
  
  - [ ] 24.3 Add real-time alerting system
    - Alert on quality degradation (feedback score drops >10%)
    - Alert on cost spikes (daily cost exceeds budget by >20%)
    - Alert on latency issues (p95 latency >5 seconds)
    - Alert on provider failures (error rate >5%)
    - Alert on handoff rate spikes (>25%)
    - Configure alert channels (email, Slack, PagerDuty)
    - Implement alert throttling to prevent spam
    - _Requirements: Proactive monitoring, incident response_
  
  - [ ] 24.4 Create model comparison tools
    - Compare models side-by-side on test set
    - Compare quality metrics across models
    - Compare cost metrics across models
    - Compare latency metrics across models
    - Visualize trade-offs (quality vs cost vs speed)
    - Generate recommendation for best model
    - Export comparison reports
    - _Requirements: Data-driven decisions, optimization_
  
  - [ ] 24.5 Implement feedback loop analytics
    - Track feedback collection rate (target >30%)
    - Track feedback quality (detailed vs simple thumbs)
    - Track correction approval rate
    - Track training data growth over time
    - Track model improvement over iterations
    - Visualize learning curve
    - Identify areas needing more training data
    - _Requirements: Continuous improvement, insights_

- [ ] 25. Integration and optimization
  - [ ] 25.1 Integrate multi-provider support into AI agent
    - Update AIAgentService to use ProviderRouter
    - Pass query complexity to router for smart selection
    - Handle provider-specific response formats
    - Track provider used in AgentInteraction model
    - Add provider selection to agent configuration UI
    - Test with all supported providers
    - _Requirements: Integration, functionality_
  
  - [ ] 25.2 Integrate feedback collection into conversation flow
    - Add feedback prompt after bot responses (configurable)
    - Handle feedback submission in webhook
    - Update AgentInteraction with feedback data
    - Show feedback in conversation history
    - Allow users to change feedback
    - Track feedback in analytics
    - _Requirements: User experience, data collection_
  
  - [ ] 25.3 Implement gradual rollout strategy
    - Start with 10% traffic to new features
    - Monitor metrics for 48 hours
    - Increase to 50% if metrics are stable
    - Monitor for another 48 hours
    - Increase to 100% if all metrics pass
    - Document rollout process
    - Create rollout checklist
    - _Requirements: Safe deployment, risk mitigation_
  
  - [ ] 25.4 Optimize caching for multi-provider
    - Cache provider selection decisions (5 min TTL)
    - Cache model responses across providers (1 min TTL)
    - Invalidate cache on provider failures
    - Track cache hit rates per provider
    - Optimize cache keys for efficiency
    - _Requirements: Performance, cost optimization_
  
  - [ ] 25.5 Create admin tools for continuous learning
    - Build feedback review dashboard
    - Build correction approval interface
    - Build training data management UI
    - Build model deployment interface
    - Build A/B test configuration UI
    - Build rollback interface
    - Add audit logging for all admin actions
    - _Requirements: Operations, management_

- [ ] 26. Testing and validation
  - [ ] 26.1 Write unit tests for multi-provider support
    - Test GeminiProvider implementation
    - Test ProviderRouter logic
    - Test failover mechanism
    - Test cost calculation per provider
    - Test provider performance tracking
    - _Requirements: Quality assurance, reliability_
  
  - [ ] 26.2 Write unit tests for feedback system
    - Test feedback model creation and validation
    - Test feedback API endpoints
    - Test implicit signal tracking
    - Test human correction capture
    - Test feedback analytics calculations
    - _Requirements: Quality assurance, correctness_
  
  - [ ] 26.3 Write unit tests for learning pipeline
    - Test training data generation
    - Test evaluation framework
    - Test A/B testing logic
    - Test model rollback mechanism
    - Test fine-tuning job scheduler
    - _Requirements: Quality assurance, safety_
  
  - [ ] 26.4 Write integration tests for end-to-end flows
    - Test conversation with Gemini provider
    - Test feedback collection and storage
    - Test A/B test assignment and tracking
    - Test model evaluation and deployment
    - Test automatic rollback on quality drop
    - _Requirements: System integration, reliability_
  
  - [ ] 26.5 Perform load testing with multiple providers
    - Test concurrent requests to OpenAI and Gemini
    - Test failover under load
    - Test cache performance under load
    - Verify latency targets (p95 <2s)
    - Verify cost targets (60% reduction)
    - _Requirements: Performance, scalability_

- [ ] 27. Documentation and training
  - [ ] 27.1 Document multi-provider architecture
    - Explain provider selection logic
    - Document configuration options
    - Provide cost comparison tables
    - Include troubleshooting guide
    - Add provider-specific considerations
    - _Requirements: Knowledge sharing, onboarding_
  
  - [ ] 27.2 Document feedback and learning system
    - Explain feedback collection process
    - Document training data requirements
    - Explain evaluation metrics
    - Provide A/B testing best practices
    - Include rollback procedures
    - _Requirements: Knowledge sharing, operations_
  
  - [ ] 27.3 Create operator training materials
    - Create video tutorials for admin dashboards
    - Create runbooks for common operations
    - Create incident response playbooks
    - Create model deployment checklist
    - Create troubleshooting guides
    - _Requirements: Team enablement, operations_
  
  - [ ] 27.4 Update API documentation
    - Document feedback API endpoints
    - Document provider selection API
    - Document A/B testing API
    - Document model management API
    - Add code examples for all endpoints
    - Update OpenAPI schema
    - _Requirements: Developer experience, integration_
  
  - [ ] 27.5 Create success metrics guide
    - Define target metrics for each category
    - Explain how to interpret metrics
    - Provide optimization recommendations
    - Include case studies and examples
    - Create metrics glossary
    - _Requirements: Business alignment, optimization_
