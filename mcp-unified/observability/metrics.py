from datetime import datetime, date
from typing import Dict, Any
import time
from collections import defaultdict
import asyncio

class MetricsCollector:
    def __init__(self):
        # In-memory storage for simplicity (reset on restart)
        # In production, this would be Redis or Prometheus
        self._tasks: Dict[date, list] = defaultdict(list)
        self._tokens: Dict[date, int] = defaultdict(int)
        self._latencies: Dict[date, list] = defaultdict(list)
        self._errors: Dict[str, int] = defaultdict(int)

    def record_task(self, success: bool, duration: float, tokens: int = 0, error: str = None):
        today = datetime.now().date()
        self._tasks[today].append({"success": success, "timestamp": time.time()})
        self._latencies[today].append(duration)
        if tokens:
            self._tokens[today] += tokens
        
        if error:
            self._errors[error] += 1

    def get_summary(self) -> Dict[str, Any]:
        today = datetime.now().date()
        
        tasks = self._tasks[today]
        total_tasks = len(tasks)
        success_tasks = len([t for t in tasks if t["success"]])
        failed_tasks = total_tasks - success_tasks
        
        latencies = self._latencies[today]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        
        return {
            "today": {
                "date": today.isoformat(),
                "total_tasks": total_tasks,
                "success_rate": round((success_tasks / total_tasks * 100), 1) if total_tasks else 0,
                "failed_tasks": failed_tasks,
                "tokens_used": self._tokens[today],
                "avg_latency_sec": round(avg_latency, 3)
            },
            "top_errors": dict(sorted(self._errors.items(), key=lambda item: item[1], reverse=True)[:5])
        }

metrics = MetricsCollector()
