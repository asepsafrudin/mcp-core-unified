import asyncio
import sys
sys.path.insert(0, '/home/aseps/MCP/mcp-unified')
from execution.registry import registry
from memory.longterm import pool

async def main():
    await pool.open()
    res = await registry.execute("memory_search", {"query": "bot telegram", "namespace": "mcp_knowledge_base"})
    print(res)
    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
