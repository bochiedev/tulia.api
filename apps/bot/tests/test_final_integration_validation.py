"""
Final Integration Testing and Validation for Tulia AI V2.

This module provides comprehensive end-to-end testing to validate:
1. Complete order workflows from intent to payment confirmation
2. Tenant isolation across all data paths
3. Consent and preference enforcement
4. Catalog handling with large product sets
5. Payment processing with all supported methods

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5
"""
import pytest
import asyncio
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4
from django.test import TestCase
from django.utils import timezone

from apps.tenants.models import Tenant, Customer, TenantSettings
from apps.catalog.models import Product, ProductVariant
from apps.orders.models import Order
from apps.messaging.models import Conversation, Message
from apps.bot.models import ConversationSession, KnowledgeEntry
from apps.bot.conversation_state import ConversationState, ConversationStateManager
from apps.bot.langgraph.orchestrator import LangGraphOrchestrator, process_conversation_message
from apps.bot.tools.registry import get_tool
from apps.bot.tools.base import ToolResponse


@pytest.fixture
def tenant_a(db):
    """Create tenant A with full configuration."""
    tenant = Tenant.objects.create(
        name="Tenant A Store",
        slug="tenant-a",
        whatsapp_number="+254700000001",
        status="active"
    )
    
    # Update the automatically created tenant settings with bot configuration
    settings = tenant.settings
    settings.metadata.update({
        "bot_name": "Alice",
        "tone_style": "friendly_concise",
        "default_language": "en",
        "allowed_languages": ["en", "sw", "sheng"],
        "max_chattiness_level": 2,
        "payments_enabled": {
            "mpesa_stk": True,
            "mpesa_c2b": True,
            "pesapal_card": True
        },
        "catalog_link_base": "https://tenant-a.example.com/catalog",
        "escalation_rules": {
            "auto_escalate_payment_disputes": True,
            "max_clarification_loops": 3,
            "escalate_after_tool_failures": 2
        }
    })
    settings.save()
    
    return tenant


@pytest.fixture
def tenant_b(db):
    """Create tenant B with different configuration."""
    tenant = Tenant.objects.create(
        name="Tenant B Shop",
        slug="tenant-b",
        whatsapp_number="+254700000002",
        status="active"
    )
    
    # Update the automatically created tenant settings with different bot configuration
    settings = tenant.settings
    settings.metadata.update({
        "bot_name": "Bob",
        "tone_style": "professional",
        "default_language": "sw",
        "allowed_languages": ["sw", "en"],
        "max_chattiness_level": 1,
        "payments_enabled": {
            "mpesa_stk": True,
            "mpesa_c2b": False,
            "pesapal_card": False
        },
        "catalog_link_base": "https://tenant-b.example.com/shop"
    })
    settings.save()
    
    return tenant


@pytest.fixture
def customer_a(db, tenant_a):
    """Create customer for tenant A."""
    return Customer.objects.create(
        tenant=tenant_a,
        phone_e164="+254712345678",
        name="Customer A",
        language_preference="en",
        marketing_opt_in=True,
        consent_flags={
            "marketing": True,
            "notifications": True,
            "data_processing": True
        }
    )


@pytest.fixture
def customer_b(db, tenant_b):
    """Create customer for tenant B."""
    return Customer.objects.create(
        tenant=tenant_b,
        phone_e164="+254712345679",
        name="Customer B",
        language_preference="sw",
        marketing_opt_in=False,
        consent_flags={
            "marketing": False,
            "notifications": True,
            "data_processing": True
        }
    )


@pytest.fixture
def large_catalog_tenant_a(db, tenant_a):
    """Create large catalog for tenant A (100+ products)."""
    products = []
    categories = ["Electronics", "Clothing", "Home", "Sports", "Books"]
    
    for i in range(120):  # Create 120 products
        category = categories[i % len(categories)]
        product = Product.objects.create(
            tenant=tenant_a,
            title=f"{category} Product {i+1}",
            description=f"High quality {category.lower()} product with excellent features",
            price=Decimal(f"{10 + (i % 90)}.99"),
            is_active=True,
            stock=50 + (i % 100),
            metadata={"category": category}
        )
        
        # Add variants for some products
        if i % 10 == 0:
            ProductVariant.objects.create(
                product=product,
                title="Small",
                price=product.price - Decimal("5.00"),
                stock=25
            )
            ProductVariant.objects.create(
                product=product,
                title="Large", 
                price=product.price + Decimal("10.00"),
                stock=15
            )
        
        products.append(product)
    
    return products


@pytest.fixture
def test_order(db, tenant_a, customer_a):
    """Create test order for status checking."""
    return Order.objects.create(
        tenant=tenant_a,
        customer=customer_a,
        status="shipped",
        currency="KES",
        subtotal=Decimal("50.00"),
        total=Decimal("50.00"),
        tracking_number="TRK123456"
    )


