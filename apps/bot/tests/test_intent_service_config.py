"""
Tests for IntentService configuration and model compatibility.
"""
import pytest
from apps.bot.services.intent_service import IntentService, create_intent_service


@pytest.mark.django_db
class TestIntentServiceConfiguration:
    """Test IntentService initialization and configuration."""
    
    def test_default_initialization(self):
        """Test that IntentService initializes with default model."""
        service = create_intent_service()
        
        assert service.model is not None
        assert service.client is not None
    
    def test_json_mode_detection_supported_models(self):
        """Test JSON mode detection for supported models."""
        supported_models = [
            'gpt-4o',
            'gpt-4o-mini',
            'gpt-4-turbo',
            'gpt-3.5-turbo-1106',
            'gpt-3.5-turbo-0125',
        ]
        
        for model_name in supported_models:
            service = IntentService(model=model_name)
            assert service.supports_json_mode is True, \
                f"{model_name} should support JSON mode"
    
    def test_json_mode_detection_unsupported_models(self):
        """Test JSON mode detection for unsupported models."""
        unsupported_models = [
            'gpt-3.5-turbo',
            'gpt-4',
            'gpt-3.5-turbo-0301',
        ]
        
        for model_name in unsupported_models:
            service = IntentService(model=model_name)
            assert service.supports_json_mode is False, \
                f"{model_name} should not support JSON mode"
    
    def test_custom_model_initialization(self):
        """Test initialization with custom model."""
        service = IntentService(model='gpt-4o')
        
        assert service.model == 'gpt-4o'
        assert service.supports_json_mode is True
    
    def test_extract_json_from_markdown(self):
        """Test JSON extraction from markdown code blocks."""
        service = create_intent_service()
        
        # Test with markdown code block
        text = '''```json
{
  "intent": "BROWSE_PRODUCTS",
  "confidence": 0.9,
  "slots": {}
}
```'''
        
        result = service._extract_json_from_text(text)
        
        assert result['intent'] == 'BROWSE_PRODUCTS'
        assert result['confidence'] == 0.9
    
    def test_extract_json_from_plain_text(self):
        """Test JSON extraction from plain text."""
        service = create_intent_service()
        
        # Test with JSON in plain text
        text = 'Here is the result: {"intent": "GREETING", "confidence": 0.95, "slots": {}}'
        
        result = service._extract_json_from_text(text)
        
        assert result['intent'] == 'GREETING'
        assert result['confidence'] == 0.95
    
    def test_extract_json_invalid_text(self):
        """Test JSON extraction fails gracefully with invalid text."""
        service = create_intent_service()
        
        with pytest.raises(Exception):  # Should raise JSONDecodeError
            service._extract_json_from_text('This is not JSON at all')
    
    def test_confidence_threshold(self):
        """Test confidence threshold checking."""
        service = create_intent_service()
        
        assert service.is_high_confidence(0.8) is True
        assert service.is_high_confidence(0.7) is True
        assert service.is_high_confidence(0.69) is False
        
        assert service.is_low_confidence(0.69) is True
        assert service.is_low_confidence(0.7) is False
    
    def test_intent_constants(self):
        """Test that intent constants are defined."""
        service = create_intent_service()
        
        assert len(service.PRODUCT_INTENTS) > 0
        assert len(service.SERVICE_INTENTS) > 0
        assert len(service.CONSENT_INTENTS) > 0
        assert len(service.SUPPORT_INTENTS) > 0
        assert len(service.ALL_INTENTS) > 0
        
        # Check specific intents exist
        assert 'BROWSE_PRODUCTS' in service.PRODUCT_INTENTS
        assert 'BOOK_APPOINTMENT' in service.SERVICE_INTENTS
        assert 'HUMAN_HANDOFF' in service.SUPPORT_INTENTS
