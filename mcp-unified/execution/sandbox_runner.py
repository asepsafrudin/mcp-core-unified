"""
execution/sandbox_runner.py — Sandbox Executor & AST Verifier Deterministik
Menjalankan kode Python di virtualenv terisolasi workspace aseps (/home/aseps/MCP/.venv/bin/python)
dengan penegakan batas waktu, inspeksi AST sebelum eksekusi, dan mekanisme self-healing.
"""

import os
import sys
import ast
import time
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from .middleware import EnforcementMiddleware, EnforcementError

PYTHON_VENV_BIN = Path("/home/aseps/MCP/.venv/bin/python").resolve()
WORKSPACE_ROOT = Path("/home/aseps/MCP").resolve()


@dataclass
class SandboxResult:
    """Hasil eksekusi proses dalam sandbox."""
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    error_summary: Optional[str] = None


class SandboxRunner:
    """Runner sandbox deterministik berbasis virtualenv lokal."""

    @staticmethod
    def verify_ast(code: str) -> Tuple[bool, Optional[str]]:
        """
        Pemeriksaan Abstract Syntax Tree (AST) secara deterministik.
        Memastikan tidak ada syntax error sebelum kode dieksekusi.
        """
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            return False, f"SyntaxError baris {e.lineno}, kolom {e.offset}: {e.msg}"
        except Exception as e:
            return False, f"AST Parsing Error: {str(e)}"

    @classmethod
    def run_script(
        cls,
        script_path: str,
        args: Optional[List[str]] = None,
        timeout_seconds: int = 120,
        extra_env: Optional[Dict[str, str]] = None
    ) -> SandboxResult:
        """
        Mengeksekusi skrip di lingkungan virtualenv .venv tanpa sudo.
        """
        # 1. Validasi path melalui middleware
        validated_path = EnforcementMiddleware.validate_path(script_path)

        if not os.path.exists(validated_path):
            return SandboxResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Berkas skrip '{validated_path}' tidak ditemukan.",
                duration_ms=0.0,
                error_summary="File not found"
            )

        # 2. Siapkan command dan environment
        cmd = [str(PYTHON_VENV_BIN), validated_path] + (args or [])

        # Pastikan tidak ada sudo
        EnforcementMiddleware.check_sudo_forbidden(" ".join(cmd))

        env = os.environ.copy()
        pythonpath = (
            f"{WORKSPACE_ROOT}:"
            f"{WORKSPACE_ROOT}/core/mcp-unified:"
            f"{WORKSPACE_ROOT}/workspace/korespondensi-server:"
            f"{env.get('PYTHONPATH', '')}"
        )
        env["PYTHONPATH"] = pythonpath
        if extra_env:
            env.update(extra_env)

        start_time = time.time()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(WORKSPACE_ROOT),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds
            )
            duration_ms = round((time.time() - start_time) * 1000, 2)
            is_success = (proc.returncode == 0)

            # Ekstrak ringkasan error jika gagal
            error_summary = None
            if not is_success:
                stderr_clean = proc.stderr.strip()
                lines = stderr_clean.splitlines()
                # Ambil 5 baris terakhir dari traceback
                error_summary = "\n".join(lines[-5:]) if len(lines) > 5 else stderr_clean

            return SandboxResult(
                success=is_success,
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_ms=duration_ms,
                error_summary=error_summary
            )

        except subprocess.TimeoutExpired:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            return SandboxResult(
                success=False,
                exit_code=124,
                stdout="",
                stderr=f"Eksekusi melebihi batas waktu ({timeout_seconds} detik).",
                duration_ms=duration_ms,
                error_summary="Execution Timeout"
            )
        except Exception as e:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            return SandboxResult(
                success=False,
                exit_code=1,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
                error_summary=str(e)
            )
