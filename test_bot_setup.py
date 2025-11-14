#!/usr/bin/env python
"""
Quick test to verify bot setup is working.

Run this to check if all components are configured correctly.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings


def test_openai_configured():
    """Check if OpenAI API key is configured."""
    api_key = getattr(settings, 'OPENAI_API_KEY', None)
    
    if not api_key:
        print("❌ OPENAI_API_KEY not configured in settings")
        return False
    
    if api_key.startswith('sk-'):
        print(f"✅ OpenAI API key configured: {api_key[:20]}...")
        return True
    else:
        print("⚠️  OpenAI API key format looks incorrect")
        return False


def test_openai_import():
    """Check if openai package is installed."""
    try:
        import openai
        print(f"✅ OpenAI package installed: v{openai.__version__}")
        return True
    except ImportError:
        print("❌ OpenAI package not installed. Run: pip install openai")
        return False


def test_celery_configured():
    """Check if Celery is configured."""
    broker_url = getattr(settings, 'CELERY_BROKER_URL', None)
    
    if not broker_url:
        print("❌ CELERY_BROKER_URL not configured")
        return False
    
    print(f"✅ Celery broker configured: {broker_url}")
    return True


def test_bot_task_registered():
    """Check if bot task is registered."""
    try:
        from apps.bot.tasks import process_inbound_message
        print("✅ Bot task registered: process_inbound_message")
        return True
    except ImportError as e:
        print(f"❌ Failed to import bot task: {e}")
        return False


def test_intent_service():
    """Check if IntentService can be created."""
    try:
        from apps.bot.services.intent_service import create_intent_service
        service = create_intent_service()
        print("✅ IntentService created successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to create IntentService: {e}")
        return False


def test_tenant_has_twilio():
    """Check if test tenant has Twilio configured."""
    from apps.tenants.models import Tenant
    
    tenant = Tenant.objects.filter(whatsapp_number='+14155238886').first()
    
    if not tenant:
        print("⚠️  Test tenant not found (WhatsApp: +14155238886)")
        return False
    
    settings = tenant.settings
    
    if not settings.twilio_sid or not settings.twilio_token:
        print(f"❌ Tenant '{tenant.name}' missing Twilio credentials")
        return False
    
    print(f"✅ Tenant '{tenant.name}' has Twilio configured")
    return True


def test_redis_connection():
    """Check if Redis is accessible."""
    try:
        import redis
        from django.conf import settings
        
        broker_url = settings.CELERY_BROKER_URL
        
        # Parse Redis URL
        if broker_url.startswith('redis://'):
            r = redis.from_url(broker_url)
            r.ping()
            print("✅ Redis connection successful")
            return True
        else:
            print("⚠️  Not using Redis broker")
            return True
    except Exception as e:
        print(f"⚠️  Redis connection failed: {e}")
        print("   Celery tasks may not work without Redis")
        return False


def main():
    """Run all tests."""
    print("="*60)
    print("BOT SETUP VERIFICATION")
    print("="*60)
    print()
    
    tests = [
        ("OpenAI Package", test_openai_import),
        ("OpenAI API Key", test_openai_configured),
        ("Celery Config", test_celery_configured),
        ("Redis Connection", test_redis_connection),
        ("Bot Task", test_bot_task_registered),
        ("Intent Service", test_intent_service),
        ("Tenant Twilio", test_tenant_has_twilio),
    ]
    
    results = []
    
    for name, test_func in tests:
        print(f"\nTesting: {name}")
        print("-" * 40)
        result = test_func()
        results.append((name, result))
        print()
    
    print("="*60)
    print("SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print()
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print()
        print("🎉 All tests passed! Your bot is ready.")
        print()
        print("Next steps:")
        print("1. Start Celery: celery -A config worker -l info")
        print("2. Send a WhatsApp message to test")
        print("3. Watch the Celery logs for processing")
    else:
        print()
        print("⚠️  Some tests failed. Fix the issues above before starting.")
    
    return passed == total


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
