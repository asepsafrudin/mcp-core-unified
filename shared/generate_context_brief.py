#!/usr/bin/env python3
"""
Generate Context Brief

Script yang dipanggil saat agent baru dibuka.
Output-nya siap di-paste ke agent atau di-inject ke .agent file.

Usage:
    python3 /home/aseps/MCP/shared/generate_context_brief.py
    python3 /home/aseps/MCP/shared/generate_context_brief.py --save
    python3 /home/aseps/MCP/shared/generate_context_brief.py --namespace myproject
"""
import asyncio
import argparse
import sys
from pathlib import Path

# Add MCP to path
sys.path.insert(0, str(Path("/home/aseps/MCP")))

from shared.mcp_client import MCPClient
from shared.context_injector import ContextInjector


async def main():
    parser = argparse.ArgumentParser(description="Generate MCP Context Brief")
    parser.add_argument("--namespace", help="Override namespace (default: auto-detect)")
    parser.add_argument("--save", action="store_true",
                       help="Save brief to .mcp/context_brief.md in current folder")
    parser.add_argument("--max", type=int, default=10,
                       help="Max memories to include (default: 10)")
    args = parser.parse_args()

    # Initialize client
    client = MCPClient(namespace=args.namespace)

    if not client.is_available:
        print("❌ MCP Hub tidak tersedia.")
        print("   Jalankan: cd /home/aseps/MCP/mcp-unified && python3 mcp_server_sse.py")
        sys.exit(1)

    # Generate brief
    injector = ContextInjector(client)
    brief = await injector.get_brief(max_memories=args.max)

    # Output
    print(brief)

    # Optionally save to file
    if args.save:
        mcp_dir = Path.cwd() / ".mcp"
        mcp_dir.mkdir(exist_ok=True)
        brief_file = mcp_dir / "context_brief.md"
        brief_file.write_text(brief)
        print(f"\n✅ Brief saved to: {brief_file}")


if __name__ == "__main__":
    asyncio.run(main())
