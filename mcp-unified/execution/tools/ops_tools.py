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

@registry.register
async def port_registry_audit() -> Dict[str, Any]:
    """
    Audit active listening ports against the port registry config to find conflicts or unregistered services.
    """
    script_path = os.path.join(SCRIPTS_DIR, "port_registry_audit.py")
    res = await _run_script_async(["python3", script_path])
    return {
        "success": res["success"],
        "report": res["stdout"],
        "errors": res["stderr"]
    }

@registry.register
async def cron_registry_audit() -> Dict[str, Any]:
    """
    Audit active system crontab entries against the cron registry config to find conflicts or unregistered jobs.
    """
    script_path = os.path.join(SCRIPTS_DIR, "cron_registry_audit.py")
    res = await _run_script_async(["python3", script_path])
    return {
        "success": res["success"],
        "report": res["stdout"],
        "errors": res["stderr"]
    }


@registry.register
async def network_status_report() -> Dict[str, Any]:
    """
    Generate a detailed report of WSL network interfaces, Tailscale VPN, Cloudflare tunnels, and listening SSH services.
    """
    script_path = os.path.join(SCRIPTS_DIR, "network_manager.py")
    res = await _run_script_async(["python3", script_path])
    return {
        "success": res["success"],
        "report": res["stdout"],
        "errors": res["stderr"]
    }


@registry.register
async def check_ssh_access() -> Dict[str, Any]:
    """
    Check if the registered remote SSH port (8022) is active and listening.
    """
    script_path = os.path.join(SCRIPTS_DIR, "network_manager.py")
    res = await _run_script_async(["python3", script_path, "json"])
    try:
        import json
        data = json.loads(res["stdout"])
        ssh_active = data["ssh_services"]["port_8022_antigravity"]["active"]
        return {
            "success": res["success"],
            "ssh_port_8022_active": ssh_active,
            "report": f"Port 8022 (Antigravity SSH) is {'ACTIVE (LISTEN)' if ssh_active else 'INACTIVE (DOWN)'}",
            "details": data["ssh_services"]
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to parse network manager output: {str(e)}",
            "raw_output": res["stdout"],
            "errors": res["stderr"]
        }


@registry.register
async def ssh_connection_manager(action: str, key_string: Optional[str] = None) -> Dict[str, Any]:
    """
    Manage SSH daemon connections, active status, systemd overrides, and troubleshoot remote access.
    
    Args:
        action: One of 'status', 'activate-port-8022', 'deactivate-port-8022', 'troubleshoot', 'authorize-key'.
        key_string: The public key string to authorize (only used with 'authorize-key' action).
    """
    script_path = os.path.join(SCRIPTS_DIR, "ssh_connection_manager.py")
    cmd = ["python3", script_path, action, "--json"]
    if action == "authorize-key" and key_string:
        cmd += ["--key", key_string]
        
    res = await _run_script_async(cmd)
    try:
        import json
        data = json.loads(res["stdout"])
        return data
    except Exception as e:
        return {
            "success": res["success"],
            "error": f"Failed to parse output as JSON: {str(e)}",
            "raw_output": res["stdout"],
            "errors": res["stderr"]
        }


@registry.register
async def cloudflare_tunnel_status() -> Dict[str, Any]:
    """
    Check the connectivity status of Cloudflare Tunnels (puu.supd2.net, dashtu, colab ollama/serena) and local systemd services.
    """
    script_path = os.path.join(SCRIPTS_DIR, "cloudflare_tunnel_monitor.py")
    res = await _run_script_async(["python3", script_path, "--json"])
    try:
        import json
        data = json.loads(res["stdout"])
        return {
            "success": res["success"],
            "overall_status": data.get("overall_status", "UNKNOWN"),
            "endpoints": data.get("endpoints", []),
            "systemd_user_services": data.get("systemd_user_services", {}),
            "active_processes": data.get("active_processes", []),
        }
    except Exception as e:
        return {
            "success": res["success"],
            "error": f"Failed to parse monitor output: {str(e)}",
            "raw_output": res["stdout"],
            "errors": res["stderr"]
        }
