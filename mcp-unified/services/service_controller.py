"""
Service controller utilities for MCP Unified.

Provides start/stop/status helpers for WhatsApp bot, Telegram bot, and Scheduler daemon.
Intended for admin web UI usage.
"""
from __future__ import annotations

import os
import json
import shutil
import signal
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]

WHATSAPP_LOG = "/tmp/whatsapp_bot.log"
TELEGRAM_LOG = "/tmp/telegram_bot.log"
SCHEDULER_LOG = "/tmp/mcp_scheduler.log"
SSE_LOG = "/tmp/mcp_sse.log"
KNOWLEDGE_ADMIN_LOG = "/tmp/knowledge_admin.log"
SELF_HEALING_LOG = "/tmp/self_healing.log"
WATCHER_LOG = "/tmp/telegram_watcher.log"
SQL_BOT_LOG = str(PROJECT_ROOT / "integrations/telegram/sql_bot.log")
SQL_BOT_PID = PROJECT_ROOT / "integrations/telegram/sql_bot.pid"

LOG_PATHS = {
    "mcp_sse": SSE_LOG,
    "knowledge_admin": KNOWLEDGE_ADMIN_LOG,
    "whatsapp": WHATSAPP_LOG,
    "telegram": TELEGRAM_LOG,
    "telegram_sql_bot": SQL_BOT_LOG,
    "telegram_watcher": WATCHER_LOG,
    "self_healing": SELF_HEALING_LOG,
    "scheduler": SCHEDULER_LOG,
}


def _run_command(cmd: List[str], cwd: Optional[Path] = None) -> Dict[str, Any]:
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def _pgrep(pattern: str) -> List[int]:
    result = subprocess.run(
        ["pgrep", "-f", pattern],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [int(pid) for pid in result.stdout.split() if pid.strip().isdigit()]


def _kill_processes(pattern: str) -> Dict[str, Any]:
    pids = _pgrep(pattern)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
    return {"killed": pids}


def _start_process(cmd: List[str], log_path: str) -> Dict[str, Any]:
    log_file = open(log_path, "a")
    proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        stdout=log_file,
        stderr=log_file,
        start_new_session=True,
        env={
            **os.environ,
            "PYTHONPATH": f"{PROJECT_ROOT}:{os.environ.get('PYTHONPATH', '')}",
        },
    )
    return {"pid": proc.pid, "log": log_path}


def _scheduler_systemctl_available() -> bool:
    return shutil.which("systemctl") is not None


def _scheduler_status() -> Dict[str, Any]:
    if _scheduler_systemctl_available():
        status = _run_command(["systemctl", "is-active", "mcp-scheduler.service"])
        return {
            "running": status["stdout"] == "active",
            "method": "systemctl",
            "raw": status,
        }

    pid_file = Path("/tmp/mcp-scheduler.pid")
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
            return {"running": True, "method": "pid_file", "pid": pid}
        except (ValueError, ProcessLookupError, PermissionError):
            return {"running": False, "method": "pid_file", "pid": None}
    return {"running": False, "method": "pid_file", "pid": None}


def _sse_status() -> Dict[str, Any]:
    pids = _pgrep("mcp_server_sse.py")
    return {"running": bool(pids), "pids": pids, "log": SSE_LOG, "label": "MCP SSE Server"}


def _knowledge_admin_status() -> Dict[str, Any]:
    pids = _pgrep("knowledge.admin.app")
    return {"running": bool(pids), "pids": pids, "log": KNOWLEDGE_ADMIN_LOG, "label": "Knowledge Admin"}


def _sql_bot_status() -> Dict[str, Any]:
    pid = None
    running = False
    if SQL_BOT_PID.exists():
        try:
            pid = int(SQL_BOT_PID.read_text().strip())
            os.kill(pid, 0)
            running = True
        except (ValueError, ProcessLookupError, PermissionError):
            running = False
    return {
        "running": running,
        "pid": pid,
        "log": SQL_BOT_LOG,
        "label": "Telegram SQL Bot",
    }


