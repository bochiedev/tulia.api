"""
Monitoring system integration for real-time alerting and dashboard updates.

This module provides integration with external monitoring systems like
Prometheus, Grafana, DataDog, and custom monitoring solutions.

Requirements: 10.1, 10.4, 10.5
"""

import logging
import time
import json
import asyncio
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
import threading
from abc import ABC, abstractmethod

try:
    import requests
except ImportError:
    requests = None

try:
    from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, push_to_gateway
except ImportError:
    Counter = Histogram = Gauge = CollectorRegistry = push_to_gateway = None

from apps.bot.services.metrics_collector import metrics_collector, MetricCategory
from apps.bot.services.observability import observability_service


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MonitoringProvider(Enum):
    """Supported monitoring providers."""
    PROMETHEUS = "prometheus"
    DATADOG = "datadog"
    GRAFANA = "grafana"
    WEBHOOK = "webhook"
    CUSTOM = "custom"


@dataclass
class Alert:
    """Alert data structure."""
    title: str
    message: str
    severity: AlertSeverity
    category: str
    timestamp: datetime
    metadata: Dict[str, Any]
    tenant_id: Optional[str] = None
    conversation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            'title': self.title,
            'message': self.message,
            'severity': self.severity.value,
            'category': self.category,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata,
            'tenant_id': self.tenant_id,
            'conversation_id': self.conversation_id
        }


