"""
Metrics collection service for journey completion rates, payment success, and escalation frequency.

This module implements comprehensive metrics collection for business KPIs,
system performance, and operational health monitoring.

Requirements: 10.1, 10.4, 10.5
"""

import logging
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
import json
from collections import defaultdict, deque
import threading

from apps.bot.services.observability import observability_service, ConversationMetrics


class MetricCategory(Enum):
    """Categories of metrics collected."""
    JOURNEY_COMPLETION = "journey_completion"
    PAYMENT_SUCCESS = "payment_success"
    ESCALATION_FREQUENCY = "escalation_frequency"
    PERFORMANCE = "performance"
    BUSINESS_KPI = "business_kpi"
    SYSTEM_HEALTH = "system_health"


@dataclass
class JourneyMetrics:
    """Metrics for journey completion tracking."""
    journey_type: str
    total_started: int = 0
    total_completed: int = 0
    total_failed: int = 0
    total_abandoned: int = 0
    avg_duration: float = 0.0
    completion_rate: float = 0.0
    failure_rate: float = 0.0
    abandonment_rate: float = 0.0
    
    def update_completion_rate(self):
        """Update calculated completion rate."""
        total = self.total_started
        if total > 0:
            self.completion_rate = self.total_completed / total
            self.failure_rate = self.total_failed / total
            self.abandonment_rate = self.total_abandoned / total


@dataclass
class PaymentMetrics:
    """Metrics for payment success tracking."""
    payment_method: str
    total_initiated: int = 0
    total_completed: int = 0
    total_failed: int = 0
    total_abandoned: int = 0
    avg_amount: float = 0.0
    success_rate: float = 0.0
    failure_rate: float = 0.0
    abandonment_rate: float = 0.0
    avg_processing_time: float = 0.0
    
    def update_success_rate(self):
        """Update calculated success rate."""
        total = self.total_initiated
        if total > 0:
            self.success_rate = self.total_completed / total
            self.failure_rate = self.total_failed / total
            self.abandonment_rate = self.total_abandoned / total


@dataclass
class EscalationMetrics:
    """Metrics for escalation frequency tracking."""
    escalation_reason: str
    total_escalations: int = 0
    avg_resolution_time: float = 0.0
    escalation_rate: float = 0.0
    resolution_rate: float = 0.0
    
    # Escalation triggers breakdown
    explicit_human_requests: int = 0
    payment_disputes: int = 0
    missing_information: int = 0
    repeated_failures: int = 0
    sensitive_content: int = 0
    user_frustration: int = 0
    system_errors: int = 0


@dataclass
class PerformanceMetrics:
    """Performance metrics for system monitoring."""
    component: str
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    avg_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0
    success_rate: float = 0.0
    error_rate: float = 0.0
    
    # Response time tracking
    response_times: deque = field(default_factory=lambda: deque(maxlen=1000))
    
    def add_response_time(self, duration: float):
        """Add response time measurement."""
        self.response_times.append(duration)
        self._update_percentiles()
    
    def _update_percentiles(self):
        """Update percentile calculations."""
        if self.response_times:
            sorted_times = sorted(self.response_times)
            count = len(sorted_times)
            
            self.avg_response_time = sum(sorted_times) / count
            
            if count >= 20:  # Only calculate percentiles with sufficient data
                p95_index = int(0.95 * count)
                p99_index = int(0.99 * count)
                self.p95_response_time = sorted_times[min(p95_index, count - 1)]
                self.p99_response_time = sorted_times[min(p99_index, count - 1)]
    
    def update_success_rate(self):
        """Update calculated success rate."""
        if self.total_operations > 0:
            self.success_rate = self.successful_operations / self.total_operations
            self.error_rate = self.failed_operations / self.total_operations


