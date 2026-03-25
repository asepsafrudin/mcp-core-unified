"""
Circuit Breaker with Simulated Cluster Failure Test
Part of TASK-029: Phase 8 - Inter-Cluster Communication

Tests circuit breaker behavior under simulated cluster failures.
"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
import aiohttp

from orchestration.communication.cluster_client import (
    ClusterClient,
    ClusterMessageRouter,
    MessageType,
)


@pytest.mark.asyncio
async def test_circuit_breaker_opens_on_cluster_failure():
    """
    Test: Circuit breaker opens after consecutive failures to remote cluster.
    
    Simulates: Remote cluster down, network timeout, connection refused
    """
    client = ClusterClient(
        local_cluster_id="cluster-a",
        remote_cluster_id="cluster-b",
        remote_endpoint="http://cluster-b:8080",
        shared_secret="test-secret",
        timeout=1.0,
    )
    
    # Simulate 5 consecutive failures (max_failures threshold)
    for i in range(5):
        with patch.object(client, '_get_session', side_effect=aiohttp.ClientError("Connection refused")):
            result = await client.send_message(
                MessageType.HEARTBEAT,
                {"status": "ping"}
            )
            assert result is None
    
    # Circuit should now be open
    assert client._circuit_open is True
    assert client._failure_count >= 5
    
    # Next request should fail fast (circuit open)
    result = await client.send_message(
        MessageType.HEARTBEAT,
        {"status": "ping"}
    )
    assert result is None  # Failed fast without trying


@pytest.mark.asyncio
async def test_circuit_breaker_closes_after_timeout():
    """
    Test: Circuit breaker closes after timeout period.
    
    Simulates: Cluster recovery after downtime
    """
    client = ClusterClient(
        local_cluster_id="cluster-a",
        remote_cluster_id="cluster-b",
        remote_endpoint="http://cluster-b:8080",
        shared_secret="test-secret",
    )
    
    # Force circuit open
    client._circuit_open = True
    client._circuit_open_time = asyncio.get_event_loop().time() - 61  # 61 seconds ago
    client._circuit_timeout = 60.0
    
    # Circuit should close after timeout
    assert client._check_circuit_breaker() is True
    assert client._circuit_open is False


@pytest.mark.asyncio
async def test_message_router_handles_cluster_failure():
    """
    Test: Message router handles cluster failure gracefully.
    
    Simulates: One cluster fails, others remain operational
    """
    router = ClusterMessageRouter(
        local_cluster_id="hub",
        shared_secret="test-secret",
    )
    
    # Add two clusters
    await router.add_cluster("cluster-a", "http://cluster-a:8080")
    await router.add_cluster("cluster-b", "http://cluster-b:8080")
    
    # Simulate cluster-a failure
    with patch.object(router._clients["cluster-a"], 'send_message', return_value=None):
        # Message to cluster-a should fail
        result_a = await router.route_message(
            "cluster-a",
            MessageType.TASK_ASSIGNMENT,
            {"task": "test"}
        )
        assert result_a is None
        
        # Message to cluster-b should still work (mocked success)
        with patch.object(router._clients["cluster-b"], 'send_message', return_value={"status": "ok"}):
            result_b = await router.route_message(
                "cluster-b",
                MessageType.TASK_ASSIGNMENT,
                {"task": "test"}
            )
            assert result_b == {"status": "ok"}
    
    await router.close_all()


@pytest.mark.asyncio
async def test_broadcast_with_partial_cluster_failure():
    """
    Test: Broadcast succeeds even if some clusters fail.
    
    Simulates: Multi-cluster broadcast with partial failures
    """
    router = ClusterMessageRouter(
        local_cluster_id="hub",
        shared_secret="test-secret",
    )
    
    # Add three clusters
    for i in range(3):
        await router.add_cluster(f"cluster-{i}", f"http://cluster-{i}:8080")
    
    # Simulate: cluster-0 succeeds, cluster-1 fails, cluster-2 succeeds
    results = {}
    
    async def mock_send_success(*args, **kwargs):
        return {"status": "ok"}
    
    async def mock_send_failure(*args, **kwargs):
        return None
    
    router._clients["cluster-0"].send_message = mock_send_success
    router._clients["cluster-1"].send_message = mock_send_failure
    router._clients["cluster-2"].send_message = mock_send_success
    
    broadcast_results = await router.broadcast(
        MessageType.STATE_SYNC,
        {"data": "sync"}
    )
    
    # Partial success expected
    assert broadcast_results["cluster-0"] == {"status": "ok"}
    assert broadcast_results["cluster-1"] is None
    assert broadcast_results["cluster-2"] == {"status": "ok"}
    
    await router.close_all()
