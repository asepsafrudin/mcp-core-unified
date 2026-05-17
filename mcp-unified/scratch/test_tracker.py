import asyncio
import sys
import os

# Add core/mcp-unified to sys.path
sys.path.append("/home/aseps/MCP/core/mcp-unified")

from monitoring.token_tracker import token_tracker
from memory.longterm import initialize_db
from core.secrets import load_runtime_secrets

async def test_tracker():
    print("Loading secrets...")
    load_runtime_secrets()
    
    print("Initializing DB...")
    await initialize_db()
    
    print("Tracking usage...")
    task_id = "test-task-123"
    model = "anthropic/claude-3-sonnet"
    usage = {
        "prompt_tokens": 1500,
        "completion_tokens": 500
    }
    
    await token_tracker.track_usage(
        task_id=task_id,
        model=model,
        usage_metadata=usage,
        extra_metadata={"test": True}
    )
    
    print("Retrieving summary...")
    summary = await token_tracker.get_total_usage(days=1)
    print(f"Usage Summary: {summary}")

if __name__ == "__main__":
    asyncio.run(test_tracker())
