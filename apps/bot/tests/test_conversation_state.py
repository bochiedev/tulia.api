"""
Tests for ConversationState schema and management.

Tests the ConversationState dataclass, serialization/deserialization,
validation, and database persistence through ConversationSession model.
"""
import json
import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.bot.conversation_state import (
    ConversationState,
    ConversationStateManager,
    Intent,
    Journey,
    Lang,
    GovernorClass,
)
from apps.bot.models_conversation_state import (
    ConversationSession,
    ConversationStateService,
)
from apps.tenants.models import Tenant, Customer
from apps.messaging.models import Conversation


class ConversationStateTests(TestCase):
    """Test ConversationState dataclass functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            whatsapp_number="+254700000001"
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            phone_e164="+254700000002",
            name="Test Customer"
        )
        self.conversation = Conversation.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            status='open'
        )
    
    def test_create_minimal_state(self):
        """Test creating ConversationState with minimal required fields."""
        state = ConversationState(
            tenant_id=str(self.tenant.id),
            conversation_id=str(self.conversation.id),
            request_id="req_123"
        )
        
        # Validate required fields
        self.assertEqual(state.tenant_id, str(self.tenant.id))
        self.assertEqual(state.conversation_id, str(self.conversation.id))
        self.assertEqual(state.request_id, "req_123")
        
        # Validate default values
        self.assertEqual(state.intent, "unknown")
        self.assertEqual(state.journey, "unknown")
        self.assertEqual(state.response_language, "en")
        self.assertEqual(state.default_language, "en")
        self.assertEqual(state.governor_classification, "business")
        self.assertEqual(state.tone_style, "friendly_concise")
        self.assertEqual(state.max_chattiness_level, 2)
        self.assertEqual(state.turn_count, 0)
        self.assertEqual(state.casual_turns, 0)
        self.assertEqual(state.spam_turns, 0)
        self.assertFalse(state.escalation_required)
        
        # Validate collections
        self.assertEqual(state.allowed_languages, ["en", "sw", "sheng"])
        self.assertEqual(state.cart, [])
        self.assertEqual(state.kb_snippets, [])
        self.assertEqual(state.selected_item_ids, [])
    
    def test_state_validation_success(self):
        """Test successful state validation."""
        state = ConversationState(
            tenant_id=str(self.tenant.id),
            conversation_id=str(self.conversation.id),
            request_id="req_123",
            intent="sales_discovery",
            journey="sales",
            response_language="sw",
            governor_classification="casual",
            intent_confidence=0.85,
            language_confidence=0.92,
            governor_confidence=0.78
        )
        
        # Should not raise any exception
        state.validate()
    
    def test_state_validation_failures(self):
        """Test state validation with invalid values."""
        # Missing required fields
        with self.assertRaises(ValueError) as cm:
            state = ConversationState(
                tenant_id="",  # Empty tenant_id
                conversation_id=str(self.conversation.id),
                request_id="req_123"
            )
            state.validate()
        self.assertIn("tenant_id is required", str(cm.exception))
        
        # Invalid intent
        with self.assertRaises(ValueError) as cm:
            state = ConversationState(
                tenant_id=str(self.tenant.id),
                conversation_id=str(self.conversation.id),
                request_id="req_123",
                intent="invalid_intent"
            )
            state.validate()
        self.assertIn("Invalid intent", str(cm.exception))
        
        # Invalid confidence score
        with self.assertRaises(ValueError) as cm:
            state = ConversationState(
                tenant_id=str(self.tenant.id),
                conversation_id=str(self.conversation.id),
                request_id="req_123",
                intent_confidence=1.5
            )
            state.validate()
        self.assertIn("intent_confidence must be between 0.0 and 1.0", str(cm.exception))
        
        # Invalid chattiness level
        with self.assertRaises(ValueError) as cm:
            state = ConversationState(
                tenant_id=str(self.tenant.id),
                conversation_id=str(self.conversation.id),
                request_id="req_123",
                max_chattiness_level=5
            )
            state.validate()
        self.assertIn("max_chattiness_level must be between 0 and 3", str(cm.exception))
    
    def test_literal_types_validation(self):
        """Test validation of literal types."""
        state = ConversationState(
            tenant_id=str(self.tenant.id),
            conversation_id=str(self.conversation.id),
            request_id="req_123"
        )
        
        # Valid intent values
        valid_intents = [
            "sales_discovery", "product_question", "support_question", "order_status",
            "discounts_offers", "preferences_consent", "payment_help",
            "human_request", "spam_casual", "unknown"
        ]
        for intent in valid_intents:
            state.intent = intent
            state.validate()  # Should not raise
        
        # Valid journey values
        valid_journeys = ["sales", "support", "orders", "offers", "prefs", "governance", "unknown"]
        for journey in valid_journeys:
            state.journey = journey
            state.validate()  # Should not raise
        
        # Valid language values
        valid_languages = ["en", "sw", "sheng", "mixed"]
        for lang in valid_languages:
            state.response_language = lang
            state.default_language = lang
            state.customer_language_pref = lang
            state.validate()  # Should not raise
        
        # Valid governor classifications
        valid_governor_classes = ["business", "casual", "spam", "abuse"]
        for gov_class in valid_governor_classes:
            state.governor_classification = gov_class
            state.validate()  # Should not raise
    
    def test_serialization_deserialization(self):
        """Test state serialization and deserialization."""
        original_state = ConversationState(
            tenant_id=str(self.tenant.id),
            conversation_id=str(self.conversation.id),
            request_id="req_123",
            customer_id=str(self.customer.id),
            intent="sales_discovery",
            journey="sales",
            response_language="sw",
            intent_confidence=0.85,
            turn_count=5,
            casual_turns=2,
            cart=[{"item_id": "prod_123", "qty": 2, "variant_selection": {"size": "L"}}],
            escalation_required=True,
            escalation_reason="Complex query"
        )
        
        # Test to_dict
        state_dict = original_state.to_dict()
        self.assertIsInstance(state_dict, dict)
        self.assertEqual(state_dict['tenant_id'], str(self.tenant.id))
        self.assertEqual(state_dict['intent'], "sales_discovery")
        self.assertEqual(state_dict['turn_count'], 5)
        
        # Test from_dict
        restored_state = ConversationState.from_dict(state_dict)
        self.assertEqual(restored_state.tenant_id, original_state.tenant_id)
        self.assertEqual(restored_state.intent, original_state.intent)
        self.assertEqual(restored_state.turn_count, original_state.turn_count)
        self.assertEqual(restored_state.cart, original_state.cart)
        
        # Test to_json
        json_str = original_state.to_json()
        self.assertIsInstance(json_str, str)
        parsed_json = json.loads(json_str)
        self.assertEqual(parsed_json['tenant_id'], str(self.tenant.id))
        
        # Test from_json
        restored_from_json = ConversationState.from_json(json_str)
        self.assertEqual(restored_from_json.tenant_id, original_state.tenant_id)
        self.assertEqual(restored_from_json.intent, original_state.intent)
        self.assertEqual(restored_from_json.escalation_required, original_state.escalation_required)
    
    def test_state_update_methods(self):
        """Test state update helper methods."""
        state = ConversationState(
            tenant_id=str(self.tenant.id),
            conversation_id=str(self.conversation.id),
            request_id="req_123"
        )
        
        # Test update_intent
        state.update_intent("sales_discovery", 0.85)
        self.assertEqual(state.intent, "sales_discovery")
        self.assertEqual(state.intent_confidence, 0.85)
        
        # Test update_language
        state.update_language("sw", 0.92)
        self.assertEqual(state.response_language, "sw")
        self.assertEqual(state.language_confidence, 0.92)
        
        # Test update_governor
        state.update_governor("casual", 0.78)
        self.assertEqual(state.governor_classification, "casual")
        self.assertEqual(state.governor_confidence, 0.78)
        
        # Test increment methods
        state.increment_turn()
        self.assertEqual(state.turn_count, 1)
        
        state.increment_casual_turns()
        self.assertEqual(state.casual_turns, 1)
        
        state.increment_spam_turns()
        self.assertEqual(state.spam_turns, 1)
        
        # Test cart operations
        state.add_to_cart("prod_123", 2, {"size": "L", "color": "blue"})
        self.assertEqual(len(state.cart), 1)
        self.assertEqual(state.cart[0]["item_id"], "prod_123")
        self.assertEqual(state.cart[0]["qty"], 2)
        
        state.clear_cart()
        self.assertEqual(len(state.cart), 0)
        
        # Test escalation operations
        state.set_escalation("Complex query", "ticket_456")
        self.assertTrue(state.escalation_required)
        self.assertEqual(state.escalation_reason, "Complex query")
        self.assertEqual(state.handoff_ticket_id, "ticket_456")
        
        state.clear_escalation()
        self.assertFalse(state.escalation_required)
        self.assertIsNone(state.escalation_reason)
        self.assertIsNone(state.handoff_ticket_id)
    
    def test_invalid_confidence_scores(self):
        """Test validation of confidence score ranges."""
        state = ConversationState(
            tenant_id=str(self.tenant.id),
            conversation_id=str(self.conversation.id),
            request_id="req_123"
        )
        
        # Test invalid confidence in update methods
        with self.assertRaises(ValueError):
            state.update_intent("sales_discovery", 1.5)
        
        with self.assertRaises(ValueError):
            state.update_language("sw", -0.1)
        
        with self.assertRaises(ValueError):
            state.update_governor("casual", 2.0)


class ConversationSessionTests(TestCase):
    """Test ConversationSession model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            whatsapp_number="+254700000003"
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            phone_e164="+254700000004",
            name="Test Customer"
        )
        self.conversation = Conversation.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            status='open'
        )
    
    def test_create_conversation_session(self):
        """Test creating ConversationSession."""
        state = ConversationState(
            tenant_id=str(self.tenant.id),
            conversation_id=str(self.conversation.id),
            request_id="req_123",
            customer_id=str(self.customer.id)
        )
        
        session = ConversationSession.objects.create(
            tenant=self.tenant,
            conversation=self.conversation,
            customer=self.customer,
            state_data=state.to_json(),
            last_request_id="req_123"
        )
        
        self.assertEqual(session.tenant, self.tenant)
        self.assertEqual(session.conversation, self.conversation)
        self.assertEqual(session.customer, self.customer)
        self.assertTrue(session.is_active)
        self.assertEqual(session.last_request_id, "req_123")
    
    def test_get_and_update_state(self):
        """Test getting and updating state in ConversationSession."""
        # Create initial state
        initial_state = ConversationState(
            tenant_id=str(self.tenant.id),
            conversation_id=str(self.conversation.id),
            request_id="req_123",
            customer_id=str(self.customer.id),
            intent="unknown",
            turn_count=0
        )
        
        session = ConversationSession.objects.create(
            tenant=self.tenant,
            conversation=self.conversation,
            customer=self.customer,
            state_data=initial_state.to_json(),
            last_request_id="req_123"
        )
        
        # Get state
        retrieved_state = session.get_state()
        self.assertEqual(retrieved_state.tenant_id, str(self.tenant.id))
        self.assertEqual(retrieved_state.intent, "unknown")
        self.assertEqual(retrieved_state.turn_count, 0)
        
        # Update state
        retrieved_state.update_intent("sales_discovery", 0.85)
        retrieved_state.increment_turn()
        retrieved_state.request_id = "req_124"
        
        session.update_and_save_state(retrieved_state)
        
        # Verify update
        session.refresh_from_db()
        updated_state = session.get_state()
        self.assertEqual(updated_state.intent, "sales_discovery")
        self.assertEqual(updated_state.intent_confidence, 0.85)
        self.assertEqual(updated_state.turn_count, 1)
        self.assertEqual(updated_state.request_id, "req_124")
        self.assertEqual(session.last_request_id, "req_124")
    
    def test_session_validation(self):
        """Test ConversationSession validation."""
        # Create session with mismatched tenant
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            whatsapp_number="+254700000005"  # Different WhatsApp number
        )
        
        # Create valid state for the session's tenant first
        valid_state = ConversationState(
            tenant_id=str(self.tenant.id),  # Correct tenant
            conversation_id=str(self.conversation.id),
            request_id="req_123"
        )
        
        # Create session with valid state
        session = ConversationSession.objects.create(
            tenant=self.tenant,
            conversation=self.conversation,
            customer=self.customer,
            state_data=valid_state.to_json(),
            last_request_id="req_123"
        )
        
        # Now create state with mismatched tenant
        mismatched_state = ConversationState(
            tenant_id=str(other_tenant.id),  # Different tenant
            conversation_id=str(self.conversation.id),
            request_id="req_124"
        )
        
        # This should raise ValidationError due to tenant mismatch
        with self.assertRaises(ValidationError):
            session.update_state(mismatched_state)
    
    def test_session_manager_methods(self):
        """Test ConversationSession manager methods."""
        # Create session
        session, created = ConversationSession.objects.get_or_create_for_conversation(
            conversation=self.conversation,
            request_id="req_123"
        )
        
        self.assertTrue(created)
        self.assertEqual(session.tenant, self.tenant)
        self.assertEqual(session.conversation, self.conversation)
        self.assertEqual(session.customer, self.customer)
        
        # Test get existing session
        session2, created2 = ConversationSession.objects.get_or_create_for_conversation(
            conversation=self.conversation,
            request_id="req_124"
        )
        
        self.assertFalse(created2)
        self.assertEqual(session.id, session2.id)
        
        # Test manager queries
        tenant_sessions = ConversationSession.objects.for_tenant(self.tenant)
        self.assertEqual(tenant_sessions.count(), 1)
        
        conversation_session = ConversationSession.objects.for_conversation(self.conversation)
        self.assertEqual(conversation_session.id, session.id)
        
        active_sessions = ConversationSession.objects.active(self.tenant)
        self.assertEqual(active_sessions.count(), 1)
        
        # Test deactivation
        session.deactivate()
        active_sessions = ConversationSession.objects.active(self.tenant)
        self.assertEqual(active_sessions.count(), 0)


