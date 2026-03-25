import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

project_root = Path('/home/aseps/MCP/mcp-unified')
sys.path.insert(0, str(project_root))
load_dotenv(project_root / '.env')

from memory import longterm

async def init_puu_group():
    await longterm.initialize_db()
    
    group_id = "6281343733332-1606811696@g.us"
    res = await longterm.upsert_group_config(
        group_id=group_id,
        name="Bagian PUU",
        system_prompt="Anda adalah asisten cerdas untuk Bagian Perundang-Undangan (PUU). Gunakan bahasa yang formal namun ramah. Bantu anggota grup dengan pencarian regulasi dan dokumentasi.",
        settings={
            "auto_backup": True,
            "ai_enabled": True,
            "polling_limit": 10
        }
    )
    print(f"Group init result: {res}")

if __name__ == "__main__":
    asyncio.run(init_puu_group())
