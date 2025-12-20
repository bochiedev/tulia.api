"""
Example usage of ConversationState schema and management.

This example demonstrates how to use the ConversationState system
for LangGraph orchestration in the Tulia AI V2 system.
"""
from apps.bot.conversation_state import ConversationState, ConversationStateManager
from apps.bot.models_conversation_state import ConversationStateService
from apps.tenants.models import Tenant, Customer
from apps.messaging.models import Conversation


def example_conversation_state_usage():
    """
    Example demonstrating ConversationState usage throughout a conversation.
    """
    
    # 1. Set up conversation entities (normally done by webhook handler)
    tenant = Tenant.objects.get(slug="example-tenant")
    customer = Customer.objects.get(tenant=tenant, phone_e164="+254700000001")
    conversation = Conversation.objects.get(tenant=tenant, customer=customer)
    
    # 2. Create initial conversation state for new conversation
    initial_state = ConversationStateService.create_initial_state_for_conversation(
        conversation=conversation,
        request_id="req_001",
        # Optional initial values
        bot_name="TuliaBot",
        tone_style="friendly_concise",
        default_language="en",
        allowed_languages=["en", "sw", "sheng"],
        max_chattiness_level=2
    )
    
    print(f"Initial state created for conversation {conversation.id}")
    print(f"Tenant: {initial_state.tenant_id}")
    print(f"Intent: {initial_state.intent}")
    print(f"Journey: {initial_state.journey}")
    
    # 3. Get or create session for the conversation
    session = ConversationStateService.get_or_create_session(
        conversation=conversation,
        request_id="req_001"
    )
    
    print(f"Session created: {session.id}")
    
    # 4. Simulate LangGraph node processing - Intent Classification
    state = ConversationStateService.get_state(conversation)
    
    # Update intent based on customer message analysis
    state.update_intent("sales_discovery", 0.85)
    state.journey = "sales"
    state.increment_turn()
    state.request_id = "req_002"
    
    # Save updated state
    ConversationStateService.update_state(conversation, state)
    
    print(f"Intent updated: {state.intent} (confidence: {state.intent_confidence})")
    print(f"Journey: {state.journey}")
    print(f"Turn count: {state.turn_count}")
    
    # 5. Simulate Language Policy node
    state = ConversationStateService.get_state(conversation)
    
    # Detect customer language
    state.update_language("sw", 0.78)
    state.customer_language_pref = "sw"
    state.request_id = "req_003"
    
    ConversationStateService.update_state(conversation, state)
    
    print(f"Language detected: {state.response_language} (confidence: {state.language_confidence})")
    print(f"Customer preference: {state.customer_language_pref}")
    
    # 6. Simulate Conversation Governor node
    state = ConversationStateService.get_state(conversation)
    
    # Classify conversation type
    state.update_governor("business", 0.92)
    state.request_id = "req_004"
    
    ConversationStateService.update_state(conversation, state)
    
    print(f"Governor classification: {state.governor_classification} (confidence: {state.governor_confidence})")
    
    # 7. Simulate Sales Journey - Product Selection
    state = ConversationStateService.get_state(conversation)
    
    # Customer selects products
    state.add_to_cart("prod_123", 2, {"size": "L", "color": "blue"})
    state.add_to_cart("prod_456", 1, {"size": "M"})
    state.selected_item_ids = ["prod_123", "prod_456"]
    state.request_id = "req_005"
    
    ConversationStateService.update_state(conversation, state)
    
    print(f"Cart items: {len(state.cart)}")
    print(f"Selected items: {state.selected_item_ids}")
    
    # 8. Simulate Order Creation
    state = ConversationStateService.get_state(conversation)
    
    # Order created
    state.order_id = "order_789"
    state.order_totals = {"subtotal": 2500, "tax": 400, "total": 2900}
    state.payment_status = "pending"
    state.request_id = "req_006"
    
    ConversationStateService.update_state(conversation, state)
    
    print(f"Order created: {state.order_id}")
    print(f"Order total: {state.order_totals['total']}")
    print(f"Payment status: {state.payment_status}")
    
    # 9. Simulate Payment Processing
    state = ConversationStateService.get_state(conversation)
    
    # Payment completed
    state.payment_request_id = "pay_req_101"
    state.payment_status = "paid"
    state.request_id = "req_007"
    
    ConversationStateService.update_state(conversation, state)
    
    print(f"Payment completed: {state.payment_request_id}")
    print(f"Final status: {state.payment_status}")
    
    # 10. Conversation completion
    state = ConversationStateService.get_state(conversation)
    
    # Clear cart and reset for next conversation
    state.clear_cart()
    state.order_id = None
    state.payment_status = None
    state.journey = "unknown"
    state.intent = "unknown"
    state.request_id = "req_008"
    
    ConversationStateService.update_state(conversation, state)
    
    print("Conversation completed and state reset")
    
    # 11. Deactivate session when conversation ends
    ConversationStateService.deactivate_session(conversation)
    
    print("Session deactivated")


