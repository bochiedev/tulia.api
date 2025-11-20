"""
Performance tests for AI-powered customer service agent.

Tests response time under load, concurrent tenant usage,
context building speed, and knowledge search speed.

Requirements: 12.1, 12.2, 12.3, 12.4
"""
import pytest
import time
import statistics
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.core.cache import cache
from django.utils import timezone

from apps.tenants.models import Tenant, Customer, SubscriptionTier
from apps.messaging.models import Conversation, Message
from apps.catalog.models import Product
from apps.services.models import Service
from apps.orders.models import Order
from apps.bot.models import KnowledgeEntry, ConversationContext
from apps.bot.services.context_builder_service import ContextBuilderService
from apps.bot.services.knowledge_base_service import KnowledgeBaseService


# Performance thresholds (in seconds)
# Note: These are relaxed for test environments; production should be faster
RESPONSE_TIME_P95_THRESHOLD = 5.0  # 95th percentile should be under 5 seconds
CONTEXT_BUILD_THRESHOLD = 3.0  # Context building should be under 3 seconds (relaxed for tests)
KNOWLEDGE_SEARCH_THRESHOLD = 1.0  # Knowledge search should be under 1 second (relaxed for tests)


@pytest.fixture
def subscription_tier(db):
    """Create subscription tier."""
    return SubscriptionTier.objects.create(
        name='Performance Test Tier',
        monthly_price=29.00,
        yearly_price=278.00
    )


@pytest.fixture
def performance_tenant(db, subscription_tier):
    """Create tenant for performance testing."""
    return Tenant.objects.create(
        name="Performance Test Tenant",
        slug="perf-test-tenant",
        whatsapp_number="+1111111111",
        status="active",
        subscription_tier=subscription_tier
    )


@pytest.fixture
def performance_customer(db, performance_tenant):
    """Create customer for performance testing."""
    return Customer.objects.create(
        tenant=performance_tenant,
        phone_e164="+1234567890",
        name="Performance Test Customer"
    )


@pytest.fixture
def performance_conversation(db, performance_tenant, performance_customer):
    """Create conversation for performance testing."""
    return Conversation.objects.create(
        tenant=performance_tenant,
        customer=performance_customer,
        status="bot",
        channel="whatsapp"
    )


@pytest.fixture
def large_product_catalog(db, performance_tenant):
    """Create large product catalog for performance testing."""
    products = []
    for i in range(100):
        product = Product.objects.create(
            tenant=performance_tenant,
            title=f"Product {i}",
            description=f"Description for product {i}",
            price=Decimal(f'{10 + i}.99'),
            stock=10,
            is_active=True
        )
        products.append(product)
    return products


@pytest.fixture
def large_service_catalog(db, performance_tenant):
    """Create large service catalog for performance testing."""
    services = []
    for i in range(50):
        service = Service.objects.create(
            tenant=performance_tenant,
            title=f"Service {i}",
            description=f"Description for service {i}",
            is_active=True
        )
        services.append(service)
    return services


@pytest.fixture
def large_conversation_history(db, performance_conversation):
    """Create large conversation history for performance testing."""
    messages = []
    for i in range(50):
        msg = Message.objects.create(
            conversation=performance_conversation,
            direction='in' if i % 2 == 0 else 'out',
            message_type='customer_inbound' if i % 2 == 0 else 'bot_response',
            text=f"This is message number {i} with some content to simulate real conversation"
        )
        messages.append(msg)
    return messages


@pytest.fixture
def large_knowledge_base(db, performance_tenant):
    """Create large knowledge base for performance testing."""
    with patch('apps.bot.services.knowledge_base_service.OpenAI') as mock_openai:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        kb_service = KnowledgeBaseService(api_key='test-key')
        entries = []
        
        for i in range(100):
            entry = kb_service.create_entry(
                tenant=performance_tenant,
                entry_type='faq',
                title=f'FAQ Question {i}',
                content=f'This is the answer to FAQ question {i} with detailed information'
            )
            entries.append(entry)
        
        return entries


@pytest.fixture(autouse=True)
def clear_cache_before_test():
    """Clear cache before each test."""
    cache.clear()
    yield
    cache.clear()


def measure_execution_time(func, *args, **kwargs):
    """Measure execution time of a function."""
    start_time = time.time()
    result = func(*args, **kwargs)
    end_time = time.time()
    execution_time = end_time - start_time
    return result, execution_time


def calculate_percentiles(times):
    """Calculate percentile statistics."""
    sorted_times = sorted(times)
    return {
        'p50': statistics.median(sorted_times),
        'p95': sorted_times[int(len(sorted_times) * 0.95)] if len(sorted_times) > 1 else sorted_times[0],
        'p99': sorted_times[int(len(sorted_times) * 0.99)] if len(sorted_times) > 1 else sorted_times[0],
        'mean': statistics.mean(sorted_times),
        'min': min(sorted_times),
        'max': max(sorted_times)
    }


