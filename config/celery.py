"""
Celery configuration for Tulia AI.
"""
import os
from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure, task_retry
import logging

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('tulia')

# Load configuration from Django settings with CELERY_ prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

logger = logging.getLogger(__name__)


@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **extra):
    """Log task start."""
    logger.info(
        f"Task started: {task.name}",
        extra={
            'task_id': task_id,
            'task_name': task.name,
            'args': args,
            'kwargs': kwargs,
        }
    )


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, **extra):
    """Log task completion."""
    logger.info(
        f"Task completed: {task.name}",
        extra={
            'task_id': task_id,
            'task_name': task.name,
            'result': str(retval)[:200] if retval else None,
        }
    )


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback=None, einfo=None, **extra):
    """Log task failure and send to Sentry."""
    logger.error(
        f"Task failed: {sender.name}",
        extra={
            'task_id': task_id,
            'task_name': sender.name,
            'exception': str(exception),
            'args': args,
            'kwargs': kwargs,
        },
        exc_info=einfo
    )
    
    # Send to Sentry with additional context
    try:
        from apps.core.sentry_utils import capture_exception
        capture_exception(
            exception,
            task={
                'task_id': task_id,
                'task_name': sender.name,
                'args': args,
                'kwargs': kwargs,
            }
        )
    except Exception as e:
        # Don't fail if Sentry capture fails
        logger.warning(f"Failed to send task failure to Sentry: {e}")


@task_retry.connect
def task_retry_handler(sender=None, task_id=None, reason=None, einfo=None, **extra):
    """Log task retry."""
    logger.warning(
        f"Task retry: {sender.name}",
        extra={
            'task_id': task_id,
            'task_name': sender.name,
            'reason': str(reason),
            'retry_count': sender.request.retries,
        }
    )


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    print(f'Request: {self.request!r}')


# Celery Beat Schedule for Periodic Tasks
app.conf.beat_schedule = {
    # Process scheduled messages every minute
    'process-scheduled-messages': {
        'task': 'apps.messaging.tasks.process_scheduled_messages',
        'schedule': 60.0,  # Every 60 seconds
    },
    
    # Send 24-hour appointment reminders every hour
    'send-24h-appointment-reminders': {
        'task': 'apps.messaging.tasks.send_24h_appointment_reminders',
        'schedule': 3600.0,  # Every hour
    },
    
    # Send 2-hour appointment reminders every 15 minutes
    'send-2h-appointment-reminders': {
        'task': 'apps.messaging.tasks.send_2h_appointment_reminders',
        'schedule': 900.0,  # Every 15 minutes
    },
    
    # Send re-engagement messages daily at 10 AM UTC
    'send-reengagement-messages': {
        'task': 'apps.messaging.tasks.send_reengagement_messages',
        'schedule': 86400.0,  # Every 24 hours
        # Note: For production, use crontab schedule to run at specific time:
        # 'schedule': crontab(hour=10, minute=0),
    },
}

app.conf.timezone = 'UTC'
