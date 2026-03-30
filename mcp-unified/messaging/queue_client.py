import aio_pika
import json
import asyncio
import os
from typing import Callable, Dict, Any, Optional
from observability.logger import logger
from core.secrets import load_runtime_secrets
from execution import registry

class MCPMessageQueue:
    """Message queue client for distributed MCP tasks"""
    
    def __init__(self, rabbitmq_url: Optional[str] = None):
        load_runtime_secrets()
        self.url = rabbitmq_url or os.getenv("RABBITMQ_URL", "amqp://localhost/")
        self.connection: Optional[aio_pika.RobustConnection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.exchange: Optional[aio_pika.Exchange] = None
        
    async def connect(self):
        """Connect to RabbitMQ"""
        try:
            self.connection = await aio_pika.connect_robust(self.url)
            self.channel = await self.connection.channel()
            
            # Declare exchange for task distribution
            self.exchange = await self.channel.declare_exchange(
                'mcp_tasks',
                aio_pika.ExchangeType.TOPIC,
                durable=True
            )
            logger.info("rabbitmq_connected")
        except Exception as e:
            logger.error("rabbitmq_connection_failed", error=str(e))
            self.connection = None
        
    async def publish_task(
        self,
        task_type: str,
        task_data: Dict[str, Any],
        priority: int = 5
    ) -> Dict[str, Any]:
        """Publish task to queue"""
        if not self.exchange:
            return {"success": False, "error": "Not connected to RabbitMQ"}
            
        try:
            message = aio_pika.Message(
                body=json.dumps(task_data).encode(),
                priority=priority,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            )
            
            routing_key = f"task.{task_type}"
            
            await self.exchange.publish(
                message,
                routing_key=routing_key
            )
            
            logger.info("task_published", type=task_type, routing_key=routing_key)
            return {"success": True, "message": "Task queued successfully"}
            
        except Exception as e:
            logger.error("publish_failed", error=str(e))
            return {"success": False, "error": str(e)}
    
    async def close(self):
        """Close connection"""
        if self.connection:
            await self.connection.close()

# Global instance
# In production, URL should come from settings/env
mq_client = MCPMessageQueue()

@registry.register
async def publish_remote_task(task_type: str, payload: Dict[str, Any], priority: int = 5) -> Dict[str, Any]:
    """
    Publish a task to be executed by a remote worker.
    """
    return await mq_client.publish_task(task_type, payload, priority)
