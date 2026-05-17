import asyncio
import sys
import os

# Add core/mcp-unified to sys.path
sys.path.append("/home/aseps/MCP/core/mcp-unified")

from orchestration.antigravity_ledger import ledger
from skills.token_controller import token_controller
from skills.virtual_queue import virtual_queue

async def test_ledger():
    print("Testing Ledger...")
    await ledger.connect()
    
    # Test quota
    print("Incrementing quota...")
    await ledger.increment_quota(1000)
    quota = await ledger.get_quota()
    print(f"Current quota: {quota}")
    
    # Test global goal
    print("Setting global goal...")
    await ledger.set_global_goal("Implement Antigravity Layer", {"priority": "high"})
    goal = await ledger.get_global_goal()
    print(f"Global goal: {goal}")
    
    # Test file cache
    print("Caching file index...")
    await ledger.cache_file_index("test.py", {"tokens": 50})
    cached = await ledger.get_file_index("test.py")
    print(f"Cached index: {cached}")

async def test_token_controller():
    print("\nTesting Token Controller...")
    text = "Hello world, this is a test of the token controller."
    est = token_controller.estimate_tokens(text)
    print(f"Estimate for '{text}': {est} tokens")
    
    # Test file estimation
    with open("temp_test.txt", "w") as f:
        f.write("A" * 1000) # 1000 chars
    
    est_file = await token_controller.estimate_files(["temp_test.txt"])
    print(f"Estimate for 1000 chars file: {est_file} tokens")
    os.remove("temp_test.txt")

async def test_virtual_queue():
    print("\nTesting Virtual Queue...")
    # This might wait if limits are low
    print("Checking quota for 5000 tokens...")
    ok = await virtual_queue.wait_for_quota(5000)
    print(f"Queue OK: {ok}")

if __name__ == "__main__":
    async def main():
        await test_ledger()
        await test_token_controller()
        await test_virtual_queue()
    asyncio.run(main())
