#!/usr/bin/env python
"""
Simple Bot Test Script

This script tests the bot functionality by creating a simple conversation
and verifying that the ConversationSession field issue is fixed.
"""
import os
import sys
import django
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.management import call_command
from apps.tenants.models import Tenant, Customer, SubscriptionTier
from apps.messaging.models import Conversation, Message
from apps.bot.models_conversation_state import ConversationSession
from apps.bot.conversation_state import ConversationState, ConversationStateManager


def test_conversation_session_creation():
    """Test that ConversationSession can be created without the 'state' field error."""
    print("🧪 Testing ConversationSession creation...")
    
    try:
        # Run migrations
        call_command('migrate', verbosity=0)
        
        # Create subscription tier
        tier = SubscriptionTier.objects.create(
            name='Test Tier',
            monthly_price=29.00,
            yearly_price=278.00
        )
        
        # Create tenant
        tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            whatsapp_number="+15555551001",
            status="active",
            subscription_tier=tier
        )
        
        # Create customer
        customer = Customer.objects.create(
            tenant=tenant,
            phone_e164="+254712345678",
            name="Test Customer"
        )
        
        # Create conversation
        conversation = Conversation.objects.create(
            tenant=tenant,
            customer=customer,
            status="bot",
            channel="whatsapp"
        )
        
        # Create message
        message = Message.objects.create(
            conversation=conversation,
            text="Hello, I need help",
            direction='in',
            message_type='customer_inbound'
        )
        
        print(f"✅ Created tenant: {tenant.name}")
        print(f"✅ Created customer: {customer.name}")
        print(f"✅ Created conversation: {conversation.id}")
        print(f"✅ Created message: {message.id}")
        
        # Now test ConversationSession creation with proper state
        print("\n🔧 Testing ConversationSession creation...")
        
        # Create initial state
        initial_state = ConversationState(
            tenant_id=str(tenant.id),
            conversation_id=str(conversation.id),
            request_id=str(message.id),
            customer_id=str(customer.id),
            phone_e164=customer.phone_e164
        )
        
        # Serialize state
        state_data = ConversationStateManager.serialize_for_storage(initial_state)
        
        # Create session with proper state_data
        session = ConversationSession.objects.create(
            tenant=tenant,
            conversation=conversation,
            customer=customer,
            is_active=True,
            state_data=state_data,
            last_request_id=str(message.id)
        )
        
        print(f"✅ Created ConversationSession: {session.id}")
        
        # Test retrieving state
        retrieved_state = session.get_state()
        print(f"✅ Retrieved state - tenant_id: {retrieved_state.tenant_id}")
        print(f"✅ Retrieved state - conversation_id: {retrieved_state.conversation_id}")
        print(f"✅ Retrieved state - intent: {retrieved_state.intent}")
        print(f"✅ Retrieved state - journey: {retrieved_state.journey}")
        
        # Test updating state
        retrieved_state.intent = "sales_discovery"
        retrieved_state.journey = "sales"
        retrieved_state.turn_count = 1
        
        session.update_state(retrieved_state)
        print(f"✅ Updated state successfully")
        
        # Verify update
        updated_state = session.get_state()
        assert updated_state.intent == "sales_discovery"
        assert updated_state.journey == "sales"
        assert updated_state.turn_count == 1
        print(f"✅ Verified state update - intent: {updated_state.intent}, journey: {updated_state.journey}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_get_or_create_session():
    """Test the get_or_create functionality that was causing the original error."""
    print("\n🧪 Testing get_or_create ConversationSession...")
    
    try:
        # Get existing data
        tenant = Tenant.objects.first()
        customer = Customer.objects.first()
        conversation = Conversation.objects.first()
        
        if not all([tenant, customer, conversation]):
            print("❌ Missing test data")
            return False
        
        # Test the problematic get_or_create call from tasks.py
        session, created = ConversationSession.objects.get_or_create(
            tenant=tenant,
            conversation=conversation,
            defaults={
                'customer': customer,
                'is_active': True,
                'state_data': ConversationStateManager.serialize_for_storage(
                    ConversationState(
                        tenant_id=str(tenant.id),
                        conversation_id=str(conversation.id),
                        request_id="test-request-id",
                        customer_id=str(customer.id),
                        phone_e164=customer.phone_e164
                    )
                ),
                'last_request_id': 'test-request-id'
            }
        )
        
        print(f"✅ get_or_create successful - created: {created}")
        print(f"✅ Session ID: {session.id}")
        
        # Test getting existing session
        session2, created2 = ConversationSession.objects.get_or_create(
            tenant=tenant,
            conversation=conversation,
            defaults={
                'customer': customer,
                'is_active': True,
                'state_data': '{}',  # This should not be used since session exists
                'last_request_id': 'test-request-id-2'
            }
        )
        
        print(f"✅ Second get_or_create successful - created: {created2}")
        assert not created2, "Should have retrieved existing session"
        assert session.id == session2.id, "Should be the same session"
        
        return True
        
    except Exception as e:
        print(f"❌ Error in get_or_create test: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test function."""
    print("🚀 SIMPLE BOT TEST")
    print("=" * 50)
    print("Testing ConversationSession field fix")
    print("=" * 50)
    
    # Test 1: Basic ConversationSession creation
    test1_result = test_conversation_session_creation()
    
    # Test 2: get_or_create functionality
    test2_result = test_get_or_create_session()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    tests = [
        ("ConversationSession Creation", test1_result),
        ("get_or_create Functionality", test2_result)
    ]
    
    passed = sum(1 for _, result in tests if result)
    total = len(tests)
    
    for name, result in tests:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ ConversationSession 'state' field error is FIXED")
        print("✅ The bot can now create and manage conversation sessions")
        print("✅ Ready for production testing")
    else:
        print("\n⚠️ Some tests failed")
        print("💡 The ConversationSession field issue may still exist")
    
    print("=" * 50)
    
    return 0 if passed == total else 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)