"""
Canary Deployment System

Gradual rollout with automated rollback capabilities.
Part of TASK-029: Phase 8 - Soft Launch Infrastructure
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CanaryStatus(Enum):
    """Canary deployment status"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class CanaryStage(Enum):
    """Canary deployment stages"""
    STAGE_1 = 5      # 5% traffic
    STAGE_2 = 25     # 25% traffic
    STAGE_3 = 50     # 50% traffic
    STAGE_4 = 100    # 100% traffic (full rollout)


@dataclass
class CanaryConfig:
    """Configuration for canary deployment"""
    # Traffic split percentages for each stage
    stages: List[int] = field(default_factory=lambda: [5, 25, 50, 100])
    
    # Duration to hold at each stage (seconds)
    stage_duration: int = 300  # 5 minutes
    
    # Health check thresholds
    max_error_rate: float = 0.01  # 1%
    max_latency_p95: float = 500  # ms
    min_success_rate: float = 0.99  # 99%
    
    # Auto-rollback on failure
    auto_rollback: bool = True
    
    # Metrics collection window
    metrics_window: int = 60  # seconds


@dataclass
class CanaryDeployment:
    """A canary deployment instance"""
    deployment_id: str
    service_name: str
    version: str
    
    config: CanaryConfig = field(default_factory=CanaryConfig)
    status: CanaryStatus = CanaryStatus.PENDING
    current_stage: int = 0  # Index into stages
    
    # Timing
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    # Metrics
    total_requests: int = 0
    error_count: int = 0
    latency_sum: float = 0.0
    
    # Stage metrics
    stage_start_time: Optional[float] = None
    stage_metrics: Dict[int, dict] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "deployment_id": self.deployment_id,
            "service_name": self.service_name,
            "version": self.version,
            "status": self.status.value,
            "current_stage": self.current_stage,
            "traffic_percentage": self.get_current_traffic_percentage(),
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metrics": {
                "total_requests": self.total_requests,
                "error_count": self.error_count,
                "error_rate": self.get_error_rate(),
            },
        }
    
    def get_current_traffic_percentage(self) -> int:
        """Get current traffic percentage"""
        if self.current_stage < len(self.config.stages):
            return self.config.stages[self.current_stage]
        return 100
    
    def get_error_rate(self) -> float:
        """Calculate error rate"""
        if self.total_requests == 0:
            return 0.0
        return self.error_count / self.total_requests
    
    def record_request(self, success: bool, latency_ms: float):
        """Record a request metric"""
        self.total_requests += 1
        if not success:
            self.error_count += 1
        self.latency_sum += latency_ms