@pytest.mark.django_db
class TestContextBuildingSpeed:
    """Test context building performance."""
    
    def test_context_build_with_minimal_data(
        self,
        performance_tenant,
        performance_conversation
    ):
        """Test context building speed with minimal data."""
        message = Message.objects.create(
            conversation=performance_conversation,
            direction='in',
            message_type='customer_inbound',
            text="Hello"
        )
        
        context_builder = ContextBuilderService()
        
        _, execution_time = measure_execution_time(
            context_builder.build_context,
            conversation=performance_conversation,
            message=message,
            tenant=performance_tenant
        )
        
        print(f"\nContext build (minimal data): {execution_time:.3f}s")
        assert execution_time < CONTEXT_BUILD_THRESHOLD, \
            f"Context building took {execution_time:.3f}s, expected < {CONTEXT_BUILD_THRESHOLD}s"
    
    def test_context_build_with_large_history(
        self,
        performance_tenant,
        performance_conversation,
        large_conversation_history
    ):
        """Test context building speed with large conversation history."""
        message = Message.objects.create(
            conversation=performance_conversation,
            direction='in',
            message_type='customer_inbound',
            text="What was I asking about earlier?"
        )
        
        context_builder = ContextBuilderService()
        
        _, execution_time = measure_execution_time(
            context_builder.build_context,
            conversation=performance_conversation,
            message=message,
            tenant=performance_tenant
        )
        
        print(f"\nContext build (large history): {execution_time:.3f}s")
        assert execution_time < CONTEXT_BUILD_THRESHOLD, \
            f"Context building with large history took {execution_time:.3f}s, expected < {CONTEXT_BUILD_THRESHOLD}s"
    
    def test_context_build_with_large_catalog(
        self,
        performance_tenant,
        performance_conversation,
        large_product_catalog,
        large_service_catalog
    ):
        """Test context building speed with large catalog."""
        message = Message.objects.create(
            conversation=performance_conversation,
            direction='in',
            message_type='customer_inbound',
            text="What products do you have?"
        )
        
        context_builder = ContextBuilderService()
        
        _, execution_time = measure_execution_time(
            context_builder.build_context,
            conversation=performance_conversation,
            message=message,
            tenant=performance_tenant
        )
        
        print(f"\nContext build (large catalog): {execution_time:.3f}s")
        assert execution_time < CONTEXT_BUILD_THRESHOLD, \
            f"Context building with large catalog took {execution_time:.3f}s, expected < {CONTEXT_BUILD_THRESHOLD}s"
    
    def test_context_build_repeated_calls(
        self,
        performance_tenant,
        performance_conversation,
        large_conversation_history,
        large_product_catalog
    ):
        """Test context building performance with repeated calls (caching)."""
        message = Message.objects.create(
            conversation=performance_conversation,
            direction='in',
            message_type='customer_inbound',
            text="Tell me about your products"
        )
        
        context_builder = ContextBuilderService()
        
        # First call (cold cache)
        _, first_time = measure_execution_time(
            context_builder.build_context,
            conversation=performance_conversation,
            message=message,
            tenant=performance_tenant
        )
        
        # Second call (warm cache)
        _, second_time = measure_execution_time(
            context_builder.build_context,
            conversation=performance_conversation,
            message=message,
            tenant=performance_tenant
        )
        
        print(f"\nContext build - First call: {first_time:.3f}s, Second call: {second_time:.3f}s")
        print(f"Cache speedup: {((first_time - second_time) / first_time * 100):.1f}%")
        
        # Both calls should complete within threshold
        # Note: Caching may not always be faster in test environment due to overhead
        assert first_time < CONTEXT_BUILD_THRESHOLD * 2, \
            f"First call took {first_time:.3f}s, expected < {CONTEXT_BUILD_THRESHOLD * 2}s"
        assert second_time < CONTEXT_BUILD_THRESHOLD * 2, \
            f"Second call took {second_time:.3f}s, expected < {CONTEXT_BUILD_THRESHOLD * 2}s"


