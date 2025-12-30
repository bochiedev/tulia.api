"""
Tests for Twilio webhook handler.

Tests webhook processing, tenant resolution, signature verification,
and message creation.
"""
import pytest
from django.test import Client
from django.urls import reverse
from unittest.mock import patch, MagicMock

from apps.tenants.models import Tenant, TenantSettings, Customer, SubscriptionTier
from apps.messaging.models import Conversation, Message
from apps.integrations.models import WebhookLog


@pytest.mark.django_db
class TestTwilioWebhook:
    """Test Twilio webhook handler."""
    
    @pytest.fixture
    def subscription_tier(self):
        """Create a subscription tier."""
        return SubscriptionTier.objects.create(
            name='Starter',
            monthly_price=29.00,
            yearly_price=278.00,
            monthly_messages=1000,
            max_products=100,
            max_services=10
        )
    
    @pytest.fixture
    def tenant(self, subscription_tier):
        """Create a test tenant."""
        tenant = Tenant.objects.create(
            name='Test Business',
            slug='test-business',
            status='active',
            whatsapp_number='+14155238886',
            subscription_tier=subscription_tier
        )
        
        # Create TenantSettings with Twilio credentials
        TenantSettings.objects.create(
            tenant=tenant,
            twilio_sid='ACtest123',
            twilio_token='test_token_123',
            twilio_webhook_secret='test_secret_123'
        )
        
        return tenant
    
    @pytest.fixture
    def webhook_payload(self):
        """Sample Twilio webhook payload."""
        return {
            'MessageSid': 'SM1234567890abcdef1234567890abcdef',
            'AccountSid': 'ACtest123',
            'From': 'whatsapp:+1234567890',
            'To': 'whatsapp:+14155238886',
            'Body': 'Hello, I need help with my order',
            'NumMedia': '0',
        }
    
    def test_webhook_creates_message_with_valid_signature(self, tenant, webhook_payload):
        """Test that webhook creates message with valid signature."""
        import hmac
        import hashlib
        import base64
        from apps.integrations.utils import verify_twilio_signature
        
        client = Client()
        
        # Build the full URL
        url = 'http://testserver' + reverse('integrations:twilio-webhook')
        
        # Compute real Twilio signature
        sorted_params = sorted(webhook_payload.items())
        data = url + ''.join(f'{k}{v}' for k, v in sorted_params)
        computed_signature = hmac.new(
            tenant.settings.twilio_token.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha1
        ).digest()
        signature = base64.b64encode(computed_signature).decode('utf-8')
        
        # Verify signature is valid
        assert verify_twilio_signature(url, webhook_payload, signature, tenant.settings.twilio_token)
        
        # Send request with valid signature
        response = client.post(
            reverse('integrations:twilio-webhook'),
            data=webhook_payload,
            HTTP_X_TWILIO_SIGNATURE=signature
        )
        
        # Should succeed
        assert response.status_code == 200
        
        # Should create message
        assert Message.objects.count() == 1
        message = Message.objects.first()
        assert message.content == 'Hello, I need help with my order'
        assert message.direction == 'inbound'
        assert message.conversation.tenant == tenant
    
    def test_webhook_rejects_invalid_signature(self, tenant, webhook_payload):
        """Test that webhook rejects invalid signature."""
        from apps.integrations.utils import verify_twilio_signature
        
        client = Client()
        
        # Build the full URL
        url = 'http://testserver' + reverse('integrations:twilio-webhook')
        
        # Use wrong signature
        wrong_signature = 'invalid_signature'
        
        # Verify signature is invalid with correct token
        assert not verify_twilio_signature(url, webhook_payload, wrong_signature, tenant.settings.twilio_token)
        
        # Send request with wrong signature
        response = client.post(
            reverse('integrations:twilio-webhook'),
            data=webhook_payload,
            HTTP_X_TWILIO_SIGNATURE=wrong_signature
        )
        
        # Should be rejected
        assert response.status_code == 403
        
        # Should not create message
        assert Message.objects.count() == 0


@pytest.mark.django_db
class TestTwilioStatusCallback:
    """Test Twilio status callback handler."""
    
    @pytest.fixture
    def subscription_tier(self):
        """Create a subscription tier."""
        return SubscriptionTier.objects.create(
            name='Starter',
            monthly_price=29.00,
            yearly_price=278.00,
            monthly_messages=1000,
            max_products=100,
            max_services=10
        )
    
    @pytest.fixture
    def tenant(self, subscription_tier):
        """Create a test tenant."""
        tenant = Tenant.objects.create(
            name='Test Business',
            slug='test-business',
            status='active',
            whatsapp_number='+14155238886',
            subscription_tier=subscription_tier
        )
        
        # Create TenantSettings with Twilio credentials
        TenantSettings.objects.create(
            tenant=tenant,
            twilio_sid='ACtest123',
            twilio_token='test_token_123',
            twilio_webhook_secret='test_secret_123'
        )
        
        return tenant
    
    @pytest.fixture
    def customer(self, tenant):
        """Create a test customer."""
        return Customer.objects.create(
            tenant=tenant,
            phone_e164='+1234567890'
        )
    
    @pytest.fixture
    def conversation(self, tenant, customer):
        """Create a test conversation."""
        return Conversation.objects.create(
            tenant=tenant,
            customer=customer,
            channel='whatsapp',
            status='active'
        )
    
    @pytest.fixture
    def message(self, conversation):
        """Create a test message."""
        return Message.objects.create(
            conversation=conversation,
            content='Test message',
            direction='outbound',
            provider_message_id='SM1234567890abcdef1234567890abcdef',
            status='sent'
        )
    
    @pytest.fixture
    def status_callback_payload(self, message):
        """Sample Twilio status callback payload."""
        return {
            'MessageSid': message.provider_message_id,
            'MessageStatus': 'delivered',
            'AccountSid': 'ACtest123',
            'From': 'whatsapp:+14155238886',
            'To': 'whatsapp:+1234567890',
        }
    
    def test_status_callback_updates_message_status(self, tenant, message, status_callback_payload):
        """Test that status callback updates message status."""
        import hmac
        import hashlib
        import base64
        from apps.integrations.utils import verify_twilio_signature
        
        client = Client()
        
        # Build the full URL
        url = 'http://testserver' + reverse('integrations:twilio-status-callback')
        
        # Compute real Twilio signature
        sorted_params = sorted(status_callback_payload.items())
        data = url + ''.join(f'{k}{v}' for k, v in sorted_params)
        computed_signature = hmac.new(
            tenant.settings.twilio_token.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha1
        ).digest()
        signature = base64.b64encode(computed_signature).decode('utf-8')
        
        # Verify signature is valid
        assert verify_twilio_signature(url, status_callback_payload, signature, tenant.settings.twilio_token)
        
        # Send request with valid signature
        response = client.post(
            reverse('integrations:twilio-status-callback'),
            data=status_callback_payload,
            HTTP_X_TWILIO_SIGNATURE=signature
        )
        
        # Should succeed
        assert response.status_code == 200
        
        # Should update message status
        message.refresh_from_db()
        assert message.status == 'delivered'