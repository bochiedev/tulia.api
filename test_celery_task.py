#!/usr/bin/env python
"""
Test script to verify Celery task execution.

Run this to test if the bot task is working correctly.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.messaging.models import Message
from apps.bot.tasks import process_inbound_message


def test_celery_task():
    """Test Celery task with a recent message."""
    
    print("="*60)
    print("CELERY TASK TEST")
    print("="*60)
    print()
    
    # Get most recent inbound message
    message = Message.objects.filter(direction='in').order_by('-created_at').first()
    
    if not message:
        print("❌ No inbound messages found in database")
        print()
        print("To test:")
        print("1. Send a WhatsApp message to your Twilio number")
        print("2. Wait for webhook to process")
        print("3. Run this script again")
        return False
    
    print(f"✅ Found message:")
    print(f"   ID: {message.id}")
    print(f"   Text: {message.text}")
    print(f"   Created: {message.created_at}")
    print(f"   Tenant: {message.conversation.tenant.name}")
    print()
    
    # Check if Celery is running
    print("Checking Celery status...")
    try:
        from celery import current_app
        inspect = current_app.control.inspect()
        stats = inspect.stats()
        
        if not stats:
            print("⚠️  WARNING: Celery worker not detected")
            print()
            print("Start Celery worker:")
            print("  ./start_celery.sh")
            print()
            print("Or manually:")
            print("  celery -A config worker -l info")
            print()
        else:
            print(f"✅ Celery worker running: {list(stats.keys())}")
            print()
    except Exception as e:
        print(f"⚠️  Could not check Celery status: {e}")
        print()
    
    # Enqueue the task
    print("Enqueueing task...")
    try:
        result = process_inbound_message.delay(str(message.id))
        print(f"✅ Task enqueued successfully!")
        print(f"   Task ID: {result.id}")
        print()
        print("Check Celery worker terminal for processing logs:")
        print("  [INFO] Processing inbound message")
        print("  [INFO] Intent classified: ...")
        print("  [INFO] Response sent successfully")
        print()
        print("If you don't see logs, Celery worker might not be running.")
        return True
        
    except Exception as e:
        print(f"❌ Failed to enqueue task: {e}")
        print()
        print("Common causes:")
        print("1. Redis not running - start with: redis-server")
        print("2. Celery not configured - check config/celery.py")
        print("3. Task not registered - check apps/bot/tasks.py")
        return False


if __name__ == '__main__':
    success = test_celery_task()
    sys.exit(0 if success else 1)