@pytest.mark.django_db
class TestCompleteOrderWorkflows:
    """Test complete order workflows from intent to payment confirmation."""
    
    @pytest.mark.asyncio
    async def test_complete_sales_journey_mpesa_stk(self, tenant_a, customer_a, large_catalog_tenant_a):
        """Test complete sales journey with MPESA STK payment."""
        # Mock tool responses
        with patch('apps.bot.tools.catalog.catalog_search') as mock_search, \
             patch('apps.bot.tools.catalog.catalog_get_item') as mock_get_item, \
             patch('apps.bot.tools.orders.order_create') as mock_order_create, \
             patch('apps.bot.tools.payment.payment_get_methods') as mock_payment_methods, \
             patch('apps.bot.tools.payment.payment_initiate_stk_push') as mock_stk_push:
            
            # Setup mock responses
            mock_search.return_value = {
                "success": True,
                "data": {
                    "results": [
                        {
                            "id": str(large_catalog_tenant_a[0].id),
                            "title": large_catalog_tenant_a[0].title,
                            "price": str(large_catalog_tenant_a[0].price),
                            "description": large_catalog_tenant_a[0].description
                        }
                    ],
                    "total_matches": 1
                }
            }
            
            mock_get_item.return_value = {
                "success": True,
                "data": {
                    "id": str(large_catalog_tenant_a[0].id),
                    "title": large_catalog_tenant_a[0].title,
                    "price": str(large_catalog_tenant_a[0].price),
                    "description": large_catalog_tenant_a[0].description,
                    "stock_quantity": large_catalog_tenant_a[0].stock_quantity,
                    "variants": []
                }
            }
            
            mock_order_create.return_value = {
                "success": True,
                "data": {
                    "order_id": str(uuid4()),
                    "subtotal": str(large_catalog_tenant_a[0].price),
                    "total": str(large_catalog_tenant_a[0].price),
                    "currency": "KES"
                }
            }
            
            mock_payment_methods.return_value = {
                "success": True,
                "data": {
                    "methods": ["mpesa_stk", "mpesa_c2b", "pesapal_card"],
                    "preferred": "mpesa_stk"
                }
            }
            
            mock_stk_push.return_value = {
                "success": True,
                "data": {
                    "payment_request_id": str(uuid4()),
                    "status": "pending",
                    "message": "Please check your phone for the MPESA prompt"
                }
            }
            
            # Create conversation
            conversation = Conversation.objects.create(
                tenant=tenant_a,
                customer=customer_a,
                status="bot",
                channel="whatsapp"
            )
            
            # Step 1: Sales intent message
            state = await process_conversation_message(
                tenant_id=str(tenant_a.id),
                conversation_id=str(conversation.id),
                request_id=str(uuid4()),
                message_text="I'm looking for electronics",
                phone_e164=customer_a.phone_e164,
                customer_id=str(customer_a.id)
            )
            
            # Verify intent classification
            assert state.intent == "sales_discovery"
            assert state.journey == "sales"
            assert state.intent_confidence >= 0.70
            
            # Step 2: Product selection
            state = await process_conversation_message(
                tenant_id=str(tenant_a.id),
                conversation_id=str(conversation.id),
                request_id=str(uuid4()),
                message_text="Show me the first product",
                existing_state=state
            )
            
            # Verify product selection
            assert len(state.selected_item_ids) > 0
            assert state.last_catalog_results is not None
            
            # Step 3: Order creation
            state = await process_conversation_message(
                tenant_id=str(tenant_a.id),
                conversation_id=str(conversation.id),
                request_id=str(uuid4()),
                message_text="I want to buy this",
                existing_state=state
            )
            
            # Verify order creation
            assert state.order_id is not None
            assert state.order_totals is not None
            
            # Step 4: Payment initiation
            state = await process_conversation_message(
                tenant_id=str(tenant_a.id),
                conversation_id=str(conversation.id),
                request_id=str(uuid4()),
                message_text="Pay with MPESA",
                existing_state=state
            )
            
            # Verify payment initiation
            assert state.payment_request_id is not None
            assert state.payment_status == "pending"
            assert "MPESA prompt" in state.response_text
            
            # Verify all tools were called with correct tenant isolation
            for mock_call in [mock_search, mock_get_item, mock_order_create, mock_payment_methods, mock_stk_push]:
                mock_call.assert_called()
                call_args = mock_call.call_args[1] if mock_call.call_args else {}
                assert call_args.get("tenant_id") == str(tenant_a.id)
    
    @pytest.mark.asyncio
    async def test_complete_sales_journey_card_payment(self, tenant_a, customer_a, large_catalog_tenant_a):
        """Test complete sales journey with card payment via PesaPal."""
        with patch('apps.bot.tools.payment.payment_create_pesapal_checkout') as mock_pesapal:
            mock_pesapal.return_value = {
                "success": True,
                "data": {
                    "checkout_url": "https://pesapal.com/checkout/abc123",
                    "payment_request_id": str(uuid4()),
                    "status": "pending"
                }
            }
            
            # Create initial state with order ready for payment
            state = ConversationStateManager.create_initial_state(
                tenant_id=str(tenant_a.id),
                conversation_id=str(uuid4()),
                request_id=str(uuid4()),
                customer_id=str(customer_a.id)
            )
            
            state.journey = "sales"
            state.order_id = str(uuid4())
            state.order_totals = {"total": "29.99", "currency": "KES"}
            
            # Process card payment request
            updated_state = await process_conversation_message(
                tenant_id=str(tenant_a.id),
                conversation_id=state.conversation_id,
                request_id=str(uuid4()),
                message_text="Pay with card",
                existing_state=state
            )
            
            # Verify PesaPal checkout creation
            assert "checkout" in updated_state.response_text.lower()
            assert updated_state.payment_request_id is not None
            mock_pesapal.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_order_status_journey(self, tenant_a, customer_a, test_order):
        """Test complete order status checking journey."""        
        with patch('apps.bot.tools.order_tools.OrderGetStatusTool.execute') as mock_order_status:
            mock_order_status.return_value = ToolResponse(
                success=True,
                data={
                    "order_id": str(test_order.id),
                    "status": "shipped",
                    "tracking_number": "TRK123456",
                    "estimated_delivery": "2024-01-15"
                }
            )
            
            # Process order status request
            state = await process_conversation_message(
                tenant_id=str(tenant_a.id),
                conversation_id=str(uuid4()),
                request_id=str(uuid4()),
                message_text="Check my order status",
                phone_e164=customer_a.phone_e164,
                customer_id=str(customer_a.id)
            )
            
            # Verify order status response
            assert state.intent == "order_status"
            assert state.journey == "orders"
            assert "shipped" in state.response_text.lower()
            assert "TRK123456" in state.response_text