def _telegram_watcher_status() -> Dict[str, Any]:
    pids = _pgrep("watch_telegram.sh")
    return {"running": bool(pids), "pids": pids, "log": WATCHER_LOG, "label": "Telegram Watcher"}


def _gdrive_mount_status() -> Dict[str, Any]:
    if shutil.which("systemctl") is None:
        return {"running": False, "method": "systemctl", "label": "GDrive Mount"}
    status = _run_command(["systemctl", "--user", "is-active", "gdrive-mount.service"])
    return {
        "running": status["stdout"] == "active",
        "method": "systemctl-user",
        "raw": status,
        "label": "GDrive Mount",
    }


def _self_healing_status() -> Dict[str, Any]:
    pids = _pgrep("run_self_healing.py")
    return {"running": bool(pids), "pids": pids, "log": SELF_HEALING_LOG, "label": "Self-Healing Agent"}


def _legal_agent_timer_status() -> Dict[str, Any]:
    if shutil.which("systemctl") is None:
        return {"running": False, "method": "systemctl", "label": "Legal Agent Timers"}
    scheduler_status = _run_command(["systemctl", "is-active", "legal-agent-scheduler.timer"])
    notify_status = _run_command(["systemctl", "is-active", "legal-agent-notify.timer"])
    return {
        "running": scheduler_status["stdout"] == "active" and notify_status["stdout"] == "active",
        "method": "systemctl",
        "raw": {
            "scheduler": scheduler_status,
            "notify": notify_status,
        },
        "label": "Legal Agent Timers",
    }


def _whatsapp_status() -> Dict[str, Any]:
    pids = _pgrep("integrations.whatsapp.bot_server")
    return {"running": bool(pids), "pids": pids, "log": WHATSAPP_LOG, "label": "WhatsApp Bot"}


def _telegram_status() -> Dict[str, Any]:
    pids = _pgrep("integrations.telegram.run")
    return {"running": bool(pids), "pids": pids, "log": TELEGRAM_LOG, "label": "Telegram Bot"}


def get_all_service_status() -> Dict[str, Any]:
    return {
        "mcp_sse": _sse_status(),
        "knowledge_admin": _knowledge_admin_status(),
        "whatsapp": _whatsapp_status(),
        "telegram": _telegram_status(),
        "telegram_sql_bot": _sql_bot_status(),
        "telegram_watcher": _telegram_watcher_status(),
        "gdrive_mount": _gdrive_mount_status(),
        "self_healing": _self_healing_status(),
        "scheduler": _scheduler_status(),
        "legal_agent_timers": _legal_agent_timer_status(),
    }


def start_whatsapp() -> Dict[str, Any]:
    _kill_processes("integrations.whatsapp.bot_server")
    result = _start_process(["python3", "integrations/whatsapp/bot_server.py"], WHATSAPP_LOG)
    return {"success": True, "started": result, "status": _whatsapp_status()}


def stop_whatsapp() -> Dict[str, Any]:
    return {"success": True, "stopped": _kill_processes("integrations.whatsapp.bot_server")}


def start_telegram() -> Dict[str, Any]:
    _kill_processes("integrations.telegram.run")
    result = _start_process(
        [
            "python3",
            "-m",
            "integrations.telegram.run",
            "--config",
            "integrations/telegram/.env",
        ],
        TELEGRAM_LOG,
    )
    return {"success": True, "started": result, "status": _telegram_status()}


def stop_telegram() -> Dict[str, Any]:
    result = _kill_processes("integrations.telegram.run")
    _kill_processes("python3 run.py")
    return {"success": True, "stopped": result}


def start_scheduler() -> Dict[str, Any]:
    if _scheduler_systemctl_available():
        result = _run_command(["systemctl", "start", "mcp-scheduler.service"])
        return {"success": result["returncode"] == 0, "result": result, "status": _scheduler_status()}

    result = _start_process(["python3", "scheduler/daemon.py"], SCHEDULER_LOG)
    return {"success": True, "started": result, "status": _scheduler_status()}


