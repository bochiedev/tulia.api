#!/usr/bin/env python
"""
Diagnostic script for authentication and Celery issues.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.rbac.models import User
from apps.rbac.services import AuthService
from apps.messaging.models import Message


def check_users():
    """Check if users exist and generate tokens."""
    print("="*60)
    print("USER & TOKEN CHECK")
    print("="*60)
    print()
    
    users = User.objects.filter(is_active=True)
    
    if not users.exists():
        print("❌ No active users found")
        print()
        print("Create a user:")
        print("  POST /v1/auth/register")
        print()
        return None
    
    print(f"✅ Found {users.count()} active users")
    print()
    
    # Show first 3 users
    for user in users[:3]:
        print(f"User: {user.email}")
        token = AuthService.generate_jwt(user)
        print(f"Token: {token}")
        print()
    
    return users.first()


def check_messages():
    """Check if there are messages to process."""
    print("="*60)
    print("MESSAGE CHECK")
    print("="*60)
    print()
    
    messages = Message.objects.filter(direction='in').order_by('-created_at')[:5]
    
    if not messages.exists():
        print("❌ No inbound messages found")
        print()
        print("To test bot:")
        print("1. Send WhatsApp message to your Twilio number")
        print("2. Check webhook logs")
        print("3. Run this script again")
        print()
        return False
    
    print(f"✅ Found {messages.count()} recent inbound messages")
    print()
    
    for msg in messages:
        print(f"Message: {msg.text[:50]}...")
        print(f"  Created: {msg.created_at}")
        print(f"  Tenant: {msg.conversation.tenant.name}")
        print()
    
    return True


def check_celery():
    """Check if Celery is running."""
    print("="*60)
    print("CELERY CHECK")
    print("="*60)
    print()
    
    try:
        from celery import current_app
        inspect = current_app.control.inspect()
        
        # Check active workers
        stats = inspect.stats()
        
        if not stats:
            print("❌ No Celery workers detected")
            print()
            print("Start Celery:")
            print("  ./start_celery.sh")
            print()
            print("Or manually:")
            print("  celery -A config worker -l info")
            print()
            return False
        
        print(f"✅ Celery workers running:")
        for worker_name in stats.keys():
            print(f"  - {worker_name}")
        print()
        
        # Check registered tasks
        registered = inspect.registered()
        if registered:
            print("Registered tasks:")
            for worker, tasks in registered.items():
                bot_tasks = [t for t in tasks if 'bot' in t]
                if bot_tasks:
                    print(f"  Bot tasks: {len(bot_tasks)}")
                    for task in bot_tasks:
                        print(f"    - {task}")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking Celery: {e}")
        print()
        return False


def check_redis():
    """Check if Redis is running."""
    print("="*60)
    print("REDIS CHECK")
    print("="*60)
    print()
    
    try:
        import redis
        from django.conf import settings
        
        r = redis.from_url(settings.CELERY_BROKER_URL)
        r.ping()
        
        print("✅ Redis is running")
        print(f"   URL: {settings.CELERY_BROKER_URL}")
        print()
        return True
        
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        print()
        print("Start Redis:")
        print("  redis-server")
        print()
        return False


def test_task():
    """Test enqueueing a task."""
    print("="*60)
    print("TASK ENQUEUE TEST")
    print("="*60)
    print()
    
    messages = Message.objects.filter(direction='in').order_by('-created_at')
    
    if not messages.exists():
        print("⚠️  No messages to test with")
        print()
        return False
    
    message = messages.first()
    print(f"Testing with message: {message.text[:50]}...")
    print()
    
    try:
        from apps.bot.tasks import process_inbound_message
        
        result = process_inbound_message.delay(str(message.id))
        
        print(f"✅ Task enqueued successfully")
        print(f"   Task ID: {result.id}")
        print()
        print("Check Celery worker terminal for logs:")
        print("  [INFO] Processing inbound message")
        print("  [INFO] Intent classified: ...")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to enqueue task: {e}")
        print()
        return False


def main():
    """Run all diagnostics."""
    print()
    print("🔍 DIAGNOSTIC REPORT")
    print()
    
    results = {
        'users': check_users(),
        'redis': check_redis(),
        'celery': check_celery(),
        'messages': check_messages(),
    }
    
    # Only test task if everything else is working
    if all([results['redis'], results['celery'], results['messages']]):
        results['task'] = test_task()
    
    print("="*60)
    print("SUMMARY")
    print("="*60)
    print()
    
    if results['users']:
        print("✅ Users exist - use token above in Postman")
    else:
        print("❌ No users - register first")
    
    if results['redis']:
        print("✅ Redis running")
    else:
        print("❌ Redis not running - start it")
    
    if results['celery']:
        print("✅ Celery running")
    else:
        print("❌ Celery not running - start it")
    
    if results['messages']:
        print("✅ Messages exist")
    else:
        print("⚠️  No messages - send WhatsApp message to test")
    
    print()
    
    if not all([results['redis'], results['celery']]):
        print("⚠️  Bot won't work until Redis and Celery are running")
        print()
        print("Quick fix:")
        print("  Terminal 1: redis-server")
        print("  Terminal 2: ./start_celery.sh")
        print()


if __name__ == '__main__':
    main()
