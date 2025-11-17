"""
Alerting system for AI agent monitoring.

Monitors metrics and triggers alerts for:
- High error rates
- Slow response times
- High costs
- Frequent handoffs
- API failures
"""
import logging
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings


logger = logging.getLogger(__name__)


@dataclass
class AlertThreshold:
    """Configuration for an alert threshold."""
    name: str
    metric_path: str  # Dot-notation path to metric (e.g., 'response_time.p95_ms')
    operator: str  # 'gt', 'lt', 'eq', 'gte', 'lte'
    threshold_value: float
    severity: str  # 'info', 'warning', 'error', 'critical'
    description: str
    cooldown_minutes: int = 15  # Minimum time between alerts


@dataclass
class Alert:
    """Represents a triggered alert."""
    name: str
    severity: str
    message: str
    metric_value: float
    threshold_value: float
    timestamp: datetime
    tenant_id: Optional[str] = None
    metadata: Dict[str, Any] = None


class AlertManager:
    """
    Manages alert thresholds and triggers alerts based on metrics.
    
    Monitors metrics from MetricsCollector and triggers alerts when
    thresholds are exceeded. Implements cooldown periods to prevent
    alert fatigue.
    """
    
    # Default alert thresholds
    DEFAULT_THRESHOLDS = [
        # Response time alerts
        AlertThreshold(
            name='slow_response_p95',
            metric_path='response_time.p95_ms',
            operator='gt',
            threshold_value=5000.0,  # 5 seconds
            severity='warning',
            description='95th percentile response time exceeds 5 seconds',
            cooldown_minutes=15
        ),
        AlertThreshold(
            name='slow_response_p99',
            metric_path='response_time.p99_ms',
            operator='gt',
            threshold_value=10000.0,  # 10 seconds
            severity='error',
            description='99th percentile response time exceeds 10 seconds',
            cooldown_minutes=15
        ),
        
        # Cost alerts
        AlertThreshold(
            name='high_cost_per_conversation',
            metric_path='cost.avg_per_conversation_usd',
            operator='gt',
            threshold_value=0.10,  # $0.10 per conversation
            severity='warning',
            description='Average cost per conversation exceeds $0.10',
            cooldown_minutes=30
        ),
        AlertThreshold(
            name='very_high_cost_per_conversation',
            metric_path='cost.avg_per_conversation_usd',
            operator='gt',
            threshold_value=0.25,  # $0.25 per conversation
            severity='error',
            description='Average cost per conversation exceeds $0.25',
            cooldown_minutes=30
        ),
        
        # Handoff alerts
        AlertThreshold(
            name='high_handoff_rate',
            metric_path='handoff.handoff_rate',
            operator='gt',
            threshold_value=0.30,  # 30% handoff rate
            severity='warning',
            description='Handoff rate exceeds 30%',
            cooldown_minutes=20
        ),
        AlertThreshold(
            name='very_high_handoff_rate',
            metric_path='handoff.handoff_rate',
            operator='gt',
            threshold_value=0.50,  # 50% handoff rate
            severity='error',
            description='Handoff rate exceeds 50%',
            cooldown_minutes=20
        ),
        
        # Knowledge base alerts
        AlertThreshold(
            name='low_knowledge_hit_rate',
            metric_path='knowledge_base.hit_rate',
            operator='lt',
            threshold_value=0.50,  # 50% hit rate
            severity='warning',
            description='Knowledge base hit rate below 50%',
            cooldown_minutes=30
        ),
    ]
    
    def __init__(self, tenant_id: Optional[str] = None):
        """
        Initialize alert manager.
        
        Args:
            tenant_id: Optional tenant ID for tenant-specific alerts
        """
        self.tenant_id = tenant_id
        self.cache_key_prefix = f"agent_alerts:{tenant_id or 'global'}"
        self.thresholds = self.DEFAULT_THRESHOLDS.copy()
        self.alert_handlers: List[Callable[[Alert], None]] = []
        
        # Register default handlers
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register default alert handlers."""
        # Log all alerts
        self.register_handler(self._log_alert)
        
        # Send critical alerts to Sentry if configured
        if hasattr(settings, 'SENTRY_DSN') and settings.SENTRY_DSN:
            self.register_handler(self._send_to_sentry)
    
    def register_handler(self, handler: Callable[[Alert], None]):
        """
        Register an alert handler function.
        
        Args:
            handler: Function that takes an Alert and handles it
        """
        self.alert_handlers.append(handler)
    
    def add_threshold(self, threshold: AlertThreshold):
        """
        Add a custom alert threshold.
        
        Args:
            threshold: AlertThreshold configuration
        """
        self.thresholds.append(threshold)
    
    def check_metrics(self, metrics: Dict[str, Any]) -> List[Alert]:
        """
        Check metrics against thresholds and trigger alerts.
        
        Args:
            metrics: Metrics dictionary from MetricsCollector
            
        Returns:
            List of triggered alerts
        """
        triggered_alerts = []
        
        for threshold in self.thresholds:
            # Check if alert is in cooldown
            if self._is_in_cooldown(threshold.name):
                continue
            
            # Get metric value
            metric_value = self._get_metric_value(metrics, threshold.metric_path)
            if metric_value is None:
                continue
            
            # Check threshold
            if self._check_threshold(metric_value, threshold):
                alert = Alert(
                    name=threshold.name,
                    severity=threshold.severity,
                    message=threshold.description,
                    metric_value=metric_value,
                    threshold_value=threshold.threshold_value,
                    timestamp=timezone.now(),
                    tenant_id=self.tenant_id,
                    metadata={
                        'metric_path': threshold.metric_path,
                        'operator': threshold.operator
                    }
                )
                
                triggered_alerts.append(alert)
                
                # Trigger alert handlers
                self._trigger_alert(alert)
                
                # Set cooldown
                self._set_cooldown(threshold.name, threshold.cooldown_minutes)
        
        return triggered_alerts
    
    def _get_metric_value(self, metrics: Dict[str, Any], path: str) -> Optional[float]:
        """
        Get metric value from nested dictionary using dot notation.
        
        Args:
            metrics: Metrics dictionary
            path: Dot-notation path (e.g., 'response_time.p95_ms')
            
        Returns:
            Metric value or None if not found
        """
        try:
            parts = path.split('.')
            value = metrics
            
            for part in parts:
                value = value[part]
            
            return float(value)
        except (KeyError, TypeError, ValueError):
            return None
    
    def _check_threshold(self, value: float, threshold: AlertThreshold) -> bool:
        """
        Check if value exceeds threshold based on operator.
        
        Args:
            value: Metric value
            threshold: AlertThreshold configuration
            
        Returns:
            True if threshold is exceeded
        """
        if threshold.operator == 'gt':
            return value > threshold.threshold_value
        elif threshold.operator == 'gte':
            return value >= threshold.threshold_value
        elif threshold.operator == 'lt':
            return value < threshold.threshold_value
        elif threshold.operator == 'lte':
            return value <= threshold.threshold_value
        elif threshold.operator == 'eq':
            return value == threshold.threshold_value
        else:
            logger.warning(f"Unknown operator: {threshold.operator}")
            return False
    
    def _is_in_cooldown(self, alert_name: str) -> bool:
        """
        Check if alert is in cooldown period.
        
        Args:
            alert_name: Name of the alert
            
        Returns:
            True if in cooldown
        """
        cache_key = f"{self.cache_key_prefix}:cooldown:{alert_name}"
        return cache.get(cache_key) is not None
    
    def _set_cooldown(self, alert_name: str, minutes: int):
        """
        Set cooldown period for an alert.
        
        Args:
            alert_name: Name of the alert
            minutes: Cooldown duration in minutes
        """
        cache_key = f"{self.cache_key_prefix}:cooldown:{alert_name}"
        cache.set(cache_key, True, minutes * 60)
    
    def _trigger_alert(self, alert: Alert):
        """
        Trigger all registered alert handlers.
        
        Args:
            alert: Alert to trigger
        """
        for handler in self.alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Error in alert handler: {e}", exc_info=True)
    
    def _log_alert(self, alert: Alert):
        """
        Log alert to standard logging.
        
        Args:
            alert: Alert to log
        """
        log_level = {
            'info': logging.INFO,
            'warning': logging.WARNING,
            'error': logging.ERROR,
            'critical': logging.CRITICAL
        }.get(alert.severity, logging.WARNING)
        
        logger.log(
            log_level,
            f"ALERT [{alert.severity.upper()}] {alert.name}: {alert.message} "
            f"(value={alert.metric_value:.2f}, threshold={alert.threshold_value:.2f})",
            extra={
                'alert_name': alert.name,
                'alert_severity': alert.severity,
                'metric_value': alert.metric_value,
                'threshold_value': alert.threshold_value,
                'tenant_id': alert.tenant_id,
                'timestamp': alert.timestamp.isoformat()
            }
        )
    
    def _send_to_sentry(self, alert: Alert):
        """
        Send alert to Sentry for critical/error alerts.
        
        Args:
            alert: Alert to send
        """
        if alert.severity not in ['error', 'critical']:
            return
        
        try:
            import sentry_sdk
            
            with sentry_sdk.push_scope() as scope:
                scope.set_tag('alert_name', alert.name)
                scope.set_tag('alert_severity', alert.severity)
                scope.set_tag('tenant_id', alert.tenant_id or 'global')
                scope.set_context('alert', {
                    'message': alert.message,
                    'metric_value': alert.metric_value,
                    'threshold_value': alert.threshold_value,
                    'metadata': alert.metadata
                })
                
                sentry_sdk.capture_message(
                    f"AI Agent Alert: {alert.message}",
                    level=alert.severity
                )
        except Exception as e:
            logger.error(f"Failed to send alert to Sentry: {e}")


class ErrorRateMonitor:
    """
    Monitors error rates and triggers alerts.
    
    Tracks errors over time windows and alerts when error rate
    exceeds thresholds.
    """
    
    def __init__(self, tenant_id: Optional[str] = None):
        """
        Initialize error rate monitor.
        
        Args:
            tenant_id: Optional tenant ID
        """
        self.tenant_id = tenant_id
        self.cache_key_prefix = f"agent_errors:{tenant_id or 'global'}"
        
        # Error rate thresholds
        self.error_rate_threshold_5min = 0.10  # 10% error rate in 5 minutes
        self.error_rate_threshold_15min = 0.05  # 5% error rate in 15 minutes
    
    def record_error(self, error_type: str, operation: str):
        """
        Record an error occurrence.
        
        Args:
            error_type: Type of error
            operation: Operation that failed
        """
        timestamp = timezone.now()
        
        # Store error in cache with timestamp
        cache_key = f"{self.cache_key_prefix}:errors"
        errors = cache.get(cache_key, [])
        
        errors.append({
            'timestamp': timestamp.isoformat(),
            'error_type': error_type,
            'operation': operation
        })
        
        # Keep only last 15 minutes of errors
        cutoff = timestamp - timedelta(minutes=15)
        errors = [
            e for e in errors
            if datetime.fromisoformat(e['timestamp'].replace('Z', '+00:00')) > cutoff
        ]
        
        cache.set(cache_key, errors, 900)  # 15 minutes
        
        # Check error rates
        self._check_error_rates(errors, timestamp)
    
    def record_success(self):
        """Record a successful operation."""
        cache_key = f"{self.cache_key_prefix}:successes"
        successes = cache.get(cache_key, [])
        
        timestamp = timezone.now()
        successes.append(timestamp.isoformat())
        
        # Keep only last 15 minutes
        cutoff = timestamp - timedelta(minutes=15)
        successes = [
            s for s in successes
            if datetime.fromisoformat(s.replace('Z', '+00:00')) > cutoff
        ]
        
        cache.set(cache_key, successes, 900)  # 15 minutes
    
    def _check_error_rates(self, errors: List[Dict], current_time: datetime):
        """
        Check error rates and trigger alerts if thresholds exceeded.
        
        Args:
            errors: List of error records
            current_time: Current timestamp
        """
        # Get successes
        cache_key = f"{self.cache_key_prefix}:successes"
        successes = cache.get(cache_key, [])
        
        # Check 5-minute error rate
        cutoff_5min = current_time - timedelta(minutes=5)
        recent_errors_5min = [
            e for e in errors
            if datetime.fromisoformat(e['timestamp'].replace('Z', '+00:00')) > cutoff_5min
        ]
        recent_successes_5min = [
            s for s in successes
            if datetime.fromisoformat(s.replace('Z', '+00:00')) > cutoff_5min
        ]
        
        total_5min = len(recent_errors_5min) + len(recent_successes_5min)
        if total_5min > 0:
            error_rate_5min = len(recent_errors_5min) / total_5min
            
            if error_rate_5min > self.error_rate_threshold_5min:
                self._trigger_error_rate_alert(
                    error_rate=error_rate_5min,
                    window_minutes=5,
                    error_count=len(recent_errors_5min),
                    total_count=total_5min
                )
        
        # Check 15-minute error rate
        cutoff_15min = current_time - timedelta(minutes=15)
        recent_errors_15min = [
            e for e in errors
            if datetime.fromisoformat(e['timestamp'].replace('Z', '+00:00')) > cutoff_15min
        ]
        recent_successes_15min = [
            s for s in successes
            if datetime.fromisoformat(s.replace('Z', '+00:00')) > cutoff_15min
        ]
        
        total_15min = len(recent_errors_15min) + len(recent_successes_15min)
        if total_15min > 0:
            error_rate_15min = len(recent_errors_15min) / total_15min
            
            if error_rate_15min > self.error_rate_threshold_15min:
                self._trigger_error_rate_alert(
                    error_rate=error_rate_15min,
                    window_minutes=15,
                    error_count=len(recent_errors_15min),
                    total_count=total_15min
                )
    
    def _trigger_error_rate_alert(
        self,
        error_rate: float,
        window_minutes: int,
        error_count: int,
        total_count: int
    ):
        """
        Trigger error rate alert.
        
        Args:
            error_rate: Error rate (0.0-1.0)
            window_minutes: Time window in minutes
            error_count: Number of errors
            total_count: Total operations
        """
        # Check cooldown
        cooldown_key = f"{self.cache_key_prefix}:alert_cooldown:{window_minutes}min"
        if cache.get(cooldown_key):
            return
        
        # Log alert
        logger.error(
            f"High error rate detected: {error_rate*100:.1f}% "
            f"({error_count}/{total_count}) in last {window_minutes} minutes",
            extra={
                'error_rate': error_rate,
                'window_minutes': window_minutes,
                'error_count': error_count,
                'total_count': total_count,
                'tenant_id': self.tenant_id
            }
        )
        
        # Set cooldown (10 minutes)
        cache.set(cooldown_key, True, 600)


# Global instances
_alert_managers: Dict[str, AlertManager] = {}
_error_monitors: Dict[str, ErrorRateMonitor] = {}


def get_alert_manager(tenant_id: Optional[str] = None) -> AlertManager:
    """
    Get alert manager instance.
    
    Args:
        tenant_id: Optional tenant ID
        
    Returns:
        AlertManager instance
    """
    key = tenant_id or 'global'
    
    if key not in _alert_managers:
        _alert_managers[key] = AlertManager(tenant_id=tenant_id)
    
    return _alert_managers[key]


def get_error_monitor(tenant_id: Optional[str] = None) -> ErrorRateMonitor:
    """
    Get error rate monitor instance.
    
    Args:
        tenant_id: Optional tenant ID
        
    Returns:
        ErrorRateMonitor instance
    """
    key = tenant_id or 'global'
    
    if key not in _error_monitors:
        _error_monitors[key] = ErrorRateMonitor(tenant_id=tenant_id)
    
    return _error_monitors[key]
