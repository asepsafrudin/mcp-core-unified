from __future__ import annotations

import json
import os
import uuid
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Import WhatsApp client from local integration
# Assumes mcp-unified is in the python path or using relative imports if within the package
try:
    from integrations.whatsapp.client import get_whatsapp_client
except ImportError:
    # Fallback to absolute import if needed
    import sys
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from integrations.whatsapp.client import get_whatsapp_client

logger = logging.getLogger("mcp-reporting-service")

# Configuration from env
# These should be set in the central .env handled by mcp-unified
LOG_DIR = Path(os.getenv("MCP_LOG_DIR", "/home/aseps/MCP/logs"))
REPORT_LOG_FILE = LOG_DIR / "universal_reports.jsonl"
WAHA_SESSION = os.getenv("WHATSAPP_SESSION", "default")
DEFAULT_RECIPIENT = os.getenv("WHATSAPP_RECIPIENT", "")

@dataclass
class UniversalReport:
    """
    A generic report structure that can be used for anomalies, 
    status updates, or audit findings.
    """
    recipient_name: str
    recipient_phone: str
    title: str
    summary: str
    details: Dict[str, Any] = field(default_factory=dict)
    impact: str = ""
    recommendation: str = ""
    report_type: str = "anomaly"  # anomaly, info, alert, audit
    reporter_name: str = "MCP Unified"
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_whatsapp_message(self) -> str:
        """Format the report into a polite WhatsApp message."""
        parts = [
            f"Assalamu’alaikum {self.recipient_name},",
            "",
            f"Saya dari {self.reporter_name} ingin melaporkan {self.report_type} data/sistem yang perlu diperhatikan.",
            "",
            f"*Judul:*",
            self.title,
            "",
            f"*Ringkasan:*",
            self.summary.strip(),
        ]

        if self.details:
            parts.append("")
            parts.append("*Detail:*")
            for key, val in self.details.items():
                label = key.replace("_", " ").title()
                parts.append(f"• {label}: {val}")

        if self.impact:
            parts.extend(["", f"*Dampak:* {self.impact}"])
        if self.recommendation:
            parts.extend(["", f"*Rekomendasi:* {self.recommendation}"])

        parts.extend([
            "",
            "Mohon arahan lebih lanjut untuk tindak lanjut.",
            "",
            "Terima kasih.",
            "Wassalamu’alaikum."
        ])
        return "\n".join(parts)

class ReportingService:
    """
    Universal service for managing and delivering reports across different channels.
    """
    
    def __init__(self):
        self.wa_client = get_whatsapp_client()
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _append_to_log(self, record: Dict[str, Any]):
        """Persist report record to JSONL log."""
        with REPORT_LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    async def send_report(self, report: UniversalReport, channel: str = "whatsapp") -> Dict[str, Any]:
        """
        Send a report via a specified channel.
        Currently supports: whatsapp
        """
        if channel == "whatsapp":
            return await self._send_via_whatsapp(report)
        else:
            error_msg = f"Channel {channel} not supported."
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    async def _send_via_whatsapp(self, report: UniversalReport) -> Dict[str, Any]:
        """Internal helper for WhatsApp delivery."""
        message = report.to_whatsapp_message()
        chat_id = report.recipient_phone
        if "@" not in chat_id:
            chat_id = f"{chat_id}@c.us"

        try:
            result = await self.wa_client.send_message(
                chat_id=chat_id,
                text=message,
                session_name=WAHA_SESSION
            )
            
            status = "sent"
            self._append_to_log({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "report_id": report.report_id,
                "channel": "whatsapp",
                "status": status,
                "recipient": report.recipient_phone,
                "payload": asdict(report),
                "wa_result": result
            })
            
            return {"success": True, "report_id": report.report_id, "wa_result": result}
        except Exception as e:
            logger.error(f"Failed to send WhatsApp report: {e}")
            self._append_to_log({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "report_id": report.report_id,
                "channel": "whatsapp",
                "status": "failed",
                "error": str(e),
                "payload": asdict(report)
            })
            return {"success": False, "error": str(e)}

    def list_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent report history."""
        if not REPORT_LOG_FILE.exists():
            return []
        
        with REPORT_LOG_FILE.open("r", encoding="utf-8") as f:
            lines = f.readlines()
            
        records = []
        for line in lines[-limit:]:
            try:
                records.append(json.loads(line.strip()))
            except:
                continue
        return records

# Singleton instance
_service: Optional[ReportingService] = None

def get_reporting_service() -> ReportingService:
    global _service
    if _service is None:
        _service = ReportingService()
    return _service
