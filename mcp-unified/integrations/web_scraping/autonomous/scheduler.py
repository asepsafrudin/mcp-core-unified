"""
Adaptive Scheduler - Schedule web scraping tasks.

Berdasarkan Autonomous Knowledge Update System.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


class AdaptiveScheduler:
    """
    Adaptive scheduler untuk web scraping.
    
    Features:
    - Dynamic scheduling berdasarkan content volatility
    - Priority-based execution
    - Resource-aware scheduling
    """
    
    def __init__(self, max_concurrent: int = 3):
        """
        Initialize scheduler.
        
        Args:
            max_concurrent: Maximum concurrent scraping tasks
        """
        self.max_concurrent = max_concurrent
        self.scheduled_tasks: List[Dict] = []
        self.running_tasks: List[Dict] = []
    
    async def schedule_task(
        self,
        url: str,
        domain: str,
        priority: str = "medium",
        interval: Optional[str] = None,
    ) -> str:
        """
        Schedule scraping task.
        
        Args:
            url: URL to scrape
            domain: Legal domain
            priority: Task priority (high/medium/low)
            interval: Repeat interval (hourly/daily/weekly/monthly)
            
        Returns:
            Task ID
        """
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(url) % 10000}"
        
        task = {
            "id": task_id,
            "url": url,
            "domain": domain,
            "priority": priority,
            "interval": interval,
            "scheduled_at": datetime.now(),
            "next_run": datetime.now(),
            "status": "scheduled",
            "run_count": 0,
        }
        
        self.scheduled_tasks.append(task)
        
        return task_id
    
    async def get_next_tasks(self, limit: int = 5) -> List[Dict]:
        """
        Get next tasks yang siap dijalankan.
        
        Args:
            limit: Maximum number of tasks
            
        Returns:
            List of tasks
        """
        now = datetime.now()
        
        # Filter tasks yang ready
        ready_tasks = [
            t for t in self.scheduled_tasks
            if t["status"] == "scheduled" and t["next_run"] <= now
        ]
        
        # Sort by priority dan scheduled time
        priority_order = {"high": 0, "medium": 1, "low": 2}
        ready_tasks.sort(
            key=lambda t: (priority_order.get(t["priority"], 3), t["scheduled_at"])
        )
        
        return ready_tasks[:limit]
    
    async def complete_task(self, task_id: str, success: bool = True):
        """
        Mark task as complete.
        
        Args:
            task_id: Task ID
            success: Whether task succeeded
        """
        for task in self.scheduled_tasks:
            if task["id"] == task_id:
                task["run_count"] += 1
                task["last_run"] = datetime.now()
                
                if success and task.get("interval"):
                    # Reschedule
                    task["next_run"] = self._calculate_next_run(
                        task["interval"],
                        task["last_run"]
                    )
                    task["status"] = "scheduled"
                else:
                    task["status"] = "completed" if success else "failed"
                
                break
    
    def _calculate_next_run(self, interval: str, last_run: datetime) -> datetime:
        """Calculate next run time berdasarkan interval."""
        intervals = {
            "hourly": timedelta(hours=1),
            "daily": timedelta(days=1),
            "weekly": timedelta(weeks=1),
            "monthly": timedelta(days=30),
        }
        
        return last_run + intervals.get(interval, timedelta(days=1))