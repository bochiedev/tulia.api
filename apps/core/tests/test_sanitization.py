"""
Tests for input sanitization utilities.
"""
from django.test import TestCase
from apps.core.sanitization import (
    sanitize_html,
    sanitize_sql,
    sanitize_text_input,
    sanitize_dict,
    validate_and_sanitize_json_field,
    contains_injection_attempt,
    sanitize_filename,
)


class SanitizeHTMLTests(TestCase):
    """Tests for HTML sanitization."""
    
    def test_escapes_script_tags(self):
        """Test that script tags are escaped."""
        result = sanitize_html('<script>alert("xss")</script>')
        self.assertIn('&lt;script&gt;', result)
        self.assertNotIn('<script>', result)
    
    def test_escapes_event_handlers(self):
        """Test that event handlers are escaped."""
        result = sanitize_html('<img src=x onerror="alert(1)">')
        # The entire tag should be escaped
        self.assertIn('&lt;img', result)
        self.assertIn('&gt;', result)
        # Should not contain unescaped HTML tags
        self.assertNotIn('<img', result)
    
    def test_allows_safe_tags_when_specified(self):
        """Test that specified tags are allowed."""
        result = sanitize_html('<b>Bold</b> text', allowed_tags=['b'])
        self.assertEqual(result, '<b>Bold</b> text')
    
    def test_escapes_dangerous_tags_even_with_allowed_list(self):
        """Test that dangerous tags are still escaped."""
        result = sanitize_html('<b>Bold</b><script>xss</script>', allowed_tags=['b'])
        self.assertIn('<b>Bold</b>', result)
        self.assertNotIn('<script>', result)
    
    def test_handles_empty_string(self):
        """Test handling of empty string."""
        result = sanitize_html('')
        self.assertEqual(result, '')
    
    def test_handles_none(self):
        """Test handling of None."""
        result = sanitize_html(None)
        self.assertIsNone(result)


class SanitizeSQLTests(TestCase):
    """Tests for SQL injection prevention."""
    
    def test_removes_drop_table(self):
        """Test that DROP TABLE is removed."""
        result = sanitize_sql("'; DROP TABLE users; --")
        self.assertNotIn('DROP TABLE', result.upper())
    
    def test_removes_union_select(self):
        """Test that UNION SELECT is removed."""
        result = sanitize_sql("' UNION SELECT * FROM users --")
        self.assertNotIn('UNION SELECT', result.upper())
    
    def test_removes_sql_comments(self):
        """Test that SQL comments are removed."""
        result = sanitize_sql("test -- comment")
        self.assertNotIn('--', result)
    
    def test_escapes_single_quotes(self):
        """Test that single quotes are escaped."""
        result = sanitize_sql("O'Brien")
        self.assertEqual(result, "O''Brien")
    
    def test_removes_or_1_equals_1(self):
        """Test that OR 1=1 is removed."""
        result = sanitize_sql("' OR 1=1 --")
        self.assertNotIn('OR 1=1', result.upper())


class SanitizeTextInputTests(TestCase):
    """Tests for general text input sanitization."""
    
    def test_strips_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        result = sanitize_text_input('  hello  ')
        self.assertEqual(result, 'hello')
    
    def test_escapes_html_by_default(self):
        """Test that HTML is escaped by default."""
        result = sanitize_text_input('<script>xss</script>')
        self.assertNotIn('<script>', result)
    
    def test_enforces_max_length(self):
        """Test that max length is enforced."""
        result = sanitize_text_input('a' * 100, max_length=50)
        self.assertEqual(len(result), 50)
    
    def test_can_disable_html_escaping(self):
        """Test that HTML escaping can be disabled."""
        result = sanitize_text_input('<b>bold</b>', strip_html=False)
        self.assertEqual(result, '<b>bold</b>')
    
    def test_can_enable_sql_sanitization(self):
        """Test that SQL sanitization can be enabled."""
        result = sanitize_text_input("'; DROP TABLE", strip_sql=True)
        self.assertNotIn('DROP TABLE', result.upper())


class SanitizeDictTests(TestCase):
    """Tests for dictionary sanitization."""
    
    def test_sanitizes_string_fields(self):
        """Test that string fields are sanitized."""
        data = {'name': '<script>xss</script>', 'age': 25}
        result = sanitize_dict(data)
        self.assertNotIn('<script>', result['name'])
        self.assertEqual(result['age'], 25)
    
    def test_sanitizes_nested_dicts(self):
        """Test that nested dictionaries are sanitized."""
        data = {
            'user': {
                'name': '<script>xss</script>',
                'email': 'test@example.com'
            }
        }
        result = sanitize_dict(data)
        self.assertNotIn('<script>', result['user']['name'])
    
    def test_sanitizes_list_items(self):
        """Test that list items are sanitized."""
        data = {'tags': ['<script>xss</script>', 'normal']}
        result = sanitize_dict(data)
        self.assertNotIn('<script>', result['tags'][0])
        self.assertEqual(result['tags'][1], 'normal')
    
    def test_only_sanitizes_specified_fields(self):
        """Test that only specified fields are sanitized."""
        data = {'name': '<b>bold</b>', 'bio': '<b>bold</b>'}
        result = sanitize_dict(data, fields_to_sanitize=['name'])
        self.assertNotIn('<b>', result['name'])
        self.assertIn('<b>', result['bio'])


