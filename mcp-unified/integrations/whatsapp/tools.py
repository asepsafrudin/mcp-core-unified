"""
MCP Tools for WhatsApp Integration using WAHA.
"""

import json
from typing import Optional, List, Dict, Any
from mcp.server.fastmcp import Context

from .client import get_whatsapp_client


async def whatsapp_get_status(ctx: Context) -> str:
    """
    Get the status of the WhatsApp integration and sessions.
    """
    try:
        client = get_whatsapp_client()
        status = await client.get_status()
        sessions = await client.list_sessions()
        
        return json.dumps({
            "success": True,
            "status": status,
            "sessions": sessions
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def whatsapp_send_message(
    ctx: Context,
    to: str,
    text: str,
    session: str = "default"
) -> str:
    """
    Send a WhatsApp message to a specific number or chat.
    
    Args:
        to: Recipient phone number with country code (e.g. '62812345678')
            Note: Do not include +, just the numbers.
        text: The message content to send.
        session: WhatsApp session name (default: 'default')
    """
    try:
        # Normalize chat_id
        chat_id = to
        if not chat_id.endswith("@c.us") and not chat_id.endswith("@g.us"):
            chat_id = f"{chat_id}@c.us"
            
        client = get_whatsapp_client()
        result = await client.send_message(chat_id=chat_id, text=text, session_name=session)
        
        return json.dumps({
            "success": True,
            "result": result
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def whatsapp_get_qr(
    ctx: Context,
    session: str = "default"
) -> str:
    """
    Get the QR code for authenticating a WhatsApp session.
    Visit the returned URL or use the base64 data to link your device.
    """
    try:
        client = get_whatsapp_client()
        
        # Ensure session is started
        try:
            await client.start_session(session)
        except:
            pass # Might already be started
            
        qr_data = await client.get_qr_code(session_name=session)
        
        return json.dumps({
            "success": True,
            "session": session,
            "qr": qr_data,
            "instructions": "Scan this QR code in your WhatsApp mobile app (Linked Devices > Link a Device)"
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def whatsapp_list_chats(
    ctx: Context,
    session: str = "default"
) -> str:
    """
    List active chats and groups in a WhatsApp session.
    """
    try:
        client = get_whatsapp_client()
        chats = await client.get_chats(session_name=session)
        
        return json.dumps({
            "success": True,
            "session": session,
            "chats": chats
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def whatsapp_get_messages(
    ctx: Context,
    chat_id: str,
    limit: int = 20,
    session: str = "default"
) -> str:
    """
    Get recent messages from a specific WhatsApp chat or group.
    
    Args:
        chat_id: The ID of the chat (e.g. '62812345678@c.us' or 'group_id@g.us')
        limit: Number of messages to retrieve (default: 20)
        session: WhatsApp session name (default: 'default')
    """
    try:
        client = get_whatsapp_client()
        messages = await client.get_messages(chat_id=chat_id, limit=limit, session_name=session)
        
        return json.dumps({
            "success": True,
            "session": session,
            "chat_id": chat_id,
            "messages": messages
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def whatsapp_send_formal_report(
    ctx: Context,
    recipient_name: str,
    recipient_phone: str,
    title: str,
    summary: str,
    details: Optional[Dict[str, Any]] = None,
    impact: str = "",
    recommendation: str = "",
    report_type: str = "anomaly"
) -> str:
    """
    Send a formal/professional report via WhatsApp.
    Useful for reporting data anomalies, audit findings, or critical alerts.
    
    Args:
        recipient_name: Name of the person receiving the report (e.g. 'Pak Asep')
        recipient_phone: Phone number (e.g. '62812345678')
        title: Short title of the finding/issue
        summary: Clear summary of the discovery
        details: Optional key-value pairs with technical details
        impact: Describe the impact of this finding
        recommendation: Provide a call to action or fix
        report_type: Category of the report (default: 'anomaly')
    """
    try:
        from core.reporting.service import UniversalReport, get_reporting_service
        
        report = UniversalReport(
            recipient_name=recipient_name,
            recipient_phone=recipient_phone,
            title=title,
            summary=summary,
            details=details or {},
            impact=impact,
            recommendation=recommendation,
            report_type=report_type
        )
        
        service = get_reporting_service()
        result = await service.send_report(report, channel="whatsapp")
        
        return json.dumps({
            "success": True,
            "message": "Formal report sent successfully",
            "report_id": report.report_id,
            "wa_result": result.get("wa_result")
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)
