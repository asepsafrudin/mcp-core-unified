"""
Production Monitoring System

Metrics, alerts, and dashboards for MCP.
Part of TASK-029: Phase 8 - Production Monitoring
"""

from .metrics import (
    MetricsCollector,
    MetricType,
    MetricValue,
    get_metrics_collector,
    record_metric,
    increment_counter,
    observe_histogram,
)
from .alerts import (
    AlertManager,
    AlertRule,
    Alert,
    AlertSeverity,
    AlertCondition,
    get_alert_manager,
)
from .dashboard import (
    DashboardAPI,
    get_health,
    get_metrics,
    get_alerts,
)

__all__ = [
    # Metrics
    "MetricsCollector",
    "MetricType",
    "MetricValue",
    "get_metrics_collector",
    "record_metric",
    "increment_counter",
    "observe_histogram",
    # Alerts
    "AlertManager",
    "AlertRule",
    "Alert",
    "AlertSeverity",
    "AlertCondition",
    "get_alert_manager",
    # Dashboard
    "DashboardAPI",
    "get_health",
    "get_metrics",
    "get_alerts",
]