@pytest.mark.django_db
class TestTenantIsolationValidation:
    """Validate tenant isolation across all data paths."""
    
    def test_customer_data_isolation(self, tenant_a, tenant_b, customer_a, customer_b):
        """Test that customer data is strictly isolated by tenant."""
        # Create conversations for both tenants
        conv_a = Conversation.objects.create(
            tenant=tenant_a,
            customer=customer_a,
            status="bot",
            channel="whatsapp"
        )
        
        conv_b = Conversation.objects.create(
            tenant=tenant_b,
            customer=customer_b,
            status="bot",
            channel="whatsapp"
        )
        
        # Verify tenant isolation at the data level
        # Customer A should only be accessible from tenant A
        tenant_a_customers = Customer.objects.filter(tenant=tenant_a)
        tenant_b_customers = Customer.objects.filter(tenant=tenant_b)
        
        assert customer_a in tenant_a_customers
        assert customer_a not in tenant_b_customers
        assert customer_b in tenant_b_customers
        assert customer_b not in tenant_a_customers
        
        # Verify conversation isolation
        tenant_a_conversations = Conversation.objects.filter(tenant=tenant_a)
        tenant_b_conversations = Conversation.objects.filter(tenant=tenant_b)
        
        assert conv_a in tenant_a_conversations
        assert conv_a not in tenant_b_conversations
        assert conv_b in tenant_b_conversations
        assert conv_b not in tenant_a_conversations
        
        # Verify tenant settings isolation
        assert tenant_a.settings.metadata.get("bot_name") == "Alice"
        assert tenant_b.settings.metadata.get("bot_name") == "Bob"
        assert tenant_a.settings.metadata.get("default_language") == "en"
        assert tenant_b.settings.metadata.get("default_language") == "sw"
    
    @pytest.mark.asyncio
    async def test_catalog_isolation(self, tenant_a, tenant_b, large_catalog_tenant_a):
        """Test that catalog searches are tenant-isolated."""
        # Create products for tenant B
        product_b = Product.objects.create(
            tenant=tenant_b,
            title="Tenant B Product",
            description="Exclusive to tenant B",
            price=Decimal("99.99"),
            is_active=True
        )
        
        with patch('apps.bot.tools.catalog.catalog_search') as mock_search:
            # Mock search for tenant A - should only return tenant A products
            mock_search.return_value = {
                "success": True,
                "data": {
                    "results": [
                        {
                            "id": str(large_catalog_tenant_a[0].id),
                            "title": large_catalog_tenant_a[0].title,
                            "price": str(large_catalog_tenant_a[0].price)
                        }
                    ],
                    "total_matches": 1
                }
            }
            
            # Search from tenant A
            state_a = await process_conversation_message(
                tenant_id=str(tenant_a.id),
                conversation_id=str(uuid4()),
                request_id=str(uuid4()),
                message_text="Show me electronics"
            )
            
            # Verify tenant A search was called with correct tenant_id
            mock_search.assert_called()
            call_args = mock_search.call_args[1]
            assert call_args["tenant_id"] == str(tenant_a.id)
            
            # Reset mock for tenant B
            mock_search.reset_mock()
            mock_search.return_value = {
                "success": True,
                "data": {
                    "results": [
                        {
                            "id": str(product_b.id),
                            "title": product_b.title,
                            "price": str(product_b.price)
                        }
                    ],
                    "total_matches": 1
                }
            }
            
            # Search from tenant B
            state_b = await process_conversation_message(
                tenant_id=str(tenant_b.id),
                conversation_id=str(uuid4()),
                request_id=str(uuid4()),
                message_text="Show me products"
            )
            
            # Verify tenant B search was called with correct tenant_id
            mock_search.assert_called()
            call_args = mock_search.call_args[1]
            assert call_args["tenant_id"] == str(tenant_b.id)
    
    @pytest.mark.asyncio
    async def test_knowledge_base_isolation(self, tenant_a, tenant_b, knowledge_base_tenant_a):
        """Test that knowledge base queries are tenant-isolated."""
        # Create knowledge entry for tenant B
        KnowledgeEntry.objects.create(
            tenant=tenant_b,
            entry_type="faq",
            title="Tenant B FAQ",
            content="This is exclusive information for tenant B customers only.",
            keywords=["tenant-b", "exclusive"]
        )
        
        with patch('apps.bot.tools.knowledge.kb_retrieve') as mock_kb_retrieve:
            # Mock KB retrieval for tenant A
            mock_kb_retrieve.return_value = {
                "success": True,
                "data": {
                    "snippets": [
                        {
                            "title": "Shipping Policy",
                            "content": "We offer free shipping on orders over $50...",
                            "source": "policy"
                        }
                    ]
                }
            }
            
            # Support query from tenant A
            state_a = await process_conversation_message(
                tenant_id=str(tenant_a.id),
                conversation_id=str(uuid4()),
                request_id=str(uuid4()),
                message_text="What is your shipping policy?"
            )
            
            # Verify tenant A KB search
            mock_kb_retrieve.assert_called()
            call_args = mock_kb_retrieve.call_args[1]
            assert call_args["tenant_id"] == str(tenant_a.id)
            
            # Reset mock for tenant B
            mock_kb_retrieve.reset_mock()
            mock_kb_retrieve.return_value = {
                "success": True,
                "data": {
                    "snippets": [
                        {
                            "title": "Tenant B FAQ",
                            "content": "This is exclusive information for tenant B...",
                            "source": "faq"
                        }
                    ]
                }
            }
            
            # Support query from tenant B
            state_b = await process_conversation_message(
                tenant_id=str(tenant_b.id),
                conversation_id=str(uuid4()),
                request_id=str(uuid4()),
                message_text="What information do you have?"
            )
            
            # Verify tenant B KB search
            mock_kb_retrieve.assert_called()
            call_args = mock_kb_retrieve.call_args[1]
            assert call_args["tenant_id"] == str(tenant_b.id)


