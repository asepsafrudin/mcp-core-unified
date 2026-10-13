"""
execution/tools/build_lint_tools.py — MCP tool: build_and_lint (TASK-169).

Menjalankan lint / format / typecheck / build di dalam workspace tanpa shell dan
tanpa sudo, lalu mengembalikan hasil terstruktur.

Toolchain:
- Python: ruff (lint), black (format), mypy (typecheck)
- JS/TS : eslint (lint), prettier (format), tsc (typecheck), `npm run build` (build)

Catatan keamanan:
- Tidak memakai `shell=True`.
- Menolak path di luar WORKSPACE_ROOT dan root-spill; menolak 'sudo'.
- `format` default hanya memeriksa (`--check`); mengubah berkas hanya bila `write=true`.
- JS tool dijalankan via `npx --no-install` (tidak memasang apa pun).
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

_ISSUE_RE = {
    "ruff": re.compile(r"[Ff]ound\s+(\d+)\s+error"),
    "mypy": re.compile(r"[Ff]ound\s+(\d+)\s+error"),
    "eslint": re.compile(r"(\d+)\s+problem"),
}

_VALID_ACTIONS = ("lint", "format", "typecheck", "build")


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


def _is_python_project(root: Path) -> bool:
    if (root / "pyproject.toml").exists() or (root / "setup.cfg").exists():
        return True
    return any(root.glob("*.py"))


def _is_js_project(root: Path) -> bool:
    return (root / "package.json").exists() or (root / "tsconfig.json").exists()


def _pick_tool(action: str, root: Path) -> Optional[str]:
    py, js = _is_python_project(root), _is_js_project(root)
    if action == "lint":
        return "ruff" if py else ("eslint" if js else None)
    if action == "format":
        return "black" if py else ("prettier" if js else None)
    if action == "typecheck":
        return "mypy" if py else ("tsc" if js else None)
    if action == "build":
        return "npm-build" if js else None
    return None


def _build_command(tool: str, root: Path, write: bool) -> List[str]:
    py = str(PYTHON_VENV_BIN)
    npx = shutil.which("npx") or "npx"
    if tool == "ruff":
        return [py, "-m", "ruff", "check", str(root)]
    if tool == "black":
        return [py, "-m", "black", str(root)] if write else [py, "-m", "black", "--check", str(root)]
    if tool == "mypy":
        return [py, "-m", "mypy", str(root)]
    if tool == "eslint":
        return [npx, "--no-install", "eslint", "."]
    if tool == "prettier":
        return [npx, "--no-install", "prettier", "--write", "."] if write else [npx, "--no-install", "prettier", "--check", "."]
    if tool == "tsc":
        return [npx, "--no-install", "tsc", "--noEmit"]
    if tool == "npm-build":
        return [shutil.which("npm") or "npm", "run", "build"]
    raise EnforcementError(f"Tool '{tool}' tidak didukung.")


def _parse_issues(tool: str, text: str) -> int:
    rx = _ISSUE_RE.get(tool)
    if not rx:
        return 0
    match = rx.search(text)
    return int(match.group(1)) if match else 0


@registry.register(category="code")
def build_and_lint(
    path: str,
    action: str = "lint",
    tool: str = "auto",
    write: bool = False,
    timeout_seconds: int = 300,
) -> str:
    """
    Menjalankan lint/format/typecheck/build proyek di sandbox workspace.

    Args:
        path: Direktori proyek (di dalam workspace).
        action: lint | format | typecheck | build.
        tool: Nama tool eksplisit, atau "auto" untuk deteksi.
        write: Untuk action="format" — bila True, terapkan perubahan; default cek saja.
        timeout_seconds: Batas waktu eksekusi.

    Mengembalikan JSON terstruktur: status, action, tool, ok, issues, exit_code,
    duration_ms, summary, stdout_tail.
    """
    trace_id = EnforcementMiddleware.generate_trace_id()
    start = time.time()
    try:
        if action not in _VALID_ACTIONS:
            return json.dumps({"status": "rejected", "summary": f"action '{action}' tidak valid; pilih {list(_VALID_ACTIONS)}."}, indent=2)

        root = _validate_workspace_path(path)
        EnforcementMiddleware.check_sudo_forbidden(" ".join([path, action, tool]))

        chosen = _pick_tool(action, root) if tool in ("auto", "", None) else tool
        if not chosen:
            return json.dumps({
                "status": "tool_unavailable",
                "action": action,
                "tool": None,
                "summary": f"Tidak menemukan toolchain untuk action='{action}' di '{root}'.",
            }, indent=2)

        cmd = _build_command(chosen, root, write)
        EnforcementMiddleware.check_sudo_forbidden(" ".join(cmd))

        env = dict(os.environ)
        env["PYTHONPATH"] = f"{WORKSPACE_ROOT}:{env.get('PYTHONPATH', '')}"

        proc = subprocess.run(
            cmd, cwd=str(root), capture_output=True, text=True,
            timeout=timeout_seconds, env=env,
        )
        duration_ms = round((time.time() - start) * 1000, 2)
        text = f"{proc.stdout}\n{proc.stderr}"
        no_files = "No Python files found" in text or "No files found" in text
        ok = proc.returncode == 0 and not no_files
        issues = 0 if proc.returncode == 0 else _parse_issues(chosen, text)
        if no_files:
            status = "no_files"
            summary = (
                f"{chosen} [{action}] di '{root}': TIDAK ADA BERKAS untuk diperiksa "
                f"(kemungkinan di-ignore .gitignore). Ini BUKAN bukti kode bersih."
            )
        else:
            status = "ok" if ok else "issues"
            summary = (
                f"{chosen} [{action}] di '{root}': {'OK' if ok else 'ISSUES'} "
                f"(exit={proc.returncode}, issues={issues}, {duration_ms} ms)."
            )

        EnforcementMiddleware.audit_log(
            trace_id=trace_id, tool_name="build_and_lint", status=status,
            details={"path": str(root), "action": action, "tool": chosen, "exit_code": proc.returncode},
        )

        return json.dumps({
            "status": status,
            "action": action,
            "tool": chosen,
            "ok": ok,
            "issues": issues,
            "exit_code": proc.returncode,
            "duration_ms": duration_ms,
            "summary": EnforcementMiddleware.truncate_summary(summary),
            "stdout_tail": text[-1500:],
        }, indent=2)

    except subprocess.TimeoutExpired:
        duration_ms = round((time.time() - start) * 1000, 2)
        return json.dumps({"status": "timeout", "action": action, "exit_code": 124,
                           "duration_ms": duration_ms, "summary": f"Eksekusi melebihi batas waktu ({timeout_seconds}s)."}, indent=2)
    except EnforcementError as e:
        return json.dumps({"status": "rejected", "summary": str(e)}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "summary": f"{type(e).__name__}: {e}"}, indent=2)
