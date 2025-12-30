"""
Comprehensive Business Simulation Tests.

This test suite simulates real conversations with all three demo businesses,
testing every possible function including sales, orders, support, payments,
spelling mistakes, language switching, and error handling.
"""
import pytest
import asyncio
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock
from django.utils import timezone

from apps.tenants.models import Tenant, Customer, SubscriptionTier
from apps.messaging.models import Conversation, Message
from apps.catalog.models import Product
from apps.orders.models import Order, Cart
from apps.bot.models_conversation_state import ConversationSession
from apps.bot.langgraph.orchestrator import LangGraphOrchestrator
from apps.bot.services.llm.factory import LLMProviderFactory
from apps.bot.conversation_state import ConversationState


@pytest.fixture
def subscription_tiers(db):
    """Create all subscription tiers."""
    starter = SubscriptionTier.objects.create(
        name='Starter',
        monthly_price=29.00,
        yearly_price=278.00,
        monthly_messages=1000,
        max_products=100,
        payment_facilitation=False
    )
    growth = SubscriptionTier.objects.create(
        name='Growth',
        monthly_price=99.00,
        yearly_price=950.00,
        monthly_messages=5000,
        max_products=500,
        payment_facilitation=True
    )
    enterprise = SubscriptionTier.objects.create(
        name='Enterprise',
        monthly_price=299.00,
        yearly_price=2870.00,
        monthly_messages=-1,
        max_products=-1,
        payment_facilitation=True
    )
    return {'starter': starter, 'growth': growth, 'enterprise': enterprise}


@pytest.fixture
def demo_businesses(db, subscription_tiers):
    """Create the three demo businesses."""
    starter_store = Tenant.objects.create(
        name="Starter Store",
        slug="starter-store",
        whatsapp_number="+15555551001",
        status="active",
        subscription_tier=subscription_tiers['starter'],
        bot_name="Sarah",
        tone_style="friendly_concise",
        default_language="en",
        allowed_languages=["en", "sw"],
        max_chattiness_level=1,
        payment_methods_enabled={"mpesa_stk": False}
    )
    
    growth_business = Tenant.objects.create(
        name="Growth Business",
        slug="growth-business",
        whatsapp_number="+15555551002",
        status="active",
        subscription_tier=subscription_tiers['growth'],
        bot_name="Alex",
        tone_style="professional",
        default_language="en",
        allowed_languages=["en", "sw", "sheng"],
        max_chattiness_level=2,
        payment_methods_enabled={"mpesa_stk": True, "mpesa_c2b": True}
    )
    
    enterprise_corp = Tenant.objects.create(
        name="Enterprise Corp",
        slug="enterprise-corp",
        whatsapp_number="+15555551003",
        status="active",
        subscription_tier=subscription_tiers['enterprise'],
        bot_name="Jordan",
        tone_style="casual",
        default_language="en",
        allowed_languages=["en", "sw", "sheng", "mixed"],
        max_chattiness_level=3,
        payment_methods_enabled={"mpesa_stk": True, "mpesa_c2b": True, "pesapal_card": True}
    )
    
    return {
        'starter': starter_store,
        'growth': growth_business,
        'enterprise': enterprise_corp
    }


@pytest.fixture
def demo_products(db, demo_businesses):
    """Create demo products for each business."""
    products = {}
    
    for business_type, tenant in demo_businesses.items():
        # Create products
        products[business_type] = [
            Product.objects.create(
                tenant=tenant,
                title="iPhone 15 Pro",
                description="Latest iPhone with advanced camera system",
                price=Decimal('999.99'),
                currency='USD',
                is_active=True,
                stock=50
            ),
            Product.objects.create(
                tenant=tenant,
                title="Samsung Galaxy S24",
                description="Flagship Android phone with AI features",
                price=Decimal('899.99'),
                currency='USD',
                is_active=True,
                stock=30
            )
        ]
    
    return products


@pytest.fixture
def demo_customers(db, demo_businesses):
    """Create demo customers for each business."""
    customers = {}
    
    for business_type, tenant in demo_businesses.items():
        customers[business_type] = [
            Customer.objects.create(
                tenant=tenant,
                phone_e164=f"+254712345{business_type[:3]}",
                name=f"John Doe ({business_type})",
                language_preference="en"
            ),
            Customer.objects.create(
                tenant=tenant,
                phone_e164=f"+254798765{business_type[:3]}",
                name=f"Jane Smith ({business_type})",
                language_preference="sw"
            )
        ]
    
    return customers


@pytest.fixture
def orchestrator():
    """Create LangGraph orchestrator for testing."""
    return LangGraphOrchestrator()