class CanaryDeploymentManager:
    """
    Manages canary deployments with gradual rollout and auto-rollback.
    
    Features:
    - Multi-stage rollout (5%, 25%, 50%, 100%)
    - Automated health checks
    - Auto-rollback on failure
    - Manual approval gates
    """
    
    def __init__(self):
        self._deployments: Dict[str, CanaryDeployment] = {}
        self._lock = asyncio.Lock()
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Callbacks
        self._on_stage_complete: Optional[Callable[[CanaryDeployment], None]] = None
        self._on_rollback: Optional[Callable[[CanaryDeployment, str], None]] = None
        
        logger.info("CanaryDeploymentManager initialized")
    
    async def start(self):
        """Start the canary manager"""
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("CanaryDeploymentManager started")
    
    async def stop(self):
        """Stop the canary manager"""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("CanaryDeploymentManager stopped")
    
    async def create_deployment(
        self,
        deployment_id: str,
        service_name: str,
        version: str,
        config: Optional[CanaryConfig] = None,
    ) -> CanaryDeployment:
        """Create a new canary deployment"""
        async with self._lock:
            if deployment_id in self._deployments:
                raise ValueError(f"Deployment {deployment_id} already exists")
            
            deployment = CanaryDeployment(
                deployment_id=deployment_id,
                service_name=service_name,
                version=version,
                config=config or CanaryConfig(),
            )
            self._deployments[deployment_id] = deployment
            
            logger.info(f"Canary deployment created: {deployment_id}")
            return deployment
    
    async def start_deployment(self, deployment_id: str) -> bool:
        """Start a canary deployment"""
        async with self._lock:
            if deployment_id not in self._deployments:
                return False
            
            deployment = self._deployments[deployment_id]
            if deployment.status != CanaryStatus.PENDING:
                logger.warning(f"Cannot start deployment {deployment_id}: status is {deployment.status}")
                return False
            
            deployment.status = CanaryStatus.RUNNING
            deployment.started_at = time.time()
            deployment.stage_start_time = time.time()
            
            logger.info(f"Canary deployment started: {deployment_id}")
            return True
    
    async def pause_deployment(self, deployment_id: str) -> bool:
        """Pause a running deployment"""
        async with self._lock:
            if deployment_id not in self._deployments:
                return False
            
            deployment = self._deployments[deployment_id]
            if deployment.status == CanaryStatus.RUNNING:
                deployment.status = CanaryStatus.PAUSED
                logger.info(f"Canary deployment paused: {deployment_id}")
                return True
            return False
    
    async def resume_deployment(self, deployment_id: str) -> bool:
        """Resume a paused deployment"""
        async with self._lock:
            if deployment_id not in self._deployments:
                return False
            
            deployment = self._deployments[deployment_id]
            if deployment.status == CanaryStatus.PAUSED:
                deployment.status = CanaryStatus.RUNNING
                deployment.stage_start_time = time.time()
                logger.info(f"Canary deployment resumed: {deployment_id}")
                return True
            return False
    
    async def promote_deployment(self, deployment_id: str) -> bool:
        """Manually promote to next stage"""
        async with self._lock:
            if deployment_id not in self._deployments:
                return False
            
            deployment = self._deployments[deployment_id]
            if deployment.status != CanaryStatus.RUNNING:
                return False
            
            return await self._advance_stage(deployment)
    
    async def rollback_deployment(
        self,
        deployment_id: str,
        reason: str = "manual",
    ) -> bool:
        """Rollback a deployment"""
        async with self._lock:
            if deployment_id not in self._deployments:
                return False
            
            deployment = self._deployments[deployment_id]
            deployment.status = CanaryStatus.ROLLED_BACK
            deployment.completed_at = time.time()
            
            if self._on_rollback:
                try:
                    self._on_rollback(deployment, reason)
                except Exception as e:
                    logger.error(f"Rollback callback error: {e}")
            
            logger.info(f"Canary deployment rolled back: {deployment_id} - {reason}")
            return True
    
    async def get_deployment(self, deployment_id: str) -> Optional[CanaryDeployment]:
        """Get deployment by ID"""
        async with self._lock:
            return self._deployments.get(deployment_id)
    
    async def list_deployments(
        self,
        service_name: Optional[str] = None,
        status: Optional[CanaryStatus] = None,
    ) -> List[CanaryDeployment]:
        """List deployments with optional filters"""
        async with self._lock:
            deployments = list(self._deployments.values())
            
            if service_name:
                deployments = [d for d in deployments if d.service_name == service_name]
            
            if status:
                deployments = [d for d in deployments if d.status == status]
            
            return deployments
    
    async def _monitor_loop(self):
        """Background monitoring loop"""
        while self._running:
            try:
                await self._check_deployments()
                await asyncio.sleep(10)  # Check every 10 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(5)
    
    async def _check_deployments(self):
        """Check all running deployments"""
        async with self._lock:
            for deployment in self._deployments.values():
                if deployment.status == CanaryStatus.RUNNING:
                    await self._evaluate_deployment(deployment)
    
    async def _evaluate_deployment(self, deployment: CanaryDeployment):
        """Evaluate deployment health and progress"""
        # Check if we've been in current stage long enough
        if deployment.stage_start_time:
            elapsed = time.time() - deployment.stage_start_time
            
            if elapsed < deployment.config.stage_duration:
                # Still in evaluation period
                # Check health metrics
                if not self._check_health(deployment):
                    if deployment.config.auto_rollback:
                        await self.rollback_deployment(
                            deployment.deployment_id,
                            "health_check_failed"
                        )
                return
            
            # Stage duration completed, check if we can advance
            if self._check_health(deployment):
                await self._advance_stage(deployment)
            else:
                # Health check failed, stay in current stage
                logger.warning(
                    f"Deployment {deployment.deployment_id} health check failed, "
                    f"staying at stage {deployment.current_stage}"
                )
    
    def _check_health(self, deployment: CanaryDeployment) -> bool:
        """Check deployment health metrics"""
        # Check error rate
        error_rate = deployment.get_error_rate()
        if error_rate > deployment.config.max_error_rate:
            logger.warning(
                f"Deployment {deployment.deployment_id} error rate {error_rate:.2%} "
                f"exceeds threshold {deployment.config.max_error_rate:.2%}"
            )
            return False
        
        # Check success rate
        success_rate = 1.0 - error_rate
        if success_rate < deployment.config.min_success_rate:
            logger.warning(
                f"Deployment {deployment.deployment_id} success rate {success_rate:.2%} "
                f"below threshold {deployment.config.min_success_rate:.2%}"
            )
            return False
        
        return True
    
    async def _advance_stage(self, deployment: CanaryDeployment) -> bool:
        """Advance to next stage"""
        deployment.current_stage += 1
        
        # Check if completed
        if deployment.current_stage >= len(deployment.config.stages):
            deployment.status = CanaryStatus.COMPLETED
            deployment.completed_at = time.time()
            logger.info(f"Canary deployment completed: {deployment.deployment_id}")
            return True
        
        # Move to next stage
        deployment.stage_start_time = time.time()
        current_percentage = deployment.get_current_traffic_percentage()
        
        if self._on_stage_complete:
            try:
                self._on_stage_complete(deployment)
            except Exception as e:
                logger.error(f"Stage complete callback error: {e}")
        
        logger.info(
            f"Deployment {deployment.deployment_id} advanced to stage "
            f"{deployment.current_stage} ({current_percentage}% traffic)"
        )
        return True
    
    def on_stage_complete(self, callback: Callable[[CanaryDeployment], None]):
        """Set callback for stage completion"""
        self._on_stage_complete = callback
    
    def on_rollback(self, callback: Callable[[CanaryDeployment, str], None]):
        """Set callback for rollback"""
        self._on_rollback = callback
    
    def get_stats(self) -> dict:
        """Get manager statistics"""
        total = len(self._deployments)
        by_status = {}
        
        for deployment in self._deployments.values():
            status = deployment.status.value
            by_status[status] = by_status.get(status, 0) + 1
        
        return {
            "total_deployments": total,
            "by_status": by_status,
        }


# Global instance
_canary_manager: Optional[CanaryDeploymentManager] = None


def get_canary_manager() -> CanaryDeploymentManager:
    """Get or create global canary manager"""
    global _canary_manager
    if _canary_manager is None:
        _canary_manager = CanaryDeploymentManager()
    return _canary_manager
