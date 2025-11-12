"""
Base Celery task classes with enhanced logging and error handling.
"""
import logging
from celery import Task
from django.conf import settings
from apps.core.sentry_utils import add_breadcrumb, capture_exception, start_transaction

logger = logging.getLogger(__name__)


class LoggedTask(Task):
    """
    Base task class with enhanced logging and Sentry integration.
    
    This task class automatically:
    - Logs task start with parameters
    - Logs task completion with result summary
    - Logs task failures with error details
    - Logs retry attempts with reason
    - Sends failures to Sentry with context
    - Creates Sentry transactions for performance monitoring
    """
    
    def __call__(self, *args, **kwargs):
        """
        Execute task with logging and error handling.
        """
        task_id = self.request.id
        task_name = self.name
        
        # Start Sentry transaction for performance monitoring
        transaction = start_transaction(
            name=f"task.{task_name}",
            op="celery.task"
        )
        
        try:
            # Log task start
            logger.info(
                f"Task started: {task_name}",
                extra={
                    'task_id': task_id,
                    'task_name': task_name,
                    'args': self._sanitize_args(args),
                    'kwargs': self._sanitize_kwargs(kwargs),
                }
            )
            
            # Add Sentry breadcrumb
            add_breadcrumb(
                category="task",
                message=f"Task started: {task_name}",
                level="info",
                data={
                    'task_id': task_id,
                    'task_name': task_name,
                }
            )
            
            # Execute task
            result = super().__call__(*args, **kwargs)
            
            # Log task completion
            logger.info(
                f"Task completed: {task_name}",
                extra={
                    'task_id': task_id,
                    'task_name': task_name,
                    'result': self._sanitize_result(result),
                }
            )
            
            # Add Sentry breadcrumb
            add_breadcrumb(
                category="task",
                message=f"Task completed: {task_name}",
                level="info",
                data={
                    'task_id': task_id,
                    'task_name': task_name,
                }
            )
            
            # Finish transaction
            if transaction:
                transaction.set_status("ok")
                transaction.finish()
            
            return result
            
        except Exception as exc:
            # Log task failure
            logger.error(
                f"Task failed: {task_name}",
                extra={
                    'task_id': task_id,
                    'task_name': task_name,
                    'exception': str(exc),
                    'args': self._sanitize_args(args),
                    'kwargs': self._sanitize_kwargs(kwargs),
                },
                exc_info=True
            )
            
            # Add Sentry breadcrumb
            add_breadcrumb(
                category="task",
                message=f"Task failed: {task_name}",
                level="error",
                data={
                    'task_id': task_id,
                    'task_name': task_name,
                    'exception': str(exc),
                }
            )
            
            # Send to Sentry
            capture_exception(
                exc,
                task={
                    'task_id': task_id,
                    'task_name': task_name,
                    'args': self._sanitize_args(args),
                    'kwargs': self._sanitize_kwargs(kwargs),
                }
            )
            
            # Finish transaction with error
            if transaction:
                transaction.set_status("internal_error")
                transaction.finish()
            
            # Re-raise exception
            raise
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """
        Log task retry attempts.
        """
        retry_count = self.request.retries
        max_retries = self.max_retries
        
        logger.warning(
            f"Task retry: {self.name} (attempt {retry_count}/{max_retries})",
            extra={
                'task_id': task_id,
                'task_name': self.name,
                'retry_count': retry_count,
                'max_retries': max_retries,
                'exception': str(exc),
                'args': self._sanitize_args(args),
                'kwargs': self._sanitize_kwargs(kwargs),
            }
        )
        
        # Add Sentry breadcrumb
        add_breadcrumb(
            category="task",
            message=f"Task retry: {self.name}",
            level="warning",
            data={
                'task_id': task_id,
                'task_name': self.name,
                'retry_count': retry_count,
                'max_retries': max_retries,
                'exception': str(exc),
            }
        )
        
        super().on_retry(exc, task_id, args, kwargs, einfo)
    
    def _sanitize_args(self, args):
        """
        Sanitize task arguments for logging (remove sensitive data).
        """
        if not args:
            return []
        
        # Convert to list and truncate if too long
        sanitized = list(args)
        if len(sanitized) > 10:
            sanitized = sanitized[:10] + ['... (truncated)']
        
        return sanitized
    
    def _sanitize_kwargs(self, kwargs):
        """
        Sanitize task keyword arguments for logging (remove sensitive data).
        """
        if not kwargs:
            return {}
        
        # Remove sensitive keys
        sensitive_keys = {
            'password', 'token', 'api_key', 'secret', 'auth_token',
            'access_token', 'refresh_token', 'phone', 'email',
        }
        
        sanitized = {}
        for key, value in kwargs.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = '********'
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _sanitize_result(self, result):
        """
        Sanitize task result for logging (truncate if too long).
        """
        if result is None:
            return None
        
        result_str = str(result)
        if len(result_str) > 200:
            return result_str[:200] + '... (truncated)'
        
        return result_str


class TenantTask(LoggedTask):
    """
    Base task class for tenant-scoped operations.
    
    Automatically sets tenant context in Sentry for error tracking.
    """
    
    def __call__(self, *args, **kwargs):
        """
        Execute task with tenant context.
        """
        # Extract tenant_id from kwargs if present
        tenant_id = kwargs.get('tenant_id')
        
        if tenant_id:
            try:
                from apps.tenants.models import Tenant
                from apps.core.sentry_utils import set_tenant_context
                
                tenant = Tenant.objects.get(id=tenant_id)
                set_tenant_context(tenant)
                
                # Add tenant_id to thread-local storage for logging
                import threading
                threading.current_thread().tenant_id = str(tenant.id)
                
            except Exception as e:
                logger.warning(
                    f"Failed to set tenant context for task: {e}",
                    extra={'tenant_id': tenant_id}
                )
        
        return super().__call__(*args, **kwargs)
