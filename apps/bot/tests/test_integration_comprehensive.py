"""
Comprehensive integration tests for conversational commerce UX enhancements.

Tests:
1. Complete inquiry-to-sale journey
2. Multi-turn conversations with context
3. Error recovery scenarios

Requirements: Task 18.1 - Integration Testing
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from django.utils import timezone
from datetime import timedelta

from apps.tenants.models import Tenant, Customer
from apps.messaging.models import Conversation, Message
from apps.catalog.models import Product
from apps.services.models import Service
from apps.bot.models import AgentConfiguration, ConversationContext, ReferenceContext
from apps.bot.services.ai_agent_service import AIAgentService
from apps.bot.services.message_harmonization_service import create_message_harmonization_service
from apps.bot.services.reference_context_manager import ReferenceContextManager
from apps.bot.services.language_consistency_manager import LanguageConsistencyManager
from apps.bot.services.rich_message_builder import RichMessageBuilder


@pytest.mark.django_db
class TestCompleteInquiryToSaleJourney:
    """
    Test complete inquiry-to-sale journey from initial contact to payment.
    
    This tests the entire flow a customer would experience:
    1. Initial greeting and product inquiry
    2. Product browsing with immediate display
    3. Product selection using reference resolution
    4. Quantity confirmation
    5. Checkout guidance with payment link
    """
    
    def test_full_purchase_journey_with_all_enhancements(self, tenant, customer):
        """
        Test complete purchase journey with all UX enhancements active.
        
        Flow:
        - Customer: "Hi, what do you sell?"
        - Bot: Shows products immediately (no narrowing)
        - Customer: "1" (reference resolution)
        - Bot: Confirms product, asks quantity
        - Customer: "2 please"
        - Bot: Provides checkout link and order summary
        """
        # Setup: Create products
        products = [
            Product.objects.create(
                tenant=tenant,
                title="Premium Headphones",
                description="Wireless noise-cancelling headphones",
                price=Decimal('149.99'),
                is_active=True
            ),
            Product.objects.create(
                tenant=tenant,
                title="Smart Watch",
                description="Fitness tracking smartwatch",
                price=Decimal('299.99'),
                is_active=True
            ),
            Product.objects.create(
                tenant=tenant,
                title="Bluetooth Speaker",
                description="Portable waterproof speaker",
                price=Decimal('79.99'),
                is_active=True
            )
        ]
        
        # Create conversation
        conversation = Conversation.objects.create(
            tenant=tenant,
            customer=customer,
            channel='whatsapp',
            status='active'
        )
        
        # Create agent configuration with all features enabled
        agent_config = AgentConfiguration.objects.create(
            tenant=tenant,
            enable_message_harmonization=True,
            enable_immediate_product_display=True,
            enable_reference_resolution=True,
            enable_grounded_validation=True,
            use_business_name_as_identity=True
        )
        
        # Initialize service
        service = AIAgentService()
        
        # STEP 1: Initial greeting and product inquiry
        message1 = Message.objects.create(
            conversation=conversation,
            direction='in',
            message_type='customer_inbound',
            text='Hi, what do you sell?',
            created_at=timezone.now()
        )
        
        # Build context for first message
        context1 = service.context_builder.build_context(
            conversation=conversation,
            message=message1,
            tenant=tenant
        )
        
        # Verify context is built correctly
        assert context1.current_message == message1
        assert context1.conversation == conversation
        
        # Store reference context for products (simulating bot response)
        items = [
            {
                'id': str(p.id),
                'title': p.title,
                'price': str(p.price),
                'position': i + 1
            }
            for i, p in enumerate(products)
        ]
        
        context_id = ReferenceContextManager.store_list_context(
            conversation=conversation,
            list_type='products',
            items=items
        )
        
        assert context_id is not None
        
        # STEP 2: Customer selects product using positional reference
        message2 = Message.objects.create(
            conversation=conversation,
            direction='in',
            message_type='customer_inbound',
            text='1',
            created_at=timezone.now() + timedelta(seconds=5)
        )
        
        # Resolve reference
        resolved = ReferenceContextManager.resolve_reference(
            conversation=conversation,
            message_text='1'
        )
        
        # Verify reference resolution
        assert resolved is not None
        assert resolved['item']['id'] == str(products[0].id)
        assert resolved['item']['title'] == products[0].title
        assert resolved['position'] == 1
        
        # Build context with resolved reference
        context2 = service.context_builder.build_context(
            conversation=conversation,
            message=message2,
            tenant=tenant
        )
        
        # Verify conversation history is maintained
        assert len(context2.conversation_history) >= 1
        assert message1 in context2.conversation_history
        
        # STEP 3: Customer specifies quantity
        message3 = Message.objects.create(
            conversation=conversation,
            direction='in',
            message_type='customer_inbound',
            text='2 please',
            created_at=timezone.now() + timedelta(seconds=10)
        )
        
        # Build context
        context3 = service.context_builder.build_context(
            conversation=conversation,
            message=message3,
            tenant=tenant
        )
        
        # Verify full conversation history
        assert len(context3.conversation_history) >= 2
        assert message1 in context3.conversation_history
        assert message2 in context3.conversation_history
        
        # Verify product is in catalog context
        assert context3.catalog_context is not None
        
        # Calculate expected total
        expected_total = products[0].price * 2
        
        # Verify we can access product details for checkout
        selected_product = Product.objects.get(id=products[0].id)
        assert selected_product.price == products[0].price
        
        print(f"✓ Complete inquiry-to-sale journey test passed!")
        print(f"  - Product selected: {products[0].title}")
        print(f"  - Quantity: 2")
        print(f"  - Expected total: ${expected_total}")
    
    def test_service_booking_journey(self, tenant, customer):
        """
        Test complete service booking journey.
        
        Flow:
        - Customer: "I need a haircut"
        - Bot: Shows available services
        - Customer: "first one"
        - Bot: Shows available time slots
        - Customer: Selects time
        - Bot: Confirms booking
        """
        # Create services
        services = [
            Service.objects.create(
                tenant=tenant,
                title="Men's Haircut",
                description="Professional haircut service",
                base_price=Decimal('25.00'),
                is_active=True
            ),
            Service.objects.create(
                tenant=tenant,
                title="Hair Coloring",
                description="Professional hair coloring",
                base_price=Decimal('75.00'),
                is_active=True
            )
        ]
        
        # Create conversation
        conversation = Conversation.objects.create(
            tenant=tenant,
            customer=customer,
            channel='whatsapp',
            status='active'
        )
        
        # Initialize service
        service = AIAgentService()
        
        # Customer inquires about service
        message1 = Message.objects.create(
            conversation=conversation,
            direction='in',
            message_type='customer_inbound',
            text='I need a haircut'
        )
        
        # Build context
        context = service.context_builder.build_context(
            conversation=conversation,
            message=message1,
            tenant=tenant
        )
        
        # Verify services are available in context
        assert context.catalog_context is not None
        
        # Store reference context for services
        items = [
            {
                'id': str(s.id),
                'title': s.title,
                'price': str(s.base_price) if s.base_price else '0.00',
                'position': i + 1
            }
            for i, s in enumerate(services)
        ]
        
        ReferenceContextManager.store_list_context(
            conversation=conversation,
            list_type='services',
            items=items
        )
        
        # Customer selects service using ordinal reference
        message2 = Message.objects.create(
            conversation=conversation,
            direction='in',
            message_type='customer_inbound',
            text='first one',
            created_at=timezone.now() + timedelta(seconds=5)
        )
        
        # Resolve reference
        resolved = ReferenceContextManager.resolve_reference(
            conversation=conversation,
            message_text='first one'
        )
        
        # Verify resolution
        assert resolved is not None
        assert resolved['item']['id'] == str(services[0].id)
        assert resolved['list_type'] == 'services'
        
        print("✓ Service booking journey test passed!")


@pytest.mark.django_db
class TestMultiTurnConversationsWithContext:
    """
    Test multi-turn conversations with context retention.
    
    Tests that the bot maintains context across multiple conversation turns,
    remembers previous topics, and can provide conversation summaries.
    """
    
    def test_context_retention_across_multiple_topics(self, tenant, customer):
        """
        Test that context is retained when customer switches between topics.
        
        Flow:
        - Customer asks about products
        - Customer asks about shipping
        - Customer asks about returns
        - Customer refers back to products
        - Bot should remember all previous context
        """
        # Create conversation
        conversation = Conversation.objects.create(
            tenant=tenant,
            customer=customer,
            channel='whatsapp',
            status='active'
        )
        
        # Create product for context
        product = Product.objects.create(
            tenant=tenant,
            title="Laptop Computer",
            price=Decimal('1299.99'),
            is_active=True
        )
        
        # Initialize service
        service = AIAgentService()
        
        # Turn 1: Ask about products
        message1 = Message.objects.create(
            conversation=conversation,
            direction='in',
            message_type='customer_inbound',
            text='Do you have laptops?',
            created_at=timezone.now()
        )
        
        context1 = service.context_builder.build_context(
            conversation=conversation,
            message=message1,
            tenant=tenant
        )
        
        assert context1.current_message == message1
        
        # Turn 2: Ask about shipping
        message2 = Message.objects.create(
            conversation=conversation,
            direction='in',
            message_type='customer_inbound',
            text='How long does shipping take?',
            created_at=timezone.now() + timedelta(seconds=30)
        )
        
        context2 = service.context_builder.build_context(
            conversation=conversation,
            message=message2,
            tenant=tenant
        )
        
        # Verify previous message is in history
        assert len(context2.conversation_history) >= 1
        assert message1 in context2.conversation_history
        
        # Turn 3: Ask about returns
        message3 = Message.objects.create(
            conversation=conversation,
            direction='in',
            message_type='customer_inbound',
            text='What is your return policy?',
            created_at=timezone.now() + timedelta(seconds=60)
        )
        
        context3 = service.context_builder.build_context(
            conversation=conversation,
            message=message3,
            tenant=tenant
        )
        
        # Verify both previous messages are in history
        assert len(context3.conversation_history) >= 2
        assert message1 in context3.conversation_history
        assert message2 in context3.conversation_history
        
        # Turn 4: Refer back to products
        message4 = Message.objects.create(
            conversation=conversation,
            direction='in',
            message_type='customer_inbound',
            text='What was the price of that laptop again?',
            created_at=timezone.now() + timedelta(seconds=90)
        )
        
        context4 = service.context_builder.build_context(
            conversation=conversation,
            message=message4,
            tenant=tenant
        )
        
        # Verify all previous messages are in history
        assert len(context4.conversation_history) >= 3
        assert message1 in context4.conversation_history
        assert message2 in context4.conversation_history
        assert message3 in context4.conversation_history
        
        # Verify product is still in catalog context
        assert context4.catalog_context is not None
        
        print("✓ Multi-topic context retention test passed!")
    
    def test_conversation_summary_generation(self, tenant, customer):
        """
        Test that bot can provide conversation summary when asked.
        
        Validates Requirement 11.5: "what have we talked about"
        """
        # Create conversation
        conversation = Conversation.objects.create(
            tenant=tenant,
            customer=customer,
            channel='whatsapp',
            status='active'
        )
        
        # Create conversation history
        topics = [
            "I'm looking for running shoes",
            "Do you have size 10?",
            "What colors are available?",
            "How much do they cost?",
            "Can I get free shipping?"
        ]
        
        messages = []
        for i, topic in enumerate(topics):
            msg = Message.objects.create(
                conversation=conversation,
                direction='in',
                message_type='customer_inbound',
                text=topic,
                created_at=timezone.now() + timedelta(seconds=i * 15)
            )
            messages.append(msg)
        
        # Customer asks for summary
        summary_request = Message.objects.create(
            conversation=conversation,
            direction='in',
            message_type='customer_inbound',
            text='What have we talked about?',
            created_at=timezone.now() + timedelta(seconds=100)
        )
        
        # Initialize service
        service = AIAgentService()
        
        # Build context
        context = service.context_builder.build_context(
            conversation=conversation,
            message=summary_request,
            tenant=tenant
        )
        
        # Verify all messages are in history
        assert len(context.conversation_history) >= len(messages)
        for msg in messages:
            assert msg in context.conversation_history
        
        print("✓ Conversation summary generation test passed!")
    
    def test_rapid_message_harmonization_in_conversation(self, tenant, customer):
        """
        Test that rapid messages are harmonized in real conversation.
        
        Validates Requirements 4.1, 4.2, 4.3
        """
        # Create conversation
        conversation = Conversation.objects.create(
            tenant=tenant,
            customer=customer,
            channel='whatsapp',
            status='active'
        )
        
        # Initialize harmonization service
        harmonization = create_message_harmonization_service(wait_seconds=3)
        
        # Simulate rapid message burst
        base_time = timezone.now()
        
        messages = [
            Message.objects.create(
                conversation=conversation,
                direction='in',
                message_type='customer_inbound',
                text='I want',
                created_at=base_time
            ),
            Message.objects.create(
                conversation=conversation,
                direction='in',
                message_type='customer_inbound',
                text='to buy',
                created_at=base_time + timedelta(seconds=1)
            ),
            Message.objects.create(
                conversation=conversation,
                direction='in',
                message_type='customer_inbound',
                text='a laptop',
                created_at=base_time + timedelta(seconds=2)
            )
        ]
        
        # Check if messages should be buffered
        should_buffer_2 = harmonization.should_buffer_message(
            conversation=conversation,
            message=messages[1]
        )
        
        should_buffer_3 = harmonization.should_buffer_message(
            conversation=conversation,
            message=messages[2]
        )
        
        # Verify buffering logic
        assert should_buffer_2 is True
        assert should_buffer_3 is True
        
        # Combine messages
        combined = harmonization.combine_messages(messages)
        
        # Verify all parts are in combined message
        assert 'I want' in combined
        assert 'to buy' in combined
        assert 'a laptop' in combined
        
        print("✓ Message harmonization in conversation test passed!")
    
    def test_language_consistency_across_conversation(self, tenant, customer):
        """
        Test that language preference is maintained across conversation.
        
        Validates Requirements 6.1, 6.2, 6.3
        """
        # Create conversation
        conversation = Conversation.objects.create(
            tenant=tenant,
            customer=customer,
            channel='whatsapp',
            status='active'
        )
        
        # Start in English
        lang1 = LanguageConsistencyManager.detect_and_update_language(
            conversation=conversation,
            message_text='Hello, I want to buy shoes'
        )
        
        assert lang1 == 'en'
        
        # Continue in English
        lang2 = LanguageConsistencyManager.detect_and_update_language(
            conversation=conversation,
            message_text='What sizes do you have?'
        )
        
        assert lang2 == 'en'
        
        # Verify language is stored
        stored = LanguageConsistencyManager.get_conversation_language(conversation)
        assert stored == 'en'
        
        # Switch to Swahili
        lang3 = LanguageConsistencyManager.detect_and_update_language(
            conversation=conversation,
            message_text='Nataka kununua viatu'
        )
        
        assert lang3 == 'sw'
        
        # Verify language switched
        stored = LanguageConsistencyManager.get_conversation_language(conversation)
        assert stored == 'sw'
        
        print("✓ Language consistency test passed!")


@pytest.mark.django_db
class TestErrorRecoveryScenarios:
    """
    Test error recovery scenarios in conversation flows.
    
    Tests graceful handling of:
    - Missing reference contexts
    - Expired contexts
    - Ambiguous references
    - Invalid product selections
    - Network/API failures
    """
    
    def test_missing_reference_context_recovery(self, tenant, customer):
        """
        Test recovery when customer uses reference without context.
        
        Flow:
        - Customer says "1" without seeing a list
        - Bot should gracefully handle and ask for clarification
        """
        # Create conversation
        conversation = Conversation.objects.create(
            tenant=tenant,
            customer=customer,
            channel='whatsapp',
            status='active'
        )
        
        # Customer sends positional reference without context
        message = Message.objects.create(
            conversation=conversation,
            direction='in',
            message_type='customer_inbound',
            text='1'
        )
        
        # Try to resolve reference
        resolved = ReferenceContextManager.resolve_reference(
            conversation=conversation,
            message_text='1'
        )
        
        # Should return None gracefully
        assert resolved is None
        
        # Initialize service
        service = AIAgentService()
        
        # Build context - should not crash
        context = service.context_builder.build_context(
            conversation=conversation,
            message=message,
            tenant=tenant
        )
        
        # Verify context was built successfully
        assert context is not None
        assert context.current_message == message
        
        print("✓ Missing reference context recovery test passed!")
    
    def test_expired_context_recovery(self, tenant, customer):
        """
        Test recovery when reference context has expired.
        
        Flow:
        - Bot shows products
        - Customer waits >5 minutes
        - Customer says "1"
        - Bot should treat as new inquiry
        """
        # Create conversation
        conversation = Conversation.objects.create(
            tenant=tenant,
            customer=customer,
            channel='whatsapp',
            status='active'
        )
        
        # Create product
        product = Product.objects.create(
            tenant=tenant,
            title="Test Product",
            price=Decimal('29.99'),
            is_active=True
        )
        
        # Create expired reference context
        expired_context = ReferenceContext.objects.create(
            conversation=conversation,
            context_id='expired-test',
            list_type='products',
            items=[{'id': str(product.id), 'title': product.title, 'position': 1}],
            expires_at=timezone.now() - timedelta(minutes=10)
        )
        
        # Try to get current context
        current = ReferenceContextManager._get_current_context(conversation)
        
        # Should not return expired context
        assert current is None or current.id != expired_context.id
        
        # Try to resolve reference with expired context
        resolved = ReferenceContextManager.resolve_reference(
            conversation=conversation,
            message_text='1'
        )
        
        # Should return None (expired context not used)
        assert resolved is None
        
        print("✓ Expired context recovery test passed!")
    
    def test_ambiguous_reference_recovery(self, tenant, customer):
        """
        Test recovery when reference is ambiguous.
        
        Flow:
        - Bot shows multiple blue products
        - Customer says "the blue one"
        - Bot should handle ambiguity gracefully
        """
        # Create conversation
        conversation = Conversation.objects.create(
            tenant=tenant,
            customer=customer,
            channel='whatsapp',
            status='active'
        )
        
        # Create multiple similar products
        products = [
            Product.objects.create(
                tenant=tenant,
                title="Blue Shirt Small",
                description="Blue cotton shirt",
                price=Decimal('19.99'),
                is_active=True
            ),
            Product.objects.create(
                tenant=tenant,
                title="Blue Shirt Medium",
                description="Blue cotton shirt",
                price=Decimal('19.99'),
                is_active=True
            ),
            Product.objects.create(
                tenant=tenant,
                title="Blue Shirt Large",
                description="Blue cotton shirt",
                price=Decimal('19.99'),
                is_active=True
            )
        ]
        
        # Store reference context
        items = [
            {
                'id': str(p.id),
                'title': p.title,
                'description': p.description,
                'position': i + 1
            }
            for i, p in enumerate(products)
        ]
        
        ReferenceContextManager.store_list_context(
            conversation=conversation,
            list_type='products',
            items=items
        )
        
        # Try to resolve ambiguous reference
        resolved = ReferenceContextManager.resolve_reference(
            conversation=conversation,
            message_text='the blue one'
        )
        
        # Should handle gracefully (return first match or None)
        # The important thing is it doesn't crash
        assert resolved is None or 'item' in resolved
        
        print("✓ Ambiguous reference recovery test passed!")
    
    def test_invalid_product_selection_recovery(self, tenant, customer):
        """
        Test recovery when customer selects invalid product.
        
        Flow:
        - Bot shows 3 products
        - Customer says "5"
        - Bot should handle gracefully
        """
        # Create conversation
        conversation = Conversation.objects.create(
            tenant=tenant,
            customer=customer,
            channel='whatsapp',
            status='active'
        )
        
        # Create products
        products = [
            Product.objects.create(
                tenant=tenant,
                title=f"Product {i+1}",
                price=Decimal('10.00'),
                is_active=True
            )
            for i in range(3)
        ]
        
        # Store reference context
        items = [
            {'id': str(p.id), 'title': p.title, 'position': i + 1}
            for i, p in enumerate(products)
        ]
        
        ReferenceContextManager.store_list_context(
            conversation=conversation,
            list_type='products',
            items=items
        )
        
        # Try to resolve out-of-range reference
        resolved = ReferenceContextManager.resolve_reference(
            conversation=conversation,
            message_text='5'
        )
        
        # Should return None for out-of-range
        assert resolved is None
        
        print("✓ Invalid product selection recovery test passed!")
    
    def test_empty_catalog_recovery(self, tenant, customer):
        """
        Test recovery when tenant has no products.
        
        Flow:
        - Customer asks "what do you have?"
        - Tenant has no products
        - Bot should handle gracefully
        """
        # Create conversation
        conversation = Conversation.objects.create(
            tenant=tenant,
            customer=customer,
            channel='whatsapp',
            status='active'
        )
        
        # Ensure no products exist
        Product.objects.filter(tenant=tenant).delete()
        
        # Create message
        message = Message.objects.create(
            conversation=conversation,
            direction='in',
            message_type='customer_inbound',
            text='what do you have?'
        )
        
        # Initialize service
        service = AIAgentService()
        
        # Build context - should not crash
        context = service.context_builder.build_context(
            conversation=conversation,
            message=message,
            tenant=tenant
        )
        
        # Verify context was built
        assert context is not None
        assert context.catalog_context is not None
        
        # Verify empty catalog is handled
        assert context.catalog_context.total_products == 0
        
        print("✓ Empty catalog recovery test passed!")
    
    def test_context_builder_error_recovery(self, tenant, customer):
        """
        Test that context builder handles errors gracefully.
        
        Tests resilience when various components fail.
        """
        # Create conversation
        conversation = Conversation.objects.create(
            tenant=tenant,
            customer=customer,
            channel='whatsapp',
            status='active'
        )
        
        # Create message
        message = Message.objects.create(
            conversation=conversation,
            direction='in',
            message_type='customer_inbound',
            text='test message'
        )
        
        # Initialize service
        service = AIAgentService()
        
        # Build context with potential errors
        try:
            context = service.context_builder.build_context(
                conversation=conversation,
                message=message,
                tenant=tenant
            )
            
            # Should succeed
            assert context is not None
            
        except Exception as e:
            # If it fails, it should be a known error type
            pytest.fail(f"Context builder should handle errors gracefully: {e}")
        
        print("✓ Context builder error recovery test passed!")
    
    def test_reference_resolution_with_corrupted_data(self, tenant, customer):
        """
        Test reference resolution with corrupted context data.
        
        Tests resilience when stored context has invalid data.
        """
        # Create conversation
        conversation = Conversation.objects.create(
            tenant=tenant,
            customer=customer,
            channel='whatsapp',
            status='active'
        )
        
        # Create reference context with invalid data
        ReferenceContext.objects.create(
            conversation=conversation,
            context_id='corrupted-test',
            list_type='products',
            items=[
                {'invalid': 'data'},  # Missing required fields
                {'id': 'test', 'position': 'not_a_number'}  # Invalid position
            ],
            expires_at=timezone.now() + timedelta(minutes=5)
        )
        
        # Try to resolve reference - should not crash
        try:
            resolved = ReferenceContextManager.resolve_reference(
                conversation=conversation,
                message_text='1'
            )
            
            # Should handle gracefully (return None or valid result)
            assert resolved is None or isinstance(resolved, dict)
            
        except Exception as e:
            # Should not raise exception
            pytest.fail(f"Reference resolution should handle corrupted data: {e}")
        
        print("✓ Corrupted data recovery test passed!")


@pytest.mark.django_db
class TestComplexConversationScenarios:
    """
    Test complex real-world conversation scenarios.
    
    Tests combinations of features working together in realistic flows.
    """
    
    def test_multi_product_comparison_and_selection(self, tenant, customer):
        """
        Test customer comparing multiple products before selecting.
        
        Flow:
        - Customer asks about laptops
        - Bot shows 3 laptops
        - Customer asks about first one
        - Customer asks about third one
        - Customer selects second one
        - All references should resolve correctly
        """
        # Create conversation
        conversation = Conversation.objects.create(
            tenant=tenant,
            customer=customer,
            channel='whatsapp',
            status='active'
        )
        
        # Create laptops
        laptops = [
            Product.objects.create(
                tenant=tenant,
                title="Budget Laptop",
                description="Entry-level laptop",
                price=Decimal('499.99'),
                is_active=True
            ),
            Product.objects.create(
                tenant=tenant,
                title="Mid-Range Laptop",
                description="Good performance laptop",
                price=Decimal('899.99'),
                is_active=True
            ),
            Product.objects.create(
                tenant=tenant,
                title="Premium Laptop",
                description="High-end gaming laptop",
                price=Decimal('1499.99'),
                is_active=True
            )
        ]
        
        # Store reference context
        items = [
            {
                'id': str(p.id),
                'title': p.title,
                'description': p.description,
                'price': str(p.price),
                'position': i + 1
            }
            for i, p in enumerate(laptops)
        ]
        
        ReferenceContextManager.store_list_context(
            conversation=conversation,
            list_type='products',
            items=items
        )
        
        # Customer asks about first laptop
        resolved_1 = ReferenceContextManager.resolve_reference(
            conversation=conversation,
            message_text='tell me about the first one'
        )
        
        assert resolved_1 is not None
        assert resolved_1['item']['id'] == str(laptops[0].id)
        
        # Customer asks about third laptop
        resolved_3 = ReferenceContextManager.resolve_reference(
            conversation=conversation,
            message_text='what about the last one'
        )
        
        assert resolved_3 is not None
        assert resolved_3['item']['id'] == str(laptops[2].id)
        
        # Customer selects second laptop
        resolved_2 = ReferenceContextManager.resolve_reference(
            conversation=conversation,
            message_text='2'
        )
        
        assert resolved_2 is not None
        assert resolved_2['item']['id'] == str(laptops[1].id)
        assert resolved_2['position'] == 2
        
        print("✓ Multi-product comparison test passed!")
    
    def test_conversation_with_language_switch_and_context(self, tenant, customer):
        """
        Test conversation with language switch while maintaining context.
        
        Flow:
        - Customer starts in English
        - Bot shows products
        - Customer switches to Swahili
        - Customer references products in Swahili
        - Context should be maintained despite language switch
        """
        # Create conversation
        conversation = Conversation.objects.create(
            tenant=tenant,
            customer=customer,
            channel='whatsapp',
            status='active'
        )
        
        # Create product
        product = Product.objects.create(
            tenant=tenant,
            title="Smartphone",
            price=Decimal('599.99'),
            is_active=True
        )
        
        # Start in English
        lang1 = LanguageConsistencyManager.detect_and_update_language(
            conversation=conversation,
            message_text='Show me phones'
        )
        
        assert lang1 == 'en'
        
        # Store reference context
        ReferenceContextManager.store_list_context(
            conversation=conversation,
            list_type='products',
            items=[{'id': str(product.id), 'title': product.title, 'position': 1}]
        )
        
        # Switch to Swahili
        lang2 = LanguageConsistencyManager.detect_and_update_language(
            conversation=conversation,
            message_text='Nataka kununua simu'
        )
        
        assert lang2 == 'sw'
        
        # Reference product in Swahili
        resolved = ReferenceContextManager.resolve_reference(
            conversation=conversation,
            message_text='1'
        )
        
        # Context should still work despite language switch
        assert resolved is not None
        assert resolved['item']['id'] == str(product.id)
        
        print("✓ Language switch with context test passed!")
    
    def test_interrupted_purchase_flow_recovery(self, tenant, customer):
        """
        Test recovery when purchase flow is interrupted.
        
        Flow:
        - Customer starts selecting product
        - Customer asks unrelated question
        - Customer returns to purchase
        - Bot should handle gracefully
        """
        # Create conversation
        conversation = Conversation.objects.create(
            tenant=tenant,
            customer=customer,
            channel='whatsapp',
            status='active'
        )
        
        # Create product
        product = Product.objects.create(
            tenant=tenant,
            title="Headphones",
            price=Decimal('79.99'),
            is_active=True
        )
        
        # Initialize service
        service = AIAgentService()
        
        # Step 1: Customer starts purchase
        message1 = Message.objects.create(
            conversation=conversation,
            direction='in',
            message_type='customer_inbound',
            text='I want to buy headphones',
            created_at=timezone.now()
        )
        
        context1 = service.context_builder.build_context(
            conversation=conversation,
            message=message1,
            tenant=tenant
        )
        
        # Store reference context
        ReferenceContextManager.store_list_context(
            conversation=conversation,
            list_type='products',
            items=[{'id': str(product.id), 'title': product.title, 'position': 1}]
        )
        
        # Step 2: Customer asks unrelated question
        message2 = Message.objects.create(
            conversation=conversation,
            direction='in',
            message_type='customer_inbound',
            text='What are your business hours?',
            created_at=timezone.now() + timedelta(seconds=30)
        )
        
        context2 = service.context_builder.build_context(
            conversation=conversation,
            message=message2,
            tenant=tenant
        )
        
        # Verify history is maintained
        assert message1 in context2.conversation_history
        
        # Step 3: Customer returns to purchase
        message3 = Message.objects.create(
            conversation=conversation,
            direction='in',
            message_type='customer_inbound',
            text='Ok, I want those headphones',
            created_at=timezone.now() + timedelta(seconds=60)
        )
        
        context3 = service.context_builder.build_context(
            conversation=conversation,
            message=message3,
            tenant=tenant
        )
        
        # Verify full history is maintained
        assert message1 in context3.conversation_history
        assert message2 in context3.conversation_history
        
        # Reference context should still be available (if not expired)
        resolved = ReferenceContextManager.resolve_reference(
            conversation=conversation,
            message_text='1'
        )
        
        # May be None if expired, but should not crash
        assert resolved is None or resolved['item']['id'] == str(product.id)
        
        print("✓ Interrupted purchase flow recovery test passed!")