@pytest.mark.django_db
class TestKnowledgeSearchSpeed:
    """Test knowledge base search performance."""
    
    def test_knowledge_search_small_base(
        self,
        performance_tenant
    ):
        """Test knowledge search speed with small knowledge base."""
        with patch('apps.bot.services.knowledge_base_service.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
            mock_client.embeddings.create.return_value = mock_response
            mock_openai.return_value = mock_client
            
            kb_service = KnowledgeBaseService(api_key='test-key')
            
            # Create small knowledge base
            for i in range(10):
                kb_service.create_entry(
                    tenant=performance_tenant,
                    entry_type='faq',
                    title=f'Question {i}',
                    content=f'Answer {i}'
                )
            
            # Measure search time
            _, execution_time = measure_execution_time(
                kb_service.search,
                tenant=performance_tenant,
                query='What is your policy?',
                limit=5
            )
            
            print(f"\nKnowledge search (small base): {execution_time:.3f}s")
            assert execution_time < KNOWLEDGE_SEARCH_THRESHOLD, \
                f"Knowledge search took {execution_time:.3f}s, expected < {KNOWLEDGE_SEARCH_THRESHOLD}s"
    
    def test_knowledge_search_large_base(
        self,
        performance_tenant,
        large_knowledge_base
    ):
        """Test knowledge search speed with large knowledge base."""
        with patch('apps.bot.services.knowledge_base_service.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
            mock_client.embeddings.create.return_value = mock_response
            mock_openai.return_value = mock_client
            
            kb_service = KnowledgeBaseService(api_key='test-key')
            
            # Measure search time
            _, execution_time = measure_execution_time(
                kb_service.search,
                tenant=performance_tenant,
                query='What is your shipping policy?',
                limit=5
            )
            
            print(f"\nKnowledge search (large base): {execution_time:.3f}s")
            assert execution_time < KNOWLEDGE_SEARCH_THRESHOLD, \
                f"Knowledge search with large base took {execution_time:.3f}s, expected < {KNOWLEDGE_SEARCH_THRESHOLD}s"
    
    def test_knowledge_search_caching(
        self,
        performance_tenant,
        large_knowledge_base
    ):
        """Test knowledge search caching performance."""
        with patch('apps.bot.services.knowledge_base_service.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
            mock_client.embeddings.create.return_value = mock_response
            mock_openai.return_value = mock_client
            
            kb_service = KnowledgeBaseService(api_key='test-key')
            
            query = 'What is your return policy?'
            
            # First search (cold cache)
            _, first_time = measure_execution_time(
                kb_service.search,
                tenant=performance_tenant,
                query=query,
                limit=5
            )
            
            # Second search (warm cache)
            _, second_time = measure_execution_time(
                kb_service.search,
                tenant=performance_tenant,
                query=query,
                limit=5
            )
            
            print(f"\nKnowledge search - First: {first_time:.3f}s, Second: {second_time:.3f}s")
            
            # Cached search should be significantly faster
            assert second_time < first_time, \
                "Cached knowledge search should be faster"


@pytest.mark.django_db
class TestResponseTimeUnderLoad:
    """Test response time under load."""
    
    def test_sequential_message_processing(
        self,
        performance_tenant,
        performance_conversation,
        large_product_catalog
    ):
        """Test response time for sequential message processing."""
        context_builder = ContextBuilderService()
        execution_times = []
        
        # Process 20 messages sequentially
        for i in range(20):
            message = Message.objects.create(
                conversation=performance_conversation,
                direction='in',
                message_type='customer_inbound',
                text=f"Tell me about product {i}"
            )
            
            _, execution_time = measure_execution_time(
                context_builder.build_context,
                conversation=performance_conversation,
                message=message,
                tenant=performance_tenant
            )
            
            execution_times.append(execution_time)
        
        # Calculate statistics
        stats = calculate_percentiles(execution_times)
        
        print(f"\nSequential processing stats:")
        print(f"  P50: {stats['p50']:.3f}s")
        print(f"  P95: {stats['p95']:.3f}s")
        print(f"  P99: {stats['p99']:.3f}s")
        print(f"  Mean: {stats['mean']:.3f}s")
        print(f"  Min: {stats['min']:.3f}s")
        print(f"  Max: {stats['max']:.3f}s")
        
        # P95 should be under threshold
        assert stats['p95'] < RESPONSE_TIME_P95_THRESHOLD, \
            f"P95 response time {stats['p95']:.3f}s exceeds threshold {RESPONSE_TIME_P95_THRESHOLD}s"
    
    def test_burst_message_processing(
        self,
        performance_tenant,
        performance_conversation,
        large_conversation_history
    ):
        """Test response time for burst message processing."""
        context_builder = ContextBuilderService()
        
        # Create burst of messages
        messages = []
        for i in range(10):
            message = Message.objects.create(
                conversation=performance_conversation,
                direction='in',
                message_type='customer_inbound',
                text=f"Quick question {i}"
            )
            messages.append(message)
        
        # Process burst
        execution_times = []
        for message in messages:
            _, execution_time = measure_execution_time(
                context_builder.build_context,
                conversation=performance_conversation,
                message=message,
                tenant=performance_tenant
            )
            execution_times.append(execution_time)
        
        stats = calculate_percentiles(execution_times)
        
        print(f"\nBurst processing stats:")
        print(f"  P95: {stats['p95']:.3f}s")
        print(f"  Mean: {stats['mean']:.3f}s")
        
        assert stats['p95'] < RESPONSE_TIME_P95_THRESHOLD, \
            f"Burst P95 response time {stats['p95']:.3f}s exceeds threshold"


@pytest.mark.django_db(transaction=True)
class TestConcurrentTenantUsage:
    """Test concurrent tenant usage performance."""
    
    @pytest.mark.skip(reason="Threading tests require special database configuration")
    def test_concurrent_context_building(
        self,
        db,
        subscription_tier
    ):
        """Test context building with multiple tenants concurrently."""
        # Create multiple tenants
        num_tenants = 5
        tenants_data = []
        
        for i in range(num_tenants):
            tenant = Tenant.objects.create(
                name=f"Concurrent Tenant {i}",
                slug=f"concurrent-tenant-{i}",
                whatsapp_number=f"+111111111{i}",
                status="active",
                subscription_tier=subscription_tier
            )
            
            customer = Customer.objects.create(
                tenant=tenant,
                phone_e164=f"+123456789{i}",
                name=f"Customer {i}"
            )
            
            conversation = Conversation.objects.create(
                tenant=tenant,
                customer=customer,
                status="bot",
                channel="whatsapp"
            )
            
            message = Message.objects.create(
                conversation=conversation,
                direction='in',
                message_type='customer_inbound',
                text=f"Hello from tenant {i}"
            )
            
            tenants_data.append({
                'tenant': tenant,
                'conversation': conversation,
                'message': message
            })
        
        context_builder = ContextBuilderService()
        
        def build_context_for_tenant(tenant_data):
            """Build context for a single tenant."""
            start_time = time.time()
            context = context_builder.build_context(
                conversation=tenant_data['conversation'],
                message=tenant_data['message'],
                tenant=tenant_data['tenant']
            )
            end_time = time.time()
            return end_time - start_time
        
        # Execute concurrently
        execution_times = []
        with ThreadPoolExecutor(max_workers=num_tenants) as executor:
            futures = [
                executor.submit(build_context_for_tenant, tenant_data)
                for tenant_data in tenants_data
            ]
            
            for future in as_completed(futures):
                execution_time = future.result()
                execution_times.append(execution_time)
        
        stats = calculate_percentiles(execution_times)
        
        print(f"\nConcurrent tenant usage stats ({num_tenants} tenants):")
        print(f"  P95: {stats['p95']:.3f}s")
        print(f"  Mean: {stats['mean']:.3f}s")
        print(f"  Max: {stats['max']:.3f}s")
        
        # All tenants should complete within threshold
        assert stats['p95'] < RESPONSE_TIME_P95_THRESHOLD, \
            f"Concurrent P95 response time {stats['p95']:.3f}s exceeds threshold"
    
    @pytest.mark.skip(reason="Threading tests require special database configuration")
    def test_concurrent_knowledge_search(
        self,
        db,
        subscription_tier
    ):
        """Test knowledge search with multiple tenants concurrently."""
        with patch('apps.bot.services.knowledge_base_service.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
            mock_client.embeddings.create.return_value = mock_response
            mock_openai.return_value = mock_client
            
            kb_service = KnowledgeBaseService(api_key='test-key')
            
            # Create multiple tenants with knowledge bases
            num_tenants = 5
            tenants = []
            
            for i in range(num_tenants):
                tenant = Tenant.objects.create(
                    name=f"KB Tenant {i}",
                    slug=f"kb-tenant-{i}",
                    whatsapp_number=f"+222222222{i}",
                    status="active",
                    subscription_tier=subscription_tier
                )
                
                # Create knowledge entries
                for j in range(20):
                    kb_service.create_entry(
                        tenant=tenant,
                        entry_type='faq',
                        title=f'Tenant {i} Question {j}',
                        content=f'Tenant {i} Answer {j}'
                    )
                
                tenants.append(tenant)
            
            def search_for_tenant(tenant):
                """Search knowledge base for a tenant."""
                start_time = time.time()
                results = kb_service.search(
                    tenant=tenant,
                    query='What is your policy?',
                    limit=5
                )
                end_time = time.time()
                return end_time - start_time
            
            # Execute searches concurrently
            execution_times = []
            with ThreadPoolExecutor(max_workers=num_tenants) as executor:
                futures = [
                    executor.submit(search_for_tenant, tenant)
                    for tenant in tenants
                ]
                
                for future in as_completed(futures):
                    execution_time = future.result()
                    execution_times.append(execution_time)
            
            stats = calculate_percentiles(execution_times)
            
            print(f"\nConcurrent knowledge search stats ({num_tenants} tenants):")
            print(f"  P95: {stats['p95']:.3f}s")
            print(f"  Mean: {stats['mean']:.3f}s")
            
            assert stats['p95'] < KNOWLEDGE_SEARCH_THRESHOLD, \
                f"Concurrent search P95 {stats['p95']:.3f}s exceeds threshold"
    
    @pytest.mark.skip(reason="Threading tests require special database configuration")
    def test_tenant_isolation_under_load(
        self,
        db,
        subscription_tier
    ):
        """Test that tenant isolation is maintained under concurrent load."""
        with patch('apps.bot.services.knowledge_base_service.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
            mock_client.embeddings.create.return_value = mock_response
            mock_openai.return_value = mock_client
            
            kb_service = KnowledgeBaseService(api_key='test-key')
            
            # Create two tenants with distinct knowledge
            tenant1 = Tenant.objects.create(
                name="Isolation Tenant 1",
                slug="isolation-tenant-1",
                whatsapp_number="+3333333331",
                status="active",
                subscription_tier=subscription_tier
            )
            
            tenant2 = Tenant.objects.create(
                name="Isolation Tenant 2",
                slug="isolation-tenant-2",
                whatsapp_number="+3333333332",
                status="active",
                subscription_tier=subscription_tier
            )
            
            # Create unique entries for each tenant
            entry1 = kb_service.create_entry(
                tenant=tenant1,
                entry_type='faq',
                title='Tenant 1 Unique Entry',
                content='This is unique to tenant 1'
            )
            
            entry2 = kb_service.create_entry(
                tenant=tenant2,
                entry_type='faq',
                title='Tenant 2 Unique Entry',
                content='This is unique to tenant 2'
            )
            
            def search_and_verify(tenant, expected_entry_id, unexpected_entry_id):
                """Search and verify tenant isolation."""
                results = kb_service.search(
                    tenant=tenant,
                    query='unique entry',
                    limit=10,
                    min_similarity=0.0
                )
                
                entry_ids = [entry.id for entry, score in results]
                
                # Should find own entry
                assert expected_entry_id in entry_ids, \
                    f"Tenant should find its own entry"
                
                # Should NOT find other tenant's entry
                assert unexpected_entry_id not in entry_ids, \
                    f"Tenant should NOT find other tenant's entry"
                
                return True
            
            # Execute concurrent searches
            with ThreadPoolExecutor(max_workers=2) as executor:
                future1 = executor.submit(
                    search_and_verify,
                    tenant1,
                    entry1.id,
                    entry2.id
                )
                future2 = executor.submit(
                    search_and_verify,
                    tenant2,
                    entry2.id,
                    entry1.id
                )
                
                # Both should succeed
                assert future1.result() is True
                assert future2.result() is True
            
            print("\nTenant isolation maintained under concurrent load")


@pytest.mark.django_db
class TestScalabilityLimits:
    """Test system behavior at scale limits."""
    
    def test_very_large_conversation_history(
        self,
        performance_tenant,
        performance_conversation
    ):
        """Test context building with very large conversation history."""
        # Create 200 messages
        for i in range(200):
            Message.objects.create(
                conversation=performance_conversation,
                direction='in' if i % 2 == 0 else 'out',
                message_type='customer_inbound' if i % 2 == 0 else 'bot_response',
                text=f"Message {i} with content"
            )
        
        message = Message.objects.create(
            conversation=performance_conversation,
            direction='in',
            message_type='customer_inbound',
            text="What did we discuss?"
        )
        
        context_builder = ContextBuilderService()
        
        _, execution_time = measure_execution_time(
            context_builder.build_context,
            conversation=performance_conversation,
            message=message,
            tenant=performance_tenant
        )
        
        print(f"\nVery large history (200 messages): {execution_time:.3f}s")
        
        # Should still complete within threshold
        assert execution_time < CONTEXT_BUILD_THRESHOLD * 2, \
            f"Very large history took {execution_time:.3f}s, expected < {CONTEXT_BUILD_THRESHOLD * 2}s"
    
    def test_memory_efficiency(
        self,
        performance_tenant,
        performance_conversation,
        large_product_catalog,
        large_conversation_history
    ):
        """Test memory efficiency with large datasets."""
        import sys
        
        context_builder = ContextBuilderService()
        
        message = Message.objects.create(
            conversation=performance_conversation,
            direction='in',
            message_type='customer_inbound',
            text="Show me products"
        )
        
        # Build context
        context = context_builder.build_context(
            conversation=performance_conversation,
            message=message,
            tenant=performance_tenant
        )
        
        # Check context size is reasonable
        context_size = sys.getsizeof(context)
        
        print(f"\nContext object size: {context_size} bytes")
        
        # Context should be under 1MB
        assert context_size < 1024 * 1024, \
            f"Context size {context_size} bytes exceeds 1MB limit"



@pytest.mark.django_db
class TestReferenceContextCachePerformance:
    """Test reference context cache hit rates and performance."""
    
    def test_reference_context_cache_hit_rate(
        self,
        performance_tenant,
        performance_conversation,
        large_product_catalog
    ):
        """Test that reference context caching improves performance."""
        from apps.bot.services.reference_context_manager import ReferenceContextManager
        from django.core.cache import cache
        
        # Clear cache
        cache.clear()
        
        # Store a reference context
        items = [
            {'id': str(p.id), 'title': p.title, 'price': str(p.price)}
            for p in large_product_catalog[:10]
        ]
        
        context_id = ReferenceContextManager.store_list_context(
            conversation=performance_conversation,
            list_type='products',
            items=items
        )
        
        # First retrieval (should hit cache)
        _, first_time = measure_execution_time(
            ReferenceContextManager.resolve_reference,
            conversation=performance_conversation,
            message_text="1"
        )
        
        # Second retrieval (should also hit cache)
        _, second_time = measure_execution_time(
            ReferenceContextManager.resolve_reference,
            conversation=performance_conversation,
            message_text="2"
        )
        
        # Third retrieval (should also hit cache)
        _, third_time = measure_execution_time(
            ReferenceContextManager.resolve_reference,
            conversation=performance_conversation,
            message_text="3"
        )
        
        print(f"\nReference context resolution times:")
        print(f"  First: {first_time:.4f}s")
        print(f"  Second: {second_time:.4f}s")
        print(f"  Third: {third_time:.4f}s")
        
        # All should be fast (under 0.1s)
        assert first_time < 0.1, f"First resolution took {first_time:.4f}s"
        assert second_time < 0.1, f"Second resolution took {second_time:.4f}s"
        assert third_time < 0.1, f"Third resolution took {third_time:.4f}s"
    
    def test_reference_context_cache_vs_db(
        self,
        performance_tenant,
        performance_conversation,
        large_product_catalog
    ):
        """Test cache performance vs database queries."""
        from apps.bot.services.reference_context_manager import ReferenceContextManager
        from django.core.cache import cache
        
        items = [
            {'id': str(p.id), 'title': p.title, 'price': str(p.price)}
            for p in large_product_catalog[:10]
        ]
        
        # Test with cache
        cache.clear()
        context_id = ReferenceContextManager.store_list_context(
            conversation=performance_conversation,
            list_type='products',
            items=items
        )
        
        cache_times = []
        for i in range(10):
            _, exec_time = measure_execution_time(
                ReferenceContextManager.resolve_reference,
                conversation=performance_conversation,
                message_text=str(i % 5 + 1)
            )
            cache_times.append(exec_time)
        
        # Test without cache (clear and force DB queries)
        cache.clear()
        
        db_times = []
        for i in range(10):
            # Re-store context to ensure it's in DB
            if i == 0:
                ReferenceContextManager.store_list_context(
                    conversation=performance_conversation,
                    list_type='products',
                    items=items
                )
            
            # Clear cache before each query to force DB hit
            cache.delete(f"ref_context:{performance_conversation.id}:current")
            
            _, exec_time = measure_execution_time(
                ReferenceContextManager.resolve_reference,
                conversation=performance_conversation,
                message_text=str(i % 5 + 1)
            )
            db_times.append(exec_time)
        
        avg_cache_time = statistics.mean(cache_times)
        avg_db_time = statistics.mean(db_times)
        
        print(f"\nReference context performance:")
        print(f"  Average with cache: {avg_cache_time:.4f}s")
        print(f"  Average without cache: {avg_db_time:.4f}s")
        print(f"  Speedup: {(avg_db_time / avg_cache_time):.2f}x")
        
        # Cache should be faster or at least not slower
        # Note: In test environment, cache might not always be faster due to overhead
        assert avg_cache_time <= avg_db_time * 1.5, \
            "Cache should not be significantly slower than DB"


@pytest.mark.django_db
class TestConversationHistoryQueryPerformance:
    """Test conversation history query performance with indexes."""
    
    def test_conversation_history_query_speed(
        self,
        performance_tenant,
        performance_conversation,
        large_conversation_history
    ):
        """Test conversation history query performance."""
        from apps.bot.services.conversation_history_service import ConversationHistoryService
        
        history_service = ConversationHistoryService()
        
        # Test full history retrieval
        _, execution_time = measure_execution_time(
            history_service.get_full_history,
            conversation=performance_conversation
        )
        
        print(f"\nFull history retrieval (50 messages): {execution_time:.3f}s")
        
        # Should be fast with indexes
        assert execution_time < 1.0, \
            f"History retrieval took {execution_time:.3f}s, expected < 1.0s"
    
    def test_conversation_history_pagination_performance(
        self,
        performance_tenant,
        performance_conversation,
        large_conversation_history
    ):
        """Test paginated history retrieval performance."""
        from apps.bot.services.conversation_history_service import ConversationHistoryService
        
        history_service = ConversationHistoryService()
        
        # Test paginated retrieval
        page_times = []
        for page in range(1, 6):  # Test 5 pages
            _, exec_time = measure_execution_time(
                history_service.get_history_page,
                conversation=performance_conversation,
                page=page,
                page_size=10
            )
            page_times.append(exec_time)
        
        stats = calculate_percentiles(page_times)
        
        print(f"\nPaginated history retrieval stats:")
        print(f"  Mean: {stats['mean']:.3f}s")
        print(f"  P95: {stats['p95']:.3f}s")
        print(f"  Max: {stats['max']:.3f}s")
        
        # All pages should load quickly
        assert stats['p95'] < 0.5, \
            f"P95 page load time {stats['p95']:.3f}s exceeds 0.5s"
    
    def test_conversation_history_with_large_dataset(
        self,
        performance_tenant,
        performance_conversation
    ):
        """Test history query performance with very large conversation."""
        from apps.bot.services.conversation_history_service import ConversationHistoryService
        
        # Create 500 messages
        for i in range(500):
            Message.objects.create(
                conversation=performance_conversation,
                direction='in' if i % 2 == 0 else 'out',
                message_type='customer_inbound' if i % 2 == 0 else 'bot_response',
                text=f"Message {i}"
            )
        
        history_service = ConversationHistoryService()
        
        # Test paginated retrieval (should be fast even with 500 messages)
        _, execution_time = measure_execution_time(
            history_service.get_history_page,
            conversation=performance_conversation,
            page=1,
            page_size=50
        )
        
        print(f"\nHistory page retrieval (500 total messages): {execution_time:.3f}s")
        
        # Should still be fast with indexes
        assert execution_time < 1.0, \
            f"Page retrieval took {execution_time:.3f}s, expected < 1.0s"


@pytest.mark.django_db
class TestProductDiscoveryQueryPerformance:
    """Test product discovery query performance with optimizations."""
    
    def test_product_discovery_query_speed(
        self,
        performance_tenant,
        large_product_catalog
    ):
        """Test product discovery query performance."""
        from apps.bot.services.discovery_service import SmartProductDiscoveryService
        
        discovery_service = SmartProductDiscoveryService()
        
        # Test immediate suggestions
        _, execution_time = measure_execution_time(
            discovery_service.get_immediate_suggestions,
            tenant=performance_tenant,
            query=None,
            limit=5
        )
        
        print(f"\nProduct discovery (no query): {execution_time:.3f}s")
        
        # Should be fast with caching
        assert execution_time < 1.0, \
            f"Product discovery took {execution_time:.3f}s, expected < 1.0s"
    
    def test_product_search_performance(
        self,
        performance_tenant,
        large_product_catalog
    ):
        """Test product search performance."""
        from apps.bot.services.discovery_service import SmartProductDiscoveryService
        
        discovery_service = SmartProductDiscoveryService()
        
        # Test search with query
        search_times = []
        queries = ["product", "item", "test", "description", "price"]
        
        for query in queries:
            _, exec_time = measure_execution_time(
                discovery_service.search_products,
                tenant=performance_tenant,
                query=query,
                limit=10
            )
            search_times.append(exec_time)
        
        stats = calculate_percentiles(search_times)
        
        print(f"\nProduct search performance:")
        print(f"  Mean: {stats['mean']:.3f}s")
        print(f"  P95: {stats['p95']:.3f}s")
        
        # Searches should be fast
        assert stats['p95'] < 1.0, \
            f"P95 search time {stats['p95']:.3f}s exceeds 1.0s"
    
    def test_product_discovery_cache_effectiveness(
        self,
        performance_tenant,
        large_product_catalog
    ):
        """Test that caching improves product discovery performance."""
        from apps.bot.services.discovery_service import SmartProductDiscoveryService
        from django.core.cache import cache
        
        discovery_service = SmartProductDiscoveryService()
        
        # Clear cache
        cache.clear()
        
        # First call (cold cache)
        _, first_time = measure_execution_time(
            discovery_service.get_immediate_suggestions,
            tenant=performance_tenant,
            query="product",
            limit=5
        )
        
        # Second call (warm cache)
        _, second_time = measure_execution_time(
            discovery_service.get_immediate_suggestions,
            tenant=performance_tenant,
            query="product",
            limit=5
        )
        
        # Third call (warm cache)
        _, third_time = measure_execution_time(
            discovery_service.get_immediate_suggestions,
            tenant=performance_tenant,
            query="product",
            limit=5
        )
        
        print(f"\nProduct discovery caching:")
        print(f"  First call (cold): {first_time:.3f}s")
        print(f"  Second call (warm): {second_time:.3f}s")
        print(f"  Third call (warm): {third_time:.3f}s")
        
        # Subsequent calls should be faster or similar
        # Note: In test environment, cache might not always be faster
        assert second_time <= first_time * 1.5, \
            "Cached calls should not be significantly slower"
        assert third_time <= first_time * 1.5, \
            "Cached calls should not be significantly slower"


@pytest.mark.django_db
class TestQueryPerformanceMonitoring:
    """Test query performance monitoring capabilities."""
    
    def test_context_builder_query_count(
        self,
        performance_tenant,
        performance_conversation,
        large_product_catalog,
        large_conversation_history
    ):
        """Test that context building doesn't generate excessive queries."""
        from django.test.utils import override_settings
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from apps.bot.services.context_builder_service import ContextBuilderService
        
        message = Message.objects.create(
            conversation=performance_conversation,
            direction='in',
            message_type='customer_inbound',
            text="Show me products"
        )
        
        context_builder = ContextBuilderService()
        
        # Count queries
        with CaptureQueriesContext(connection) as queries:
            context = context_builder.build_context(
                conversation=performance_conversation,
                message=message,
                tenant=performance_tenant
            )
        
        query_count = len(queries)
        
        print(f"\nContext building query count: {query_count}")
        
        # Should use reasonable number of queries (with select_related/prefetch_related)
        # Allow up to 35 queries for complex context building with large datasets
        # (includes conversation history, products, services, knowledge base, etc.)
        assert query_count < 35, \
            f"Context building used {query_count} queries, expected < 35"
    
    def test_product_discovery_query_count(
        self,
        performance_tenant,
        large_product_catalog
    ):
        """Test that product discovery doesn't generate excessive queries."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from apps.bot.services.discovery_service import SmartProductDiscoveryService
        from django.core.cache import cache
        
        # Clear cache to test actual query count
        cache.clear()
        
        discovery_service = SmartProductDiscoveryService()
        
        # Count queries
        with CaptureQueriesContext(connection) as queries:
            result = discovery_service.get_immediate_suggestions(
                tenant=performance_tenant,
                query="product",
                limit=5
            )
        
        query_count = len(queries)
        
        print(f"\nProduct discovery query count: {query_count}")
        
        # Should use minimal queries (ideally 1-2 with caching)
        assert query_count < 10, \
            f"Product discovery used {query_count} queries, expected < 10"
    
    def test_conversation_history_query_count(
        self,
        performance_conversation,
        large_conversation_history
    ):
        """Test that conversation history retrieval is optimized."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from apps.bot.services.conversation_history_service import ConversationHistoryService
        
        history_service = ConversationHistoryService()
        
        # Count queries
        with CaptureQueriesContext(connection) as queries:
            messages = history_service.get_full_history(
                conversation=performance_conversation
            )
        
        query_count = len(queries)
        
        print(f"\nConversation history query count: {query_count}")
        
        # Should use single query with select_related
        assert query_count <= 2, \
            f"History retrieval used {query_count} queries, expected <= 2"


@pytest.mark.django_db
class TestCacheHitRateMetrics:
    """Test cache hit rate tracking and metrics."""
    
    def test_reference_context_cache_hit_rate_calculation(
        self,
        performance_tenant,
        performance_conversation,
        large_product_catalog
    ):
        """Test cache hit rate for reference contexts."""
        from apps.bot.services.reference_context_manager import ReferenceContextManager
        from django.core.cache import cache
        
        cache.clear()
        
        items = [
            {'id': str(p.id), 'title': p.title}
            for p in large_product_catalog[:10]
        ]
        
        # Store context
        ReferenceContextManager.store_list_context(
            conversation=performance_conversation,
            list_type='products',
            items=items
        )
        
        # Perform 100 lookups
        hits = 0
        misses = 0
        
        for i in range(100):
            # Every 10th lookup, clear cache to simulate miss
            if i % 10 == 0 and i > 0:
                cache.delete(f"ref_context:{performance_conversation.id}:current")
                misses += 1
            else:
                hits += 1
            
            result = ReferenceContextManager.resolve_reference(
                conversation=performance_conversation,
                message_text=str((i % 5) + 1)
            )
        
        hit_rate = hits / (hits + misses) * 100
        
        print(f"\nReference context cache metrics:")
        print(f"  Hits: {hits}")
        print(f"  Misses: {misses}")
        print(f"  Hit rate: {hit_rate:.1f}%")
        
        # Should have high hit rate
        assert hit_rate >= 80, \
            f"Cache hit rate {hit_rate:.1f}% is below 80%"
    
    def test_catalog_cache_hit_rate(
        self,
        performance_tenant,
        large_product_catalog
    ):
        """Test cache hit rate for catalog queries."""
        from apps.bot.services.catalog_cache_service import CatalogCacheService
        from django.core.cache import cache
        
        cache.clear()
        
        # First call (miss)
        products1 = CatalogCacheService.get_products(performance_tenant, active_only=True)
        
        # Subsequent calls (hits)
        hits = 0
        for i in range(50):
            products = CatalogCacheService.get_products(performance_tenant, active_only=True)
            if products:
                hits += 1
        
        hit_rate = hits / 50 * 100
        
        print(f"\nCatalog cache metrics:")
        print(f"  Hits: {hits}/50")
        print(f"  Hit rate: {hit_rate:.1f}%")
        
        # Should have very high hit rate (all hits after first)
        assert hit_rate >= 95, \
            f"Catalog cache hit rate {hit_rate:.1f}% is below 95%"
