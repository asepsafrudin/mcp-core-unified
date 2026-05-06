import asyncio
import os
import sys
import glob
import json

PROJECT_ROOT = "/home/aseps/MCP/mcp-unified"
sys.path.insert(0, PROJECT_ROOT)

from memory.longterm import memory_save, pool

async def main():
    # Path to Antigravity's brain
    brain_dir = os.path.expanduser("~/.gemini/antigravity/brain")
    
    if not os.path.exists(brain_dir):
        print(f"Error: Brain directory {brain_dir} not found.")
        return

    try:
        await pool.open()
        
        count = 0
        print(f"Scanning conversation logs in {brain_dir}...")
        
        # Iterate over conversation directories
        for conv_id in os.listdir(brain_dir):
            conv_path = os.path.join(brain_dir, conv_id)
            if not os.path.isdir(conv_path):
                continue
                
            # Read overview.txt (the full conversation transcript)
            overview_path = os.path.join(conv_path, ".system_generated", "logs", "overview.txt")
            if not os.path.exists(overview_path):
                continue
                
            with open(overview_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Truncate content if it's too large to prevent LTM payload issues, but keep most of it
            # (Limiting to last 50,000 characters just to be safe for vector storage limits)
            if len(content) > 50000:
                content = "...[TRUNCATED]...\n" + content[-50000:]
                
            # Use deterministic key to prevent duplicates
            key = f"antigravity_conv_{conv_id}"
            
            result = await memory_save(
                key=key,
                content=content,
                namespace="agent_conversations", # Separate namespace to avoid cluttering knowledge base
                metadata={
                    "type": "conversation_log",
                    "conversation_id": conv_id,
                    "source": "antigravity",
                    "agent": "Antigravity AI"
                }
            )
            print(f"Synced conversation {conv_id} to LTM")
            count += 1
            
        print(f"\nSuccessfully synced {count} conversation logs to the LTM database.")

    except Exception as e:
        print(f"Error during conversation sync: {e}")
    finally:
        await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
