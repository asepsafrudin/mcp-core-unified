"""
execution/tools/test_runner_tools.py — MCP tool: run_tests (TASK-167).

Menjalankan test suite (pytest / npm test) di dalam workspace tanpa shell dan
tanpa sudo, lalu mengembalikan hasil terstruktur.

Catatan keamanan:
- Tidak memakai `shell=True` (argumen sebagai list).
- Menolak path di luar WORKSPACE_ROOT dan penulisan di root workspace.
- Menolak argumen yang memuat 'sudo'.
- Batas waktu keras via `timeout_seconds`.
"""
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

from execution.registry import registry
from execution.middleware import EnforcementMiddleware, EnforcementError

WORKSPACE_ROOT = Path("/home/aseps/MCP").resolve()
PYTHON_VENV_BIN = Path("/home/aseps/MCP/.venv/bin/python")

_SUMMARY_RE = {
    "passed": re.compile(r"(\d+)\s+passed"),
    "failed": re.compile(r"(\d+)\s+failed"),
    "errors": re.compile(r"(\d+)\s+error"),
    "skipped": re.compile(r"(\d+)\s+skipped"),
}


def _validate_test_path(target: str) -> Path:
    """Path harus berada di dalam WORKSPACE_ROOT, bukan root itu sendiri, dan ada."""
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


def _detect_framework(path: Path) -> Optional[str]:
    if (path / "package.json").exists():
        try:
            pkg = json.loads((path / "package.json").read_text(encoding="utf-8"))
        except Exception:
            pkg = {}
        if "test" in (pkg.get("scripts") or {}):
            return "npm"
    for marker in ("pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini", "conftest.py"):
        if (path / marker).exists():
            return "pytest"
    if (path / "tests").is_dir():
        return "pytest"
    if (path / "node_modules").is_dir():
        return "npm"
    return None


def _build_command(framework: str, path: Path, pattern: Optional[str]) -> List[str]:
    if framework == "pytest":
        cmd = [str(PYTHON_VENV_BIN), "-m", "pytest", "-q", "--tb=short"]
        if pattern:
            cmd += ["-k", pattern]
        return cmd
    if framework == "npm":
        cmd = [shutil.which("npm") or "npm", "test", "--silent"]
        if pattern:
            cmd += ["--", pattern]
        return cmd
    raise EnforcementError(f"Framework '{framework}' tidak didukung.")


def _parse_pytest(stdout: str, stderr: str) -> Dict[str, int]:
    text = f"{stdout}\n{stderr}"
    counts: Dict[str, int] = {}
    for key, rx in _SUMMARY_RE.items():
        match = rx.search(text)
        counts[key] = int(match.group(1)) if match else 0
    return counts


@registry.register(category="code")
def run_tests(
    path: str,
    framework: str = "auto",
    pattern: Optional[str] = None,
    timeout_seconds: int = 300,
) -> str:
    """
    Menjalankan test suite proyek (pytest / npm test) di sandbox workspace.

    Mengembalikan JSON terstruktur: status, framework, exit_code, passed, failed,
    errors, skipped, duration_ms, summary, dan stdout_tail. Tidak memakai shell dan
    menolak sudo.
    """
    trace_id = EnforcementMiddleware.generate_trace_id()
    start = time.time()
    try:
        root = _validate_test_path(path)
        EnforcementMiddleware.check_sudo_forbidden(" ".join([path, pattern or "", framework]))

        fw = _detect_framework(root) if framework in ("auto", "", None) else framework
        if not fw:
            return json.dumps({
                "status": "no_tests",
                "framework": None,
                "exit_code": None,
                "summary": f"Tidak menemukan konfigurasi test (pytest/package.json) di '{root}'.",
            }, indent=2)

        cmd = _build_command(fw, root, pattern)
        EnforcementMiddleware.check_sudo_forbidden(" ".join(cmd))

        env = dict(os.environ)
        env["PYTHONPATH"] = f"{WORKSPACE_ROOT}:{env.get('PYTHONPATH', '')}"

        proc = subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
        )
        duration_ms = round((time.time() - start) * 1000, 2)

        counts = _parse_pytest(proc.stdout, proc.stderr) if fw == "pytest" else {}
        status = "passed" if proc.returncode == 0 else "failed"
        summary = (
            f"{fw} di '{root}': {status.upper()} "
            f"(exit={proc.returncode}, {counts.get('passed', 0)} passed, "
            f"{counts.get('failed', 0)} failed, {counts.get('errors', 0)} error, "
            f"{counts.get('skipped', 0)} skipped, {duration_ms} ms)."
        )

        EnforcementMiddleware.audit_log(
            trace_id=trace_id,
            tool_name="run_tests",
            status=status,
            details={"path": str(root), "framework": fw, "exit_code": proc.returncode},
        )

        return json.dumps({
            "status": status,
            "framework": fw,
            "exit_code": proc.returncode,
            "passed": counts.get("passed", 0),
            "failed": counts.get("failed", 0),
            "errors": counts.get("errors", 0),
            "skipped": counts.get("skipped", 0),
            "duration_ms": duration_ms,
            "summary": EnforcementMiddleware.truncate_summary(summary),
            "stdout_tail": (proc.stdout or proc.stderr or "")[-1500:],
        }, indent=2)

    except subprocess.TimeoutExpired:
        duration_ms = round((time.time() - start) * 1000, 2)
        return json.dumps({
            "status": "timeout",
            "exit_code": 124,
            "duration_ms": duration_ms,
            "summary": f"Test melebihi batas waktu ({timeout_seconds}s).",
        }, indent=2)
    except EnforcementError as e:
        return json.dumps({"status": "rejected", "summary": str(e)}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "summary": f"{type(e).__name__}: {e}"}, indent=2)
