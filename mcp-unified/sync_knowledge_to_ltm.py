import asyncio
import os
import sys
import glob
import json

import argparse

PROJECT_ROOT = "/home/aseps/MCP/mcp-unified"
sys.path.insert(0, PROJECT_ROOT)

from memory.longterm import memory_save, pool

async def main():
    parser = argparse.ArgumentParser(description="Sync local agent knowledge to LTM database.")
    parser.add_argument("--dir", type=str, default=os.path.join(PROJECT_ROOT, "knowledge"),
                        help="Path to the knowledge directory to sync (default: mcp-unified/knowledge)")
    args = parser.parse_args()

    try:
        await pool.open()
        
        knowledge_dir = args.dir
        if not os.path.exists(knowledge_dir):
            print(f"Error: Directory {knowledge_dir} does not exist.")
            return

        print(f"Syncing knowledge from: {knowledge_dir}")
        count = 0
        for item in os.listdir(knowledge_dir):
            item_path = os.path.join(knowledge_dir, item)
            if os.path.isdir(item_path):
                artifacts_path = os.path.join(item_path, "artifacts")
                
                if os.path.exists(artifacts_path):
                    for md_file in glob.glob(os.path.join(artifacts_path, "*.md")):
                        with open(md_file, 'r') as f:
                            content = f.read()
                        
                        key = f"knowledge_{item}_{os.path.basename(md_file)}"
                        result = await memory_save(
                            key=key[:255], # Ensure key is not too long
                            content=content,
                            namespace="mcp_knowledge_base",
                            metadata={
                                "type": "documentation",
                                "topic": item,
                                "file": os.path.basename(md_file),
                                "source": "antigravity_sync"
                            }
                        )
                        print(f"Synced {md_file} -> DB LTM")
                        count += 1
                        
        print(f"\nSuccessfully synced {count} knowledge artifacts to the Long-Term Memory (LTM) database.")

    except Exception as e:
        print(f"Error during LTM sync: {e}")
    finally:
        await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
