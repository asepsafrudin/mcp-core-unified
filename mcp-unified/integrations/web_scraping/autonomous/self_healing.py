"""
Self-Healing Manager - Auto-recovery dari failures.

Berdasarkan Autonomous Knowledge Update System.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class FailureRecord:
    """Record dari failure."""
    url: str
    error: str
    timestamp: datetime
    retry_count: int = 0
    resolved: bool = False


class SelfHealingManager:
    """
    Manager untuk self-healing capabilities.
    
    Features:
    - Failure tracking
    - Automatic retry dengan backoff
    - Alternative strategy selection
    - Health monitoring
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: int = 60,
        enable_auto_heal: bool = True,
    ):
        """
        Initialize self-healing manager.
        
        Args:
            max_retries: Maximum retry attempts
            base_delay: Base delay dalam seconds
            enable_auto_heal: Enable automatic healing
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.enable_auto_heal = enable_auto_heal
        
        self.failure_history: List[FailureRecord] = []
        self.healing_strategies: Dict[str, Any] = {}
    
    def record_failure(self, url: str, error: str) -> FailureRecord:
        """
        Record failure untuk tracking.
        
        Args:
            url: URL yang failed
            error: Error message
            
        Returns:
            FailureRecord
        """
        # Check untuk existing record
        existing = None
        for record in self.failure_history:
            if record.url == url and not record.resolved:
                existing = record
                break
        
        if existing:
            existing.retry_count += 1
            existing.timestamp = datetime.now()
            return existing
        
        # Create new record
        record = FailureRecord(
            url=url,
            error=error,
            timestamp=datetime.now(),
            retry_count=1,
        )
        self.failure_history.append(record)
        
        return record
    
    def should_retry(self, url: str) -> bool:
        """
        Check apakah URL boleh diretry.
        
        Args:
            url: URL to check
            
        Returns:
            True jika boleh retry
        """
        for record in self.failure_history:
            if record.url == url and not record.resolved:
                return record.retry_count < self.max_retries
        
        return True
    
    def get_retry_delay(self, url: str) -> int:
        """
        Get retry delay dengan exponential backoff.
        
        Args:
            url: URL yang akan diretry
            
        Returns:
            Delay dalam seconds
        """
        for record in self.failure_history:
            if record.url == url:
                # Exponential backoff: 60s, 120s, 240s
                return self.base_delay * (2 ** (record.retry_count - 1))
        
        return self.base_delay
    
    def resolve_failure(self, url: str):
        """
        Mark failure as resolved.
        
        Args:
            url: URL yang berhasil
        """
        for record in self.failure_history:
            if record.url == url:
                record.resolved = True
                break
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status dari system.
        
        Returns:
            Health status dictionary
        """
        total_failures = len(self.failure_history)
        unresolved = sum(1 for r in self.failure_history if not r.resolved)
        
        return {
            "total_failures": total_failures,
            "unresolved_failures": unresolved,
            "resolved_failures": total_failures - unresolved,
            "health_score": 1.0 - (unresolved / max(total_failures, 1)),
            "status": "healthy" if unresolved == 0 else "degraded" if unresolved < 5 else "unhealthy",
        }
    
    def get_healing_strategy(self, error: str) -> Optional[str]:
        """
        Get healing strategy untuk specific error.
        
        Args:
            error: Error message
            
        Returns:
            Strategy name atau None
        """
        error_lower = error.lower()
        
        if "timeout" in error_lower:
            return "increase_timeout"
        elif "blocked" in error_lower or "forbidden" in error_lower:
            return "rotate_user_agent"
        elif "not found" in error_lower or "404" in error_lower:
            return "skip_url"
        elif "rate" in error_lower or "429" in error_lower:
            return "increase_delay"
        
        return None