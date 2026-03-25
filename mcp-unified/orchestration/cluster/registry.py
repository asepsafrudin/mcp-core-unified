"""
Cluster Registry Module

Manages multi-cluster registration, discovery, and health monitoring.
Part of TASK-029: Phase 8 - Advanced Orchestration
"""

import asyncio
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Set
from enum import Enum
from datetime import datetime, timedelta
import hashlib
import logging

logger = logging.getLogger(__name__)


class ClusterStatus(Enum):
    """Cluster health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class ClusterCapability(Enum):
    """Cluster capabilities"""
    COMPUTE = "compute"
    STORAGE = "storage"
    GPU = "gpu"
    MEMORY_INTENSIVE = "memory_intensive"
    NETWORK_INTENSIVE = "network_intensive"


@dataclass
class ClusterResource:
    """Resource information for a cluster"""
    cpu_cores: int = 0
    memory_gb: float = 0.0
    storage_gb: float = 0.0
    gpu_count: int = 0
    
    # Utilization (0-100)
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    storage_percent: float = 0.0
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ClusterInfo:
    """Information about a cluster"""
    cluster_id: str
    name: str
    region: str
    endpoint: str  # API endpoint for this cluster
    status: ClusterStatus = ClusterStatus.HEALTHY
    
    # Capabilities
    capabilities: Set[ClusterCapability] = field(default_factory=set)
    
    # Resources
    resources: ClusterResource = field(default_factory=ClusterResource)
    
    # Metadata
    version: str = "1.0.0"
    tags: Dict[str, str] = field(default_factory=dict)
    
    # Health tracking
    last_heartbeat: float = field(default_factory=time.time)
    heartbeat_interval: int = 30  # seconds
    missed_heartbeats: int = 0
    max_missed_heartbeats: int = 3
    
    # Task tracking
    active_tasks: int = 0
    queued_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    
    def to_dict(self) -> dict:
        return {
            "cluster_id": self.cluster_id,
            "name": self.name,
            "region": self.region,
            "endpoint": self.endpoint,
            "status": self.status.value,
            "capabilities": [c.value for c in self.capabilities],
            "resources": self.resources.to_dict(),
            "version": self.version,
            "tags": self.tags,
            "last_heartbeat": self.last_heartbeat,
            "heartbeat_interval": self.heartbeat_interval,
            "missed_heartbeats": self.missed_heartbeats,
            "active_tasks": self.active_tasks,
            "queued_tasks": self.queued_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ClusterInfo":
        """Create ClusterInfo from dictionary"""
        capabilities = {ClusterCapability(c) for c in data.get("capabilities", [])}
        resources = ClusterResource(**data.get("resources", {}))
        
        return cls(
            cluster_id=data["cluster_id"],
            name=data["name"],
            region=data["region"],
            endpoint=data["endpoint"],
            status=ClusterStatus(data.get("status", "healthy")),
            capabilities=capabilities,
            resources=resources,
            version=data.get("version", "1.0.0"),
            tags=data.get("tags", {}),
            last_heartbeat=data.get("last_heartbeat", time.time()),
            heartbeat_interval=data.get("heartbeat_interval", 30),
            missed_heartbeats=data.get("missed_heartbeats", 0),
            active_tasks=data.get("active_tasks", 0),
            queued_tasks=data.get("queued_tasks", 0),
            completed_tasks=data.get("completed_tasks", 0),
            failed_tasks=data.get("failed_tasks", 0),
        )
    
    def is_healthy(self) -> bool:
        """Check if cluster is healthy"""
        return (
            self.status == ClusterStatus.HEALTHY
            and self.missed_heartbeats < self.max_missed_heartbeats
        )
    
    def update_heartbeat(self):
        """Update heartbeat timestamp"""
        self.last_heartbeat = time.time()
        self.missed_heartbeats = 0
    
    def check_heartbeat_timeout(self) -> bool:
        """Check if cluster has missed heartbeats"""
        elapsed = time.time() - self.last_heartbeat
        expected_intervals = elapsed / self.heartbeat_interval
        
        if expected_intervals > 1:
            self.missed_heartbeats = int(expected_intervals)
        
        return self.missed_heartbeats >= self.max_missed_heartbeats


class ClusterRegistry:
    """
    Registry for managing multiple clusters in a federated MCP deployment.
    
    Features:
    - Cluster registration/deregistration
    - Health monitoring
    - Capability discovery
    - Resource tracking
    """
    
    def __init__(self):
        self._clusters: Dict[str, ClusterInfo] = {}
        self._lock = asyncio.Lock()
        self._health_check_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info("ClusterRegistry initialized")
    
    async def start(self):
        """Start the cluster registry with health monitoring"""
        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("ClusterRegistry started")
    
    async def stop(self):
        """Stop the cluster registry"""
        self._running = False
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        logger.info("ClusterRegistry stopped")
    
    async def register_cluster(
        self,
        cluster_id: str,
        name: str,
        region: str,
        endpoint: str,
        capabilities: Optional[List[ClusterCapability]] = None,
        resources: Optional[ClusterResource] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> ClusterInfo:
        """
        Register a new cluster in the registry.
        
        Args:
            cluster_id: Unique identifier for the cluster
            name: Human-readable name
            region: Geographic region
            endpoint: API endpoint URL
            capabilities: List of cluster capabilities
            resources: Resource information
            tags: Additional metadata tags
        
        Returns:
            ClusterInfo object
        """
        async with self._lock:
            if cluster_id in self._clusters:
                logger.warning(f"Cluster {cluster_id} already registered, updating info")
            
            cluster = ClusterInfo(
                cluster_id=cluster_id,
                name=name,
                region=region,
                endpoint=endpoint,
                capabilities=set(capabilities or []),
                resources=resources or ClusterResource(),
                tags=tags or {},
            )
            
            self._clusters[cluster_id] = cluster
            logger.info(f"Cluster registered: {cluster_id} ({name}) in {region}")
            
            return cluster
    
    async def deregister_cluster(self, cluster_id: str) -> bool:
        """
        Deregister a cluster from the registry.
        
        Args:
            cluster_id: Cluster identifier
        
        Returns:
            True if deregistered, False if not found
        """
        async with self._lock:
            if cluster_id not in self._clusters:
                logger.warning(f"Cluster {cluster_id} not found for deregistration")
                return False
            
            del self._clusters[cluster_id]
            logger.info(f"Cluster deregistered: {cluster_id}")
            return True
    
    async def get_cluster(self, cluster_id: str) -> Optional[ClusterInfo]:
        """Get cluster information by ID"""
        async with self._lock:
            return self._clusters.get(cluster_id)
    
    async def get_all_clusters(self) -> List[ClusterInfo]:
        """Get all registered clusters"""
        async with self._lock:
            return list(self._clusters.values())
    
    async def get_healthy_clusters(self) -> List[ClusterInfo]:
        """Get all healthy clusters"""
        async with self._lock:
            return [c for c in self._clusters.values() if c.is_healthy()]
    
    async def get_clusters_by_region(self, region: str) -> List[ClusterInfo]:
        """Get clusters in a specific region"""
        async with self._lock:
            return [c for c in self._clusters.values() if c.region == region]
    
    async def get_clusters_by_capability(
        self, capability: ClusterCapability
    ) -> List[ClusterInfo]:
        """Get clusters with specific capability"""
        async with self._lock:
            return [
                c for c in self._clusters.values()
                if capability in c.capabilities and c.is_healthy()
            ]
    
    async def update_cluster_status(
        self, cluster_id: str, status: ClusterStatus
    ) -> bool:
        """Update cluster status"""
        async with self._lock:
            if cluster_id not in self._clusters:
                return False
            
            self._clusters[cluster_id].status = status
            logger.info(f"Cluster {cluster_id} status updated to {status.value}")
            return True
    
    async def update_cluster_resources(
        self, cluster_id: str, resources: ClusterResource
    ) -> bool:
        """Update cluster resource information"""
        async with self._lock:
            if cluster_id not in self._clusters:
                return False
            
            self._clusters[cluster_id].resources = resources
            return True
    
    async def update_heartbeat(self, cluster_id: str) -> bool:
        """Update cluster heartbeat"""
        async with self._lock:
            if cluster_id not in self._clusters:
                return False
            
            self._clusters[cluster_id].update_heartbeat()
            return True
    
    async def update_task_counts(
        self,
        cluster_id: str,
        active: Optional[int] = None,
        queued: Optional[int] = None,
        completed: Optional[int] = None,
        failed: Optional[int] = None,
    ) -> bool:
        """Update task counts for a cluster"""
        async with self._lock:
            if cluster_id not in self._clusters:
                return False
            
            cluster = self._clusters[cluster_id]
            if active is not None:
                cluster.active_tasks = active
            if queued is not None:
                cluster.queued_tasks = queued
            if completed is not None:
                cluster.completed_tasks = completed
            if failed is not None:
                cluster.failed_tasks = failed
            
            return True
    
    async def find_best_cluster_for_task(
        self,
        required_capabilities: Optional[List[ClusterCapability]] = None,
        prefer_low_load: bool = True,
    ) -> Optional[ClusterInfo]:
        """
        Find the best cluster for executing a task.
        
        Args:
            required_capabilities: Required cluster capabilities
            prefer_low_load: Prefer clusters with lower load
        
        Returns:
            Best matching cluster or None
        """
        async with self._lock:
            candidates = list(self._clusters.values())
            
            # Filter by health
            candidates = [c for c in candidates if c.is_healthy()]
            
            # Filter by capabilities
            if required_capabilities:
                required = set(required_capabilities)
                candidates = [
                    c for c in candidates
                    if required.issubset(c.capabilities)
                ]
            
            if not candidates:
                return None
            
            # Sort by load (if prefer_low_load)
            if prefer_low_load:
                candidates.sort(key=lambda c: (
                    c.active_tasks + c.queued_tasks,
                    c.resources.cpu_percent,
                ))
            
            return candidates[0] if candidates else None
    
    async def _health_check_loop(self):
        """Background task for health checking"""
        while self._running:
            try:
                await self._check_cluster_health()
                await asyncio.sleep(10)  # Check every 10 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(5)
    
    async def _check_cluster_health(self):
        """Check health of all clusters"""
        async with self._lock:
            for cluster_id, cluster in self._clusters.items():
                # Check heartbeat timeout
                if cluster.check_heartbeat_timeout():
                    if cluster.status != ClusterStatus.OFFLINE:
                        logger.warning(
                            f"Cluster {cluster_id} marked offline - "
                            f"missed {cluster.missed_heartbeats} heartbeats"
                        )
                        cluster.status = ClusterStatus.OFFLINE
                
                # Check resource utilization
                elif cluster.resources.cpu_percent > 90:
                    if cluster.status != ClusterStatus.DEGRADED:
                        logger.warning(
                            f"Cluster {cluster_id} marked degraded - "
                            f"high CPU: {cluster.resources.cpu_percent}%"
                        )
                        cluster.status = ClusterStatus.DEGRADED
                
                # Recover from degraded if resources improve
                elif (cluster.status == ClusterStatus.DEGRADED and
                      cluster.resources.cpu_percent < 70):
                    logger.info(f"Cluster {cluster_id} recovered to healthy")
                    cluster.status = ClusterStatus.HEALTHY
    
    def get_registry_summary(self) -> dict:
        """Get summary of registry state"""
        total = len(self._clusters)
        healthy = sum(1 for c in self._clusters.values() if c.is_healthy())
        by_region = {}
        by_status = {}
        
        for cluster in self._clusters.values():
            by_region[cluster.region] = by_region.get(cluster.region, 0) + 1
            status = cluster.status.value
            by_status[status] = by_status.get(status, 0) + 1
        
        return {
            "total_clusters": total,
            "healthy_clusters": healthy,
            "by_region": by_region,
            "by_status": by_status,
        }


# Global registry instance
_cluster_registry: Optional[ClusterRegistry] = None


def get_cluster_registry() -> ClusterRegistry:
    """Get or create global cluster registry instance"""
    global _cluster_registry
    if _cluster_registry is None:
        _cluster_registry = ClusterRegistry()
    return _cluster_registry
