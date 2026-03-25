"""
MCP Client Quickstart Examples

Jalankan dari folder manapun:
    cd /any/project/folder
    python3 /home/aseps/MCP/shared/examples/quickstart.py
"""
import asyncio
import sys
from pathlib import Path

# Add MCP shared to path
sys.path.insert(0, str(Path("/home/aseps/MCP")))

from shared.mcp_client import MCPClient


async def demo():
    print("=" * 50)
    print("MCP Hub — Portable Client Demo")
    print("=" * 50)

    # Zero-config initialization
    client = MCPClient()
    print(f"\nClient: {client}")

    if not client.is_available:
        print("\n❌ Hub tidak tersedia. Jalankan server dulu:")
        print("   cd /home/aseps/MCP/mcp-unified")
        print("   python3 mcp_server_sse.py")
        return

    # Get project context
    print("\n📦 Getting project context...")
    context = await client.get_context()
    print(f"   Namespace: {context['namespace']}")
    print(f"   Total memories: {context['total_memories']}")

    # Save something to memory
    print("\n💾 Saving to memory...")
    save_result = await client.save_context(
        key="demo_test",
        content="Demo berjalan sukses dari portable client",
        metadata={"source": "quickstart_demo", "timestamp": "2026-02-19"}
    )
    print(f"   Result: {save_result.get('message', save_result)}")

    # Search memory
    print("\n🔍 Searching memory...")
    results = await client.search_context("demo portable client")
    print(f"   Found {len(results)} results")
    for r in results:
        print(f"   - {r.get('key')}: {r.get('content', '')[:60]}...")

    print("\n✅ Demo selesai!")
    print(f"   Semua data tersimpan di namespace: {client.namespace}")


if __name__ == "__main__":
    asyncio.run(demo())