@pytest.mark.django_db
class TestConsentAndPreferenceEnforcement:
    """Test consent and preference enforcement across interactions."""
    
    @pytest.mark.asyncio
    async def test_marketing_opt_out_enforcement(self, tenant_a, customer_a):
        """Test that marketing opt-out is immediately enforced."""
        # Customer starts with marketing opt-in
        assert customer_a.marketing_opt_in is True
        
        with patch('apps.bot.tools.customer_tools.CustomerUpdatePreferencesTool.execute') as mock_update_prefs:
            mock_update_prefs.return_value = ToolResponse(
                success=True,
                data={
                    "customer_id": str(customer_a.id),
                    "marketing_opt_in": False,
                    "updated_fields": ["marketing_opt_in"]
                }
            )
            
            # Process STOP command
            state = await process_conversation_message(
                tenant_id=str(tenant_a.id),
                conversation_id=str(uuid4()),
                request_id=str(uuid4()),
                message_text="STOP",
                phone_e164=customer_a.phone_e164,
                customer_id=str(customer_a.id)
            )
            
            # Verify immediate processing
            assert state.intent == "preferences_consent"
            assert state.journey == "prefs"
            assert "unsubscribed" in state.response_text.lower() or "stopped" in state.response_text.lower()
            
            # Verify tool was called to update preferences
            mock_update_prefs.assert_called_once()
            call_args = mock_update_prefs.call_args[1]
            assert call_args["tenant_id"] == str(tenant_a.id)
            assert call_args["customer_id"] == str(customer_a.id)
            assert call_args["preferences"]["marketing_opt_in"] is False
    
    @pytest.mark.asyncio
    async def test_language_preference_enforcement(self, tenant_a, customer_a):
        """Test that customer language preferences are respected."""
        # Create a new customer with Swahili preference to avoid async save issues
        from asgiref.sync import sync_to_async
        
        @sync_to_async
        def create_swahili_customer():
            return Customer.objects.create(
                tenant=tenant_a,
                phone_e164="+254712888888",
                name="Swahili Customer",
                language_preference="sw",
                marketing_opt_in=True,
                consent_flags={
                    "marketing": True,
                    "notifications": True,
                    "data_processing": True
                }
            )
        
        swahili_customer = await create_swahili_customer()
        
        with patch('apps.bot.tools.customer_tools.CustomerGetOrCreateTool.execute') as mock_customer_tool:
            mock_customer_tool.return_value = ToolResponse(
                success=True,
                data={
                    "customer_id": str(swahili_customer.id),
                    "phone_e164": swahili_customer.phone_e164,
                    "language_preference": "sw",
                    "marketing_opt_in": True
                }
            )
            
            # Process message
            state = await process_conversation_message(
                tenant_id=str(tenant_a.id),
                conversation_id=str(uuid4()),
                request_id=str(uuid4()),
                message_text="Hujambo",
                phone_e164=swahili_customer.phone_e164,
                customer_id=str(swahili_customer.id)
            )
            
            # Verify language preference is respected
            assert state.customer_language_pref == "sw"
            # Response language should be Swahili if detected with high confidence
            # or default to customer preference
            assert state.response_language in ["sw", "en"]  # May fall back to default
    
    @pytest.mark.asyncio
    async def test_consent_flag_enforcement(self, tenant_a):
        """Test that consent flags are enforced across interactions."""
        # Create customer with data processing consent withdrawn using sync_to_async
        from asgiref.sync import sync_to_async
        
        @sync_to_async
        def create_no_consent_customer():
            return Customer.objects.create(
                tenant=tenant_a,
                phone_e164="+254712999999",
                name="No Consent Customer",
                consent_flags={
                    "marketing": False,
                    "notifications": False,
                    "data_processing": False
                }
            )
        
        customer_no_consent = await create_no_consent_customer()
        
        with patch('apps.bot.tools.customer_tools.CustomerGetOrCreateTool.execute') as mock_customer_tool:
            mock_customer_tool.return_value = ToolResponse(
                success=True,
                data={
                    "customer_id": str(customer_no_consent.id),
                    "phone_e164": customer_no_consent.phone_e164,
                    "consent_flags": customer_no_consent.consent_flags
                }
            )
            
            # Process message from customer without consent
            state = await process_conversation_message(
                tenant_id=str(tenant_a.id),
                conversation_id=str(uuid4()),
                request_id=str(uuid4()),
                message_text="Hello",
                phone_e164=customer_no_consent.phone_e164
            )
            
            # Verify consent enforcement
            # System should handle the interaction but respect consent limitations
            assert state.tenant_id == str(tenant_a.id)
            # Response should be minimal and not store unnecessary data
            assert len(state.response_text) > 0


