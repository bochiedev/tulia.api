"""
Intent classification service using LLM for natural language understanding.

Classifies customer messages into actionable intents and extracts relevant
entities/slots for downstream processing.
"""
import logging
import time
import json
from typing import Dict, Any, Optional, Tuple
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Import OpenAI (will be installed as dependency)
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI library not available. Install with: pip install openai")

# Import jsonschema for response validation
try:
    import jsonschema
    from jsonschema import validate, ValidationError
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    logger.warning("jsonschema library not available. Install with: pip install jsonschema")


class IntentServiceError(Exception):
    """Base exception for intent service errors."""
    pass


class IntentService:
    """
    Service for classifying customer intents using LLM.
    
    Supports multiple intents for products, services, bookings, and support.
    Extracts slots/entities from messages for downstream handlers.
    """
    
    # Confidence threshold for accepting intent classification
    CONFIDENCE_THRESHOLD = 0.7
    
    # Maximum consecutive low-confidence attempts before handoff
    MAX_LOW_CONFIDENCE_ATTEMPTS = 2
    
    # Supported intents
    PRODUCT_INTENTS = [
        'GREETING',
        'BROWSE_PRODUCTS',
        'PRODUCT_DETAILS',
        'PRICE_CHECK',
        'STOCK_CHECK',
        'ADD_TO_CART',
        'CHECKOUT_LINK',
    ]
    
    SERVICE_INTENTS = [
        'BROWSE_SERVICES',
        'SERVICE_DETAILS',
        'CHECK_AVAILABILITY',
        'BOOK_APPOINTMENT',
        'RESCHEDULE_APPOINTMENT',
        'CANCEL_APPOINTMENT',
    ]
    
    CONSENT_INTENTS = [
        'OPT_IN_PROMOTIONS',
        'OPT_OUT_PROMOTIONS',
        'STOP_ALL',
        'START_ALL',
    ]
    
    SUPPORT_INTENTS = [
        'HUMAN_HANDOFF',
        'OTHER',
    ]
    
    ALL_INTENTS = PRODUCT_INTENTS + SERVICE_INTENTS + CONSENT_INTENTS + SUPPORT_INTENTS
    
    # JSON Schema for validating LLM intent responses
    # This schema ensures responses are well-formed and safe to process
    INTENT_RESPONSE_SCHEMA = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": ["intent", "confidence"],
        "properties": {
            "intent": {
                "type": "string",
                "description": "The classified intent name",
                # Note: enum validation is done separately with ALL_INTENTS
                # to allow for dynamic intent lists
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Confidence score between 0.0 and 1.0"
            },
            "slots": {
                "type": "object",
                "description": "Extracted entities/slots from the message",
                "maxProperties": 20,  # Prevent excessive slot extraction
                "patternProperties": {
                    # Slot keys must be alphanumeric with underscores only
                    "^[a-zA-Z0-9_]+$": {
                        "oneOf": [
                            {"type": "string", "maxLength": 500},
                            {"type": "number"},
                            {"type": "boolean"},
                            {"type": "null"}
                        ]
                    }
                },
                "additionalProperties": False
            },
            "reasoning": {
                "type": "string",
                "maxLength": 1000,
                "description": "Brief explanation of the classification"
            }
        },
        "additionalProperties": False  # Reject unknown fields
    }
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize intent service.
        
        Args:
            api_key: OpenAI API key (uses settings.OPENAI_API_KEY if not provided)
            model: Model to use for classification (uses settings.OPENAI_MODEL or defaults to gpt-4o-mini)
        """
        if not OPENAI_AVAILABLE:
            raise IntentServiceError("OpenAI library not installed")
        
        self.api_key = api_key or getattr(settings, 'OPENAI_API_KEY', None)
        if not self.api_key:
            raise IntentServiceError("OpenAI API key not configured")
        
        # Use provided model, or from settings, or default to gpt-4o-mini
        self.model = model or getattr(settings, 'OPENAI_MODEL', 'gpt-4o-mini')
        self.client = openai.OpenAI(api_key=self.api_key)
        
        # Check if model supports JSON mode
        self.supports_json_mode = self._check_json_mode_support()
        
        logger.info(
            f"IntentService initialized with model: {self.model} (JSON mode: {self.supports_json_mode})"
        )
    
    def classify_intent(
        self,
        message_text: str,
        conversation_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Classify customer message intent using LLM.
        
        Args:
            message_text: Customer message text
            conversation_context: Optional context (previous intents, customer info)
            
        Returns:
            dict: Classification result with intent_name, confidence_score, slots
            
        Example:
            >>> service = IntentService()
            >>> result = service.classify_intent("I want to book a haircut for tomorrow")
            >>> print(result['intent_name'])  # 'BOOK_APPOINTMENT'
            >>> print(result['slots'])  # {'service_query': 'haircut', 'date': 'tomorrow'}
        """
        start_time = time.time()
        
        try:
            # Build system prompt
            system_prompt = self._build_system_prompt()
            
            # Build user prompt with context
            user_prompt = self._build_user_prompt(message_text, conversation_context)
            
            # Call OpenAI API with appropriate parameters
            api_params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.3,  # Lower temperature for more consistent classification
                "max_tokens": 500,
            }
            
            # Only add response_format if model supports it
            if self.supports_json_mode:
                api_params["response_format"] = {"type": "json_object"}
            
            response = self.client.chat.completions.create(**api_params)
            
            # Parse response
            result_text = response.choices[0].message.content
            
            # Try to parse as JSON
            try:
                result = json.loads(result_text)
            except json.JSONDecodeError as e:
                # Log the JSON parsing failure
                logger.warning(
                    f"LLM response is not valid JSON, attempting to extract from text",
                    extra={
                        'message_text': message_text[:100],
                        'response_text': result_text[:200],
                        'json_error': str(e)
                    }
                )
                # If not JSON, try to extract JSON from markdown code blocks
                try:
                    result = self._extract_json_from_text(result_text)
                    logger.info(
                        "Successfully extracted JSON from markdown code block",
                        extra={'message_text': message_text[:100]}
                    )
                except json.JSONDecodeError as extract_error:
                    logger.error(
                        f"Failed to extract valid JSON from LLM response",
                        extra={
                            'message_text': message_text[:100],
                            'response_text': result_text[:500],
                            'extraction_error': str(extract_error)
                        }
                    )
                    raise IntentServiceError(
                        f"Invalid JSON response from LLM: {str(extract_error)}"
                    )
            
            # Calculate processing time
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Validate response against schema
            if JSONSCHEMA_AVAILABLE:
                try:
                    self._validate_intent_response(result)
                    logger.debug(
                        "LLM response passed schema validation",
                        extra={
                            'message_text': message_text[:100],
                            'intent': result.get('intent'),
                            'confidence': result.get('confidence')
                        }
                    )
                except ValidationError as e:
                    logger.error(
                        f"LLM response failed schema validation: {e.message}",
                        extra={
                            'message_text': message_text[:100],
                            'validation_error': str(e),
                            'validation_path': list(e.path) if hasattr(e, 'path') else [],
                            'response': result,
                            'schema_path': list(e.schema_path) if hasattr(e, 'schema_path') else []
                        }
                    )
                    raise IntentServiceError(f"Invalid LLM response structure: {e.message}")
            else:
                logger.warning(
                    "jsonschema not available, skipping response validation",
                    extra={'message_text': message_text[:100]}
                )
            
            # Extract and validate result
            intent_name = result.get('intent', 'OTHER')
            confidence_score = float(result.get('confidence', 0.0))
            slots = result.get('slots', {})
            reasoning = result.get('reasoning', '')
            
            # Validate intent name against whitelist
            if intent_name not in self.ALL_INTENTS:
                logger.warning(
                    f"Unknown intent '{intent_name}' returned by LLM, defaulting to OTHER",
                    extra={
                        'message_text': message_text[:100],
                        'invalid_intent': intent_name,
                        'original_confidence': confidence_score,
                        'allowed_intents': self.ALL_INTENTS
                    }
                )
                intent_name = 'OTHER'
                confidence_score = 0.5
            
            # Sanitize slots
            original_slot_count = len(slots)
            slots = self._sanitize_slots(slots)
            sanitized_slot_count = len(slots)
            
            if original_slot_count != sanitized_slot_count:
                logger.info(
                    f"Slot sanitization removed {original_slot_count - sanitized_slot_count} invalid slots",
                    extra={
                        'message_text': message_text[:100],
                        'original_count': original_slot_count,
                        'sanitized_count': sanitized_slot_count
                    }
                )
            
            logger.info(
                f"Intent classified: {intent_name} (confidence: {confidence_score:.2f})",
                extra={
                    'intent': intent_name,
                    'confidence': confidence_score,
                    'processing_time_ms': processing_time_ms,
                    'message_text': message_text[:100]
                }
            )
            
            return {
                'intent_name': intent_name,
                'confidence_score': confidence_score,
                'slots': slots,
                'reasoning': reasoning,
                'model': self.model,
                'processing_time_ms': processing_time_ms,
                'metadata': {
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                    'total_tokens': response.usage.total_tokens
                }
            }
            
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse LLM response as JSON",
                extra={'message_text': message_text},
                exc_info=True
            )
            raise IntentServiceError(f"Invalid JSON response from LLM: {str(e)}")
        
        except Exception as e:
            logger.error(
                f"Error classifying intent",
                extra={'message_text': message_text},
                exc_info=True
            )
            raise IntentServiceError(f"Intent classification failed: {str(e)}")
    
    def extract_slots(self, message_text: str, intent: str) -> Dict[str, Any]:
        """
        Extract entities/slots from message for a specific intent.
        
        This is called automatically by classify_intent, but can be used
        standalone for re-extraction or refinement.
        
        Args:
            message_text: Customer message text
            intent: Intent name to extract slots for
            
        Returns:
            dict: Extracted slots/entities
        """
        # This is handled within classify_intent for efficiency
        # But we provide this method for explicit slot extraction if needed
        result = self.classify_intent(message_text)
        return result['slots']
    
    def handle_low_confidence(
        self,
        conversation,
        message_text: str,
        confidence_score: float,
        attempt_count: int
    ) -> Dict[str, Any]:
        """
        Handle low-confidence intent classification.
        
        After MAX_LOW_CONFIDENCE_ATTEMPTS consecutive low-confidence
        classifications, automatically trigger human handoff.
        
        Args:
            conversation: Conversation model instance
            message_text: Customer message text
            confidence_score: Confidence score from classification
            attempt_count: Number of consecutive low-confidence attempts
            
        Returns:
            dict: Action to take (clarify or handoff)
        """
        if attempt_count >= self.MAX_LOW_CONFIDENCE_ATTEMPTS:
            logger.info(
                f"Auto-handoff triggered after {attempt_count} low-confidence attempts",
                extra={
                    'conversation_id': str(conversation.id),
                    'tenant_id': str(conversation.tenant_id)
                }
            )
            
            # Mark conversation for handoff
            conversation.mark_handoff()
            
            return {
                'action': 'handoff',
                'message': "I'm having trouble understanding. Let me connect you with a team member who can help.",
                'reason': 'consecutive_low_confidence',
                'attempt_count': attempt_count
            }
        
        else:
            logger.info(
                f"Low confidence ({confidence_score:.2f}), asking for clarification",
                extra={
                    'conversation_id': str(conversation.id),
                    'attempt_count': attempt_count
                }
            )
            
            return {
                'action': 'clarify',
                'message': "I'm not quite sure what you're looking for. Could you please rephrase or provide more details?",
                'attempt_count': attempt_count
            }
    
    def _validate_intent_response(self, response: Dict[str, Any]) -> None:
        """
        Validate LLM response against JSON schema.
        
        Args:
            response: Parsed JSON response from LLM
            
        Raises:
            ValidationError: If response doesn't match schema
        """
        if not JSONSCHEMA_AVAILABLE:
            return
        
        # Validate against base schema
        try:
            validate(instance=response, schema=self.INTENT_RESPONSE_SCHEMA)
        except ValidationError as e:
            logger.error(
                f"Schema validation failed: {e.message}",
                extra={
                    'validation_error': str(e),
                    'failed_field': list(e.path) if hasattr(e, 'path') else None,
                    'response_keys': list(response.keys()) if isinstance(response, dict) else None
                }
            )
            raise
        
        # Additional validation: intent must be in whitelist
        intent = response.get('intent')
        if intent and intent not in self.ALL_INTENTS:
            logger.error(
                f"Intent validation failed: '{intent}' not in allowed intents",
                extra={
                    'invalid_intent': intent,
                    'allowed_intents_count': len(self.ALL_INTENTS)
                }
            )
            raise ValidationError(
                f"Intent '{intent}' not in allowed intents list"
            )
        
        # Additional validation: confidence must be in range
        confidence = response.get('confidence')
        if confidence is not None and not (0.0 <= confidence <= 1.0):
            logger.error(
                f"Confidence validation failed: {confidence} out of range",
                extra={
                    'invalid_confidence': confidence,
                    'valid_range': '0.0-1.0'
                }
            )
            raise ValidationError(
                f"Confidence {confidence} must be between 0.0 and 1.0"
            )
        
        # Additional validation: slot keys must be alphanumeric + underscore
        slots = response.get('slots', {})
        if slots:
            import re
            slot_key_pattern = re.compile(r'^[a-zA-Z0-9_]+$')
            invalid_keys = []
            for key in slots.keys():
                if not slot_key_pattern.match(key):
                    invalid_keys.append(key)
            
            if invalid_keys:
                logger.error(
                    f"Slot key validation failed: invalid characters in keys",
                    extra={
                        'invalid_keys': invalid_keys,
                        'valid_pattern': '^[a-zA-Z0-9_]+$'
                    }
                )
                raise ValidationError(
                    f"Slot keys {invalid_keys} contain invalid characters. "
                    f"Only alphanumeric and underscore allowed."
                )
    
    def _escape_slot_value(self, value: str) -> str:
        """
        Escape slot value to prevent SQL injection and XSS attacks.
        
        This method provides defense-in-depth by escaping dangerous characters
        even though Django ORM and templates provide their own protection.
        
        Escaping rules:
        - SQL: Escape single quotes, backslashes, and SQL keywords
        - XSS: Escape HTML special characters (<, >, &, ", ')
        - Control characters: Remove or escape control characters
        
        Args:
            value: Raw string value from LLM
            
        Returns:
            str: Escaped string safe for database and display
        """
        import html
        import re
        
        original_value = value
        escape_operations = []
        
        # First, escape HTML entities to prevent XSS
        # This converts: < > & " ' to &lt; &gt; &amp; &quot; &#x27;
        value = html.escape(value, quote=True)
        if value != original_value:
            escape_operations.append('html_escape')
        
        # Remove or escape control characters (except common whitespace)
        # Control characters can cause issues in logs and databases
        # Keep: tab (\t), newline (\n), carriage return (\r)
        # Remove: all other control characters (0x00-0x1F, 0x7F-0x9F)
        control_chars_removed = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F]', '', value)
        if control_chars_removed != value:
            escape_operations.append('control_chars_removed')
            value = control_chars_removed
        
        # Additional SQL injection prevention (defense-in-depth)
        # Django ORM handles this, but we add extra protection
        # Escape backslashes and single quotes that could break SQL strings
        if '\\' in value:
            value = value.replace('\\', '\\\\')  # Escape backslashes first
            escape_operations.append('backslash_escape')
        
        if "'" in value:
            value = value.replace("'", "''")     # SQL standard: double single quotes
            escape_operations.append('quote_escape')
        
        # Remove SQL comment markers to prevent comment-based injection
        if '--' in value or '/*' in value or '*/' in value:
            value = value.replace('--', '')
            value = value.replace('/*', '')
            value = value.replace('*/', '')
            escape_operations.append('sql_comment_removed')
        
        # Remove semicolons that could terminate statements
        # (though Django ORM doesn't allow multiple statements)
        if ';' in value:
            value = value.replace(';', '')
            escape_operations.append('semicolon_removed')
        
        # Log if any escaping was performed
        if escape_operations:
            logger.debug(
                f"Applied escaping to slot value",
                extra={
                    'escape_operations': escape_operations,
                    'original_length': len(original_value),
                    'escaped_length': len(value),
                    'original_preview': original_value[:50],
                    'escaped_preview': value[:50]
                }
            )
        
        return value
    
    def _sanitize_slots(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize slot values to prevent injection attacks.
        
        Performs comprehensive sanitization including:
        - Length limits (500 chars for strings)
        - Type validation and coercion
        - Numeric bounds checking
        - Removal of dangerous characters
        - Prevention of NaN/Infinity values
        - SQL/XSS escaping for string values
        
        Args:
            slots: Raw slots from LLM response
            
        Returns:
            dict: Sanitized slots with validated types and values
        """
        if not slots:
            return {}
        
        import re
        import math
        
        sanitized = {}
        sanitization_stats = {
            'total_slots': len(slots),
            'removed_slots': 0,
            'truncated_strings': 0,
            'clamped_numbers': 0,
            'invalid_numbers': 0,
            'type_conversions': 0,
            'invalid_keys': 0
        }
        
        # Maximum values for numeric types to prevent overflow
        MAX_INT = 2**31 - 1  # Max 32-bit signed integer
        MIN_INT = -(2**31)
        MAX_FLOAT = 1e308  # Close to sys.float_info.max
        MIN_FLOAT = -1e308
        
        for key, value in slots.items():
            # Skip if key is invalid (should be caught by validation)
            if not re.match(r'^[a-zA-Z0-9_]+$', key):
                logger.warning(
                    f"Skipping slot with invalid key: {key}",
                    extra={'slot_key': key, 'value_type': type(value).__name__}
                )
                sanitization_stats['invalid_keys'] += 1
                sanitization_stats['removed_slots'] += 1
                continue
            
            # Sanitize value based on type
            if isinstance(value, str):
                original_length = len(value)
                
                # Enforce length limit
                if original_length > 500:
                    logger.warning(
                        f"Truncating slot value for key '{key}' (length: {original_length})",
                        extra={
                            'slot_key': key,
                            'original_length': original_length,
                            'truncated_to': 500
                        }
                    )
                    value = value[:500]
                    sanitization_stats['truncated_strings'] += 1
                
                # Remove null bytes (can cause issues in databases)
                if '\x00' in value:
                    logger.debug(
                        f"Removing null bytes from slot '{key}'",
                        extra={'slot_key': key}
                    )
                    value = value.replace('\x00', '')
                
                # Strip leading/trailing whitespace
                value = value.strip()
                
                # Skip empty strings after sanitization
                if not value:
                    logger.debug(
                        f"Skipping empty string value for key '{key}' after sanitization",
                        extra={'slot_key': key, 'original_length': original_length}
                    )
                    sanitization_stats['removed_slots'] += 1
                    continue
                
                # Apply SQL/XSS escaping
                value = self._escape_slot_value(value)
                
                sanitized[key] = value
            
            elif isinstance(value, bool):
                # Handle booleans before numbers (bool is subclass of int in Python)
                sanitized[key] = value
            
            elif isinstance(value, int):
                # Validate integer bounds to prevent overflow
                if value > MAX_INT or value < MIN_INT:
                    original_value = value
                    value = max(MIN_INT, min(MAX_INT, value))
                    logger.warning(
                        f"Integer value out of bounds for key '{key}', clamped to valid range",
                        extra={
                            'slot_key': key,
                            'original_value': original_value,
                            'clamped_value': value,
                            'valid_range': f'{MIN_INT} to {MAX_INT}'
                        }
                    )
                    sanitization_stats['clamped_numbers'] += 1
                
                sanitized[key] = value
            
            elif isinstance(value, float):
                # Prevent NaN and Infinity
                if math.isnan(value) or math.isinf(value):
                    logger.warning(
                        f"Skipping invalid numeric value for key '{key}': {value}",
                        extra={
                            'slot_key': key,
                            'value': str(value),
                            'is_nan': math.isnan(value),
                            'is_inf': math.isinf(value)
                        }
                    )
                    sanitization_stats['invalid_numbers'] += 1
                    sanitization_stats['removed_slots'] += 1
                    continue
                
                # Validate float bounds
                if value > MAX_FLOAT or value < MIN_FLOAT:
                    original_value = value
                    value = max(MIN_FLOAT, min(MAX_FLOAT, value))
                    logger.warning(
                        f"Float value out of bounds for key '{key}', clamped to valid range",
                        extra={
                            'slot_key': key,
                            'original_value': original_value,
                            'clamped_value': value,
                            'valid_range': f'{MIN_FLOAT} to {MAX_FLOAT}'
                        }
                    )
                    sanitization_stats['clamped_numbers'] += 1
                
                sanitized[key] = value
            
            elif value is None:
                sanitized[key] = None
            
            else:
                # Unknown type, convert to string and sanitize
                logger.warning(
                    f"Converting unknown type to string for key '{key}': {type(value)}",
                    extra={
                        'slot_key': key,
                        'value_type': str(type(value)),
                        'value_repr': repr(value)[:100]
                    }
                )
                sanitization_stats['type_conversions'] += 1
                str_value = str(value)[:500]
                # Apply string sanitization
                str_value = str_value.replace('\x00', '').strip()
                if str_value:  # Only add if not empty after sanitization
                    sanitized[key] = str_value
                else:
                    sanitization_stats['removed_slots'] += 1
        
        # Log sanitization summary if any changes were made
        if sanitization_stats['removed_slots'] > 0 or \
           sanitization_stats['truncated_strings'] > 0 or \
           sanitization_stats['clamped_numbers'] > 0 or \
           sanitization_stats['invalid_numbers'] > 0 or \
           sanitization_stats['type_conversions'] > 0 or \
           sanitization_stats['invalid_keys'] > 0:
            logger.info(
                f"Slot sanitization completed with modifications",
                extra={
                    'sanitization_stats': sanitization_stats,
                    'original_count': sanitization_stats['total_slots'],
                    'final_count': len(sanitized)
                }
            )
        
        return sanitized
    
    def _check_json_mode_support(self) -> bool:
        """
        Check if the model supports JSON mode.
        
        Models that support JSON mode:
        - gpt-4o, gpt-4o-mini, gpt-4-turbo
        - gpt-3.5-turbo-1106 and later
        
        Returns:
            bool: True if model supports JSON mode
        """
        json_mode_models = [
            'gpt-4o',
            'gpt-4o-mini',
            'gpt-4-turbo',
            'gpt-4-1106-preview',
            'gpt-4-0125-preview',
            'gpt-3.5-turbo-1106',
            'gpt-3.5-turbo-0125',
        ]
        
        # Check if model name starts with any supported model
        for supported_model in json_mode_models:
            if self.model.startswith(supported_model):
                return True
        
        return False
    
    def _extract_json_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extract JSON from text that might contain markdown code blocks.
        
        Args:
            text: Text that might contain JSON
            
        Returns:
            dict: Parsed JSON object
            
        Raises:
            json.JSONDecodeError: If no valid JSON found
        """
        # Try to find JSON in markdown code blocks
        import re
        
        # Look for ```json ... ``` or ``` ... ```
        code_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        match = re.search(code_block_pattern, text, re.DOTALL)
        
        if match:
            logger.debug(
                "Found JSON in markdown code block",
                extra={'extraction_method': 'code_block'}
            )
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError as e:
                logger.warning(
                    f"JSON in code block is malformed: {e}",
                    extra={
                        'extraction_method': 'code_block',
                        'json_content': match.group(1)[:200]
                    }
                )
                # Continue to try other methods
        
        # Look for JSON object directly
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        match = re.search(json_pattern, text, re.DOTALL)
        
        if match:
            logger.debug(
                "Found JSON object in text",
                extra={'extraction_method': 'direct_pattern'}
            )
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Extracted JSON is malformed: {e}",
                    extra={
                        'extraction_method': 'direct_pattern',
                        'json_content': match.group(0)[:200]
                    }
                )
        
        # If nothing found, raise error
        logger.error(
            "Failed to extract valid JSON from text",
            extra={
                'text_preview': text[:200],
                'text_length': len(text)
            }
        )
        raise json.JSONDecodeError(f"No valid JSON found in text: {text[:200]}", text, 0)
    
    def _build_system_prompt(self) -> str:
        """Build system prompt with intent definitions."""
        return f"""You are an AI assistant for a WhatsApp commerce and services platform.
Your task is to classify customer messages into specific intents and extract relevant information.

SUPPORTED INTENTS:

Product Intents:
- GREETING: Customer greets or starts conversation
- BROWSE_PRODUCTS: Customer wants to see available products
- PRODUCT_DETAILS: Customer asks about a specific product
- PRICE_CHECK: Customer asks about product pricing
- STOCK_CHECK: Customer asks about product availability
- ADD_TO_CART: Customer wants to add product to cart
- CHECKOUT_LINK: Customer wants to complete purchase

Service Intents:
- BROWSE_SERVICES: Customer wants to see available services
- SERVICE_DETAILS: Customer asks about a specific service
- CHECK_AVAILABILITY: Customer wants to see available appointment slots
- BOOK_APPOINTMENT: Customer wants to book an appointment
- RESCHEDULE_APPOINTMENT: Customer wants to change appointment time
- CANCEL_APPOINTMENT: Customer wants to cancel appointment

Consent Intents:
- OPT_IN_PROMOTIONS: Customer wants to receive promotional messages
- OPT_OUT_PROMOTIONS: Customer wants to stop promotional messages
- STOP_ALL: Customer wants to stop all non-essential messages (keywords: STOP, UNSUBSCRIBE)
- START_ALL: Customer wants to resume all messages (keyword: START)

Support Intents:
- HUMAN_HANDOFF: Customer explicitly requests human assistance
- OTHER: Message doesn't match any specific intent

SLOT EXTRACTION:
Extract relevant entities based on the intent:
- product_query, product_id: For product-related intents
- service_query, service_id, variant_id: For service-related intents
- date, time, time_range: For availability and booking intents
- quantity: For cart operations
- notes: Additional customer notes

RESPONSE FORMAT:
Return a JSON object with:
{{
  "intent": "INTENT_NAME",
  "confidence": 0.0-1.0,
  "slots": {{"key": "value"}},
  "reasoning": "Brief explanation of classification"
}}

GUIDELINES:
- Be confident in clear requests (confidence > 0.8)
- Use moderate confidence for ambiguous messages (0.5-0.8)
- Use low confidence when unclear (< 0.5)
- Extract all relevant slots from the message
- Consider context when provided
"""
    
    def _build_user_prompt(
        self,
        message_text: str,
        conversation_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build user prompt with message and context."""
        prompt = f"Classify this customer message:\n\n\"{message_text}\""
        
        if conversation_context:
            context_parts = []
            
            if conversation_context.get('last_intent'):
                context_parts.append(f"Previous intent: {conversation_context['last_intent']}")
            
            if conversation_context.get('customer_name'):
                context_parts.append(f"Customer name: {conversation_context['customer_name']}")
            
            if conversation_context.get('recent_products'):
                context_parts.append(f"Recently viewed products: {', '.join(conversation_context['recent_products'])}")
            
            if conversation_context.get('recent_services'):
                context_parts.append(f"Recently viewed services: {', '.join(conversation_context['recent_services'])}")
            
            if context_parts:
                prompt += f"\n\nContext:\n" + "\n".join(context_parts)
        
        return prompt
    
    def create_intent_event(
        self,
        conversation,
        message_text: str,
        classification_result: Dict[str, Any]
    ):
        """
        Create IntentEvent record for tracking and analytics.
        
        Args:
            conversation: Conversation model instance
            message_text: Original message text
            classification_result: Result from classify_intent()
            
        Returns:
            IntentEvent: Created intent event instance
        """
        from apps.bot.models import IntentEvent
        
        intent_event = IntentEvent.objects.create(
            conversation=conversation,
            intent_name=classification_result['intent_name'],
            confidence_score=classification_result['confidence_score'],
            slots=classification_result['slots'],
            model=classification_result['model'],
            message_text=message_text,
            processing_time_ms=classification_result.get('processing_time_ms'),
            metadata=classification_result.get('metadata', {})
        )
        
        # Update conversation with last intent
        conversation.last_intent = classification_result['intent_name']
        conversation.intent_confidence = classification_result['confidence_score']
        
        # Handle low confidence
        if classification_result['confidence_score'] < self.CONFIDENCE_THRESHOLD:
            conversation.increment_low_confidence()
        else:
            conversation.reset_low_confidence()
        
        conversation.save(update_fields=['last_intent', 'intent_confidence'])
        
        return intent_event
    
    def is_high_confidence(self, confidence_score: float) -> bool:
        """Check if confidence score meets threshold."""
        return confidence_score >= self.CONFIDENCE_THRESHOLD
    
    def is_low_confidence(self, confidence_score: float) -> bool:
        """Check if confidence score is below threshold."""
        return confidence_score < self.CONFIDENCE_THRESHOLD


def create_intent_service(model: Optional[str] = None) -> IntentService:
    """
    Factory function to create IntentService instance.
    
    Args:
        model: OpenAI model to use (uses settings.OPENAI_MODEL or defaults to gpt-4o-mini)
        
    Returns:
        IntentService: Configured service instance
        
    Example:
        >>> service = create_intent_service()
        >>> result = service.classify_intent("Show me your products")
    """
    return IntentService(model=model)
