"""
Alerting System

Define alerts and notification rules.
Part of TASK-029: Phase 8 - Production Monitoring
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import logging

from .metrics import MetricValue, get_metrics_collector

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertCondition(Enum):
    """Alert condition types"""
    ABOVE = "above"
    BELOW = "below"
    EQUALS = "equals"
    CHANGE = "change"


@dataclass
class AlertRule:
    """An alert rule definition"""
    name: str
    metric_name: str
    condition: AlertCondition
    threshold: float
    severity: AlertSeverity
    duration: int = 60  # seconds
    description: str = ""
    enabled: bool = True
    
    def check(self, value: float) -> bool:
        """Check if value triggers alert"""
        if self.condition == AlertCondition.ABOVE:
            return value > self.threshold
        elif self.condition == AlertCondition.BELOW:
            return value < self.threshold
        elif self.condition == AlertCondition.EQUALS:
            return value == self.threshold
        return False


@dataclass
class Alert:
    """An active alert"""
    alert_id: str
    rule_name: str
    severity: AlertSeverity
    message: str
    metric_value: float
    timestamp: float
    acknowledged: bool = False
    resolved: bool = False
    resolved_at: Optional[float] = None


class AlertManager:
    """
    Manages alert rules and notifications.
    
    Features:
    - Multiple severity levels
    - Configurable conditions
    - Alert aggregation
    - Notification callbacks
    """
    
    def __init__(self):
        self._rules: Dict[str, AlertRule] = {}
        self._alerts: Dict[str, Alert] = {}
        self._active_since: Dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._check_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Notification callbacks by severity
        self._notifiers: Dict[AlertSeverity, List[Callable[[Alert], None]]] = {
            AlertSeverity.INFO: [],
            AlertSeverity.WARNING: [],
            AlertSeverity.CRITICAL: [],
        }
        
        logger.info("AlertManager initialized")
    
    async def start(self):
        """Start alert checking"""
        self._running = True
        self._check_task = asyncio.create_task(self._check_loop())
        
        # Subscribe to metrics
        get_metrics_collector().add_callback(self._on_metric)
        
        logger.info("AlertManager started")
    
    async def stop(self):
        """Stop alert checking"""
        self._running = False
        get_metrics_collector().remove_callback(self._on_metric)
        
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
        
        logger.info("AlertManager stopped")
    
    def add_rule(self, rule: AlertRule):
        """Add an alert rule"""
        self._rules[rule.name] = rule
        logger.info(f"Alert rule added: {rule.name}")
    
    def remove_rule(self, name: str):
        """Remove an alert rule"""
        if name in self._rules:
            del self._rules[name]
            logger.info(f"Alert rule removed: {name}")
    
    def add_notifier(
        self,
        severity: AlertSeverity,
        callback: Callable[[Alert], None]
    ):
        """Add a notification callback"""
        self._notifiers[severity].append(callback)
    
    def _on_metric(self, metric: MetricValue):
        """Handle metric update"""
        for rule in self._rules.values():
            if not rule.enabled:
                continue
            
            if rule.metric_name == metric.name:
                self._check_rule(rule, metric.value)
    
    def _check_rule(self, rule: AlertRule, value: float):
        """Check if rule is triggered"""
        triggered = rule.check(value)
        rule_key = f"{rule.name}"
        
        if triggered:
            now = time.time()
            
            if rule_key not in self._active_since:
                self._active_since[rule_key] = now
            
            # Check if duration exceeded
            elapsed = now - self._active_since[rule_key]
            if elapsed >= rule.duration:
                self._fire_alert(rule, value)
        else:
            # Reset if condition cleared
            if rule_key in self._active_since:
                del self._active_since[rule_key]
                self._resolve_alert(rule.name)
    
    def _fire_alert(self, rule: AlertRule, value: float):
        """Fire an alert"""
        alert_id = f"{rule.name}-{int(time.time())}"
        
        alert = Alert(
            alert_id=alert_id,
            rule_name=rule.name,
            severity=rule.severity,
            message=f"{rule.description or rule.name}: {value}",
            metric_value=value,
            timestamp=time.time(),
        )
        
        self._alerts[alert_id] = alert
        
        # Notify
        for callback in self._notifiers.get(rule.severity, []):
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Notifier error: {e}")
        
        logger.warning(f"ALERT [{rule.severity.value.upper()}]: {rule.name}")
    
    def _resolve_alert(self, rule_name: str):
        """Resolve alerts for a rule"""
        for alert in list(self._alerts.values()):
            if alert.rule_name == rule_name and not alert.resolved:
                alert.resolved = True
                alert.resolved_at = time.time()
                logger.info(f"Alert resolved: {rule_name}")
    
    async def _check_loop(self):
        """Background check loop"""
        while self._running:
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                break
    
    def get_active_alerts(
        self,
        severity: Optional[AlertSeverity] = None
    ) -> List[Alert]:
        """Get active alerts"""
        alerts = [
            a for a in self._alerts.values()
            if not a.resolved and not a.acknowledged
        ]
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert"""
        if alert_id in self._alerts:
            self._alerts[alert_id].acknowledged = True
            return True
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get alert statistics"""
        active = len([a for a in self._alerts.values() if not a.resolved])
        critical = len([
            a for a in self._alerts.values()
            if not a.resolved and a.severity == AlertSeverity.CRITICAL
        ])
        
        return {
            "total_rules": len(self._rules),
            "active_alerts": active,
            "critical_alerts": critical,
        }


# Global instance
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get or create global alert manager"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager
