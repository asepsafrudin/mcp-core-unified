"""
MCP Orchestration Module

Multi-cluster orchestration, federation, and advanced scheduling capabilities.
Part of TASK-029: Phase 8 - Advanced Orchestration
"""

from .cluster.registry import (
    ClusterRegistry,
    ClusterInfo,
    ClusterResource,
    ClusterStatus,
    ClusterCapability,
    get_cluster_registry,
)
from .scheduler.distributed import (
    DistributedScheduler,
    TaskPriority,
    TaskStatus,
    SchedulingAlgorithm,
    get_distributed_scheduler,
)
from .communication.cluster_client import (
    ClusterClient,
    ClusterMessage,
    ClusterMessageRouter,
    MessageType,
    get_cluster_router,
)
from .federation.control_plane import (
    FederationControlPlane,
    FederationPolicy,
    PolicyAction,
    GlobalTaskState,
    get_federation_control_plane,
)

__all__ = [
    "ClusterRegistry",
    "ClusterInfo",
    "ClusterResource",
    "ClusterStatus",
    "ClusterCapability",
    "get_cluster_registry",
    "DistributedScheduler",
    "TaskPriority",
    "TaskStatus",
    "SchedulingAlgorithm",
    "get_distributed_scheduler",
    "ClusterClient",
    "ClusterMessage",
    "ClusterMessageRouter",
    "MessageType",
    "get_cluster_router",
    "FederationControlPlane",
    "FederationPolicy",
    "PolicyAction",
    "GlobalTaskState",
    "get_federation_control_plane",
]
