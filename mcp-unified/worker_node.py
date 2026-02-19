import asyncio
import json
import os
import aio_pika
from typing import Dict, Any

# Configuration
# On a remote machine, replace 'localhost' with the Master Node's Tailscale IP
# Example: "amqp://mcp:mcp_secure_pass@100.88.72.19/"
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://mcp:mcp_secure_pass@localhost/")
WORKER_ID = os.getenv("WORKER_ID", "worker-node-1")

class MCPWorker:
    def __init__(self, broker_url: str):
        self.url = broker_url
        self.connection = None
        self.channel = None
        self.exchange = None
        self.queue = None

    async def connect(self):
        print(f"[{WORKER_ID}] 🔌 Connecting to broker at {self.url}...")
        try:
            self.connection = await aio_pika.connect_robust(self.url)
            self.channel = await self.connection.channel()
            
            # Declare the same exchange as Master
            self.exchange = await self.channel.declare_exchange(
                'mcp_tasks',
                aio_pika.ExchangeType.TOPIC,
                durable=True
            )
            
            # Create a queue for this worker (or shared queue for load balancing)
            # Using a shared queue name 'mcp_worker_queue' means tasks are distributed round-robin
            self.queue = await self.channel.declare_queue(
                'mcp_worker_pool',
                durable=True
            )
            
            # Bind to all tasks or specific types
            # Here we bind to everything "task.*"
            await self.queue.bind(self.exchange, routing_key="task.#")
            
            print(f"[{WORKER_ID}] ✅ Connected and waiting for tasks...")
            
        except Exception as e:
            print(f"[{WORKER_ID}] ❌ Connection failed: {e}")
            raise e

    async def process_task(self, message: aio_pika.IncomingMessage):
        async with message.process():
            task_data = json.loads(message.body.decode())
            task_type = message.routing_key
            
            print(f"[{WORKER_ID}] 📥 Received task: {task_type}")
            print(f"             ID: {task_data.get('id')}")
            print(f"             Payload: {task_data}")

            # --- SIMULATE WORK ---
            try:
                # 1. Parsing Input
                # 2. Doing heavy computation / file op
                await asyncio.sleep(2) # Simulate work
                
                result = {"status": "success", "result": "Calculated 42"}
                print(f"[{WORKER_ID}] 🎉 Task Complete!")
                
                # In real impl, publish result back to a 'results' queue
                
            except Exception as e:
                print(f"[{WORKER_ID}] 💥 Task execution failed: {e}")

    async def start(self):
        await self.connect()
        await self.queue.consume(self.process_task)
        
        # Keep running
        try:
            await asyncio.Future()
        finally:
            await self.connection.close()

if __name__ == "__main__":
    try:
        worker = MCPWorker(RABBITMQ_URL)
        asyncio.run(worker.start())
    except KeyboardInterrupt:
        print("Worker stopped.")
