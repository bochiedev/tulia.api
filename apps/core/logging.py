"""
Custom logging formatters for structured JSON logging.
"""
import json
import logging
import traceback
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """
    Format log records as JSON for structured logging.
    Includes request_id and tenant_id from extra fields if available.
    """
    
    def format(self, record):
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add request_id if available
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id
        
        # Add tenant_id if available
        if hasattr(record, 'tenant_id'):
            log_data['tenant_id'] = str(record.tenant_id)
        
        # Add task_id for Celery tasks
        if hasattr(record, 'task_id'):
            log_data['task_id'] = record.task_id
        
        # Add task_name for Celery tasks
        if hasattr(record, 'task_name'):
            log_data['task_name'] = record.task_name
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info),
            }
        
        # Add any extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename', 'funcName',
                          'levelname', 'lineno', 'module', 'msecs', 'message',
                          'pathname', 'process', 'processName', 'relativeCreated',
                          'thread', 'threadName', 'exc_info', 'exc_text', 'stack_info',
                          'request_id', 'tenant_id', 'task_id', 'task_name']:
                if not key.startswith('_'):
                    try:
                        json.dumps(value)  # Test if serializable
                        log_data[key] = value
                    except (TypeError, ValueError):
                        log_data[key] = str(value)
        
        return json.dumps(log_data)
