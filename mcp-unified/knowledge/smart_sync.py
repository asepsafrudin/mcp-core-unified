"""
Smart Google Sheets Sync with Change Detection.
Captures data to local JSON/CSV and only ingests if changes are detected.
"""
import os
import sys
import json
import hashlib
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Add project root to path
PROJECT_ROOT = "/home/aseps/MCP/mcp-unified"
sys.path.insert(0, PROJECT_ROOT)

# Load environment variables
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from integrations.google_workspace.client import get_google_client
from knowledge.tools import knowledge_ingest_googlesheet
from observability.logger import logger

STORAGE_DIR = "/home/aseps/MCP/storage/admin_data/korespondensi"
STATE_FILE = os.path.join(STORAGE_DIR, "sync_state.json")

async def get_sheet_data(spreadsheet_id: str, range_name: str) -> List[List[Any]]:
    """Fetch raw data from Google Sheet."""
    client = get_google_client()
    sheets = client.sheets
    
    result = sheets.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range_name
    ).execute()
    
    return result.get("values", [])

def calculate_hash(data: List[List[Any]]) -> str:
    """Calculate MD5 hash of the sheet data."""
    data_str = json.dumps(data, sort_keys=True)
    return hashlib.md5(data_str.encode()).hexdigest()

async def smart_sync(spreadsheet_id: str, range_name: str, namespace: str):
    """
    Sync Google Sheet only if data has changed.
    """
    try:
        os.makedirs(STORAGE_DIR, exist_ok=True)
        
        # 1. Fetch current data
        logger.info("smart_sync_fetching", spreadsheet_id=spreadsheet_id, range=range_name)
        current_values = await get_sheet_data(spreadsheet_id, range_name)
        
        if not current_values:
            logger.warning("smart_sync_empty_data", spreadsheet_id=spreadsheet_id)
            return
        
        # 2. Check for changes
        current_hash = calculate_hash(current_values)
        local_file = os.path.join(STORAGE_DIR, f"{namespace}_data.json")
        
        # Load state
        state = {}
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
        
        previous_hash = state.get(namespace, {}).get("hash")
        
        if current_hash == previous_hash and os.path.exists(local_file):
            logger.info("smart_sync_no_changes", namespace=namespace)
            return {"success": True, "changed": False}
        
        # 3. Data changed or first run - Save local copy
        logger.info("smart_sync_detected_changes", namespace=namespace)
        with open(local_file, 'w') as f:
            json.dump({
                "spreadsheet_id": spreadsheet_id,
                "range": range_name,
                "values": current_values,
                "synced_at": datetime.now(timezone.utc).isoformat()
            }, f, indent=2)
            
        # 4. Trigger Ingestion
        logger.info("smart_sync_triggering_ingestion", namespace=namespace)
        ingest_result = await knowledge_ingest_googlesheet(
            spreadsheet_id=spreadsheet_id,
            range_name=range_name,
            namespace=namespace
        )
        
        # 5. Update state
        state[namespace] = {
            "hash": current_hash,
            "last_sync": datetime.now(timezone.utc).isoformat(),
            "spreadsheet_id": spreadsheet_id
        }
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
            
        return {
            "success": True, 
            "changed": True, 
            "ingest_result": json.loads(ingest_result)
        }
        
    except Exception as e:
        logger.error("smart_sync_failed", error=str(e))
        return {"success": False, "error": str(e)}

async def main():
    # Load targets from config file
    config_path = os.path.join(PROJECT_ROOT, "knowledge/sync_targets.json")
    if not os.path.exists(config_path):
        logger.error(f"Sync targets config not found at {config_path}")
        return

    with open(config_path, 'r') as f:
        targets = json.load(f)
    
    results = []
    for target in targets:
        logger.info(f"Starting smart sync for {target['name']} ({target['namespace']})...")
        result = await smart_sync(
            spreadsheet_id=target["spreadsheet_id"],
            range_name=target["range_name"],
            namespace=target["namespace"]
        )
        results.append({
            "name": target["name"],
            "namespace": target["namespace"],
            "result": result
        })
    
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
