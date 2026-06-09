import subprocess
import json
import logging
import time
from typing import Dict, Any, Optional

from .base import register_tool

logger = logging.getLogger(__name__)

# Kita juga panggil db_logger yang baru dibuat jika memungkinkan
try:
    from services.db_logger import log_browser_action
except ImportError:
    log_browser_action = None

def _run_ab_cli(command: list, tool_name: str, input_summary: str) -> Dict[str, Any]:
    """Helper untuk menjalankan agent-browser CLI dan parsing JSON."""
    start_time = time.time()
    try:
        # Panggil binary agent-browser. Asumsi ia mengembalikan JSON.
        result = subprocess.run(
            ['agent-browser'] + command + ['--json'],
            capture_output=True, text=True, timeout=30
        )
        duration_ms = int((time.time() - start_time) * 1000)
        
        if result.returncode != 0:
            error_msg = result.stderr.strip()
            if log_browser_action:
                log_browser_action(
                    engine="agent_browser", tool_name=tool_name, status="error",
                    input_summary=input_summary, duration_ms=duration_ms,
                    error_code="AB_EXEC_FAILED", error_message=error_msg
                )
            return {"success": False, "error": "AB_EXEC_FAILED", "message": error_msg}
            
        try:
            output = json.loads(result.stdout)
            if log_browser_action:
                # Coba ambil estimasi token jika ada di output CLI
                tokens = output.get("snapshot_tokens", output.get("token_estimate", 0))
                log_browser_action(
                    engine="agent_browser", tool_name=tool_name, status="success",
                    input_summary=input_summary, duration_ms=duration_ms,
                    snapshot_tokens=tokens
                )
            return output
        except json.JSONDecodeError:
            # Jika CLI tidak mereturn JSON valid
            return {"success": True, "raw_output": result.stdout}
            
    except subprocess.TimeoutExpired:
        duration_ms = int((time.time() - start_time) * 1000)
        if log_browser_action:
            log_browser_action(
                engine="agent_browser", tool_name=tool_name, status="error",
                input_summary=input_summary, duration_ms=duration_ms,
                error_code="TIMEOUT", error_message="Execution timed out"
            )
        return {"success": False, "error": "TIMEOUT", "message": "Command timed out after 30s"}
    except Exception as e:
        return {"success": False, "error": "SYSTEM_ERROR", "message": str(e)}

@register_tool
def ab_navigate(url: str, wait_for: str = "load") -> Dict[str, Any]:
    """
    Navigasi agent-browser ke URL tujuan.
    
    Args:
        url: URL tujuan
        wait_for: 'load', 'networkidle', atau 'domcontentloaded'
    """
    cmd = ["navigate", "--url", url, "--wait-for", wait_for]
    return _run_ab_cli(cmd, "ab_navigate", f"Navigate to {url}")

@register_tool
def ab_snapshot(format: str = "text", include_refs: bool = True) -> Dict[str, Any]:
    """
    Mengambil representasi snapshot semantik halaman.
    
    Args:
        format: 'text' atau 'json'
        include_refs: Sertakan semantic references (@eN)
    """
    cmd = ["snapshot", "--format", format]
    if include_refs:
        cmd.append("--include-refs")
    return _run_ab_cli(cmd, "ab_snapshot", f"Snapshot format={format}")

@register_tool
def ab_click(target: str, strategy: str = "semantic") -> Dict[str, Any]:
    """
    Meng-klik elemen berdasarkan semantic locator.
    
    Args:
        target: Semantic locator (e.g. 'button Login' atau '@e12')
        strategy: 'semantic', 'ref', atau 'text'
    """
    cmd = ["click", "--target", target, "--strategy", strategy]
    return _run_ab_cli(cmd, "ab_click", f"Click {target}")

@register_tool
def ab_type(target: str, text: str, clear_first: bool = True) -> Dict[str, Any]:
    """
    Mengetik ke dalam input field.
    
    Args:
        target: Semantic locator
        text: Teks yang akan diketik
        clear_first: Kosongkan isi sebelum mengetik
    """
    cmd = ["type", "--target", target, "--text", text]
    if clear_first:
        cmd.append("--clear")
    return _run_ab_cli(cmd, "ab_type", f"Type into {target}")

@register_tool
def ab_extract(query: str, format: str = "json", scope: Optional[str] = None) -> Dict[str, Any]:
    """
    Mengekstrak data dari halaman menggunakan agent-browser.
    
    Args:
        query: Deskripsi natural language data
        format: Format ekstraksi ('json', 'text', 'table')
        scope: Area pembatas (opsional)
    """
    cmd = ["extract", "--query", query, "--format", format]
    if scope:
        cmd.extend(["--scope", scope])
    return _run_ab_cli(cmd, "ab_extract", f"Extract: {query}")

@register_tool
def ab_screenshot(path: Optional[str] = None, full_page: bool = False, element: Optional[str] = None) -> Dict[str, Any]:
    """
    Mengambil screenshot halaman.
    
    Args:
        path: Output file (jika None, mengembalikan base64)
        full_page: Screenshot seluruh tinggi halaman
        element: Semantic locator untuk screenshot elemen saja
    """
    cmd = ["screenshot"]
    if path:
        cmd.extend(["--path", path])
    if full_page:
        cmd.append("--full-page")
    if element:
        cmd.extend(["--element", element])
    return _run_ab_cli(cmd, "ab_screenshot", f"Screenshot to {path or 'base64'}")
