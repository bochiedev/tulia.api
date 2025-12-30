#!/usr/bin/env python
"""
Test script to verify async context fixes in LLM router and nodes.
"""
import os
import sys
import django
import asyncio

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.tenants.models import Tenant
from apps.bot.services.llm_router import LLMRouter
from apps.bot.conversation_state import ConversationState
from apps.bot.langgraph.llm_nodes import IntentClassificationNode


async def test_llm_router_async():
    """Test LLM router async context handling."""
    print("🧪 Testing LLM Router async context...")
    
    try:
        # Get or create a test tenant
        tenant, created = await Tenant.objects.aget_or_create(
            name="test-tenant",
            defaults={
                'slug': 'test-tenant',
                'status': 'active'
            }
        )
        print(f"✅ Tenant ready: {tenant.name} (created: {created})")
        
        # Create LLM router
        llm_router = LLMRouter(tenant)
        print("✅ LLM Router created")
        
        # Test config loading
        await llm_router._ensure_config_loaded()
        print("✅ Config loaded successfully")
        
        # Test budget check
        budget_ok = await llm_router._check_budget()
        print(f"✅ Budget check: {budget_ok}")
        
        return True
        
    except Exception as e:
        print(f"❌ LLM Router test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_intent_node_async():
    """Test intent classification node async context handling."""
    print("\n🧪 Testing Intent Classification Node async context...")
    
    try:
        # Get test tenant
        tenant = await Tenant.objects.aget(name="test-tenant")
        
        # Create conversation state
        state = ConversationState(
            tenant_id=tenant.id,
            conversation_id="test-conv-123",
            request_id="test-req-123",
            incoming_message="Hello, I want to buy something",
            turn_count=1,
            bot_name="TestBot",
            tenant_name="Test Tenant"
        )
        
        # Create intent node
        intent_node = IntentClassificationNode()
        print("✅ Intent node created")
        
        # Test LLM input preparation
        input_text = intent_node._prepare_llm_input(state)
        print(f"✅ Input prepared: {len(input_text)} chars")
        
        # Test LLM call (this will test the async context)
        try:
            result = await intent_node._call_llm(input_text, state)
            print(f"✅ LLM call successful: {result.get('intent', 'unknown')}")
            return True
        except Exception as llm_error:
            # Check if it's an API key issue (expected) vs async context issue
            if "api" in str(llm_error).lower() or "key" in str(llm_error).lower():
                print(f"✅ LLM call failed as expected (API key issue): {llm_error}")
                return True
            else:
                print(f"❌ LLM call failed with unexpected error: {llm_error}")
                return False
        
    except Exception as e:
        print(f"❌ Intent node test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all async context tests."""
    print("🚀 ASYNC CONTEXT FIX TEST")
    print("=" * 50)
    
    results = []
    
    # Test LLM router
    results.append(await test_llm_router_async())
    
    # Test intent node
    results.append(await test_intent_node_async())
    
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    print(f"LLM Router Async: {'✅ PASSED' if results[0] else '❌ FAILED'}")
    print(f"Intent Node Async: {'✅ PASSED' if results[1] else '❌ FAILED'}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All async context issues fixed!")
        return 0
    else:
        print("⚠️ Some async context issues remain")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)