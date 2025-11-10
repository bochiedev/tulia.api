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
