"""
Metrics Collection System

Collect and aggregate metrics for monitoring and alerting.
Part of TASK-029: Phase 8 - Production Monitoring
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from collections import defaultdict, deque
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics"""
    COUNTER = "counter"      # Monotonically increasing
    GAUGE = "gauge"          # Can go up or down
    HISTOGRAM = "histogram"  # Distribution of values
    SUMMARY = "summary"      # Similar to histogram


@dataclass
class MetricValue:
    """A single metric value"""
    name: str
    value: float
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)
    metric_type: MetricType = MetricType.GAUGE


@dataclass
class MetricSeries:
    """Time series for a metric"""
    name: str
    metric_type: MetricType
    description: str = ""
    unit: str = ""
    values: deque = field(default_factory=lambda: deque(maxlen=1000))
    
    def add(self, value: float, labels: Optional[Dict[str, str]] = None):
        """Add a value to the series"""
        self.values.append(MetricValue(
            name=self.name,
            value=value,
            timestamp=time.time(),
            labels=labels or {},
            metric_type=self.metric_type
        ))
    
    def get_latest(self) -> Optional[MetricValue]:
        """Get the latest value"""
        return self.values[-1] if self.values else None
    
    def get_range(self, start_time: float, end_time: float) -> List[MetricValue]:
        """Get values within time range"""
        return [
            v for v in self.values
            if start_time <= v.timestamp <= end_time
        ]


class MetricsCollector:
    """
    Central metrics collector for MCP.
    
    Features:
    - Multiple metric types (counter, gauge, histogram)
    - Label support for dimensional metrics
    - Automatic aggregation
    - Export to various formats
    """
    
    def __init__(self, retention_seconds: int = 3600):
        self._metrics: Dict[str, MetricSeries] = {}
        self._lock = asyncio.Lock()
        self._retention_seconds = retention_seconds
        self._callbacks: List[Callable[[MetricValue], None]] = []
        
        # Counters for incrementing
        self._counters: Dict[str, float] = defaultdict(float)
        
        logger.info(f"MetricsCollector initialized (retention: {retention_seconds}s)")
    
    def register_metric(
        self,
        name: str,
        metric_type: MetricType,
        description: str = "",
        unit: str = "",
    ) -> MetricSeries:
        """Register a new metric"""
        if name not in self._metrics:
            self._metrics[name] = MetricSeries(
                name=name,
                metric_type=metric_type,
                description=description,
                unit=unit,
            )
            logger.info(f"Metric registered: {name} ({metric_type.value})")
        return self._metrics[name]
    
    def record(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ):
        """Record a metric value"""
        if name not in self._metrics:
            # Auto-register as gauge
            self.register_metric(name, MetricType.GAUGE)
        
        series = self._metrics[name]
        series.add(value, labels)
        
        # Notify callbacks
        metric_value = MetricValue(
            name=name,
            value=value,
            timestamp=time.time(),
            labels=labels or {},
            metric_type=series.metric_type
        )
        for callback in self._callbacks:
            try:
                callback(metric_value)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def increment(
        self,
        name: str,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None,
    ):
        """Increment a counter metric"""
        key = f"{name}:{str(sorted(labels.items())) if labels else ''}"
        self._counters[key] += value
        self.record(name, self._counters[key], labels)
    
    def decrement(
        self,
        name: str,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None,
    ):
        """Decrement a gauge metric"""
        key = f"{name}:{str(sorted(labels.items())) if labels else ''}"
        self._counters[key] -= value
        self.record(name, self._counters[key], labels)
    
    def observe(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ):
        """Observe a value for histogram/summary"""
        if name not in self._metrics:
            self.register_metric(name, MetricType.HISTOGRAM)
        
        self.record(name, value, labels)
    
    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get a metric series by name"""
        return self._metrics.get(name)
    
    def get_all_metrics(self) -> Dict[str, MetricSeries]:
        """Get all registered metrics"""
        return dict(self._metrics)
    
    def query(
        self,
        name: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> List[MetricValue]:
        """Query metric values"""
        series = self._metrics.get(name)
        if not series:
            return []
        
        now = time.time()
        start = start_time or (now - self._retention_seconds)
        end = end_time or now
        
        return series.get_range(start, end)
    
    def get_summary(self, name: str) -> Dict[str, Any]:
        """Get summary statistics for a metric"""
        series = self._metrics.get(name)
        if not series or not series.values:
            return {}
        
        values = [v.value for v in series.values]
        
        return {
            "name": name,
            "count": len(values),
            "latest": values[-1],
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
        }
    
    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format"""
        lines = []
        
        for name, series in self._metrics.items():
            # Add HELP and TYPE
            lines.append(f"# HELP {name} {series.description}")
            lines.append(f"# TYPE {name} {series.metric_type.value}")
            
            # Add values
            latest = series.get_latest()
            if latest:
                label_str = ",".join(
                    f'{k}="{v}"' for k, v in latest.labels.items()
                )
                if label_str:
                    lines.append(f"{name}{{{label_str}}} {latest.value}")
                else:
                    lines.append(f"{name} {latest.value}")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def export_json(self) -> Dict[str, Any]:
        """Export metrics as JSON"""
        result = {
            "timestamp": time.time(),
            "metrics": {}
        }
        
        for name, series in self._metrics.items():
            latest = series.get_latest()
            result["metrics"][name] = {
                "type": series.metric_type.value,
                "description": series.description,
                "unit": series.unit,
                "latest": latest.value if latest else None,
                "summary": self.get_summary(name),
            }
        
        return result
    
    def add_callback(self, callback: Callable[[MetricValue], None]):
        """Add a callback for metric updates"""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[MetricValue], None]):
        """Remove a callback"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get collector statistics"""
        return {
            "registered_metrics": len(self._metrics),
            "total_samples": sum(len(s.values) for s in self._metrics.values()),
            "retention_seconds": self._retention_seconds,
        }


# Global instance
_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create global metrics collector"""
    global _collector
    if _collector is None:
        _collector = MetricsCollector()
    return _collector


# Convenience functions
def record_metric(name: str, value: float, labels: Optional[Dict[str, str]] = None):
    """Record a metric value"""
    get_metrics_collector().record(name, value, labels)


def increment_counter(name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
    """Increment a counter"""
    get_metrics_collector().increment(name, value, labels)


def observe_histogram(name: str, value: float, labels: Optional[Dict[str, str]] = None):
    """Observe a histogram value"""
    get_metrics_collector().observe(name, value, labels)
