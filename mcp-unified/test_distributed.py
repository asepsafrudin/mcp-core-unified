import asyncio
import json
from messaging.queue_client import MCPMessageQueue

async def test_distributed_flow():
    print("🚀 Connecting to RabbitMQ...")
    mq = MCPMessageQueue()
    await mq.connect()
    
    if not mq.connection or mq.connection.is_closed:
        print("❌ Failed to connect to RabbitMQ")
        return

    print("✅ Connected!")
    
    task_payload = {
        "id": "task_dist_001",
        "file": "/tmp/test_remote.py",
        "content": "print('hello from remote')"
    }
    
    print("📤 Publishing task...")
    result = await mq.publish_task(
        task_type="code_analysis",
        task_data=task_payload
    )
    
    print(f"Result: {result}")
    
    if result["success"]:
        print("✅ Task published successfully!")
    else:
        print("❌ Failed to publish task")
        
    await mq.close()

if __name__ == "__main__":
    asyncio.run(test_distributed_flow())