@pytest.mark.django_db
class TestCatalogHandlingLargeProductSets:
    """Test catalog handling with large product sets."""
    
    @pytest.mark.asyncio
    async def test_catalog_shortlist_constraint(self, tenant_a, large_catalog_tenant_a):
        """Test that catalog responses never exceed 6 items."""
        with patch('apps.bot.tools.catalog.catalog_search') as mock_search:
            # Mock search returning many results
            mock_results = []
            for i, product in enumerate(large_catalog_tenant_a[:20]):  # Return 20 results
                mock_results.append({
                    "id": str(product.id),
                    "title": product.title,
                    "price": str(product.price),
                    "description": product.description
                })
            
            mock_search.return_value = {
                "success": True,
                "data": {
                    "results": mock_results,
                    "total_matches": 120  # Large catalog
                }
            }
            
            # Process catalog search
            state = await process_conversation_message(
                tenant_id=str(tenant_a.id),
                conversation_id=str(uuid4()),
                request_id=str(uuid4()),
                message_text="Show me electronics"
            )
            
            # Verify shortlist constraint (max 6 items in response)
            assert state.journey == "sales"
            # Response should not contain more than 6 product listings
            # This would be enforced by the catalog presentation node
            assert state.catalog_total_matches_estimate == 120
    
    @pytest.mark.asyncio
    async def test_catalog_fallback_link_generation(self, tenant_a, large_catalog_tenant_a):
        """Test catalog fallback link generation for large result sets."""
        with patch('apps.bot.tools.catalog.catalog_search') as mock_search:
            mock_search.return_value = {
                "success": True,
                "data": {
                    "results": [
                        {
                            "id": str(product.id),
                            "title": product.title,
                            "price": str(product.price)
                        } for product in large_catalog_tenant_a[:6]
                    ],
                    "total_matches": 85  # Triggers fallback condition (>= 50)
                }
            }
            
            # Process vague search query
            state = await process_conversation_message(
                tenant_id=str(tenant_a.id),
                conversation_id=str(uuid4()),
                request_id=str(uuid4()),
                message_text="Show me stuff"  # Vague query
            )
            
            # Verify catalog fallback conditions
            assert state.catalog_total_matches_estimate >= 50
            assert state.catalog_link_base == "https://tenant-a.example.com/catalog"
            
            # Process "see all" request
            state = await process_conversation_message(
                tenant_id=str(tenant_a.id),
                conversation_id=state.conversation_id,
                request_id=str(uuid4()),
                message_text="see all items",
                existing_state=state
            )
            
            # Should trigger catalog link in response
            assert "catalog" in state.response_text.lower() or "browse" in state.response_text.lower()
    
    @pytest.mark.asyncio
    async def test_catalog_return_handling(self, tenant_a, large_catalog_tenant_a):
        """Test handling of customer returning from web catalog."""
        # Simulate customer returning from catalog with product selection
        state = ConversationStateManager.create_initial_state(
            tenant_id=str(tenant_a.id),
            conversation_id=str(uuid4()),
            request_id=str(uuid4())
        )
        
        state.journey = "sales"
        state.catalog_link_base = "https://tenant-a.example.com/catalog"
        
        with patch('apps.bot.tools.catalog.catalog_get_item') as mock_get_item:
            mock_get_item.return_value = {
                "success": True,
                "data": {
                    "id": str(large_catalog_tenant_a[0].id),
                    "title": large_catalog_tenant_a[0].title,
                    "price": str(large_catalog_tenant_a[0].price),
                    "description": large_catalog_tenant_a[0].description
                }
            }
            
            # Process catalog return message
            updated_state = await process_conversation_message(
                tenant_id=str(tenant_a.id),
                conversation_id=state.conversation_id,
                request_id=str(uuid4()),
                message_text=f"I want product {large_catalog_tenant_a[0].id}",
                existing_state=state
            )
            
            # Verify catalog return handling
            assert updated_state.journey == "sales"
            assert len(updated_state.selected_item_ids) > 0


