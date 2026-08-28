"""
TASK-120: Bridge untuk mendelegasi task IDE ke services/ai-orchestrator.

Modul ini mengekspos fungsi `call_ai_orchestrator_sync` yang memanggil endpoint
`/api/v1/chat/sync` di AI Orchestrator (port 8001) dan mengembalikan response
text secara langsung tanpa webhook delivery.
"""

import os
import sys
import uuid
from pathlib import Path
from typing import Optional

import httpx

# Load workspace env sebelum baca secret
_mcp_root = Path('/home/aseps/MCP')
if str(_mcp_root) not in sys.path:
    sys.path.insert(0, str(_mcp_root))
from scripts.load_env import load_env

load_env()

AI_ORCHESTRATOR_URL = os.getenv("AI_ORCHESTRATOR_URL", "http://localhost:8001")
CHAT_SYNC_ENDPOINT = f"{AI_ORCHESTRATOR_URL}/api/v1/chat/sync"


def _webhook_secret() -> str:
    """Ambil webhook secret dengan fallback ke legacy name."""
    return os.getenv("MCP_WEBHOOK_SECRET") or os.getenv("WEBHOOK_SECRET") or ""


async def call_ai_orchestrator_sync(
    message: str,
    user_id: str = "ide-agent",
    platform: str = "ide",
    context: str = "",
    conversation_id: Optional[str] = None,
    timeout_seconds: float = 120.0,
) -> dict:
    """
    Panggil AI Orchestrator secara synchronous untuk task IDE.

    Args:
        message: Pesan/task dari user IDE.
        user_id: Identifier session/user IDE.
        platform: Platform identifier (default "ide").
        context: Konteks tambahan untuk orchestrator.
        conversation_id: ID percakapan untuk observability (digenerate jika kosong).
        timeout_seconds: Timeout request ke orchestrator.

    Returns:
        Dictionary dengan keys: status, response, request_id, error (jika ada).
    """
    secret = _webhook_secret()
    if not secret:
        return {
            "status": "error",
            "response": "",
            "request_id": "",
            "error": "Webhook secret tidak dikonfigurasi (MCP_WEBHOOK_SECRET / WEBHOOK_SECRET).",
        }

    payload = {
        "platform": platform,
        "user_id": user_id,
        "message": message,
        "webhook_url": "http://localhost:8000/noop",
        "request_id": conversation_id or str(uuid.uuid4()),
        "context": context,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(
                CHAT_SYNC_ENDPOINT,
                json=payload,
                headers={"X-Webhook-Secret": secret},
            )
            response.raise_for_status()
            data = response.json()
            return {
                "status": data.get("status", "ok"),
                "response": data.get("response", ""),
                "request_id": data.get("request_id", payload["request_id"]),
                "error": "",
            }
    except httpx.HTTPStatusError as e:
        return {
            "status": "error",
            "response": "",
            "request_id": payload["request_id"],
            "error": f"HTTP {e.response.status_code}: {e.response.text[:500]}",
        }
    except httpx.RequestError as e:
        return {
            "status": "error",
            "response": "",
            "request_id": payload["request_id"],
            "error": f"Request gagal: {str(e)}",
        }
    except Exception as e:
        return {
            "status": "error",
            "response": "",
            "request_id": payload["request_id"],
            "error": f"Unexpected error: {str(e)}",
        }
