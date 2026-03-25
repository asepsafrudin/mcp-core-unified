"""
Federation Control Plane

Global resource management, cross-cluster policies, and federated RBAC.
Part of TASK-029: Phase 8 - Advanced Orchestration
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

from ..cluster.registry import ClusterRegistry, get_cluster_registry
from ..communication.cluster_client import ClusterMessageRouter, MessageType

logger = logging.getLogger(__name__)


class PolicyAction(Enum):
    """Policy enforcement actions"""
    ALLOW = "allow"
    DENY = "deny"
    AUDIT = "audit"


@dataclass
class FederationPolicy:
    """Policy for cross-cluster operations"""
    policy_id: str
    name: str
    description: str
    allowed_clusters: Set[str] = field(default_factory=set)
    denied_clusters: Set[str] = field(default_factory=set)
    action: PolicyAction = PolicyAction.ALLOW
    enabled: bool = True
    priority: int = 100


@dataclass  
class GlobalTaskState:
    """Global state of a task across federation"""
    task_id: str
    source_cluster: str
    target_cluster: str
    status: str = "pending"
    created_at: float = field(default_factory=time.time)


class FederationControlPlane:
    """
    Central control plane for federated MCP deployment.
    Manages policies, global state, and cross-cluster RBAC.
    """
    
    def __init__(
        self,
        control_plane_id: str = "global-cp-001",
        cluster_registry: Optional[ClusterRegistry] = None,
    ):
        self.control_plane_id = control_plane_id
        self._registry = cluster_registry or get_cluster_registry()
        
        self._policies: Dict[str, FederationPolicy] = {}
        self._policies_lock = asyncio.Lock()
        
        self._global_tasks: Dict[str, GlobalTaskState] = {}
        self._tasks_lock = asyncio.Lock()
        
        logger.info(f"FederationControlPlane initialized: {control_plane_id}")
    
    async def start(self):
        """Start the control plane"""
        logger.info("FederationControlPlane started")
    
    async def stop(self):
        """Stop the control plane"""
        logger.info("FederationControlPlane stopped")
    
    # === Policy Management ===
    
    async def create_policy(
        self,
        policy_id: str,
        name: str,
        description: str,
        **kwargs
    ) -> FederationPolicy:
        """Create a new federation policy"""
        async with self._policies_lock:
            if policy_id in self._policies:
                raise ValueError(f"Policy {policy_id} already exists")
            
            policy = FederationPolicy(
                policy_id=policy_id,
                name=name,
                description=description,
                **kwargs
            )
            self._policies[policy_id] = policy
            logger.info(f"Policy created: {policy_id}")
            return policy
    
    async def get_policy(self, policy_id: str) -> Optional[FederationPolicy]:
        """Get a policy by ID"""
        async with self._policies_lock:
            return self._policies.get(policy_id)
    
    async def list_policies(self) -> List[FederationPolicy]:
        """List all policies"""
        async with self._policies_lock:
            return list(self._policies.values())
    
    async def delete_policy(self, policy_id: str) -> bool:
        """Delete a policy"""
        async with self._policies_lock:
            if policy_id not in self._policies:
                return False
            del self._policies[policy_id]
            logger.info(f"Policy deleted: {policy_id}")
            return True
    
    async def evaluate_policy(
        self,
        operation: str,
        source_cluster: str,
        target_cluster: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Evaluate policies for an operation.
        Returns: (allowed, reason)
        """
        async with self._policies_lock:
            policies = sorted(self._policies.values(), key=lambda p: p.priority)
            
            for policy in policies:
                if not policy.enabled:
                    continue
                
                if policy.denied_clusters and target_cluster in policy.denied_clusters:
                    return False, f"Denied by policy: {policy.name}"
                
                if policy.allowed_clusters and target_cluster not in policy.allowed_clusters:
                    return False, f"Target not allowed by policy: {policy.name}"
        
        return True, None
    
    # === Global Task State ===
    
    async def register_task(
        self,
        task_id: str,
        source_cluster: str,
        target_cluster: str,
    ) -> GlobalTaskState:
        """Register a task in global state"""
        async with self._tasks_lock:
            task_state = GlobalTaskState(
                task_id=task_id,
                source_cluster=source_cluster,
                target_cluster=target_cluster,
            )
            self._global_tasks[task_id] = task_state
            return task_state
    
    async def update_task_status(
        self,
        task_id: str,
        status: str,
    ) -> bool:
        """Update task status"""
        async with self._tasks_lock:
            if task_id not in self._global_tasks:
                return False
            self._global_tasks[task_id].status = status
            return True
    
    async def get_task_state(self, task_id: str) -> Optional[GlobalTaskState]:
        """Get global task state"""
        async with self._tasks_lock:
            return self._global_tasks.get(task_id)
    
    # === Global Statistics ===
    
    def get_control_plane_stats(self) -> dict:
        """Get control plane statistics"""
        return {
            "control_plane_id": self.control_plane_id,
            "policies_count": len(self._policies),
            "global_tasks_count": len(self._global_tasks),
        }


# Global instance
_control_plane_instance: Optional[FederationControlPlane] = None


def get_federation_control_plane() -> FederationControlPlane:
    """Get or create global federation control plane"""
    global _control_plane_instance
    if _control_plane_instance is None:
        _control_plane_instance = FederationControlPlane()
    return _control_plane_instance
