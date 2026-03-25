"""
Unified Sync Logic for Phase 3.
Syncs messages from Gmail and WhatsApp to the unified_messages table.
"""

import json
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from mcp.server.fastmcp import Context

from integrations.google_workspace.client import get_google_client
from integrations.whatsapp.client import get_whatsapp_client
from memory.longterm import message_save, message_list

async def sync_gmail_messages(max_results: int = 10, namespace: str = "default") -> Dict[str, Any]:
    """Sync recent Gmail messages to DB."""
    try:
        client = get_google_client()
        gmail = client.gmail
        
        results = gmail.users().messages().list(
            userId="me",
            maxResults=max_results
        ).execute()
        
        messages = results.get("messages", [])
        synced_count = 0
        
        for msg in messages:
            # Get full detail
            msg_detail = gmail.users().messages().get(
                userId="me",
                id=msg["id"]
            ).execute()
            
            headers = msg_detail.get("payload", {}).get("headers", [])
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
            sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown")
            date_str = next((h["value"] for h in headers if h["name"] == "Date"), None)
            
            content = msg_detail.get("snippet", "")
            
            # Save to DB
            res = await message_save(
                platform="gmail",
                content=content,
                external_id=msg["id"],
                sender=sender,
                recipient="me",
                metadata={"subject": subject, "headers": headers},
                namespace=namespace
            )
            if res.get("success"):
                synced_count += 1
                
        return {"success": True, "synced_count": synced_count}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def sync_whatsapp_messages(session: str = "default", limit: int = 20, namespace: str = "default") -> Dict[str, Any]:
    """Sync recent WhatsApp messages to DB (from all active chats)."""
    try:
        client = get_whatsapp_client()
        chats = await client.get_chats(session_name=session)
        
        synced_count = 0
        for chat in chats[:5]: # Sync first 5 chats to avoid rate limits
            chat_id = chat.get("id", {}).get("_serialized") or chat.get("id")
            if not chat_id: continue
            
            messages = await client.get_messages(chat_id=chat_id, limit=limit, session_name=session)
            
            for msg in messages:
                # Save to DB
                res = await message_save(
                    platform="whatsapp",
                    content=msg.get("body", ""),
                    external_id=msg.get("id", {}).get("_serialized") or msg.get("id"),
                    sender=msg.get("from"),
                    recipient=msg.get("to"),
                    metadata=msg,
                    namespace=namespace
                )
                if res.get("success"):
                    synced_count += 1
                    
        return {"success": True, "synced_count": synced_count}
    except Exception as e:
        return {"success": False, "error": str(e)}

# MCP Tool Wrappers
async def tool_sync_communications(ctx: Context, namespace: str = "default") -> str:
    """
    Sync recent communications from all platforms (Gmail, WhatsApp) to the unified database.
    This allows the agent to see a chronological history of all interactions.
    """
    results = {}
    
    # Sync Gmail
    results["gmail"] = await sync_gmail_messages(max_results=10, namespace=namespace)
    
    # Sync WhatsApp
    results["whatsapp"] = await sync_whatsapp_messages(namespace=namespace)
    
    return json.dumps({
        "success": True,
        "results": results,
        "timestamp": datetime.now().isoformat()
    }, indent=2)

async def tool_get_unified_history(ctx: Context, platform: Optional[str] = None, limit: int = 20, namespace: str = "default") -> str:
    """
    Get a unified view of recent communications from the database.
    """
    res = await message_list(platform=platform, namespace=namespace, limit=limit)
    return json.dumps(res, indent=2)
