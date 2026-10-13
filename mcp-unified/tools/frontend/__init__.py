"""
Frontend Design Tools — TASK-188

Gate anti-"AI slop" deterministik berbasis engine Impeccable yang ter-vendor
(vendor/impeccable/bin/impeccable). Hanya subcommand `detect` yang dipakai:
deterministik, tanpa LLM, tanpa API key. Telemetry WAJIB mati (DO_NOT_TRACK=1).

Lihat:
- vendor/impeccable/NOTICE.md  (atribusi & lingkup adopsi)
- tasks/01_active/TASK-188-frontend-agent-impeccable.md  (konteks task)
"""
import json
import os
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from observability.logger import logger
from tools.file.path_utils import is_safe_path
from execution import registry

_WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
IMPECCABLE_BIN = os.environ.get("IMPECCABLE_BIN") or str(
    _WORKSPACE_ROOT / "vendor" / "impeccable" / "bin" / "impeccable"
)

_DEFAULT_TIMEOUT = 60


def _bin_available() -> tuple:
    p = Path(IMPECCABLE_BIN)
    if p.is_file() and os.access(IMPECCABLE_BIN, os.X_OK):
        return True, str(p)
    return False, (
        f"Engine binary tidak ditemukan/tidak eksekutabel di {IMPECCABLE_BIN}. "
        "Jalankan: bash vendor/impeccable/fetch.sh"
    )


async def frontend_detect(
    target: str,
    json_output: bool = True,
    no_config: bool = False,
    scope: str = "",
    viewport: str = "",
    timeout_seconds: int = _DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """
    Jalankan detector anti-pattern desain frontend (engine Impeccable) pada file, direktori, atau URL.
    Gate objektif anti-"AI slop": deterministik, tanpa LLM, tanpa API key. Menangkap gradien
    ungu default, font overused (Inter), bounce easing, kartu bersarang, kontras rendah (WCAG),
    ikon-tile di atas heading, dsb.

    Args:
        target: Path absolut ke file/direktori, atau URL (http(s):// atau file://). Path lokal wajib absolut.
        json_output: True (default) → findings terstruktur di field `findings` + `summary`.
        no_config: True untuk mengabaikan .impeccable/config.json, DESIGN.md, dan inline ignore (raw scan).
        scope: Batasi aturan ke domain, mis. "type" atau "layout" (comma-separated). Kosong = semua.
        viewport: Viewport browser untuk URL scan, mis. "390x844" (mobile). Default engine 1280x800.
        timeout_seconds: Batas eksekusi detector (default 60s).

    Returns:
        Dict { success, exit_code, target, findings, summary, stderr }.
        exit_code: 0 = bersih, 2 = ada primary findings, 1 = target tak terbaca (operasional).
        success True hanya untuk exit_code 0 atau 2.
    """
    is_url = target.startswith(("http://", "https://", "file://"))
    if not is_url:
        if not target.startswith("/"):
            return {"success": False, "error": "Path lokal harus absolut.", "target": target}
        if not is_safe_path(target):
            return {"success": False, "error": f"Path ditolak oleh keamanan: {target}", "target": target}
        if not Path(target).exists():
            return {"success": False, "error": f"Target tidak ditemukan: {target}", "target": target}

    ok, msg = _bin_available()
    if not ok:
        return {"success": False, "error": msg}

    cmd: List[str] = [IMPECCABLE_BIN, "detect"]
    if json_output:
        cmd.append("--json")
    if no_config:
        cmd.append("--no-config")
    if scope:
        cmd.extend(["--scope", scope])
    if viewport:
        cmd.extend(["--viewport", viewport])
    cmd.append(target)

    env = dict(os.environ)
    env["DO_NOT_TRACK"] = "1"
    env["IMPECCABLE_NO_TELEMETRY"] = "1"

    logger.info("frontend_detect_run", target=target, json_output=json_output, scope=scope)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Detector timeout setelah {timeout_seconds}s", "target": target}
    except Exception as e:
        logger.error("frontend_detect_exec_error", error=str(e), target=target)
        return {"success": False, "error": f"Gagal menjalankan detector: {e}", "target": target}

    exit_code = proc.returncode
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""

    findings: List[Dict[str, Any]] = []
    parsed = False
    if json_output and stdout.strip():
        try:
            data = json.loads(stdout)
            if isinstance(data, list):
                findings = data
                parsed = True
            elif isinstance(data, dict):
                findings = data.get("findings", []) or []
                parsed = True
        except json.JSONDecodeError as e:
            logger.warning("frontend_detect_json_parse_error", error=str(e), target=target)

    by_rule = dict(Counter(f.get("antipattern") or f.get("rule") for f in findings))
    by_severity = dict(Counter(f.get("severity") for f in findings))
    by_category = dict(Counter(f.get("category") for f in findings))

    return {
        "success": exit_code in (0, 2),
        "exit_code": exit_code,
        "target": target,
        "findings": findings,
        "summary": {
            "total": len(findings),
            "by_rule": by_rule,
            "by_severity": by_severity,
            "by_category": by_category,
            "parsed_json": parsed,
        },
        "stderr": stderr.strip(),
        "raw_stdout_truncated": (stdout[:4000] if not parsed else None),
    }


def register_frontend_tools(registry_obj) -> int:
    """Daftarkan frontend tools ke execution.registry. Idempoten."""
    tools_list = [frontend_detect]
    registered = 0
    for fn in tools_list:
        try:
            name = getattr(fn, "__name__", None)
            if name and registry_obj.get_tool(name) is None:
                registry_obj.register(fn, name=name, category="frontend")
                registered += 1
        except Exception as e:
            logger.warning("frontend_tool_register_failed", name=name, error=str(e))
    return registered


__all__ = ["frontend_detect", "register_frontend_tools", "IMPECCABLE_BIN"]
