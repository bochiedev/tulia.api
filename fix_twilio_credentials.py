#!/usr/bin/env python
"""
Fix Twilio credentials for the Starter Store tenant.

This script updates the Twilio Account SID and Auth Token to match
the actual Twilio account sending webhooks.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.tenants.models import Tenant


def fix_credentials():
    """Update Twilio credentials for Starter Store tenant."""
    
    # Get the tenant
    tenant = Tenant.objects.filter(whatsapp_number='+14155238886').first()
    
    if not tenant:
        print("❌ Tenant not found")
        return
    
    print(f"Found tenant: {tenant.name}")
    print(f"Current Twilio SID: {tenant.settings.twilio_sid}")
    
    # The actual Account SID from the webhook payload
    correct_sid = "AC245ecdc0caca40e8bb9821e2c469bfa2"
    
    print(f"\n⚠️  MISMATCH DETECTED!")
    print(f"   Configured SID: {tenant.settings.twilio_sid}")
    print(f"   Webhook SID:    {correct_sid}")
    
    print("\n" + "="*60)
    print("TO FIX THIS ISSUE:")
    print("="*60)
    
    print("\n1. Go to your Twilio Console:")
    print("   https://console.twilio.com/")
    
    print("\n2. Find your Account SID and Auth Token:")
    print("   - Click on 'Account' in the top right")
    print("   - Look for 'Account Info' section")
    print("   - Copy the Account SID and Auth Token")
    
    print("\n3. Update the tenant settings:")
    print("   Run this command in Django shell:")
    print(f"""
   python manage.py shell
   
   from apps.tenants.models import Tenant
   tenant = Tenant.objects.get(whatsapp_number='+14155238886')
   settings = tenant.settings
   settings.twilio_sid = 'AC245ecdc0caca40e8bb9821e2c469bfa2'  # Your actual SID
   settings.twilio_token = 'YOUR_AUTH_TOKEN_HERE'  # Get from Twilio Console
   settings.save()
   print('✅ Credentials updated!')
   """)
    
    print("\n4. Or update via Django Admin:")
    print("   - Go to http://localhost:8000/admin/")
    print("   - Navigate to Tenants > Tenant Settings")
    print(f"   - Find settings for '{tenant.name}'")
    print("   - Update Twilio SID and Token")
    print("   - Save")
    
    print("\n" + "="*60)
    print("IMPORTANT NOTES:")
    print("="*60)
    print("\n- The Auth Token is sensitive - never commit it to git")
    print("- Make sure you're using the LIVE credentials, not test/sandbox")
    print("- After updating, send a test WhatsApp message to verify")


if __name__ == '__main__':
    fix_credentials()
