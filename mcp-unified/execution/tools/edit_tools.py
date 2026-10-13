"""
execution/tools/edit_tools.py — MCP tool: edit_file_patch (TASK-171).

Edit bedah untuk berkas:
- `search_replace`: ganti `old_string` -> `new_string` (unik, atau `replace_all`).
- `diff`: menerapkan unified diff via `git apply`.

Penulisan atomik (temp + rename) dan preservasi line-ending. Path divalidasi di
dalam WORKSPACE_ROOT (tolak root-spill).
"""
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

from execution.registry import registry
from execution.middleware import EnforcementMiddleware, EnforcementError

WORKSPACE_ROOT = Path("/home/aseps/MCP").resolve()


def _validate_file(target: str) -> Path:
    if not target:
        raise EnforcementError("Parameter 'path' wajib diisi.")
    p = Path(target).expanduser()
    p = (WORKSPACE_ROOT / p).resolve() if not p.is_absolute() else p.resolve()
    if WORKSPACE_ROOT not in p.parents and p != WORKSPACE_ROOT:
        raise EnforcementError(f"Akses ditolak: '{p}' di luar workspace {WORKSPACE_ROOT}.")
    if p == WORKSPACE_ROOT or p.parent == WORKSPACE_ROOT:
        raise EnforcementError("Root workspace tidak diizinkan; arahkan ke subdirektori proyek.")
    return p


def _read_preserve(path: Path) -> str:
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()


def _atomic_write(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".editpatch-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


@registry.register(category="code")
def edit_file_patch(
    path: str,
    mode: str = "search_replace",
    old_string: Optional[str] = None,
    new_string: Optional[str] = None,
    diff: Optional[str] = None,
    replace_all: bool = False,
) -> str:
    """
    Mengedit berkas secara bedah (non-destruktif).

    Args:
        path: Berkas sasaran (di dalam workspace).
        mode: "search_replace" atau "diff".
        old_string / new_string: untuk mode search_replace (old_string wajib unik kecuali replace_all).
        diff: unified diff untuk mode "diff" (diterapkan via `git apply`).
        replace_all: ganti semua kemunculan (mode search_replace).

    Mengembalikan JSON: {status, path, mode, changed, replacements, summary, stdout_tail}.
    """
    trace_id = EnforcementMiddleware.generate_trace_id()
    start = time.time()
    try:
        p = _validate_file(path)

        if mode == "search_replace":
            if old_string is None or new_string is None:
                return json.dumps({"status": "rejected", "summary": "old_string & new_string wajib untuk mode search_replace."}, indent=2)
            if old_string == "":
                return json.dumps({"status": "rejected", "summary": "old_string tidak boleh kosong."}, indent=2)
            if not p.exists() or p.is_dir():
                return json.dumps({"status": "rejected", "summary": f"Berkas '{p}' tidak ditemukan atau bukan berkas."}, indent=2)

            raw = _read_preserve(p)
            occurrences = raw.count(old_string)
            if occurrences == 0:
                return json.dumps({"status": "rejected", "summary": "old_string tidak ditemukan di berkas."}, indent=2)
            if occurrences > 1 and not replace_all:
                return json.dumps({"status": "rejected", "summary": f"old_string ambigu ({occurrences} kemunculan); set replace_all=true atau perjelas konteks."}, indent=2)

            new_text = raw.replace(old_string, new_string, -1 if replace_all else 1)
            replacements = occurrences if replace_all else 1
            _atomic_write(p, new_text)

            EnforcementMiddleware.audit_log(trace_id=trace_id, tool_name="edit_file_patch", status="ok",
                                            details={"path": str(p), "mode": mode, "replacements": replacements})
            duration_ms = round((time.time() - start) * 1000, 2)
            return json.dumps({
                "status": "ok",
                "path": str(p),
                "mode": mode,
                "changed": True,
                "replacements": replacements,
                "duration_ms": duration_ms,
                "summary": f"search_replace pada '{p}': {replacements} penggantian.",
            }, indent=2)

        if mode == "diff":
            if not diff:
                return json.dumps({"status": "rejected", "summary": "Parameter 'diff' wajib untuk mode diff."}, indent=2)
            proc = subprocess.run(
                ["git", "apply", "--whitespace=nowarn", "-"],
                cwd=str(WORKSPACE_ROOT), input=diff, capture_output=True, text=True, timeout=60,
            )
            ok = proc.returncode == 0
            EnforcementMiddleware.audit_log(trace_id=trace_id, tool_name="edit_file_patch", status="ok" if ok else "failed",
                                            details={"path": str(p), "mode": mode, "exit_code": proc.returncode})
            duration_ms = round((time.time() - start) * 1000, 2)
            return json.dumps({
                "status": "ok" if ok else "failed",
                "path": str(p),
                "mode": mode,
                "changed": ok,
                "exit_code": proc.returncode,
                "duration_ms": duration_ms,
                "summary": f"git apply pada '{p}': {'OK' if ok else 'GAGAL'} (exit={proc.returncode}).",
                "stdout_tail": (proc.stdout or proc.stderr or "")[-1000:],
            }, indent=2)

        return json.dumps({"status": "rejected", "summary": f"mode '{mode}' tidak didukung (search_replace|diff)."}, indent=2)

    except EnforcementError as e:
        return json.dumps({"status": "rejected", "summary": str(e)}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "summary": f"{type(e).__name__}: {e}"}, indent=2)