def stop_scheduler() -> Dict[str, Any]:
    if _scheduler_systemctl_available():
        result = _run_command(["systemctl", "stop", "mcp-scheduler.service"])
        return {"success": result["returncode"] == 0, "result": result, "status": _scheduler_status()}

    pid_file = Path("/tmp/mcp-scheduler.pid")
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            return {"success": True, "stopped": pid}
        except (ValueError, ProcessLookupError, PermissionError) as exc:
            return {"success": False, "error": str(exc)}
    return {"success": False, "error": "pid_file_not_found"}


def restart_service(service: str) -> Dict[str, Any]:
    if service == "mcp_sse":
        stop_mcp_sse()
        return start_mcp_sse()
    if service == "knowledge_admin":
        stop_knowledge_admin()
        return start_knowledge_admin()
    if service == "whatsapp":
        stop_whatsapp()
        return start_whatsapp()
    if service == "telegram":
        stop_telegram()
        return start_telegram()
    if service == "telegram_sql_bot":
        stop_telegram_sql_bot()
        return start_telegram_sql_bot()
    if service == "telegram_watcher":
        stop_telegram_watcher()
        return start_telegram_watcher()
    if service == "gdrive_mount":
        stop_gdrive_mount()
        return start_gdrive_mount()
    if service == "self_healing":
        return start_self_healing()
    if service == "scheduler":
        stop_scheduler()
        return start_scheduler()
    if service == "legal_agent_timers":
        stop_legal_agent_timers()
        return start_legal_agent_timers()
    return {"success": False, "error": f"Unknown service: {service}"}


def start_service(service: str) -> Dict[str, Any]:
    if service == "mcp_sse":
        return start_mcp_sse()
    if service == "knowledge_admin":
        return start_knowledge_admin()
    if service == "whatsapp":
        return start_whatsapp()
    if service == "telegram":
        return start_telegram()
    if service == "telegram_sql_bot":
        return start_telegram_sql_bot()
    if service == "telegram_watcher":
        return start_telegram_watcher()
    if service == "gdrive_mount":
        return start_gdrive_mount()
    if service == "self_healing":
        return start_self_healing()
    if service == "scheduler":
        return start_scheduler()
    if service == "legal_agent_timers":
        return start_legal_agent_timers()
    return {"success": False, "error": f"Unknown service: {service}"}


def stop_service(service: str) -> Dict[str, Any]:
    if service == "mcp_sse":
        return stop_mcp_sse()
    if service == "knowledge_admin":
        return stop_knowledge_admin()
    if service == "whatsapp":
        return stop_whatsapp()
    if service == "telegram":
        return stop_telegram()
    if service == "telegram_sql_bot":
        return stop_telegram_sql_bot()
    if service == "telegram_watcher":
        return stop_telegram_watcher()
    if service == "gdrive_mount":
        return stop_gdrive_mount()
    if service == "self_healing":
        return {"success": True, "message": "Self-healing is a one-off task"}
    if service == "scheduler":
        return stop_scheduler()
    if service == "legal_agent_timers":
        return stop_legal_agent_timers()
    return {"success": False, "error": f"Unknown service: {service}"}


def get_service_log(service: str, lines: int = 200) -> Dict[str, Any]:
    log_path = LOG_PATHS.get(service)
    if not log_path:
        return {"success": False, "error": "log_not_available"}
    if not os.path.exists(log_path):
        return {"success": False, "error": "log_file_missing", "path": log_path}
    try:
        with open(log_path, "r") as handle:
            data = handle.readlines()[-lines:]
        return {"success": True, "path": log_path, "lines": data}
    except Exception as exc:
        return {"success": False, "error": str(exc), "path": log_path}


def get_error_summary(lines: int = 200) -> Dict[str, Any]:
    """Return error summary per service based on log keywords."""
    keywords = ["ERROR", "EXCEPTION", "Traceback"]
    summary: Dict[str, Any] = {}
    for service, log_path in LOG_PATHS.items():
        if not os.path.exists(log_path):
            summary[service] = {"count": 0, "latest": None}
            continue
        try:
            with open(log_path, "r") as handle:
                data = handle.readlines()[-lines:]
            error_lines = [line for line in data if any(k in line for k in keywords)]
            summary[service] = {
                "count": len(error_lines),
                "latest": error_lines[-1].strip() if error_lines else None,
            }
        except Exception:
            summary[service] = {"count": 0, "latest": None}
    return summary