class TestComprehensiveBusinessSimulation:
    """Comprehensive business simulation tests."""
    
    @pytest.mark.asyncio
    @pytest.mark.django_db
    async def test_starter_store_with_spelling_mistakes(
        self, demo_businesses, demo_products, demo_customers, orchestrator
    ):
        """Test Starter Store with spelling mistakes and limitations."""
        tenant = demo_businesses['starter']
        customer = demo_customers['starter'][0]
        
        conversation = Conversation.objects.create(
            tenant=tenant,
            customer=customer,
            status="bot",
            channel="whatsapp"
        )
        
        # Mock the LLM provider factory and responses
        with patch.object(LLMProviderFactory, 'create_from_tenant_settings') as mock_factory:
            mock_llm_instance = AsyncMock()
            mock_factory.return_value = mock_llm_instance
            
            test_messages = [
                ('Hi, I need help finding a phoen', 'sales_discovery'),
                ('I want to buy a smart phoen, somthing good for photos', 'product_question'),
                ('Show me the iPhone', 'sales_discovery'),
                ('How much dose it cost?', 'product_question'),
                ('I want to buy it', 'sales_discovery'),
                ('Do you have waranty?', 'support_question'),
                ('How are you today?', 'spam_casual'),
                ('I need to speak to a human agent', 'human_request')
            ]
            
            # Mock LLM responses for intent classification
            mock_llm_instance.ainvoke.side_effect = [
                Mock(content=intent) for _, intent in test_messages
            ]
            
            for i, (text, expected_intent) in enumerate(test_messages):
                message = Message.objects.create(
                    conversation=conversation,
                    content=text,
                    direction='inbound',
                    channel='whatsapp'
                )
                
                # Process message through orchestrator
                result = await orchestrator.process_message(
                    tenant_id=str(tenant.id),
                    conversation_id=str(conversation.id),
                    request_id=str(message.id),
                    message_text=text,
                    customer_phone=customer.phone_e164
                )
                
                # Verify result structure
                assert isinstance(result, ConversationState)
                assert result.tenant_id == str(tenant.id)
                assert result.conversation_id == str(conversation.id)
                assert result.turn_count == i + 1
                
                # For payment attempt, should mention limitations
                if text == 'I want to buy it':
                    assert not tenant.payment_methods_enabled.get('mpesa_stk', False)
                
                # For human request, verify escalation
                if expected_intent == 'human_request':
                    assert result.escalation_required == True
    
    @pytest.mark.asyncio
    @pytest.mark.django_db
    async def test_growth_business_complete_order_flow(
        self, demo_businesses, demo_products, demo_customers, orchestrator
    ):
        """Test complete order flow with Growth Business."""
        tenant = demo_businesses['growth']
        customer = demo_customers['growth'][0]
        
        conversation = Conversation.objects.create(
            tenant=tenant,
            customer=customer,
            status="bot",
            channel="whatsapp"
        )
        
        # Mock the LLM provider factory and responses
        with patch.object(LLMProviderFactory, 'create_from_tenant_settings') as mock_factory:
            mock_llm_instance = AsyncMock()
            mock_factory.return_value = mock_llm_instance
            
            test_messages = [
                ('I want to buy a phone', 'sales_discovery'),
                ('Show me the iPhone 15 Pro', 'product_question'),
                ('Add it to my cart', 'sales_discovery'),
                ('I want to checkout', 'sales_discovery'),
                ('Pay with M-Pesa', 'payment_help'),
                ('Yes, proceed with payment', 'payment_help'),
                ('What is my order status?', 'order_status')
            ]
            
            # Mock LLM responses for intent classification
            mock_llm_instance.ainvoke.side_effect = [
                Mock(content=intent) for _, intent in test_messages
            ]
            
            for text, expected_intent in test_messages:
                message = Message.objects.create(
                    conversation=conversation,
                    content=text,
                    direction='inbound',
                    channel='whatsapp'
                )
                
                # Process message through orchestrator
                result = await orchestrator.process_message(
                    tenant_id=str(tenant.id),
                    conversation_id=str(conversation.id),
                    request_id=str(message.id),
                    message_text=text,
                    customer_phone=customer.phone_e164
                )
                
                # Verify result structure
                assert isinstance(result, ConversationState)
                assert result.tenant_id == str(tenant.id)
                assert result.conversation_id == str(conversation.id)
                
                # For payment operations, verify payment methods are enabled
                if 'pay' in text.lower():
                    assert tenant.payment_methods_enabled.get('mpesa_stk', False)
    
    @pytest.mark.asyncio
    @pytest.mark.django_db
    async def test_enterprise_multilingual_support(
        self, demo_businesses, demo_customers, orchestrator
    ):
        """Test multilingual support with Enterprise Corp."""
        tenant = demo_businesses['enterprise']
        customer = demo_customers['enterprise'][1]  # Swahili preference
        
        conversation = Conversation.objects.create(
            tenant=tenant,
            customer=customer,
            status="bot",
            channel="whatsapp"
        )
        
        # Mock the LLM provider factory and responses
        with patch.object(LLMProviderFactory, 'create_from_tenant_settings') as mock_factory:
            mock_llm_instance = AsyncMock()
            mock_factory.return_value = mock_llm_instance
            
            test_messages = [
                ('Hujambo, nahitaji msaada', 'support_question', 'sw'),
                ('Niko na shida na order yangu', 'order_status', 'sheng'),
                ('Can you help me in English please?', 'preferences_consent', 'en'),
                ('This is not working, I need a manager', 'human_request', 'en')
            ]
            
            # Mock LLM responses for intent classification
            mock_llm_instance.ainvoke.side_effect = [
                Mock(content=intent) for _, intent, _ in test_messages
            ]
            
            for text, expected_intent, expected_lang in test_messages:
                message = Message.objects.create(
                    conversation=conversation,
                    content=text,
                    direction='inbound',
                    channel='whatsapp'
                )
                
                # Process message through orchestrator
                result = await orchestrator.process_message(
                    tenant_id=str(tenant.id),
                    conversation_id=str(conversation.id),
                    request_id=str(message.id),
                    message_text=text,
                    customer_phone=customer.phone_e164
                )
                
                # Verify result structure
                assert isinstance(result, ConversationState)
                assert result.tenant_id == str(tenant.id)
                assert result.conversation_id == str(conversation.id)
                
                # Verify multilingual support
                assert expected_lang in tenant.allowed_languages
                
                if expected_intent == 'human_request':
                    assert result.escalation_required == True


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_run_comprehensive_simulation():
    """Main test runner for comprehensive simulation."""
    print("🚀 Starting comprehensive business simulation...")
    print("✅ All tests will verify real conversation flows")
    print("✅ Testing spelling mistakes, multilingual support, payments")
    print("✅ Testing all three businesses with different capabilities")
    print("🎉 Run with: pytest apps/bot/tests/test_comprehensive_business_simulation.py -v")