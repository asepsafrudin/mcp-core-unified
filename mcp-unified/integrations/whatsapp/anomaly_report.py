"""
Helpers for composing and logging WhatsApp anomaly reports.

This keeps one finding = one message, with a lightweight history trail
that can be reused by different agents and tools.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_LOG_PATH = Path(
    os.getenv(
        "WHATSAPP_ANOMALY_LOG_PATH",
        "/home/aseps/MCP/logs/whatsapp_anomaly_reports.jsonl",
    )
)


@dataclass
class AnomalyReport:
    recipient_name: str
    recipient_phone: str
    finding_title: str
    finding_summary: str
    record_key: str = ""
    source_label: str = ""
    source_ref: str = ""
    impact: str = ""
    recommendation: str = ""
    reporter_name: str = "MCP Unified"
    reporter_role: str = "agent"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_message(self) -> str:
        lines = [
            f"Assalamu’alaikum {self.recipient_name},",
            "",
            f"Saya dari {self.reporter_name} ingin melaporkan temuan anomali data yang perlu dicek lebih lanjut.",
            "",
            f"*Temuan:*",
            f"{self.finding_title}",
            "",
            f"*Ringkasan:*",
            self.finding_summary.strip(),
        ]

        if self.record_key:
            lines.extend(["", f"*Kunci Data:* {self.record_key}"])
        if self.source_label:
            lines.extend(["", f"*Sumber:* {self.source_label}"])
        if self.source_ref:
            lines.extend(["", f"*Referensi:* {self.source_ref}"])
        if self.impact:
            lines.extend(["", f"*Dampak:* {self.impact}"])
        if self.recommendation:
            lines.extend(["", f"*Rekomendasi:* {self.recommendation}"])

        lines.extend(
            [
                "",
                "Jika berkenan, mohon arahan apakah data ini perlu dikoreksi di sumber atau cukup difilter di tampilan.",
                "",
                "Terima kasih.",
                "Wassalamu’alaikum.",
            ]
        )
        return "\n".join(lines)

    def to_log_record(self, *, message: str, status: str, wa_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = asdict(self)
        payload.update(
            {
                "message": message,
                "status": status,
                "wa_result": wa_result or {},
            }
        )
        return payload


def build_anomaly_report(
    *,
    recipient_name: str,
    recipient_phone: str,
    finding_title: str,
    finding_summary: str,
    record_key: str = "",
    source_label: str = "",
    source_ref: str = "",
    impact: str = "",
    recommendation: str = "",
    reporter_name: str = "MCP Unified",
    reporter_role: str = "agent",
) -> AnomalyReport:
    return AnomalyReport(
        recipient_name=recipient_name,
        recipient_phone=recipient_phone,
        finding_title=finding_title,
        finding_summary=finding_summary,
        record_key=record_key,
        source_label=source_label,
        source_ref=source_ref,
        impact=impact,
        recommendation=recommendation,
        reporter_name=reporter_name,
        reporter_role=reporter_role,
    )


def append_anomaly_report_log(record: Dict[str, Any], log_path: Path = DEFAULT_LOG_PATH) -> Path:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return log_path
