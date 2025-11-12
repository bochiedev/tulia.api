"""
Tests for structured logging and PII masking.
"""
import json
import logging
from django.test import TestCase
from apps.core.logging import PIIMasker, JSONFormatter


class PIIMaskerTestCase(TestCase):
    """Test PII masking functionality."""
    
    def test_mask_phone_numbers(self):
        """Test phone number masking."""
        text = "Call me at +1234567890 or +447700900123"
        masked = PIIMasker.mask_phone(text)
        
        self.assertIn("+12*", masked)
        self.assertNotIn("+1234567890", masked)
        self.assertIn("+44*", masked)
        self.assertNotIn("+447700900123", masked)
    
    def test_mask_email_addresses(self):
        """Test email address masking."""
        text = "Contact user@example.com or admin@test.org"
        masked = PIIMasker.mask_email(text)
        
        self.assertIn("u***@example.com", masked)
        self.assertNotIn("user@example.com", masked)
        self.assertIn("a****@test.org", masked)
        self.assertNotIn("admin@test.org", masked)
    
    def test_mask_api_keys(self):
        """Test API key masking."""
        text = 'api_key: "sk_live_abc123" and token="bearer_xyz789"'
        masked = PIIMasker.mask_api_keys(text)
        
        self.assertIn("api_key: ********", masked)
        self.assertNotIn("sk_live_abc123", masked)
        self.assertIn("token: ********", masked)
        self.assertNotIn("bearer_xyz789", masked)
    
    def test_mask_credit_cards(self):
        """Test credit card masking."""
        text = "Card: 4111 1111 1111 1111 or 5500-0000-0000-0004"
        masked = PIIMasker.mask_credit_cards(text)
        
        self.assertIn("1111", masked)  # Last 4 digits visible
        self.assertNotIn("4111 1111 1111 1111", masked)
        self.assertIn("0004", masked)  # Last 4 digits visible
        self.assertNotIn("5500-0000-0000-0004", masked)
    
    def test_mask_dict_sensitive_fields(self):
        """Test masking sensitive fields in dictionaries."""
        data = {
            'name': 'John Doe',
            'phone_e164': '+1234567890',
            'email': 'john@example.com',
            'api_key': 'sk_live_abc123',
            'order_total': 99.99,
        }
        
        masked = PIIMasker.mask_dict(data)
        
        self.assertEqual(masked['name'], 'John Doe')  # Not sensitive
        self.assertEqual(masked['phone_e164'], '********')  # Masked
        self.assertEqual(masked['email'], '********')  # Masked
        self.assertEqual(masked['api_key'], '********')  # Masked
        self.assertEqual(masked['order_total'], 99.99)  # Not sensitive
    
    def test_mask_nested_dict(self):
        """Test masking nested dictionaries."""
        data = {
            'user': {
                'name': 'John Doe',
                'email': 'john@example.com',
                'phone': '+1234567890',
            },
            'order': {
                'total': 99.99,
                'items': ['item1', 'item2'],
            }
        }
        
        masked = PIIMasker.mask_dict(data)
        
        self.assertEqual(masked['user']['name'], 'John Doe')
        self.assertEqual(masked['user']['email'], '********')
        self.assertEqual(masked['user']['phone'], '********')
        self.assertEqual(masked['order']['total'], 99.99)


class JSONFormatterTestCase(TestCase):
    """Test JSON log formatting."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.formatter = JSONFormatter()
        self.logger = logging.getLogger('test_logger')
    
    def test_basic_log_format(self):
        """Test basic log record formatting."""
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=10,
            msg='Test message',
            args=(),
            exc_info=None
        )
        
        formatted = self.formatter.format(record)
        log_data = json.loads(formatted)
        
        self.assertEqual(log_data['level'], 'INFO')
        self.assertEqual(log_data['logger'], 'test_logger')
        self.assertEqual(log_data['message'], 'Test message')
        self.assertEqual(log_data['line'], 10)
        self.assertIn('timestamp', log_data)
    
    def test_log_with_request_id(self):
        """Test log record with request_id."""
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=10,
            msg='Test message',
            args=(),
            exc_info=None
        )
        record.request_id = 'test-request-id-123'
        
        formatted = self.formatter.format(record)
        log_data = json.loads(formatted)
        
        self.assertEqual(log_data['request_id'], 'test-request-id-123')
    
    def test_log_with_tenant_id(self):
        """Test log record with tenant_id."""
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=10,
            msg='Test message',
            args=(),
            exc_info=None
        )
        record.tenant_id = 'tenant-uuid-123'
        
        formatted = self.formatter.format(record)
        log_data = json.loads(formatted)
        
        self.assertEqual(log_data['tenant_id'], 'tenant-uuid-123')
    
    def test_log_with_task_info(self):
        """Test log record with Celery task info."""
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=10,
            msg='Test message',
            args=(),
            exc_info=None
        )
        record.task_id = 'task-id-123'
        record.task_name = 'apps.tasks.my_task'
        
        formatted = self.formatter.format(record)
        log_data = json.loads(formatted)
        
        self.assertEqual(log_data['task_id'], 'task-id-123')
        self.assertEqual(log_data['task_name'], 'apps.tasks.my_task')
    
    def test_log_masks_pii_in_message(self):
        """Test that PII is masked in log messages."""
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=10,
            msg='User phone: +1234567890 email: user@example.com',
            args=(),
            exc_info=None
        )
        
        formatted = self.formatter.format(record)
        log_data = json.loads(formatted)
        
        # Phone should be masked
        self.assertNotIn('+1234567890', log_data['message'])
        self.assertIn('+12*', log_data['message'])
        
        # Email should be masked
        self.assertNotIn('user@example.com', log_data['message'])
        self.assertIn('u***@example.com', log_data['message'])
    
    def test_log_masks_pii_in_extra_fields(self):
        """Test that PII is masked in extra fields."""
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=10,
            msg='Test message',
            args=(),
            exc_info=None
        )
        record.customer_data = {
            'name': 'John Doe',
            'phone_e164': '+1234567890',
            'email': 'john@example.com',
        }
        
        formatted = self.formatter.format(record)
        log_data = json.loads(formatted)
        
        # Sensitive fields should be masked
        self.assertEqual(log_data['customer_data']['phone_e164'], '********')
        self.assertEqual(log_data['customer_data']['email'], '********')
        # Non-sensitive fields should not be masked
        self.assertEqual(log_data['customer_data']['name'], 'John Doe')
