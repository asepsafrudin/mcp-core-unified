"""
Script to create the dynamic Google Sheets sync task in the scheduler.
"""
import asyncio
import os
import sys
import json
from pathlib import Path

project_root = '/home/aseps/MCP/mcp-unified'
sys.path.insert(0, project_root)
from core.secrets import load_runtime_secrets

load_runtime_secrets()

from scheduler.database import create_job

async def main():
    spreadsheet_id = '1GRLdIr0ONXKTGWxPqyJW9vgcwgaYkU8YdN6eAoVPAeQ'
    range_name = 'Surat Masuk!A1:Z500' # Sync up to 500 rows
    namespace = 'korespondensi_eksternal'
    
    # Task configuration
    task_config = {
        "steps": [
            {
                "name": "ingest_gsheet_rows",
                "tool": "run_shell",
                # We use a python one-liner to call our existing ingest tool
                "command": f"python3 -c \"import asyncio; from knowledge.tools import knowledge_ingest_googlesheet; asyncio.run(knowledge_ingest_googlesheet('{spreadsheet_id}', '{range_name}', '{namespace}'))\"",
                "timeout": 600
            },
            {
                "name": "notify_sync_status",
                "tool": "memory_save",
                "key": f"sync:{namespace}:last_run",
                "content": "Sync completed at {timestamp}"
            }
        ],
        "notification": {
            "on_success": True,
            "on_failure": True,
            "channels": ["telegram"]
        }
    }
    
    print(f"Creating sync job for {namespace}...")
    res = await create_job(
        name=f"sync_gsheet_{namespace}",
        job_type="ltm_sync_remote", # Reusing an existing allowed job_type
        category="sync",
        schedule_type="cron",
        schedule_expr="0 8 * * *", # Every day at 08:00 AM
        task_config=task_config,
        description=f"Automatic daily sync for Google Sheet {spreadsheet_id} ({namespace})",
        priority=60,
        namespace=namespace
    )
    
    print(f"Job Creation Result: {json.dumps(res, indent=2)}")

if __name__ == '__main__':
    asyncio.run(main())