def example_state_serialization():
    """
    Example demonstrating state serialization and deserialization.
    """
    
    # Create a complex state
    state = ConversationState(
        tenant_id="tenant_123",
        conversation_id="conv_456",
        request_id="req_789",
        customer_id="cust_101",
        phone_e164="+254700000001",
        bot_name="TuliaBot",
        intent="sales_discovery",
        journey="sales",
        response_language="sw",
        intent_confidence=0.85,
        language_confidence=0.78,
        governor_classification="business",
        governor_confidence=0.92,
        turn_count=5,
        cart=[
            {"item_id": "prod_123", "qty": 2, "variant_selection": {"size": "L"}},
            {"item_id": "prod_456", "qty": 1, "variant_selection": {"color": "red"}}
        ],
        order_id="order_789",
        order_totals={"subtotal": 2500, "tax": 400, "total": 2900},
        payment_status="pending",
        escalation_required=False
    )
    
    print("Original state:")
    print(f"  Intent: {state.intent} (confidence: {state.intent_confidence})")
    print(f"  Journey: {state.journey}")
    print(f"  Language: {state.response_language}")
    print(f"  Cart items: {len(state.cart)}")
    print(f"  Order ID: {state.order_id}")
    
    # Serialize to JSON
    json_str = ConversationStateManager.serialize_for_storage(state)
    print(f"\nSerialized to JSON ({len(json_str)} characters)")
    
    # Deserialize from JSON
    restored_state = ConversationStateManager.deserialize_from_storage(json_str)
    
    print("\nRestored state:")
    print(f"  Intent: {restored_state.intent} (confidence: {restored_state.intent_confidence})")
    print(f"  Journey: {restored_state.journey}")
    print(f"  Language: {restored_state.response_language}")
    print(f"  Cart items: {len(restored_state.cart)}")
    print(f"  Order ID: {restored_state.order_id}")
    
    # Validate restored state
    restored_state.validate()
    print("\nState validation passed!")


def example_state_validation():
    """
    Example demonstrating state validation.
    """
    
    print("Testing state validation...")
    
    # Valid state
    try:
        valid_state = ConversationState(
            tenant_id="tenant_123",
            conversation_id="conv_456",
            request_id="req_789",
            intent="sales_discovery",
            journey="sales",
            intent_confidence=0.85,
            max_chattiness_level=2
        )
        valid_state.validate()
        print("✓ Valid state passed validation")
    except ValueError as e:
        print(f"✗ Valid state failed: {e}")
    
    # Invalid intent
    try:
        invalid_state = ConversationState(
            tenant_id="tenant_123",
            conversation_id="conv_456",
            request_id="req_789",
            intent="invalid_intent"  # Invalid
        )
        invalid_state.validate()
        print("✗ Invalid intent should have failed")
    except ValueError as e:
        print(f"✓ Invalid intent correctly rejected: {e}")
    
    # Invalid confidence score
    try:
        invalid_state = ConversationState(
            tenant_id="tenant_123",
            conversation_id="conv_456",
            request_id="req_789",
            intent_confidence=1.5  # Invalid (> 1.0)
        )
        invalid_state.validate()
        print("✗ Invalid confidence should have failed")
    except ValueError as e:
        print(f"✓ Invalid confidence correctly rejected: {e}")
    
    # Invalid chattiness level
    try:
        invalid_state = ConversationState(
            tenant_id="tenant_123",
            conversation_id="conv_456",
            request_id="req_789",
            max_chattiness_level=5  # Invalid (> 3)
        )
        invalid_state.validate()
        print("✗ Invalid chattiness level should have failed")
    except ValueError as e:
        print(f"✓ Invalid chattiness level correctly rejected: {e}")


if __name__ == "__main__":
    print("ConversationState Usage Examples")
    print("=" * 40)
    
    print("\n1. State Serialization Example:")
    example_state_serialization()
    
    print("\n2. State Validation Example:")
    example_state_validation()
    
    # Note: The conversation usage example requires actual database objects
    # print("\n3. Full Conversation Example:")
    # example_conversation_state_usage()