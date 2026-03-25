"""
Dashboard API

REST API endpoints for monitoring dashboards.
Part of TASK-029: Phase 8 - Production Monitoring
"""

from typing import Dict, Any, List
from datetime import datetime

from .metrics import get_metrics_collector
from .alerts import get_alert_manager, AlertSeverity


class DashboardAPI:
    """API for monitoring dashboards"""
    
    @staticmethod
    def get_health_overview() -> Dict[str, Any]:
        """Get system health overview"""
        collector = get_metrics_collector()
        alert_manager = get_alert_manager()
        
        # Get key metrics
        metrics = {
            "requests_per_second": collector.get_summary("http_requests_total").get("latest", 0),
            "error_rate": collector.get_summary("http_errors_total").get("latest", 0),
            "avg_latency": collector.get_summary("http_request_duration").get("avg", 0),
        }
        
        # Get alerts
        alerts = alert_manager.get_stats()
        
        return {
            "status": "healthy" if alerts["critical_alerts"] == 0 else "degraded",
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics,
            "alerts": alerts,
        }
    
    @staticmethod
    def get_metrics_summary() -> Dict[str, Any]:
        """Get metrics summary"""
        collector = get_metrics_collector()
        return collector.export_json()
    
    @staticmethod
    def get_active_alerts(severity: str = None) -> List[Dict]:
        """Get active alerts"""
        alert_manager = get_alert_manager()
        sev = AlertSeverity(severity) if severity else None
        alerts = alert_manager.get_active_alerts(sev)
        return [{
            "id": a.alert_id,
            "rule": a.rule_name,
            "severity": a.severity.value,
            "message": a.message,
            "timestamp": a.timestamp,
        } for a in alerts]
    
    @staticmethod
    def get_prometheus_metrics() -> str:
        """Export metrics in Prometheus format"""
        return get_metrics_collector().export_prometheus()


# Convenience functions
def get_health() -> Dict[str, Any]:
    """Get health status"""
    return DashboardAPI.get_health_overview()


def get_metrics() -> Dict[str, Any]:
    """Get all metrics"""
    return DashboardAPI.get_metrics_summary()


def get_alerts(severity: str = None) -> List[Dict]:
    """Get alerts"""
    return DashboardAPI.get_active_alerts(severity)