class ValidateAndSanitizeJSONTests(TestCase):
    """Tests for JSON field validation and sanitization."""
    
    def test_rejects_deeply_nested_objects(self):
        """Test that deeply nested objects are rejected."""
        data = {'a': {'b': {'c': {'d': {'e': {'f': 'too deep'}}}}}}
        with self.assertRaises(ValueError) as cm:
            validate_and_sanitize_json_field(data, max_depth=3)
        self.assertIn('depth', str(cm.exception).lower())
    
    def test_rejects_too_many_keys(self):
        """Test that objects with too many keys are rejected."""
        data = {f'key{i}': i for i in range(150)}
        with self.assertRaises(ValueError) as cm:
            validate_and_sanitize_json_field(data, max_keys=100)
        self.assertIn('keys', str(cm.exception).lower())
    
    def test_rejects_long_strings(self):
        """Test that excessively long strings are rejected."""
        data = {'text': 'a' * 2000}
        with self.assertRaises(ValueError) as cm:
            validate_and_sanitize_json_field(data, max_string_length=1000)
        self.assertIn('length', str(cm.exception).lower())
    
    def test_sanitizes_html_in_strings(self):
        """Test that HTML in strings is sanitized."""
        data = {'message': '<script>xss</script>'}
        result = validate_and_sanitize_json_field(data)
        self.assertNotIn('<script>', result['message'])
    
    def test_accepts_valid_json(self):
        """Test that valid JSON is accepted."""
        data = {
            'name': 'John',
            'age': 30,
            'active': True,
            'tags': ['user', 'admin'],
            'metadata': {'role': 'admin'}
        }
        result = validate_and_sanitize_json_field(data)
        self.assertEqual(result['name'], 'John')
        self.assertEqual(result['age'], 30)


class ContainsInjectionAttemptTests(TestCase):
    """Tests for injection attempt detection."""
    
    def test_detects_sql_injection(self):
        """Test that SQL injection is detected."""
        self.assertTrue(contains_injection_attempt("'; DROP TABLE users; --"))
        self.assertTrue(contains_injection_attempt("' UNION SELECT * FROM"))
    
    def test_detects_xss_attempts(self):
        """Test that XSS attempts are detected."""
        self.assertTrue(contains_injection_attempt('<script>alert(1)</script>'))
        self.assertTrue(contains_injection_attempt('javascript:alert(1)'))
        self.assertTrue(contains_injection_attempt('<img onerror="alert(1)">'))
    
    def test_detects_command_injection(self):
        """Test that command injection is detected."""
        self.assertTrue(contains_injection_attempt('test; rm -rf /'))
        self.assertTrue(contains_injection_attempt('test | cat /etc/passwd'))
        self.assertTrue(contains_injection_attempt('test && whoami'))
    
    def test_detects_path_traversal(self):
        """Test that path traversal is detected."""
        self.assertTrue(contains_injection_attempt('../../etc/passwd'))
        self.assertTrue(contains_injection_attempt('..\\..\\windows\\system32'))
    
    def test_accepts_normal_text(self):
        """Test that normal text is not flagged."""
        self.assertFalse(contains_injection_attempt('Hello world'))
        self.assertFalse(contains_injection_attempt('user@example.com'))
        self.assertFalse(contains_injection_attempt('Price: $19.99'))


class SanitizeFilenameTests(TestCase):
    """Tests for filename sanitization."""
    
    def test_removes_path_traversal(self):
        """Test that path traversal is removed."""
        result = sanitize_filename('../../etc/passwd')
        self.assertNotIn('..', result)
        self.assertNotIn('/', result)
    
    def test_removes_dangerous_characters(self):
        """Test that dangerous characters are removed."""
        result = sanitize_filename('file<script>.txt')
        self.assertNotIn('<', result)
        self.assertNotIn('>', result)
    
    def test_preserves_extension(self):
        """Test that file extension is preserved."""
        result = sanitize_filename('a' * 300 + '.txt', max_length=255)
        self.assertTrue(result.endswith('.txt'))
        self.assertLessEqual(len(result), 255)
    
    def test_handles_empty_filename(self):
        """Test that empty filename gets default name."""
        result = sanitize_filename('')
        self.assertEqual(result, 'unnamed')
    
    def test_removes_control_characters(self):
        """Test that control characters are removed."""
        result = sanitize_filename('file\x00\x1f.txt')
        self.assertNotIn('\x00', result)
        self.assertNotIn('\x1f', result)