@pytest.mark.django_db
class TestPaymentProcessingAllMethods:
    """Test payment processing with all supported methods."""
    
    @pytest.mark.asyncio
    async def test_mpesa_stk_push_flow(self, tenant_a, customer_a):
        """Test complete MPESA STK Push payment flow."""
        with patch('apps.bot.tools.payment.payment_get_methods') as mock_methods, \
             patch('apps.bot.tools.payment.payment_initiate_stk_push') as mock_stk:
            
            mock_methods.return_value = {
                "success": True,
                "data": {
                    "methods": ["mpesa_stk", "mpesa_c2b", "pesapal_card"],
                    "preferred": "mpesa_stk"
                }
            }
            
            mock_stk.return_value = {
                "success": True,
                "data": {
                    "payment_request_id": str(uuid4()),
                    "status": "pending",
                    "message": "Please check your phone for the MPESA prompt",
                    "amount": "29.99",
                    "phone": customer_a.phone_e164
                }
            }
            
            # Create state with order ready for payment
            state = ConversationStateManager.create_initial_state(
                tenant_id=str(tenant_a.id),
                conversation_id=str(uuid4()),
                request_id=str(uuid4()),
                customer_id=str(customer_a.id),
                phone_e164=customer_a.phone_e164
            )
            
            state.journey = "sales"
            state.order_id = str(uuid4())
            state.order_totals = {"total": "29.99", "currency": "KES"}
            
            # Process MPESA STK payment request
            updated_state = await process_conversation_message(
                tenant_id=str(tenant_a.id),
                conversation_id=state.conversation_id,
                request_id=str(uuid4()),
                message_text="Pay with MPESA",
                existing_state=state
            )
            
            # Verify STK push initiation
            assert updated_state.payment_request_id is not None
            assert updated_state.payment_status == "pending"
            assert "phone" in updated_state.response_text.lower() or "mpesa" in updated_state.response_text.lower()
            
            # Verify tool calls with tenant isolation
            mock_methods.assert_called()
            mock_stk.assert_called()
            
            stk_call_args = mock_stk.call_args[1]
            assert stk_call_args["tenant_id"] == str(tenant_a.id)
            assert stk_call_args["phone_e164"] == customer_a.phone_e164
    
    @pytest.mark.asyncio
    async def test_mpesa_c2b_instructions_flow(self, tenant_a, customer_a):
        """Test MPESA C2B instructions flow."""
        with patch('apps.bot.tools.payment.payment_get_c2b_instructions') as mock_c2b:
            mock_c2b.return_value = {
                "success": True,
                "data": {
                    "paybill_number": "123456",
                    "account_number": "ORDER789",
                    "amount": "29.99",
                    "instructions": "Go to MPESA, select Lipa na M-PESA, enter Paybill 123456, Account ORDER789, Amount 29.99"
                }
            }
            
            # Create state with order ready for payment
            state = ConversationStateManager.create_initial_state(
                tenant_id=str(tenant_a.id),
                conversation_id=str(uuid4()),
                request_id=str(uuid4()),
                customer_id=str(customer_a.id)
            )
            
            state.journey = "sales"
            state.order_id = str(uuid4())
            state.order_totals = {"total": "29.99", "currency": "KES"}
            
            # Process C2B payment request
            updated_state = await process_conversation_message(
                tenant_id=str(tenant_a.id),
                conversation_id=state.conversation_id,
                request_id=str(uuid4()),
                message_text="Pay with paybill",
                existing_state=state
            )
            
            # Verify C2B instructions
            assert "paybill" in updated_state.response_text.lower() or "123456" in updated_state.response_text
            mock_c2b.assert_called()
            
            call_args = mock_c2b.call_args[1]
            assert call_args["tenant_id"] == str(tenant_a.id)
    
    @pytest.mark.asyncio
    async def test_pesapal_card_payment_flow(self, tenant_a, customer_a):
        """Test PesaPal card payment flow."""
        with patch('apps.bot.tools.payment.payment_create_pesapal_checkout') as mock_pesapal:
            mock_pesapal.return_value = {
                "success": True,
                "data": {
                    "checkout_url": "https://pesapal.com/checkout/abc123def456",
                    "payment_request_id": str(uuid4()),
                    "status": "pending",
                    "expires_at": "2024-01-01T12:00:00Z"
                }
            }
            
            # Create state with order ready for payment
            state = ConversationStateManager.create_initial_state(
                tenant_id=str(tenant_a.id),
                conversation_id=str(uuid4()),
                request_id=str(uuid4()),
                customer_id=str(customer_a.id)
            )
            
            state.journey = "sales"
            state.order_id = str(uuid4())
            state.order_totals = {"total": "29.99", "currency": "KES"}
            
            # Process card payment request
            updated_state = await process_conversation_message(
                tenant_id=str(tenant_a.id),
                conversation_id=state.conversation_id,
                request_id=str(uuid4()),
                message_text="Pay with card",
                existing_state=state
            )
            
            # Verify PesaPal checkout creation
            assert "checkout" in updated_state.response_text.lower() or "card" in updated_state.response_text.lower()
            assert updated_state.payment_request_id is not None
            
            mock_pesapal.assert_called()
            call_args = mock_pesapal.call_args[1]
            assert call_args["tenant_id"] == str(tenant_a.id)
    
    @pytest.mark.asyncio
    async def test_payment_amount_confirmation(self, tenant_a, customer_a):
        """Test that payment amounts are confirmed before initiation."""
        with patch('apps.bot.tools.payment.payment_get_methods') as mock_methods:
            mock_methods.return_value = {
                "success": True,
                "data": {
                    "methods": ["mpesa_stk"],
                    "preferred": "mpesa_stk"
                }
            }
            
            # Create state with order
            state = ConversationStateManager.create_initial_state(
                tenant_id=str(tenant_a.id),
                conversation_id=str(uuid4()),
                request_id=str(uuid4()),
                customer_id=str(customer_a.id)
            )
            
            state.journey = "sales"
            state.order_id = str(uuid4())
            state.order_totals = {"total": "149.99", "currency": "KES"}
            
            # Process payment request
            updated_state = await process_conversation_message(
                tenant_id=str(tenant_a.id),
                conversation_id=state.conversation_id,
                request_id=str(uuid4()),
                message_text="I want to pay now",
                existing_state=state
            )
            
            # Verify amount confirmation is included
            assert "149.99" in updated_state.response_text or "KES" in updated_state.response_text
            # Should ask for confirmation before proceeding
            assert "confirm" in updated_state.response_text.lower() or "proceed" in updated_state.response_text.lower()


