import asyncio
import sys
sys.path.insert(0, '/home/aseps/MCP/mcp-unified')
from memory.longterm import memory_search, pool

async def main():
    await pool.open()
    res = await memory_search(query="bot telegram", namespace="mcp_knowledge_base", strategy="keyword")
    print(f"KEYWORD SEARCH Results count: {len(res.get('results', []))}")
    for r in res.get('results', []):
        print(f"Key: {r['key']}, Score: {r['score']}")
    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