class ConversationStateServiceTests(TestCase):
    """Test ConversationStateService functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            whatsapp_number="+254700000006"
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            phone_e164="+254700000007",
            name="Test Customer"
        )
        self.conversation = Conversation.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            status='open'
        )
    
    def test_get_or_create_session(self):
        """Test getting or creating session through service."""
        session = ConversationStateService.get_or_create_session(
            conversation=self.conversation,
            request_id="req_123",
            intent="sales_discovery",
            journey="sales"
        )
        
        self.assertEqual(session.conversation, self.conversation)
        self.assertTrue(session.is_active)
        
        # Verify initial state
        state = session.get_state()
        self.assertEqual(state.tenant_id, str(self.tenant.id))
        self.assertEqual(state.conversation_id, str(self.conversation.id))
        self.assertEqual(state.request_id, "req_123")
        self.assertEqual(state.intent, "sales_discovery")
        self.assertEqual(state.journey, "sales")
    
    def test_get_and_update_state(self):
        """Test getting and updating state through service."""
        # Create session first
        session = ConversationStateService.get_or_create_session(
            conversation=self.conversation,
            request_id="req_123"
        )
        
        # Get state
        state = ConversationStateService.get_state(self.conversation)
        self.assertIsNotNone(state)
        self.assertEqual(state.conversation_id, str(self.conversation.id))
        
        # Update state
        state.update_intent("product_question", 0.92)
        state.increment_turn()
        state.request_id = "req_124"
        
        ConversationStateService.update_state(self.conversation, state)
        
        # Verify update
        updated_state = ConversationStateService.get_state(self.conversation)
        self.assertEqual(updated_state.intent, "product_question")
        self.assertEqual(updated_state.intent_confidence, 0.92)
        self.assertEqual(updated_state.turn_count, 1)
        self.assertEqual(updated_state.request_id, "req_124")
    
    def test_create_initial_state(self):
        """Test creating initial state for conversation."""
        state = ConversationStateService.create_initial_state_for_conversation(
            conversation=self.conversation,
            request_id="req_123",
            intent="support_question",
            journey="support",
            response_language="sw"
        )
        
        self.assertEqual(state.tenant_id, str(self.tenant.id))
        self.assertEqual(state.conversation_id, str(self.conversation.id))
        self.assertEqual(state.customer_id, str(self.customer.id))
        self.assertEqual(state.request_id, "req_123")
        self.assertEqual(state.intent, "support_question")
        self.assertEqual(state.journey, "support")
        self.assertEqual(state.response_language, "sw")
    
    def test_deactivate_session(self):
        """Test deactivating session through service."""
        # Create session
        session = ConversationStateService.get_or_create_session(
            conversation=self.conversation,
            request_id="req_123"
        )
        self.assertTrue(session.is_active)
        
        # Deactivate
        ConversationStateService.deactivate_session(self.conversation)
        
        # Verify deactivation
        session.refresh_from_db()
        self.assertFalse(session.is_active)


class ConversationStateManagerTests(TestCase):
    """Test ConversationStateManager functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            whatsapp_number="+254700000008"
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            phone_e164="+254700000009",
            name="Test Customer"
        )
        self.conversation = Conversation.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            status='open'
        )
    
    def test_create_initial_state(self):
        """Test creating initial state with manager."""
        state = ConversationStateManager.create_initial_state(
            tenant_id=str(self.tenant.id),
            conversation_id=str(self.conversation.id),
            request_id="req_123",
            customer_id=str(self.customer.id),
            intent="sales_discovery",
            journey="sales"
        )
        
        self.assertEqual(state.tenant_id, str(self.tenant.id))
        self.assertEqual(state.conversation_id, str(self.conversation.id))
        self.assertEqual(state.request_id, "req_123")
        self.assertEqual(state.customer_id, str(self.customer.id))
        self.assertEqual(state.intent, "sales_discovery")
        self.assertEqual(state.journey, "sales")
        
        # Should validate successfully
        state.validate()
    
    def test_serialize_deserialize_for_storage(self):
        """Test serialization and deserialization for storage."""
        state = ConversationState(
            tenant_id=str(self.tenant.id),
            conversation_id=str(self.conversation.id),
            request_id="req_123",
            customer_id=str(self.customer.id),
            intent="product_question",
            journey="sales",
            turn_count=3,
            cart=[{"item_id": "prod_456", "qty": 1, "variant_selection": {}}]
        )
        
        # Serialize
        json_str = ConversationStateManager.serialize_for_storage(state)
        self.assertIsInstance(json_str, str)
        
        # Deserialize
        restored_state = ConversationStateManager.deserialize_from_storage(json_str)
        self.assertEqual(restored_state.tenant_id, state.tenant_id)
        self.assertEqual(restored_state.intent, state.intent)
        self.assertEqual(restored_state.turn_count, state.turn_count)
        self.assertEqual(restored_state.cart, state.cart)
        
        # Should validate successfully
        restored_state.validate()