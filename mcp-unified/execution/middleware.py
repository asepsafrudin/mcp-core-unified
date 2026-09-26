"""
execution/middleware.py — Enforcement Middleware & Governance Guardrails
Menegakkan aturan operasional secara deterministik:
1. Path Allowlist: scripts/, storage/, scratch/, brain/ (Anti-Root Spill)
2. Larangan keras 'sudo' (Non-root enforcement aseps:aseps)
3. Audit Trail dengan Trace ID unik per request
4. Truncation Guard: Menjaga payload ringkasan < 500 token
"""

import os
import re
import json
import uuid
import time
from pathlib import Path
from typing import Dict, Any, Optional

WORKSPACE_ROOT = Path("/home/aseps/MCP").resolve()

ALLOWED_DIR_PREFIXES = (
    str(WORKSPACE_ROOT / "scripts"),
    str(WORKSPACE_ROOT / "storage"),
    str(WORKSPACE_ROOT / "scratch"),
    "/home/aseps/.gemini/antigravity-ide/brain",
)

LOG_DIR = WORKSPACE_ROOT / "logs"
AUDIT_LOG_FILE = LOG_DIR / "agent_audit.log"


class EnforcementError(PermissionError):
    """Exception khusus untuk pelanggaran governance workspace."""
    pass


class EnforcementMiddleware:
    """Middleware deterministik pelindung integritas workspace & audit trail."""

    @staticmethod
    def validate_path(target_path: str) -> str:
        """
        Validasi apakah berkas sasaran berada dalam direktori yang diizinkan (Allowlist).
        Mencegah penulisan berkas liar di root workspace atau direktori sistem.
        """
        if not target_path:
            raise EnforcementError("Path target tidak boleh kosong.")

        path_obj = Path(target_path).expanduser()
        if not path_obj.is_absolute():
            path_obj = (WORKSPACE_ROOT / path_obj).resolve()
        else:
            path_obj = path_obj.resolve()

        resolved_str = str(path_obj)

        # Cek apakah persis di root workspace (dilarang sesuai Aturan Kebersihan Root)
        if path_obj.parent == WORKSPACE_ROOT:
            raise EnforcementError(
                f"Pelanggaran Integritas: Dilarang menulis file langsung di root '{WORKSPACE_ROOT}'. "
                f"Gunakan direktori scripts/, storage/, atau scratch/."
            )

        # Cek apakah berada dalam salah satu allowlist
        is_allowed = any(resolved_str.startswith(prefix) for prefix in ALLOWED_DIR_PREFIXES)
        if not is_allowed:
            raise EnforcementError(
                f"Akses Ditolak: Path '{resolved_str}' berada di luar allowlist direktori aman "
                f"(Hanya scripts/, storage/, scratch/, atau brain/ yang diizinkan)."
            )

        # Pastikan parent direktori ada
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        return resolved_str

    @staticmethod
    def check_sudo_forbidden(command_or_code: str) -> None:
        """
        Pemeriksaan larangan keras sudo.
        Dijalankan sebelum subprocess atau penulisan skrip eksekusi.
        """
        if not command_or_code:
            return

        if re.search(r"\bsudo\b", command_or_code, re.IGNORECASE):
            raise EnforcementError(
                "Pelanggaran Kritis Protokol #1.5: Penggunaan perintah 'sudo' DILARANG KERAS di lingkungan workspace aseps:aseps."
            )

    @staticmethod
    def generate_trace_id() -> str:
        """Membuat Trace ID unik untuk ketertelusuran lintas komponen."""
        return f"TRC-{int(time.time())}-{uuid.uuid4().hex[:8].upper()}"

    @staticmethod
    def truncate_summary(text: str, max_chars: int = 1800) -> str:
        """
        Memastikan response text tidak melebihi ~450 token
        untuk mencegah context window bloat di Agent IDE.
        """
        if not text:
            return ""
        if len(text) <= max_chars:
            return text
        return text[:max_chars - 30] + "\n... [Ringkasan dipotong untuk efisiensi context window]"

    @classmethod
    def audit_log(cls, trace_id: str, tool_name: str, status: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Mencatat aktivitas eksekusi ke audit log lokal."""
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            record = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "trace_id": trace_id,
                "tool_name": tool_name,
                "status": status,
                "details": details or {}
            }
            with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            # Audit log tidak boleh mematikan proses utama jika gagal menulis
            pass
