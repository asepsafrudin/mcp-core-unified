import asyncio
import sys
sys.path.insert(0, '/home/aseps/MCP/mcp-unified')
from memory.longterm import memory_search, pool

async def main():
    await pool.open()
    
    query = "ai bot telegram"
    print(f"\nSearching for: '{query}' in 'default' namespace")
    res1 = await memory_search(query=query, namespace='default')
    print(res1)

    print(f"\nSearching for: '{query}' in 'mcp_knowledge_base' namespace")
    res2 = await memory_search(query=query, namespace='mcp_knowledge_base')
    print(res2)

    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