def start_mcp_sse() -> Dict[str, Any]:
    _kill_processes("mcp_server_sse.py")
    result = _start_process(["python3", "mcp_server_sse.py"], SSE_LOG)
    return {"success": True, "started": result, "status": _sse_status()}


def stop_mcp_sse() -> Dict[str, Any]:
    return {"success": True, "stopped": _kill_processes("mcp_server_sse.py")}


def start_knowledge_admin() -> Dict[str, Any]:
    _kill_processes("knowledge.admin.app")
    result = _start_process(["python3", "-m", "knowledge.admin.app"], KNOWLEDGE_ADMIN_LOG)
    return {"success": True, "started": result, "status": _knowledge_admin_status()}


def stop_knowledge_admin() -> Dict[str, Any]:
    return {"success": True, "stopped": _kill_processes("knowledge.admin.app")}


def start_telegram_sql_bot() -> Dict[str, Any]:
    result = _run_command(["bash", "run_sql_bot.sh"], cwd=PROJECT_ROOT / "integrations/telegram")
    return {"success": result["returncode"] == 0, "result": result, "status": _sql_bot_status()}


def stop_telegram_sql_bot() -> Dict[str, Any]:
    stopped = []
    if SQL_BOT_PID.exists():
        try:
            pid = int(SQL_BOT_PID.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            stopped.append(pid)
        except (ValueError, ProcessLookupError, PermissionError):
            pass
    _kill_processes("bot_server_sql_focused.py")
    return {"success": True, "stopped": stopped}


def start_telegram_watcher() -> Dict[str, Any]:
    _kill_processes("watch_telegram.sh")
    result = _start_process(["bash", "integrations/telegram/watch_telegram.sh"], WATCHER_LOG)
    return {"success": True, "started": result, "status": _telegram_watcher_status()}


def stop_telegram_watcher() -> Dict[str, Any]:
    return {"success": True, "stopped": _kill_processes("watch_telegram.sh")}


def start_gdrive_mount() -> Dict[str, Any]:
    if shutil.which("systemctl") is None:
        return {"success": False, "error": "systemctl not available"}
    result = _run_command(["systemctl", "--user", "start", "gdrive-mount.service"])
    return {"success": result["returncode"] == 0, "result": result, "status": _gdrive_mount_status()}


def stop_gdrive_mount() -> Dict[str, Any]:
    if shutil.which("systemctl") is None:
        return {"success": False, "error": "systemctl not available"}
    result = _run_command(["systemctl", "--user", "stop", "gdrive-mount.service"])
    return {"success": result["returncode"] == 0, "result": result, "status": _gdrive_mount_status()}


def start_self_healing() -> Dict[str, Any]:
    result = _start_process(["python3", "core/monitoring/run_self_healing.py"], SELF_HEALING_LOG)
    return {"success": True, "started": result, "status": _self_healing_status()}


def start_legal_agent_timers() -> Dict[str, Any]:
    if shutil.which("systemctl") is None:
        return {"success": False, "error": "systemctl not available"}
    scheduler_result = _run_command(["systemctl", "start", "legal-agent-scheduler.timer"])
    notify_result = _run_command(["systemctl", "start", "legal-agent-notify.timer"])
    return {
        "success": scheduler_result["returncode"] == 0 and notify_result["returncode"] == 0,
        "result": {"scheduler": scheduler_result, "notify": notify_result},
        "status": _legal_agent_timer_status(),
    }


def stop_legal_agent_timers() -> Dict[str, Any]:
    if shutil.which("systemctl") is None:
        return {"success": False, "error": "systemctl not available"}
    scheduler_result = _run_command(["systemctl", "stop", "legal-agent-scheduler.timer"])
    notify_result = _run_command(["systemctl", "stop", "legal-agent-notify.timer"])
    return {
        "success": scheduler_result["returncode"] == 0 and notify_result["returncode"] == 0,
        "result": {"scheduler": scheduler_result, "notify": notify_result},
        "status": _legal_agent_timer_status(),
    }