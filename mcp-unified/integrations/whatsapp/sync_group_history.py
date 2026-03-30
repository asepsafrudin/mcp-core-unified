import asyncio
import os
import json
import sys
import logging
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path('/home/aseps/MCP/mcp-unified')
sys.path.insert(0, str(project_root))
from core.secrets import load_runtime_secrets

load_runtime_secrets()

from integrations.whatsapp.client import get_whatsapp_client
from memory import longterm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("whatsapp-history-sync")

async def sync_group_history(group_id: str, limit: int = 1000):
    """
    Sync history from a WhatsApp group to unified_messages and group_documentation.
    Filters for messages in the year 2026.
    """
    client = get_whatsapp_client()
    session = os.getenv("WHATSAPP_SESSION", "default")
    
    logger.info(f"🚀 Starting 2026 history sync for group {group_id} (limit: {limit})")
    
    try:
        # 1. Initialize DB
        await longterm.initialize_db()
        
        # 2. Fetch messages from WAHA
        messages = await client.get_messages(group_id, limit=limit, session_name=session)
        
        if not messages:
            logger.info("No messages found to sync.")
            return
            
        logger.info(f"Found {len(messages)} messages. Filtering for year 2026...")
        
        counts = {"total_fetched": len(messages), "year_2026": 0, "saved_msg": 0, "saved_doc": 0, "errors": 0}
        
        for msg in messages:
            try:
                if not isinstance(msg, dict): continue
                
                # Timestamp check
                ts_int = msg.get("timestamp")
                if not ts_int: continue
                
                dt = datetime.fromtimestamp(ts_int)
                if dt.year != 2026:
                    continue # Skip non-2026 messages
                
                counts["year_2026"] += 1
                
                # Extract meta
                raw_id = msg.get("id")
                msg_id = raw_id.get("_serialized") or raw_id.get("id") if isinstance(raw_id, dict) else raw_id
                
                body = msg.get("body", "")
                sender = msg.get("author") or msg.get("from")
                ts_iso = dt.isoformat()
                
                # A. Save to unified_messages (with deduplication check if needed, but message_save handles it if schema has constraints)
                res_msg = await longterm.message_save(
                    platform="whatsapp",
                    external_id=msg_id,
                    sender=sender,
                    recipient=group_id,
                    content=body,
                    timestamp=ts_iso,
                    namespace="group_history_2026",
                    metadata={"original": msg}
                )
                if res_msg.get("success"):
                    counts["saved_msg"] += 1
                
                # B. Save to group_documentation if it contains a link or media
                has_link = "http://" in body or "https://" in body
                has_media = msg.get("hasMedia", False)
                
                if (has_link or has_media) and body:
                    doc_type = "link" if has_link else "file"
                    content_val = body
                    
                    if has_media:
                        # Attempt to download physical file
                        media_res = await client.download_media(msg_id, session_name=session)
                        if media_res:
                            file_bytes, content_type = media_res
                            import mimetypes
                            ext = mimetypes.guess_extension(content_type) or ".bin"
                            filename = f"sync_{ts_int}_{msg_id[:8]}{ext}"
                            storage_path = Path(f"/home/aseps/MCP/storage/whatsapp_media/2026/{filename}")
                            storage_path.parent.mkdir(parents=True, exist_ok=True)
                            with open(storage_path, "wb") as f:
                                f.write(file_bytes)
                            content_val = str(storage_path)
                            logger.info(f"💾 Synced media saved: {storage_path}")

                    res_doc = await longterm.doc_save(
                        group_id=group_id,
                        doc_type=doc_type,
                        content=content_val,
                        sender_id=sender,
                        summary=f"[SYNC 2026] {body[:100]}",
                        metadata={"msg_id": msg_id, "timestamp": ts_iso}
                    )
                    if res_doc.get("success"):
                        counts["saved_doc"] += 1
                        
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                counts["errors"] += 1
                
        logger.info(f"✅ Sync 2026 complete: {json.dumps(counts)}")
        return counts

    except Exception as e:
        logger.error(f"Sync failed: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    target_group = "6281343733332-1606811696@g.us" # Bagian PUU
    asyncio.run(sync_group_history(target_group, limit=200))