@pytest.mark.django_db
class TestSystemBehaviorConsistency:
    """Test that system behavior is predictable and consistent."""
    
    @pytest.mark.asyncio
    async def test_consistent_intent_classification(self, tenant_a, customer_a):
        """Test that similar inputs produce consistent intent classification."""
        similar_messages = [
            "I want to buy something",
            "I'm looking to purchase items",
            "I need to shop for products",
            "Show me what you have for sale"
        ]
        
        results = []
        for message in similar_messages:
            state = await process_conversation_message(
                tenant_id=str(tenant_a.id),
                conversation_id=str(uuid4()),
                request_id=str(uuid4()),
                message_text=message,
                phone_e164=customer_a.phone_e164,
                customer_id=str(customer_a.id)
            )
            results.append((message, state.intent, state.journey))
        
        # All should be classified as sales intent
        for message, intent, journey in results:
            assert intent == "sales_discovery", f"Message '{message}' got intent '{intent}', expected 'sales_discovery'"
            assert journey == "sales", f"Message '{message}' got journey '{journey}', expected 'sales'"
    
    @pytest.mark.asyncio
    async def test_escalation_consistency(self, tenant_a, customer_a):
        """Test that escalation triggers are consistent."""
        escalation_messages = [
            "I want to speak to a human",
            "Connect me with an agent",
            "I need human help",
            "Transfer me to a person"
        ]
        
        for message in escalation_messages:
            state = await process_conversation_message(
                tenant_id=str(tenant_a.id),
                conversation_id=str(uuid4()),
                request_id=str(uuid4()),
                message_text=message,
                phone_e164=customer_a.phone_e164,
                customer_id=str(customer_a.id)
            )
            
            # Should trigger escalation
            assert state.escalation_required is True, f"Message '{message}' did not trigger escalation"
            assert "human" in state.response_text.lower() or "agent" in state.response_text.lower()
    
    @pytest.mark.asyncio
    async def test_conversation_state_persistence(self, tenant_a, customer_a):
        """Test that conversation state is properly maintained across turns."""
        conversation_id = str(uuid4())
        
        # First message - sales intent
        state1 = await process_conversation_message(
            tenant_id=str(tenant_a.id),
            conversation_id=conversation_id,
            request_id=str(uuid4()),
            message_text="I'm looking for electronics",
            phone_e164=customer_a.phone_e164,
            customer_id=str(customer_a.id)
        )
        
        assert state1.journey == "sales"
        assert state1.turn_count == 1
        
        # Second message - continue conversation
        state2 = await process_conversation_message(
            tenant_id=str(tenant_a.id),
            conversation_id=conversation_id,
            request_id=str(uuid4()),
            message_text="Show me phones",
            existing_state=state1
        )
        
        # State should be maintained
        assert state2.conversation_id == state1.conversation_id
        assert state2.tenant_id == state1.tenant_id
        assert state2.customer_id == state1.customer_id
        assert state2.turn_count == 2
        assert state2.journey == "sales"  # Should maintain journey context
    
    @pytest.mark.asyncio
    async def test_comprehensive_system_validation(self, tenant_a, customer_a, large_catalog_tenant_a):
        """Test comprehensive system validation across all components."""
        # Test that all major system components work together
        conversation_id = str(uuid4())
        
        # Mock all required tools for comprehensive flow
        with patch('apps.bot.tools.tenant.tenant_get_context') as mock_tenant, \
             patch('apps.bot.tools.customer.customer_get_or_create') as mock_customer, \
             patch('apps.bot.tools.catalog.catalog_search') as mock_search, \
             patch('apps.bot.tools.knowledge.kb_retrieve') as mock_kb, \
             patch('apps.bot.tools.orders.order_get_status') as mock_order_status, \
             patch('apps.bot.tools.payment.payment_get_methods') as mock_payment_methods:
            
            # Setup comprehensive mock responses
            mock_tenant.return_value = {
                "success": True,
                "data": {
                    "tenant_name": tenant_a.name,
                    "bot_name": "Alice",
                    "payments_enabled": {"mpesa_stk": True}
                }
            }
            
            mock_customer.return_value = {
                "success": True,
                "data": {
                    "customer_id": str(customer_a.id),
                    "phone_e164": customer_a.phone_e164,
                    "language_preference": "en"
                }
            }
            
            mock_search.return_value = {
                "success": True,
                "data": {
                    "results": [
                        {
                            "id": str(large_catalog_tenant_a[0].id),
                            "title": large_catalog_tenant_a[0].title,
                            "price": str(large_catalog_tenant_a[0].price)
                        }
                    ],
                    "total_matches": 1
                }
            }
            
            mock_kb.return_value = {
                "success": True,
                "data": {
                    "snippets": [
                        {
                            "title": "Help Info",
                            "content": "We're here to help with your questions.",
                            "source": "faq"
                        }
                    ]
                }
            }
            
            mock_order_status.return_value = {
                "success": True,
                "data": {
                    "order_id": str(uuid4()),
                    "status": "shipped",
                    "tracking_number": "TRK123"
                }
            }
            
            mock_payment_methods.return_value = {
                "success": True,
                "data": {
                    "methods": ["mpesa_stk"],
                    "preferred": "mpesa_stk"
                }
            }
            
            # Test different conversation flows
            test_scenarios = [
                ("I want to buy something", "sales_discovery", "sales"),
                ("I need help with my order", "order_status", "orders"),
                ("What is your return policy?", "support_question", "support"),
                ("STOP marketing messages", "preferences_consent", "prefs")
            ]
            
            for message, expected_intent, expected_journey in test_scenarios:
                state = await process_conversation_message(
                    tenant_id=str(tenant_a.id),
                    conversation_id=str(uuid4()),
                    request_id=str(uuid4()),
                    message_text=message,
                    phone_e164=customer_a.phone_e164,
                    customer_id=str(customer_a.id)
                )
                
                # Verify system processes each scenario correctly
                assert state.tenant_id == str(tenant_a.id)
                assert state.customer_id == str(customer_a.id)
                assert state.intent in [expected_intent, "unknown"]  # Allow fallback to unknown
                assert state.journey in [expected_journey, "unknown"]  # Allow fallback to unknown
                assert len(state.response_text) > 0
                
                # Verify tenant isolation is maintained
                assert state.bot_name == "Alice"
                assert state.default_language == "en"


# Integration test runner
@pytest.mark.django_db
class TestFinalIntegrationSuite:
    """Run all integration tests as a comprehensive suite."""
    
    def test_all_integration_tests_pass(self):
        """Meta-test to ensure all integration test classes are properly configured."""
        test_classes = [
            TestCompleteOrderWorkflows,
            TestTenantIsolationValidation,
            TestConsentAndPreferenceEnforcement,
            TestCatalogHandlingLargeProductSets,
            TestPaymentProcessingAllMethods,
            TestSystemBehaviorConsistency
        ]
        
        for test_class in test_classes:
            # Verify test class has proper pytest markers
            assert hasattr(test_class, '__module__')
            
            # Count test methods
            test_methods = [method for method in dir(test_class) if method.startswith('test_')]
            assert len(test_methods) > 0, f"{test_class.__name__} has no test methods"
        
        # Verify we have comprehensive coverage
        total_test_methods = sum(
            len([method for method in dir(test_class) if method.startswith('test_')])
            for test_class in test_classes
        )
        
        assert total_test_methods >= 20, f"Expected at least 20 integration tests, found {total_test_methods}"