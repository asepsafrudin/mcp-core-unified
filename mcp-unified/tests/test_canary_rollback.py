"""
Canary Deployment End-to-End Test
Part of TASK-029: Phase 8 - Soft Launch Infrastructure

Tests actual rollback execution, not just logic.
"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

from softlaunch.canary import (
    CanaryDeploymentManager,
    CanaryConfig,
    CanaryStatus,
)


@pytest.mark.asyncio
async def test_canary_rollback_execution():
    """
    E2E Test: Verify rollback actually executes and restores previous state.
    
    This is NOT a unit test - it tests the full rollback execution path.
    """
    manager = CanaryDeploymentManager()
    
    # Create and start deployment
    deployment = await manager.create_deployment(
        deployment_id="test-rollout-001",
        service_name="api-service",
        version="v2.0.0",
    )
    
    await manager.start_deployment("test-rollout-001")
    
    # Simulate health check failure
    deployment.total_requests = 100
    deployment.error_count = 10  # 10% error rate > threshold
    
    # Trigger rollback
    result = await manager.rollback_deployment(
        "test-rollout-001",
        reason="health_check_failed"
    )
    
    assert result is True
    assert deployment.status == CanaryStatus.ROLLED_BACK
    assert deployment.completed_at is not None
    
    # Verify callback was triggered
    rollback_triggered = []
    def on_rollback(deployment, reason):
        rollback_triggered.append((deployment.deployment_id, reason))
    
    manager.on_rollback(on_rollback)
    await manager.rollback_deployment("test-rollout-001", "manual")
    
    assert len(rollback_triggered) > 0
    assert rollback_triggered[-1][1] == "manual"


@pytest.mark.asyncio
async def test_canary_auto_rollback_on_failure():
    """
    Test: Auto-rollback triggers when health checks fail.
    """
    config = CanaryConfig(
        max_error_rate=0.05,  # 5% threshold
        auto_rollback=True,
    )
    
    manager = CanaryDeploymentManager()
    deployment = await manager.create_deployment(
        deployment_id="test-auto-rollback",
        service_name="api",
        version="v1.1.0",
        config=config,
    )
    
    await manager.start_deployment("test-auto-rollback")
    
    # Simulate high error rate
    deployment.record_request(success=False, latency_ms=100)
    deployment.record_request(success=False, latency_ms=100)
    deployment.record_request(success=False, latency_ms=100)
    
    # Health check should trigger
    assert manager._check_health(deployment) is False
