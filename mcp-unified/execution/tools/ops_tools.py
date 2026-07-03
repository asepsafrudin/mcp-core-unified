import asyncio
import os
import sys
import subprocess
from typing import Dict, Any, List, Optional
from observability.logger import logger
from execution import registry

# Path helper
PROJECT_ROOT = "/home/aseps/MCP"
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts")

async def _run_script_async(cmd: List[str], cwd: str = PROJECT_ROOT) -> Dict[str, Any]:
    """Execute a script asynchronously and return stdout, stderr, and code."""
    try:
        # Use absolute python binary if python3 is called
        if cmd[0] == "python3":
            venv_python = os.path.join(PROJECT_ROOT, ".venv", "bin", "python3")
            if os.path.exists(venv_python):
                cmd[0] = venv_python

        logger.info("ops_tools_executing", command=cmd)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd
        )
        
        stdout, stderr = await proc.communicate()
        return {
            "success": proc.returncode == 0,
            "stdout": stdout.decode("utf-8", errors="replace").strip(),
            "stderr": stderr.decode("utf-8", errors="replace").strip(),
            "returncode": proc.returncode
        }
    except Exception as e:
        logger.error("ops_tools_execution_failed", error=str(e), command=cmd)
        return {
            "success": False,
            "error": str(e),
            "stdout": "",
            "stderr": "",
            "returncode": -1
        }

@registry.register
async def mcp_health_check() -> Dict[str, Any]:
    """
    Check the overall health of the MCP system (PostgreSQL, Redis, MCP server).
    """
    script_path = os.path.join(SCRIPTS_DIR, "mcp_health_check.sh")
    res = await _run_script_async(["bash", script_path])
    return {
        "success": res["success"],
        "status_code": res["returncode"],
        "report": res["stdout"],
        "errors": res["stderr"]
    }

@registry.register
async def memory_status_report() -> Dict[str, Any]:
    """
    Generate a detailed report of Long Term Memory (LTM) namespaces, entry counts, and ontology status.
    """
    script_path = os.path.join(SCRIPTS_DIR, "report_memory_status.py")
    res = await _run_script_async(["python3", script_path])
    return {
        "success": res["success"],
        "report": res["stdout"],
        "errors": res["stderr"]
    }

@registry.register
async def data_audit_report() -> Dict[str, Any]:
    """
    Run a data integrity audit on the korespondensi database (raw pool, internal PUU, bangda).
    """
    script_path = os.path.join(SCRIPTS_DIR, "db_data_audit_report.py")
    res = await _run_script_async(["python3", script_path])
    # Rich print outputs formatting codes, but we return raw text
    return {
        "success": res["success"],
        "report": res["stdout"],
        "errors": res["stderr"]
    }

@registry.register
async def workspace_hygiene_check() -> Dict[str, Any]:
    """
    Audit the workspace to detect residue files, forbidden extensions, or broken symlinks.
    """
    script_path = os.path.join(SCRIPTS_DIR, "workspace_hygiene_audit.py")
    res = await _run_script_async(["python3", script_path])
    return {
        "success": res["success"],
        "report": res["stdout"],
        "errors": res["stderr"]
    }

@registry.register
async def arsip_pending_status() -> Dict[str, Any]:
    """
    Check the status of pending archives that are waiting for OCR processing or linking.
    """
    script_path = os.path.join(SCRIPTS_DIR, "check_pending_arsip.py")
    res = await _run_script_async(["python3", script_path])
    return {
        "success": res["success"],
        "report": res["stdout"],
        "errors": res["stderr"]
    }

@registry.register
async def puu_posisi_analysis() -> Dict[str, Any]:
    """
    Analyze the positions and processing delays of PUU letters.
    """
    script_path = os.path.join(SCRIPTS_DIR, "puu_posisi_analysis.py")
    res = await _run_script_async(["python3", script_path])
    return {
        "success": res["success"],
        "report": res["stdout"],
        "errors": res["stderr"]
    }

@registry.register
async def backup_knowledge_db() -> Dict[str, Any]:
    """
    Backup the mcp_knowledge database into a safe SQL file.
    """
    script_path = os.path.join(SCRIPTS_DIR, "backup_mcp_knowledge.py")
    res = await _run_script_async(["python3", script_path])
    return {
        "success": res["success"],
        "report": res["stdout"],
        "errors": res["stderr"]
    }

@registry.register
async def whatsapp_gateway_status() -> Dict[str, Any]:
    """
    Check the connection and container status of the WAHA WhatsApp Gateway.
    """
    script_path = os.path.join(SCRIPTS_DIR, "waha_manager.py")
    res = await _run_script_async(["python3", script_path, "status"])
    return {
        "success": res["success"],
        "report": res["stdout"],
        "errors": res["stderr"]
    }

@registry.register
async def system_recovery_check(auto_recover: bool = False) -> Dict[str, Any]:
    """
    Check WSL + MCP services health (systemd, docker, databases, WAHA, Ollama) and optionally auto-recover if down.
    
    Args:
        auto_recover: If True, attempts to restart down services automatically.
    """
    status_script = os.path.join(SCRIPTS_DIR, "wsl-status.sh")
    restart_script = os.path.join(SCRIPTS_DIR, "wsl-restart.sh")
    
    # 1. Run wsl-status.sh without sending WA
    status_res = await _run_script_async(["bash", status_script, "--no-wa"])
    
    recovery_initiated = False
    recovery_res = None
    
    # Check if anything is failed and recover if requested
    # We can detect "🔴" or "✗" in status output
    needs_recovery = "🔴" in status_res["stdout"] or "✗" in status_res["stdout"]
    
    if needs_recovery and auto_recover:
        recovery_initiated = True
        logger.info("system_recovery_check_initiating_recovery")
        # Run wsl-restart.sh without --full
        recovery_res = await _run_script_async(["bash", restart_script])
        
        # Re-check status after recovery
        status_res = await _run_script_async(["bash", status_script, "--no-wa"])
        
    return {
        "success": status_res["success"],
        "needs_recovery": needs_recovery,
        "recovery_initiated": recovery_initiated,
        "recovery_result": recovery_res["stdout"] if recovery_res else "No recovery requested/needed",
        "status_report": status_res["stdout"],
        "errors": status_res["stderr"]
    }
