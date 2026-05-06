import asyncio
import sys
sys.path.insert(0, '/home/aseps/MCP/mcp-unified')
from memory.longterm import memory_list, pool

async def main():
    await pool.open()
    
    print("\n=== LTM NAMESPACE: mcp_knowledge_base ===")
    kb = await memory_list(namespace='mcp_knowledge_base', limit=15)
    if kb.get('success'):
        for m in kb['memories']:
            print(f"- {m['key']} (Created: {m['created_at']})")
            
    print("\n=== LTM NAMESPACE: agent_conversations ===")
    conv = await memory_list(namespace='agent_conversations', limit=15)
    if conv.get('success'):
        for m in conv['memories']:
            print(f"- {m['key']} (Created: {m['created_at']})")
            
    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
