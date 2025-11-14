#!/usr/bin/env python
"""
Debug script to test Twilio signature verification.

Usage:
    python debug_twilio_signature.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.tenants.models import Tenant
from apps.integrations.services.twilio_service import TwilioService


def test_signature_verification():
    """Test Twilio signature verification with your tenant's credentials."""
    
    # Get the tenant
    tenant = Tenant.objects.filter(whatsapp_number='+14155238886').first()
    
    if not tenant:
        print("❌ Tenant not found for WhatsApp number +14155238886")
        return
    
    print(f"✅ Found tenant: {tenant.name}")
    print(f"   WhatsApp: {tenant.whatsapp_number}")
    
    # Get Twilio credentials
    settings = tenant.settings
    
    if not settings.twilio_sid or not settings.twilio_token:
        print("❌ Twilio credentials not configured")
        return
    
    print(f"✅ Twilio SID: {settings.twilio_sid}")
    print(f"✅ Twilio Token: {settings.twilio_token[:10]}... (length: {len(settings.twilio_token)})")
    
    # Create TwilioService
    service = TwilioService(
        account_sid=settings.twilio_sid,
        auth_token=settings.twilio_token,
        from_number=tenant.whatsapp_number
    )
    
    print("\n" + "="*60)
    print("SIGNATURE VERIFICATION TEST")
    print("="*60)
    
    # Test with sample data (you'll need to replace with actual webhook data)
    print("\nTo test with real webhook data:")
    print("1. Check your Django logs for the last failed webhook")
    print("2. Look for the URL and payload in the logs")
    print("3. Update this script with that data")
    print("\nExample test:")
    
    # Example test data
    url = "https://d17968b46250.ngrok-free.app/v1/webhooks/twilio/"
    params = {
        'MessageSid': 'SM1234567890abcdef',
        'From': 'whatsapp:+254722244161',
        'To': 'whatsapp:+14155238886',
        'Body': 'Hello'
    }
    
    # This is a fake signature - you need the real one from Twilio
    fake_signature = "fake_signature_for_testing"
    
    print(f"\nURL: {url}")
    print(f"Params: {params}")
    print(f"Signature: {fake_signature}")
    
    result = service.verify_signature(url, params, fake_signature)
    print(f"\nVerification result: {result}")
    print("(This will be False because we're using fake data)")
    
    print("\n" + "="*60)
    print("NEXT STEPS")
    print("="*60)
    print("\n1. Check if your Twilio auth token is correct:")
    print("   - Go to https://console.twilio.com/")
    print("   - Navigate to Account > API keys & tokens")
    print("   - Verify the Auth Token matches what's in your database")
    
    print("\n2. Check the webhook URL in Twilio:")
    print("   - Go to Messaging > Settings > WhatsApp Sandbox")
    print("   - Verify the URL exactly matches (including trailing slash)")
    print("   - Current ngrok URL in ALLOWED_HOSTS: d17968b46250.ngrok-free.app")
    
    print("\n3. Test with curl:")
    print("   Run this from your terminal to simulate a Twilio webhook:")
    print(f"""
   curl -X POST https://d17968b46250.ngrok-free.app/v1/webhooks/twilio/ \\
     -d "MessageSid=SM1234567890abcdef" \\
     -d "From=whatsapp:+254722244161" \\
     -d "To=whatsapp:+14155238886" \\
     -d "Body=Test message" \\
     -H "X-Twilio-Signature: test"
   """)
    
    print("\n4. Check recent webhook logs:")
    print("   python manage.py shell -c \"from apps.integrations.models import WebhookLog; logs = WebhookLog.objects.filter(provider='twilio').order_by('-created_at')[:5]; [print(f'{l.created_at} - {l.status} - {l.error_message}') for l in logs]\"")


if __name__ == '__main__':
    test_signature_verification()