class MetricsCollector:
    """
    Comprehensive metrics collection service.
    
    Collects and aggregates metrics for journey completion rates, payment success,
    escalation frequency, and system performance monitoring.
    """
    
    def __init__(self):
        """Initialize metrics collector."""
        self.logger = logging.getLogger("tulia.metrics")
        
        # Metrics storage
        self.journey_metrics: Dict[str, JourneyMetrics] = {}
        self.payment_metrics: Dict[str, PaymentMetrics] = {}
        self.escalation_metrics: Dict[str, EscalationMetrics] = {}
        self.performance_metrics: Dict[str, PerformanceMetrics] = {}
        
        # Time-series data for trending
        self.hourly_metrics: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.daily_metrics: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Last aggregation time
        self.last_hourly_aggregation = datetime.now(timezone.utc)
        self.last_daily_aggregation = datetime.now(timezone.utc)
    
    def track_journey_start(self, journey_type: str, conversation_id: str, tenant_id: str):
        """Track journey start event."""
        with self._lock:
            if journey_type not in self.journey_metrics:
                self.journey_metrics[journey_type] = JourneyMetrics(journey_type)
            
            self.journey_metrics[journey_type].total_started += 1
            
            self.logger.info(
                f"Journey started: {journey_type}",
                extra={
                    'metric_category': MetricCategory.JOURNEY_COMPLETION.value,
                    'journey_type': journey_type,
                    'conversation_id': conversation_id,
                    'tenant_id': tenant_id,
                    'event_type': 'journey_start'
                }
            )
    
    def track_journey_completion(self, journey_type: str, conversation_id: str, 
                               tenant_id: str, success: bool, duration: float = None):
        """Track journey completion event."""
        with self._lock:
            if journey_type not in self.journey_metrics:
                self.journey_metrics[journey_type] = JourneyMetrics(journey_type)
            
            metrics = self.journey_metrics[journey_type]
            
            if success:
                metrics.total_completed += 1
            else:
                metrics.total_failed += 1
            
            # Update average duration
            if duration is not None:
                current_total = metrics.total_completed + metrics.total_failed
                if current_total > 1:
                    metrics.avg_duration = (
                        (metrics.avg_duration * (current_total - 1) + duration) / current_total
                    )
                else:
                    metrics.avg_duration = duration
            
            metrics.update_completion_rate()
            
            self.logger.info(
                f"Journey completed: {journey_type} ({'success' if success else 'failed'})",
                extra={
                    'metric_category': MetricCategory.JOURNEY_COMPLETION.value,
                    'journey_type': journey_type,
                    'conversation_id': conversation_id,
                    'tenant_id': tenant_id,
                    'success': success,
                    'duration': duration,
                    'completion_rate': metrics.completion_rate,
                    'event_type': 'journey_completion'
                }
            )
    
    def track_journey_abandonment(self, journey_type: str, conversation_id: str, 
                                tenant_id: str, step: str = None):
        """Track journey abandonment event."""
        with self._lock:
            if journey_type not in self.journey_metrics:
                self.journey_metrics[journey_type] = JourneyMetrics(journey_type)
            
            metrics = self.journey_metrics[journey_type]
            metrics.total_abandoned += 1
            metrics.update_completion_rate()
            
            self.logger.info(
                f"Journey abandoned: {journey_type}",
                extra={
                    'metric_category': MetricCategory.JOURNEY_COMPLETION.value,
                    'journey_type': journey_type,
                    'conversation_id': conversation_id,
                    'tenant_id': tenant_id,
                    'abandonment_step': step,
                    'abandonment_rate': metrics.abandonment_rate,
                    'event_type': 'journey_abandonment'
                }
            )
    
    def track_payment_initiation(self, payment_method: str, conversation_id: str,
                               tenant_id: str, amount: float = None, currency: str = None):
        """Track payment initiation event."""
        with self._lock:
            if payment_method not in self.payment_metrics:
                self.payment_metrics[payment_method] = PaymentMetrics(payment_method)
            
            metrics = self.payment_metrics[payment_method]
            metrics.total_initiated += 1
            
            # Update average amount
            if amount is not None:
                if metrics.total_initiated > 1:
                    metrics.avg_amount = (
                        (metrics.avg_amount * (metrics.total_initiated - 1) + amount) / metrics.total_initiated
                    )
                else:
                    metrics.avg_amount = amount
            
            self.logger.info(
                f"Payment initiated: {payment_method}",
                extra={
                    'metric_category': MetricCategory.PAYMENT_SUCCESS.value,
                    'payment_method': payment_method,
                    'conversation_id': conversation_id,
                    'tenant_id': tenant_id,
                    'amount': amount,
                    'currency': currency,
                    'event_type': 'payment_initiation'
                }
            )
    
    def track_payment_completion(self, payment_method: str, conversation_id: str,
                               tenant_id: str, success: bool, processing_time: float = None,
                               amount: float = None, transaction_id: str = None):
        """Track payment completion event."""
        with self._lock:
            if payment_method not in self.payment_metrics:
                self.payment_metrics[payment_method] = PaymentMetrics(payment_method)
            
            metrics = self.payment_metrics[payment_method]
            
            if success:
                metrics.total_completed += 1
            else:
                metrics.total_failed += 1
            
            # Update average processing time
            if processing_time is not None:
                completed_count = metrics.total_completed + metrics.total_failed
                if completed_count > 1:
                    metrics.avg_processing_time = (
                        (metrics.avg_processing_time * (completed_count - 1) + processing_time) / completed_count
                    )
                else:
                    metrics.avg_processing_time = processing_time
            
            metrics.update_success_rate()
            
            self.logger.info(
                f"Payment completed: {payment_method} ({'success' if success else 'failed'})",
                extra={
                    'metric_category': MetricCategory.PAYMENT_SUCCESS.value,
                    'payment_method': payment_method,
                    'conversation_id': conversation_id,
                    'tenant_id': tenant_id,
                    'success': success,
                    'processing_time': processing_time,
                    'amount': amount,
                    'transaction_id': transaction_id,
                    'success_rate': metrics.success_rate,
                    'event_type': 'payment_completion'
                }
            )
    
    def track_payment_abandonment(self, payment_method: str, conversation_id: str,
                                tenant_id: str, step: str = None):
        """Track payment abandonment event."""
        with self._lock:
            if payment_method not in self.payment_metrics:
                self.payment_metrics[payment_method] = PaymentMetrics(payment_method)
            
            metrics = self.payment_metrics[payment_method]
            metrics.total_abandoned += 1
            metrics.update_success_rate()
            
            self.logger.info(
                f"Payment abandoned: {payment_method}",
                extra={
                    'metric_category': MetricCategory.PAYMENT_SUCCESS.value,
                    'payment_method': payment_method,
                    'conversation_id': conversation_id,
                    'tenant_id': tenant_id,
                    'abandonment_step': step,
                    'abandonment_rate': metrics.abandonment_rate,
                    'event_type': 'payment_abandonment'
                }
            )
    
    def track_escalation(self, escalation_reason: str, escalation_trigger: str,
                        conversation_id: str, tenant_id: str, context: Dict[str, Any] = None):
        """Track escalation event."""
        with self._lock:
            if escalation_reason not in self.escalation_metrics:
                self.escalation_metrics[escalation_reason] = EscalationMetrics(escalation_reason)
            
            metrics = self.escalation_metrics[escalation_reason]
            metrics.total_escalations += 1
            
            # Track escalation trigger breakdown
            if escalation_trigger == "explicit_human_request":
                metrics.explicit_human_requests += 1
            elif escalation_trigger == "payment_dispute":
                metrics.payment_disputes += 1
            elif escalation_trigger == "missing_information":
                metrics.missing_information += 1
            elif escalation_trigger == "repeated_failures":
                metrics.repeated_failures += 1
            elif escalation_trigger == "sensitive_content":
                metrics.sensitive_content += 1
            elif escalation_trigger == "user_frustration":
                metrics.user_frustration += 1
            elif escalation_trigger == "system_error":
                metrics.system_errors += 1
            
            self.logger.warning(
                f"Escalation tracked: {escalation_reason}",
                extra={
                    'metric_category': MetricCategory.ESCALATION_FREQUENCY.value,
                    'escalation_reason': escalation_reason,
                    'escalation_trigger': escalation_trigger,
                    'conversation_id': conversation_id,
                    'tenant_id': tenant_id,
                    'context': context or {},
                    'total_escalations': metrics.total_escalations,
                    'event_type': 'escalation'
                }
            )
    
    def track_performance(self, component: str, operation: str, duration: float, 
                         success: bool, conversation_id: str = None):
        """Track performance metrics for system components."""
        component_key = f"{component}_{operation}"
        
        with self._lock:
            if component_key not in self.performance_metrics:
                self.performance_metrics[component_key] = PerformanceMetrics(component_key)
            
            metrics = self.performance_metrics[component_key]
            metrics.total_operations += 1
            
            if success:
                metrics.successful_operations += 1
            else:
                metrics.failed_operations += 1
            
            metrics.add_response_time(duration)
            metrics.update_success_rate()
            
            self.logger.info(
                f"Performance tracked: {component_key}",
                extra={
                    'metric_category': MetricCategory.PERFORMANCE.value,
                    'component': component,
                    'operation': operation,
                    'duration': duration,
                    'success': success,
                    'conversation_id': conversation_id,
                    'avg_response_time': metrics.avg_response_time,
                    'success_rate': metrics.success_rate,
                    'event_type': 'performance_metric'
                }
            )
    
    def get_journey_completion_rates(self) -> Dict[str, float]:
        """Get current journey completion rates."""
        with self._lock:
            return {
                journey_type: metrics.completion_rate
                for journey_type, metrics in self.journey_metrics.items()
            }
    
    def get_payment_success_rates(self) -> Dict[str, float]:
        """Get current payment success rates."""
        with self._lock:
            return {
                payment_method: metrics.success_rate
                for payment_method, metrics in self.payment_metrics.items()
            }
    
    def get_escalation_frequencies(self) -> Dict[str, int]:
        """Get current escalation frequencies."""
        with self._lock:
            return {
                reason: metrics.total_escalations
                for reason, metrics in self.escalation_metrics.items()
            }
    
    def get_performance_summary(self) -> Dict[str, Dict[str, float]]:
        """Get performance summary for all components."""
        with self._lock:
            return self._get_performance_summary_unlocked()
    
    def _get_performance_summary_unlocked(self) -> Dict[str, Dict[str, float]]:
        """Get performance summary without acquiring lock (internal use only)."""
        return {
            component: {
                'avg_response_time': metrics.avg_response_time,
                'p95_response_time': metrics.p95_response_time,
                'p99_response_time': metrics.p99_response_time,
                'success_rate': metrics.success_rate,
                'error_rate': metrics.error_rate,
                'total_operations': metrics.total_operations
            }
            for component, metrics in self.performance_metrics.items()
        }
    
    def get_comprehensive_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary for monitoring dashboards."""
        with self._lock:
            return {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'journey_metrics': {
                    journey_type: {
                        'total_started': metrics.total_started,
                        'total_completed': metrics.total_completed,
                        'total_failed': metrics.total_failed,
                        'total_abandoned': metrics.total_abandoned,
                        'completion_rate': metrics.completion_rate,
                        'failure_rate': metrics.failure_rate,
                        'abandonment_rate': metrics.abandonment_rate,
                        'avg_duration': metrics.avg_duration
                    }
                    for journey_type, metrics in self.journey_metrics.items()
                },
                'payment_metrics': {
                    payment_method: {
                        'total_initiated': metrics.total_initiated,
                        'total_completed': metrics.total_completed,
                        'total_failed': metrics.total_failed,
                        'total_abandoned': metrics.total_abandoned,
                        'success_rate': metrics.success_rate,
                        'failure_rate': metrics.failure_rate,
                        'abandonment_rate': metrics.abandonment_rate,
                        'avg_amount': metrics.avg_amount,
                        'avg_processing_time': metrics.avg_processing_time
                    }
                    for payment_method, metrics in self.payment_metrics.items()
                },
                'escalation_metrics': {
                    reason: {
                        'total_escalations': metrics.total_escalations,
                        'explicit_human_requests': metrics.explicit_human_requests,
                        'payment_disputes': metrics.payment_disputes,
                        'missing_information': metrics.missing_information,
                        'repeated_failures': metrics.repeated_failures,
                        'sensitive_content': metrics.sensitive_content,
                        'user_frustration': metrics.user_frustration,
                        'system_errors': metrics.system_errors
                    }
                    for reason, metrics in self.escalation_metrics.items()
                },
                'performance_metrics': self._get_performance_summary_unlocked()
            }
    
    def aggregate_hourly_metrics(self):
        """Aggregate metrics for hourly reporting."""
        now = datetime.now(timezone.utc)
        
        if now - self.last_hourly_aggregation >= timedelta(hours=1):
            with self._lock:
                hourly_data = {
                    'timestamp': now.isoformat(),
                    'journey_completion_rates': self.get_journey_completion_rates(),
                    'payment_success_rates': self.get_payment_success_rates(),
                    'escalation_frequencies': self.get_escalation_frequencies(),
                    'performance_summary': self.get_performance_summary()
                }
                
                self.hourly_metrics['system'].append(hourly_data)
                
                # Keep only last 24 hours of hourly data
                if len(self.hourly_metrics['system']) > 24:
                    self.hourly_metrics['system'] = self.hourly_metrics['system'][-24:]
                
                self.last_hourly_aggregation = now
                
                self.logger.info(
                    "Hourly metrics aggregated",
                    extra={
                        'metric_category': MetricCategory.SYSTEM_HEALTH.value,
                        'aggregation_type': 'hourly',
                        'metrics_data': hourly_data,
                        'event_type': 'metrics_aggregation'
                    }
                )
    
    def aggregate_daily_metrics(self):
        """Aggregate metrics for daily reporting."""
        now = datetime.now(timezone.utc)
        
        if now - self.last_daily_aggregation >= timedelta(days=1):
            with self._lock:
                daily_data = {
                    'timestamp': now.isoformat(),
                    'comprehensive_summary': self.get_comprehensive_metrics_summary()
                }
                
                self.daily_metrics['system'].append(daily_data)
                
                # Keep only last 30 days of daily data
                if len(self.daily_metrics['system']) > 30:
                    self.daily_metrics['system'] = self.daily_metrics['system'][-30:]
                
                self.last_daily_aggregation = now
                
                self.logger.info(
                    "Daily metrics aggregated",
                    extra={
                        'metric_category': MetricCategory.SYSTEM_HEALTH.value,
                        'aggregation_type': 'daily',
                        'metrics_data': daily_data,
                        'event_type': 'metrics_aggregation'
                    }
                )


# Global metrics collector instance
metrics_collector = MetricsCollector()


def track_journey_metrics(journey_type: str):
    """Decorator for automatic journey metrics tracking."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            conversation_id = kwargs.get('conversation_id', 'unknown')
            tenant_id = kwargs.get('tenant_id', 'unknown')
            
            # Track journey start
            metrics_collector.track_journey_start(journey_type, conversation_id, tenant_id)
            
            start_time = time.time()
            success = False
            
            try:
                result = func(*args, **kwargs)
                success = True
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration = time.time() - start_time
                metrics_collector.track_journey_completion(
                    journey_type, conversation_id, tenant_id, success, duration
                )
        
        return wrapper
    return decorator


def track_payment_metrics(payment_method: str):
    """Decorator for automatic payment metrics tracking."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            conversation_id = kwargs.get('conversation_id', 'unknown')
            tenant_id = kwargs.get('tenant_id', 'unknown')
            amount = kwargs.get('amount')
            
            # Track payment initiation
            metrics_collector.track_payment_initiation(
                payment_method, conversation_id, tenant_id, amount
            )
            
            start_time = time.time()
            success = False
            
            try:
                result = func(*args, **kwargs)
                success = True
                return result
            except Exception as e:
                success = False
                raise
            finally:
                processing_time = time.time() - start_time
                metrics_collector.track_payment_completion(
                    payment_method, conversation_id, tenant_id, success, processing_time, amount
                )
        
        return wrapper
    return decorator