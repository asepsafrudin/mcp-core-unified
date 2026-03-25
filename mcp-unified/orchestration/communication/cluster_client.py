"""
Inter-Cluster Communication Client

Secure communication between MCP clusters.
Part of TASK-029: Phase 8 - Advanced Orchestration
"""

import asyncio
import json
import time
import hmac
import hashlib
from typing import Dict, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
import logging
import aiohttp

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of inter-cluster messages"""
    HEARTBEAT = "heartbeat"
    TASK_ASSIGNMENT = "task_assignment"
    TASK_RESULT = "task_result"
    TASK_CANCEL = "task_cancel"
    RESOURCE_UPDATE = "resource_update"
    AGENT_REQUEST = "agent_request"
    AGENT_RESPONSE = "agent_response"
    STATE_SYNC = "state_sync"


@dataclass
class ClusterMessage:
    """Message sent between clusters"""
    message_id: str
    message_type: MessageType
    source_cluster: str
    target_cluster: str
    payload: Dict[str, Any]
    timestamp: float
    signature: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "message_type": self.message_type.value,
            "source_cluster": self.source_cluster,
            "target_cluster": self.target_cluster,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "signature": self.signature,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ClusterMessage":
        return cls(
            message_id=data["message_id"],
            message_type=MessageType(data["message_type"]),
            source_cluster=data["source_cluster"],
            target_cluster=data["target_cluster"],
            payload=data["payload"],
            timestamp=data["timestamp"],
            signature=data.get("signature"),
        )


class ClusterAuth:
    """Authentication for cluster-to-cluster communication"""
    
    def __init__(self, cluster_id: str, shared_secret: str):
        self.cluster_id = cluster_id
        self.shared_secret = shared_secret.encode()
    
    def sign_message(self, message: ClusterMessage) -> str:
        """Sign a message with HMAC"""
        data = f"{message.message_id}:{message.source_cluster}:{message.target_cluster}:{message.timestamp}"
        signature = hmac.new(
            self.shared_secret,
            data.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def verify_message(self, message: ClusterMessage) -> bool:
        """Verify message signature"""
        if not message.signature:
            return False
        
        expected = self.sign_message(message)
        return hmac.compare_digest(message.signature, expected)


class ClusterClient:
    """
    Client for communicating with remote MCP clusters.
    
    Features:
    - Secure authentication (HMAC)
    - Async message sending
    - Connection pooling
    - Retry logic
    - Circuit breaker pattern
    """
    
    def __init__(
        self,
        local_cluster_id: str,
        remote_cluster_id: str,
        remote_endpoint: str,
        shared_secret: str,
        timeout: float = 30.0,
    ):
        self.local_cluster_id = local_cluster_id
        self.remote_cluster_id = remote_cluster_id
        self.remote_endpoint = remote_endpoint
        self.auth = ClusterAuth(local_cluster_id, shared_secret)
        self.timeout = timeout
        
        self._session: Optional[aiohttp.ClientSession] = None
        self._lock = asyncio.Lock()
        
        # Circuit breaker state
        self._failure_count = 0
        self._circuit_open = False
        self._circuit_open_time: Optional[float] = None
        self._circuit_timeout = 60.0  # Open for 60s after failures
        self._max_failures = 5
        
        logger.info(f"ClusterClient initialized for {remote_cluster_id} at {remote_endpoint}")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        async with self._lock:
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                    headers={
                        "Content-Type": "application/json",
                        "X-Cluster-ID": self.local_cluster_id,
                    },
                )
            return self._session
    
    async def close(self):
        """Close the client"""
        async with self._lock:
            if self._session and not self._session.closed:
                await self._session.close()
                self._session = None
    
    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker allows requests"""
        if not self._circuit_open:
            return True
        
        # Check if circuit should close
        if self._circuit_open_time:
            elapsed = time.time() - self._circuit_open_time
            if elapsed > self._circuit_timeout:
                logger.info(f"Circuit breaker closing for {self.remote_cluster_id}")
                self._circuit_open = False
                self._failure_count = 0
                self._circuit_open_time = None
                return True
        
        return False
    
    def _record_success(self):
        """Record successful request"""
        self._failure_count = max(0, self._failure_count - 1)
    
    def _record_failure(self):
        """Record failed request"""
        self._failure_count += 1
        
        if self._failure_count >= self._max_failures:
            logger.warning(f"Circuit breaker opening for {self.remote_cluster_id}")
            self._circuit_open = True
            self._circuit_open_time = time.time()
    
    async def send_message(
        self,
        message_type: MessageType,
        payload: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Send a message to the remote cluster.
        
        Args:
            message_type: Type of message
            payload: Message payload
        
        Returns:
            Response from remote cluster or None on failure
        """
        if not self._check_circuit_breaker():
            logger.warning(f"Circuit breaker open for {self.remote_cluster_id}")
            return None
        
        # Create message
        message = ClusterMessage(
            message_id=f"{self.local_cluster_id}-{int(time.time() * 1000)}",
            message_type=message_type,
            source_cluster=self.local_cluster_id,
            target_cluster=self.remote_cluster_id,
            payload=payload,
            timestamp=time.time(),
        )
        
        # Sign message
        message.signature = self.auth.sign_message(message)
        
        try:
            session = await self._get_session()
            url = f"{self.remote_endpoint}/cluster/message"
            
            async with session.post(
                url,
                json=message.to_dict(),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self._record_success()
                    return data
                else:
                    logger.error(f"Message failed with status {response.status}")
                    self._record_failure()
                    return None
                    
        except asyncio.TimeoutError:
            logger.error(f"Timeout sending message to {self.remote_cluster_id}")
            self._record_failure()
            return None
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self._record_failure()
            return None
    
    async def send_heartbeat(self, cluster_info: dict) -> bool:
        """Send heartbeat to remote cluster"""
        response = await self.send_message(
            MessageType.HEARTBEAT,
            {"cluster_info": cluster_info}
        )
        return response is not None
    
    async def assign_task(
        self,
        task_id: str,
        task_type: str,
        payload: Dict[str, Any],
        requirements: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """Assign a task to remote cluster"""
        return await self.send_message(
            MessageType.TASK_ASSIGNMENT,
            {
                "task_id": task_id,
                "task_type": task_type,
                "payload": payload,
                "requirements": requirements or {},
            }
        )
    
    async def send_task_result(
        self,
        task_id: str,
        result: Dict[str, Any],
    ) -> bool:
        """Send task result back to source cluster"""
        response = await self.send_message(
            MessageType.TASK_RESULT,
            {
                "task_id": task_id,
                "result": result,
            }
        )
        return response is not None
    
    async def get_cluster_status(self) -> Optional[Dict]:
        """Get status of remote cluster"""
        return await self.send_message(
            MessageType.RESOURCE_UPDATE,
            {"query": "status"}
        )


class ClusterMessageRouter:
    """
    Routes messages between multiple clusters.
    
    Maintains connections to all known clusters and routes
    messages to the appropriate destination.
    """
    
    def __init__(self, local_cluster_id: str, shared_secret: str):
        self.local_cluster_id = local_cluster_id
        self.shared_secret = shared_secret
        self._clients: Dict[str, ClusterClient] = {}
        self._lock = asyncio.Lock()
        
        # Message handlers
        self._handlers: Dict[MessageType, Callable] = {}
        
        logger.info(f"ClusterMessageRouter initialized for {local_cluster_id}")
    
    def register_handler(self, message_type: MessageType, handler: Callable):
        """Register a handler for a message type"""
        self._handlers[message_type] = handler
    
    async def add_cluster(
        self,
        cluster_id: str,
        endpoint: str,
    ) -> ClusterClient:
        """Add a remote cluster connection"""
        async with self._lock:
            if cluster_id in self._clients:
                await self._clients[cluster_id].close()
            
            client = ClusterClient(
                local_cluster_id=self.local_cluster_id,
                remote_cluster_id=cluster_id,
                remote_endpoint=endpoint,
                shared_secret=self.shared_secret,
            )
            self._clients[cluster_id] = client
            
            logger.info(f"Added cluster connection: {cluster_id}")
            return client
    
    async def remove_cluster(self, cluster_id: str):
        """Remove a cluster connection"""
        async with self._lock:
            if cluster_id in self._clients:
                await self._clients[cluster_id].close()
                del self._clients[cluster_id]
                logger.info(f"Removed cluster connection: {cluster_id}")
    
    async def route_message(
        self,
        target_cluster: str,
        message_type: MessageType,
        payload: Dict[str, Any],
    ) -> Optional[Dict]:
        """Route a message to target cluster"""
        async with self._lock:
            if target_cluster not in self._clients:
                logger.error(f"No connection to cluster: {target_cluster}")
                return None
            
            client = self._clients[target_cluster]
        
        return await client.send_message(message_type, payload)
    
    async def broadcast(
        self,
        message_type: MessageType,
        payload: Dict[str, Any],
        exclude: Optional[list] = None,
    ) -> Dict[str, Optional[Dict]]:
        """Broadcast message to all connected clusters"""
        exclude = exclude or []
        results = {}
        
        async with self._lock:
            clients = dict(self._clients)
        
        for cluster_id, client in clients.items():
            if cluster_id not in exclude:
                results[cluster_id] = await client.send_message(
                    message_type, payload
                )
        
        return results
    
    async def handle_incoming_message(
        self,
        message: ClusterMessage,
    ) -> Optional[Dict]:
        """Handle incoming message from another cluster"""
        # Verify message
        auth = ClusterAuth(self.local_cluster_id, self.shared_secret)
        if not auth.verify_message(message):
            logger.warning(f"Invalid message signature from {message.source_cluster}")
            return {"error": "invalid_signature"}
        
        # Route to handler
        handler = self._handlers.get(message.message_type)
        if handler:
            try:
                result = await handler(message)
                return result or {"status": "ok"}
            except Exception as e:
                logger.error(f"Handler error: {e}")
                return {"error": str(e)}
        
        return {"status": "no_handler"}
    
    async def close_all(self):
        """Close all connections"""
        async with self._lock:
            for client in self._clients.values():
                await client.close()
            self._clients.clear()
    
    def get_connected_clusters(self) -> list:
        """Get list of connected clusters"""
        return list(self._clients.keys())


# Global router instance
_router_instance: Optional[ClusterMessageRouter] = None


def get_cluster_router(
    local_cluster_id: str,
    shared_secret: str,
) -> ClusterMessageRouter:
    """Get or create global cluster router"""
    global _router_instance
    if _router_instance is None:
        _router_instance = ClusterMessageRouter(
            local_cluster_id,
            shared_secret,
        )
    return _router_instance