@dataclass
class MetricUpdate:
    """Metric update data structure."""
    metric_name: str
    metric_type: str  # counter, gauge, histogram
    value: float
    labels: Dict[str, str]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metric update to dictionary."""
        return {
            'metric_name': self.metric_name,
            'metric_type': self.metric_type,
            'value': self.value,
            'labels': self.labels,
            'timestamp': self.timestamp.isoformat()
        }


class MonitoringAdapter(ABC):
    """Abstract base class for monitoring system adapters."""
    
    @abstractmethod
    async def send_alert(self, alert: Alert) -> bool:
        """Send alert to monitoring system."""
        pass
    
    @abstractmethod
    async def send_metric(self, metric: MetricUpdate) -> bool:
        """Send metric update to monitoring system."""
        pass
    
    @abstractmethod
    async def send_batch_metrics(self, metrics: List[MetricUpdate]) -> bool:
        """Send batch of metric updates."""
        pass


class PrometheusAdapter(MonitoringAdapter):
    """Prometheus monitoring adapter."""
    
    def __init__(self, gateway_url: str, job_name: str = "tulia-ai"):
        """Initialize Prometheus adapter."""
        self.gateway_url = gateway_url
        self.job_name = job_name
        self.registry = CollectorRegistry() if CollectorRegistry else None
        self.metrics = {}
        self.logger = logging.getLogger("tulia.monitoring.prometheus")
        
        if not push_to_gateway:
            self.logger.warning("Prometheus client not available. Install prometheus_client package.")
    
    def _get_or_create_metric(self, metric_name: str, metric_type: str, labels: Dict[str, str]):
        """Get or create Prometheus metric."""
        if not self.registry:
            return None
        
        metric_key = f"{metric_name}_{metric_type}"
        
        if metric_key not in self.metrics:
            label_names = list(labels.keys())
            
            if metric_type == "counter":
                self.metrics[metric_key] = Counter(
                    metric_name, f"Tulia AI {metric_name}", label_names, registry=self.registry
                )
            elif metric_type == "gauge":
                self.metrics[metric_key] = Gauge(
                    metric_name, f"Tulia AI {metric_name}", label_names, registry=self.registry
                )
            elif metric_type == "histogram":
                self.metrics[metric_key] = Histogram(
                    metric_name, f"Tulia AI {metric_name}", label_names, registry=self.registry
                )
        
        return self.metrics.get(metric_key)
    
    async def send_alert(self, alert: Alert) -> bool:
        """Send alert as Prometheus metric."""
        try:
            # Convert alert to metric
            metric = MetricUpdate(
                metric_name="tulia_alerts_total",
                metric_type="counter",
                value=1,
                labels={
                    'severity': alert.severity.value,
                    'category': alert.category,
                    'tenant_id': alert.tenant_id or 'unknown'
                },
                timestamp=alert.timestamp
            )
            
            return await self.send_metric(metric)
        except Exception as e:
            self.logger.error(f"Failed to send alert to Prometheus: {e}")
            return False
    
    async def send_metric(self, metric: MetricUpdate) -> bool:
        """Send metric to Prometheus."""
        try:
            if not push_to_gateway or not self.registry:
                return False
            
            prom_metric = self._get_or_create_metric(
                metric.metric_name, metric.metric_type, metric.labels
            )
            
            if prom_metric:
                if metric.metric_type == "counter":
                    prom_metric.labels(**metric.labels).inc(metric.value)
                elif metric.metric_type == "gauge":
                    prom_metric.labels(**metric.labels).set(metric.value)
                elif metric.metric_type == "histogram":
                    prom_metric.labels(**metric.labels).observe(metric.value)
                
                # Push to gateway
                push_to_gateway(self.gateway_url, job=self.job_name, registry=self.registry)
                return True
            
            return False
        except Exception as e:
            self.logger.error(f"Failed to send metric to Prometheus: {e}")
            return False
    
    async def send_batch_metrics(self, metrics: List[MetricUpdate]) -> bool:
        """Send batch of metrics to Prometheus."""
        try:
            for metric in metrics:
                prom_metric = self._get_or_create_metric(
                    metric.metric_name, metric.metric_type, metric.labels
                )
                
                if prom_metric:
                    if metric.metric_type == "counter":
                        prom_metric.labels(**metric.labels).inc(metric.value)
                    elif metric.metric_type == "gauge":
                        prom_metric.labels(**metric.labels).set(metric.value)
                    elif metric.metric_type == "histogram":
                        prom_metric.labels(**metric.labels).observe(metric.value)
            
            # Push all metrics at once
            if push_to_gateway and self.registry:
                push_to_gateway(self.gateway_url, job=self.job_name, registry=self.registry)
                return True
            
            return False
        except Exception as e:
            self.logger.error(f"Failed to send batch metrics to Prometheus: {e}")
            return False


class WebhookAdapter(MonitoringAdapter):
    """Generic webhook monitoring adapter."""
    
    def __init__(self, webhook_url: str, headers: Dict[str, str] = None):
        """Initialize webhook adapter."""
        self.webhook_url = webhook_url
        self.headers = headers or {'Content-Type': 'application/json'}
        self.logger = logging.getLogger("tulia.monitoring.webhook")
        
        if not requests:
            self.logger.warning("Requests library not available. Install requests package.")
    
    async def send_alert(self, alert: Alert) -> bool:
        """Send alert via webhook."""
        try:
            if not requests:
                return False
            
            payload = {
                'type': 'alert',
                'data': alert.to_dict()
            }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers=self.headers,
                timeout=10
            )
            
            response.raise_for_status()
            return True
        except Exception as e:
            self.logger.error(f"Failed to send alert via webhook: {e}")
            return False
    
    async def send_metric(self, metric: MetricUpdate) -> bool:
        """Send metric via webhook."""
        try:
            if not requests:
                return False
            
            payload = {
                'type': 'metric',
                'data': metric.to_dict()
            }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers=self.headers,
                timeout=10
            )
            
            response.raise_for_status()
            return True
        except Exception as e:
            self.logger.error(f"Failed to send metric via webhook: {e}")
            return False
    
    async def send_batch_metrics(self, metrics: List[MetricUpdate]) -> bool:
        """Send batch of metrics via webhook."""
        try:
            if not requests:
                return False
            
            payload = {
                'type': 'batch_metrics',
                'data': [metric.to_dict() for metric in metrics]
            }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers=self.headers,
                timeout=30
            )
            
            response.raise_for_status()
            return True
        except Exception as e:
            self.logger.error(f"Failed to send batch metrics via webhook: {e}")
            return False


class MonitoringIntegration:
    """
    Central monitoring integration service.
    
    Manages connections to multiple monitoring systems and provides
    unified interface for sending alerts and metrics.
    """
    
    def __init__(self):
        """Initialize monitoring integration."""
        self.logger = logging.getLogger("tulia.monitoring")
        self.adapters: Dict[str, MonitoringAdapter] = {}
        self.alert_rules: Dict[str, Callable[[Dict[str, Any]], Optional[Alert]]] = {}
        
        # Background task management
        self._running = False
        self._background_task = None
        self._metrics_queue = []
        self._queue_lock = threading.Lock()
        
        # Setup default alert rules
        self._setup_default_alert_rules()
    
    def add_adapter(self, name: str, adapter: MonitoringAdapter):
        """Add monitoring adapter."""
        self.adapters[name] = adapter
        self.logger.info(f"Added monitoring adapter: {name}")
    
    def remove_adapter(self, name: str):
        """Remove monitoring adapter."""
        if name in self.adapters:
            del self.adapters[name]
            self.logger.info(f"Removed monitoring adapter: {name}")
    
    def add_alert_rule(self, name: str, rule_func: Callable[[Dict[str, Any]], Optional[Alert]]):
        """Add custom alert rule."""
        self.alert_rules[name] = rule_func
        self.logger.info(f"Added alert rule: {name}")
    
    async def send_alert(self, alert: Alert):
        """Send alert to all configured adapters."""
        if not self.adapters:
            self.logger.warning("No monitoring adapters configured")
            return
        
        self.logger.info(f"Sending alert: {alert.title} ({alert.severity.value})")
        
        for name, adapter in self.adapters.items():
            try:
                success = await adapter.send_alert(alert)
                if success:
                    self.logger.debug(f"Alert sent successfully to {name}")
                else:
                    self.logger.warning(f"Failed to send alert to {name}")
            except Exception as e:
                self.logger.error(f"Error sending alert to {name}: {e}")
    
    async def send_metric(self, metric: MetricUpdate):
        """Send metric to all configured adapters."""
        if not self.adapters:
            return
        
        for name, adapter in self.adapters.items():
            try:
                success = await adapter.send_metric(metric)
                if not success:
                    self.logger.warning(f"Failed to send metric to {name}")
            except Exception as e:
                self.logger.error(f"Error sending metric to {name}: {e}")
    
    def queue_metric(self, metric: MetricUpdate):
        """Queue metric for batch processing."""
        with self._queue_lock:
            self._metrics_queue.append(metric)
    
    async def flush_metrics_queue(self):
        """Flush queued metrics to all adapters."""
        with self._queue_lock:
            if not self._metrics_queue:
                return
            
            metrics_to_send = self._metrics_queue.copy()
            self._metrics_queue.clear()
        
        if not self.adapters:
            return
        
        for name, adapter in self.adapters.items():
            try:
                success = await adapter.send_batch_metrics(metrics_to_send)
                if success:
                    self.logger.debug(f"Batch metrics sent successfully to {name}")
                else:
                    self.logger.warning(f"Failed to send batch metrics to {name}")
            except Exception as e:
                self.logger.error(f"Error sending batch metrics to {name}: {e}")
    
    def _setup_default_alert_rules(self):
        """Setup default alert rules for common conditions."""
        
        def high_error_rate_rule(metrics: Dict[str, Any]) -> Optional[Alert]:
            """Alert on high error rate."""
            error_rate = metrics.get('error_rate', 0)
            if error_rate > 0.1:  # 10% error rate threshold
                return Alert(
                    title="High Error Rate Detected",
                    message=f"System error rate is {error_rate:.2%}, exceeding 10% threshold",
                    severity=AlertSeverity.ERROR,
                    category="system_health",
                    timestamp=datetime.now(timezone.utc),
                    metadata={'error_rate': error_rate}
                )
            return None
        
        def high_escalation_rate_rule(metrics: Dict[str, Any]) -> Optional[Alert]:
            """Alert on high escalation rate."""
            escalation_rate = metrics.get('escalation_rate', 0)
            if escalation_rate > 0.2:  # 20% escalation rate threshold
                return Alert(
                    title="High Escalation Rate Detected",
                    message=f"Escalation rate is {escalation_rate:.2%}, exceeding 20% threshold",
                    severity=AlertSeverity.WARNING,
                    category="customer_experience",
                    timestamp=datetime.now(timezone.utc),
                    metadata={'escalation_rate': escalation_rate}
                )
            return None
        
        def low_payment_success_rule(metrics: Dict[str, Any]) -> Optional[Alert]:
            """Alert on low payment success rate."""
            payment_success_rates = metrics.get('payment_success_rates', {})
            for method, rate in payment_success_rates.items():
                if rate < 0.8:  # 80% success rate threshold
                    return Alert(
                        title=f"Low Payment Success Rate: {method}",
                        message=f"Payment success rate for {method} is {rate:.2%}, below 80% threshold",
                        severity=AlertSeverity.WARNING,
                        category="payment_processing",
                        timestamp=datetime.now(timezone.utc),
                        metadata={'payment_method': method, 'success_rate': rate}
                    )
            return None
        
        def slow_response_time_rule(metrics: Dict[str, Any]) -> Optional[Alert]:
            """Alert on slow response times."""
            performance_metrics = metrics.get('performance_metrics', {})
            for component, perf_data in performance_metrics.items():
                p95_time = perf_data.get('p95_response_time', 0)
                if p95_time > 5.0:  # 5 second P95 threshold
                    return Alert(
                        title=f"Slow Response Time: {component}",
                        message=f"P95 response time for {component} is {p95_time:.2f}s, exceeding 5s threshold",
                        severity=AlertSeverity.WARNING,
                        category="performance",
                        timestamp=datetime.now(timezone.utc),
                        metadata={'component': component, 'p95_response_time': p95_time}
                    )
            return None
        
        # Register default rules
        self.alert_rules['high_error_rate'] = high_error_rate_rule
        self.alert_rules['high_escalation_rate'] = high_escalation_rate_rule
        self.alert_rules['low_payment_success'] = low_payment_success_rule
        self.alert_rules['slow_response_time'] = slow_response_time_rule
    
    async def check_alert_rules(self):
        """Check all alert rules against current metrics."""
        try:
            # Get current metrics summary
            metrics_summary = metrics_collector.get_comprehensive_metrics_summary()
            system_health = observability_service.get_system_health_summary()
            
            combined_metrics = {**metrics_summary, **system_health}
            
            # Check each alert rule
            for rule_name, rule_func in self.alert_rules.items():
                try:
                    alert = rule_func(combined_metrics)
                    if alert:
                        await self.send_alert(alert)
                except Exception as e:
                    self.logger.error(f"Error checking alert rule {rule_name}: {e}")
        
        except Exception as e:
            self.logger.error(f"Error checking alert rules: {e}")
    
    def start_background_monitoring(self, interval: int = 60):
        """Start background monitoring task."""
        if self._running:
            return
        
        self._running = True
        
        async def monitoring_loop():
            while self._running:
                try:
                    # Check alert rules
                    await self.check_alert_rules()
                    
                    # Flush metrics queue
                    await self.flush_metrics_queue()
                    
                    # Send system health metrics
                    await self._send_system_health_metrics()
                    
                except Exception as e:
                    self.logger.error(f"Error in monitoring loop: {e}")
                
                await asyncio.sleep(interval)
        
        # Start background task
        self._background_task = asyncio.create_task(monitoring_loop())
        self.logger.info(f"Started background monitoring with {interval}s interval")
    
    def stop_background_monitoring(self):
        """Stop background monitoring task."""
        self._running = False
        if self._background_task:
            self._background_task.cancel()
            self._background_task = None
        self.logger.info("Stopped background monitoring")
    
    async def _send_system_health_metrics(self):
        """Send system health metrics to monitoring systems."""
        try:
            health_summary = observability_service.get_system_health_summary()
            timestamp = datetime.now(timezone.utc)
            
            # Convert health summary to metrics
            metrics = [
                MetricUpdate(
                    metric_name="tulia_active_conversations",
                    metric_type="gauge",
                    value=health_summary.get('active_conversations', 0),
                    labels={'system': 'tulia'},
                    timestamp=timestamp
                ),
                MetricUpdate(
                    metric_name="tulia_error_rate",
                    metric_type="gauge",
                    value=health_summary.get('error_rate', 0),
                    labels={'system': 'tulia'},
                    timestamp=timestamp
                ),
                MetricUpdate(
                    metric_name="tulia_escalation_rate",
                    metric_type="gauge",
                    value=health_summary.get('escalation_rate', 0),
                    labels={'system': 'tulia'},
                    timestamp=timestamp
                )
            ]
            
            # Send metrics
            for metric in metrics:
                await self.send_metric(metric)
        
        except Exception as e:
            self.logger.error(f"Error sending system health metrics: {e}")


# Global monitoring integration instance
monitoring_integration = MonitoringIntegration()


def create_prometheus_adapter(gateway_url: str, job_name: str = "tulia-ai") -> PrometheusAdapter:
    """Create and configure Prometheus adapter."""
    return PrometheusAdapter(gateway_url, job_name)


def create_webhook_adapter(webhook_url: str, headers: Dict[str, str] = None) -> WebhookAdapter:
    """Create and configure webhook adapter."""
    return WebhookAdapter(webhook_url, headers)


def setup_monitoring(config: Dict[str, Any]):
    """Setup monitoring integration from configuration."""
    if 'prometheus' in config:
        prometheus_config = config['prometheus']
        adapter = create_prometheus_adapter(
            prometheus_config['gateway_url'],
            prometheus_config.get('job_name', 'tulia-ai')
        )
        monitoring_integration.add_adapter('prometheus', adapter)
    
    if 'webhook' in config:
        webhook_config = config['webhook']
        adapter = create_webhook_adapter(
            webhook_config['url'],
            webhook_config.get('headers')
        )
        monitoring_integration.add_adapter('webhook', adapter)
    
    # Start background monitoring if configured
    if config.get('background_monitoring', {}).get('enabled', False):
        interval = config['background_monitoring'].get('interval', 60)
        monitoring_integration.start_background_monitoring(interval)


# Convenience functions for common monitoring tasks

async def alert_high_error_rate(error_rate: float, threshold: float = 0.1):
    """Send alert for high error rate."""
    if error_rate > threshold:
        alert = Alert(
            title="High Error Rate Alert",
            message=f"Error rate {error_rate:.2%} exceeds threshold {threshold:.2%}",
            severity=AlertSeverity.ERROR,
            category="system_health",
            timestamp=datetime.now(timezone.utc),
            metadata={'error_rate': error_rate, 'threshold': threshold}
        )
        await monitoring_integration.send_alert(alert)


async def alert_payment_failure(payment_method: str, failure_rate: float, threshold: float = 0.2):
    """Send alert for payment failures."""
    if failure_rate > threshold:
        alert = Alert(
            title=f"Payment Failure Alert: {payment_method}",
            message=f"Payment failure rate {failure_rate:.2%} exceeds threshold {threshold:.2%}",
            severity=AlertSeverity.WARNING,
            category="payment_processing",
            timestamp=datetime.now(timezone.utc),
            metadata={
                'payment_method': payment_method,
                'failure_rate': failure_rate,
                'threshold': threshold
            }
        )
        await monitoring_integration.send_alert(alert)


async def alert_escalation_spike(escalation_count: int, threshold: int = 10):
    """Send alert for escalation spikes."""
    if escalation_count > threshold:
        alert = Alert(
            title="Escalation Spike Alert",
            message=f"Escalation count {escalation_count} exceeds threshold {threshold}",
            severity=AlertSeverity.WARNING,
            category="customer_experience",
            timestamp=datetime.now(timezone.utc),
            metadata={'escalation_count': escalation_count, 'threshold': threshold}
        )
        await monitoring_integration.send_alert(alert)