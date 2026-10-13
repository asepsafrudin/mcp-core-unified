"""
execution/tools/dependency_tools.py — MCP tool: dependency_install (TASK-168).

Memasang dependensi proyek (pip / npm / pnpm / yarn) di dalam workspace tanpa
`sudo` dan tanpa `shell=True`, dengan mode `dry_run` yang mengembalikan rencana
tanpa eksekusi.

Catatan keamanan:
- Menolak `sudo` di argumen.
- Menolak path di luar WORKSPACE_ROOT dan root-spill.
- `dry_run=True` TIDAK mengeksekusi apa pun — hanya mengembalikan rencana.
- Audit log per operasi.
"""
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import List, Optional

from execution.registry import registry
from execution.middleware import EnforcementMiddleware, EnforcementError

WORKSPACE_ROOT = Path("/home/aseps/MCP").resolve()
PYTHON_VENV_BIN = Path("/home/aseps/MCP/.venv/bin/python")

_ALLOWED_MANAGERS = ("pip", "npm", "pnpm", "yarn")
_PKG_SPLIT = re.compile(r"[,\s]+")


def _validate_workspace_path(target: str) -> Path:
    if not target:
        raise EnforcementError("Parameter 'path' wajib diisi.")
    p = Path(target).expanduser()
    p = (WORKSPACE_ROOT / p).resolve() if not p.is_absolute() else p.resolve()
    if WORKSPACE_ROOT not in p.parents and p != WORKSPACE_ROOT:
        raise EnforcementError(f"Akses ditolak: '{p}' di luar workspace {WORKSPACE_ROOT}.")
    if p == WORKSPACE_ROOT:
        raise EnforcementError("Path root workspace tidak diizinkan; arahkan ke subdirektori proyek.")
    if not p.exists():
        raise EnforcementError(f"Path '{p}' tidak ditemukan.")
    return p


def _detect_manager(root: Path) -> Optional[str]:
    if (root / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (root / "yarn.lock").exists():
        return "yarn"
    if (root / "package.json").exists():
        return "npm"
    if (root / "requirements.txt").exists() or (root / "pyproject.toml").exists():
        return "pip"
    return None


def _parse_packages(packages: Optional[str]) -> List[str]:
    if not packages:
        return []
    return [p for p in _PKG_SPLIT.split(packages.strip()) if p]


def _build_command(manager: str, root: Path, pkgs: List[str]) -> List[str]:
    if manager == "pip":
        base = [str(PYTHON_VENV_BIN), "-m", "pip", "install"]
        return base + (pkgs if pkgs else ["-r", "requirements.txt"])
    if manager == "npm":
        return [shutil.which("npm") or "npm", "install", *pkgs]
    if manager == "pnpm":
        return [shutil.which("pnpm") or "pnpm", "install", *pkgs]
    if manager == "yarn":
        return [shutil.which("yarn") or "yarn", "install", *pkgs]
    raise EnforcementError(f"Manager '{manager}' tidak didukung.")


@registry.register(category="code")
def dependency_install(
    path: str,
    manager: str = "auto",
    packages: Optional[str] = None,
    dry_run: bool = False,
    timeout_seconds: int = 600,
) -> str:
    """
    Memasang dependensi proyek (pip/npm/pnpm/yarn) di sandbox workspace.

    Args:
        path: Direktori proyek (di dalam workspace).
        manager: pip | npm | pnpm | yarn, atau "auto" untuk deteksi dari lockfile.
        packages: Daftar paket (dipisah spasi/koma). Kosong = pakai lockfile/requirements.
        dry_run: Bila True, hanya mengembalikan rencana — TIDAK mengeksekusi.
        timeout_seconds: Batas waktu eksekusi.

    Mengembalikan JSON terstruktur: status, manager, packages, dry_run, command,
    executed, exit_code, duration_ms, summary, stdout_tail.
    """
    trace_id = EnforcementMiddleware.generate_trace_id()
    start = time.time()
    try:
        root = _validate_workspace_path(path)
        EnforcementMiddleware.check_sudo_forbidden(" ".join([path, manager, packages or ""]))

        chosen = _detect_manager(root) if manager in ("auto", "", None) else manager
        if chosen not in _ALLOWED_MANAGERS:
            return json.dumps({"status": "rejected", "summary": f"manager '{manager}' tidak valid; pilih {list(_ALLOWED_MANAGERS)} atau 'auto'."}, indent=2)

        pkgs = _parse_packages(packages)
        cmd = _build_command(chosen, root, pkgs)
        EnforcementMiddleware.check_sudo_forbidden(" ".join(cmd))

        if dry_run:
            return json.dumps({
                "status": "dry_run",
                "manager": chosen,
                "packages": pkgs,
                "dry_run": True,
                "command": cmd,
                "executed": False,
                "summary": f"Rencana pemasangan ({chosen}) untuk '{root}': {' '.join(cmd)}",
            }, indent=2)

        env = dict(os.environ)
        env["PYTHONPATH"] = f"{WORKSPACE_ROOT}:{env.get('PYTHONPATH', '')}"
        proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True, timeout=timeout_seconds, env=env)
        duration_ms = round((time.time() - start) * 1000, 2)
        ok = proc.returncode == 0
        status = "ok" if ok else "failed"
        summary = f"{chosen} install di '{root}': {'OK' if ok else 'GAGAL'} (exit={proc.returncode}, {duration_ms} ms)."

        EnforcementMiddleware.audit_log(
            trace_id=trace_id, tool_name="dependency_install", status=status,
            details={"path": str(root), "manager": chosen, "packages": pkgs, "exit_code": proc.returncode},
        )

        return json.dumps({
            "status": status,
            "manager": chosen,
            "packages": pkgs,
            "dry_run": False,
            "command": cmd,
            "executed": True,
            "exit_code": proc.returncode,
            "duration_ms": duration_ms,
            "summary": EnforcementMiddleware.truncate_summary(summary),
            "stdout_tail": (proc.stdout or proc.stderr or "")[-1500:],
        }, indent=2)

    except subprocess.TimeoutExpired:
        duration_ms = round((time.time() - start) * 1000, 2)
        return json.dumps({"status": "timeout", "exit_code": 124, "duration_ms": duration_ms,
                           "summary": f"Instalasi melebihi batas waktu ({timeout_seconds}s)."}, indent=2)
    except EnforcementError as e:
        return json.dumps({"status": "rejected", "summary": str(e)}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "summary": f"{type(e).__name__}: {e}"}, indent=2)
