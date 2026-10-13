"""
execution/tools/git_write_tools.py — MCP tool: git_write (TASK-170).

Operasi git TULIS (add/commit/branch/checkout/push/create_pr) dengan guardrails ketat:
- Tanpa `shell=True` (argumen sebagai list).
- DILARANG force-push, reset --hard, clean -fd, rebase (tak ada di whitelist op).
- Pesan commit WAJIB diakhiri trailer co-author; mendukung `Refs: TASK-{NNN}`.
- `push`/`create_pr` (irreversible/publik) WAJIB `confirm=True`.
- Pre-commit secret-scan: bila binary `gitleaks` tersedia, `protect --staged` dijalankan
  sebelum commit; selain itu mengandalkan hook pre-commit repo (jangan pakai --no-verify).
- Audit log tiap operasi tulis.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from execution.registry import registry
from execution.middleware import EnforcementMiddleware, EnforcementError

WORKSPACE_ROOT = Path("/home/aseps/MCP").resolve()

COAUTHOR_TRAILER = "Co-authored-by: CommandCodeBot <noreply@commandcode.ai>"

ALLOWED_OPS = frozenset({"add", "commit", "branch", "checkout", "push", "create_pr"})

# Subperintah git destruktif yang DITOLAK pada MVP (defense-in-depth).
FORBIDDEN_TOKENS = ("--force", "--force-with-lease", "reset", "clean", "rebase", "push -f")

_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


def ensure_coauthor_trailer(message: str) -> str:
    """Pastikan pesan commit diakhiri trailer co-author (append bila belum ada)."""
    msg = (message or "").rstrip()
    if COAUTHOR_TRAILER not in msg:
        msg = f"{msg}\n\n{COAUTHOR_TRAILER}"
    return msg


def validate_ref(name: str, label: str) -> str:
    """Validasi nama branch/remote: karakter aman, tanpa '..', tanpa spasi/'-' di awal."""
    if not name or not _REF_RE.match(name):
        raise EnforcementError(f"Nama {label} tidak valid: {name!r} (hanya [A-Za-z0-9._/-], tanpa spasi).")
    if ".." in name or name.startswith("-"):
        raise EnforcementError(f"Nama {label} tidak valid: {name!r}.")
    return name


def _reject_forbidden(*values: str) -> None:
    joined = " ".join(v for v in values if v)
    low = joined.lower()
    for token in FORBIDDEN_TOKENS:
        if token in low:
            raise EnforcementError(f"Operasi git destruktif/force tidak diizinkan: '{token}'.")


def _run_git(args: List[str], timeout: int = 120) -> subprocess.CompletedProcess:
    EnforcementMiddleware.check_sudo_forbidden(" ".join(args))
    return subprocess.run(
        ["git", *args],
        cwd=str(WORKSPACE_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _secret_scan_staged() -> Optional[str]:
    """Jalankan gitleaks pada staged changes bila tersedia. Return pesan error bila ada leak."""
    gitleaks = shutil.which("gitleaks")
    if not gitleaks:
        return None  # andalkan hook pre-commit repo
    try:
        proc = subprocess.run(
            [gitleaks, "protect", "--staged", "--redact", "--no-banner"],
            cwd=str(WORKSPACE_ROOT), capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0:
            return "Secret-scan (gitleaks) mendeteksi kebocoran pada staged changes; commit dibatalkan."
    except Exception as e:
        return f"Secret-scan gagal dijalankan: {e}"
    return None


def _result(status: str, op: str, summary: str, **extra) -> str:
    payload = {"status": status, "op": op, "summary": summary}
    payload.update(extra)
    return json.dumps(payload, indent=2)


@registry.register(category="code")
def git_write(
    op: str,
    path: Optional[str] = None,
    message: Optional[str] = None,
    branch: Optional[str] = None,
    remote: str = "origin",
    confirm: bool = False,
) -> str:
    """
    Operasi git TULIS dengan guardrails.

    Args:
        op: "add" | "commit" | "branch" | "checkout" | "push" | "create_pr".
        path: Path sasaran untuk op "add" (relatif workspace; wajib).
        message: Pesan commit untuk op "commit" (trailer co-author otomatis ditambahkan).
        branch: Nama branch (op "branch"/"checkout"/"push"/"create_pr").
        remote: Remote untuk op "push" (default "origin").
        confirm: Wajib True untuk op "push"/"create_pr" (irreversible/terlihat publik).

    Mengembalikan JSON: {status, op, summary, ...}. status: ok|rejected|unavailable|error.
    """
    trace_id = EnforcementMiddleware.generate_trace_id()
    try:
        if op not in ALLOWED_OPS:
            return _result("rejected", str(op), f"op '{op}' tidak didukung (add|commit|branch|checkout|push|create_pr).")

        if op == "add":
            if not path:
                return _result("rejected", op, "Parameter 'path' wajib untuk op 'add'.")
            target = Path(path)
            resolved = (WORKSPACE_ROOT / target).resolve() if not target.is_absolute() else target.resolve()
            if WORKSPACE_ROOT not in resolved.parents and resolved != WORKSPACE_ROOT:
                return _result("rejected", op, f"Path '{resolved}' di luar workspace.")
            rel = str(resolved.relative_to(WORKSPACE_ROOT))
            if rel in (".", ""):
                return _result("rejected", op, "Dilarang `git add` seluruh root; sebutkan path spesifik.")
            proc = _run_git(["add", "--", rel])
            ok = proc.returncode == 0
            EnforcementMiddleware.audit_log(trace_id=trace_id, tool_name="git_write", status="ok" if ok else "failed",
                                            details={"op": op, "path": rel, "exit_code": proc.returncode})
            return _result("ok" if ok else "error", op, f"git add '{rel}' -> {'OK' if ok else 'GAGAL'}.",
                           exit_code=proc.returncode, stdout_tail=(proc.stdout or proc.stderr or "")[-800:])

        if op == "commit":
            if not message:
                return _result("rejected", op, "Parameter 'message' wajib untuk op 'commit'.")
            _reject_forbidden(message)
            full_message = ensure_coauthor_trailer(message)
            scan_err = _secret_scan_staged()
            if scan_err:
                EnforcementMiddleware.audit_log(trace_id=trace_id, tool_name="git_write", status="failed",
                                                details={"op": op, "reason": "secret_scan"})
                return _result("rejected", op, scan_err)
            proc = _run_git(["commit", "-m", full_message])
            ok = proc.returncode == 0
            EnforcementMiddleware.audit_log(trace_id=trace_id, tool_name="git_write", status="ok" if ok else "failed",
                                            details={"op": op, "exit_code": proc.returncode})
            return _result("ok" if ok else "error", op, f"git commit -> {'OK' if ok else 'GAGAL'}.",
                           exit_code=proc.returncode, trailer_applied=True,
                           stdout_tail=(proc.stdout or proc.stderr or "")[-800:])

        if op == "branch":
            if not branch:
                return _result("rejected", op, "Parameter 'branch' wajib untuk op 'branch'.")
            b = validate_ref(branch, "branch")
            _reject_forbidden(b)
            proc = _run_git(["branch", b])
            ok = proc.returncode == 0
            EnforcementMiddleware.audit_log(trace_id=trace_id, tool_name="git_write", status="ok" if ok else "failed",
                                            details={"op": op, "branch": b, "exit_code": proc.returncode})
            return _result("ok" if ok else "error", op, f"git branch '{b}' -> {'OK' if ok else 'GAGAL'}.",
                           exit_code=proc.returncode, stdout_tail=(proc.stdout or proc.stderr or "")[-800:])

        if op == "checkout":
            if not branch:
                return _result("rejected", op, "Parameter 'branch' wajib untuk op 'checkout'.")
            b = validate_ref(branch, "branch")
            _reject_forbidden(b)
            proc = _run_git(["checkout", b])  # tanpa -f
            ok = proc.returncode == 0
            EnforcementMiddleware.audit_log(trace_id=trace_id, tool_name="git_write", status="ok" if ok else "failed",
                                            details={"op": op, "branch": b, "exit_code": proc.returncode})
            return _result("ok" if ok else "error", op, f"git checkout '{b}' -> {'OK' if ok else 'GAGAL'}.",
                           exit_code=proc.returncode, stdout_tail=(proc.stdout or proc.stderr or "")[-800:])

        if op == "push":
            if not confirm:
                return _result("rejected", op, "op 'push' bersifat irreversible/publik: set confirm=True untuk melanjutkan.")
            if not branch:
                return _result("rejected", op, "Parameter 'branch' wajib untuk op 'push'.")
            b = validate_ref(branch, "branch")
            r = validate_ref(remote, "remote")
            _reject_forbidden(b, r)
            proc = _run_git(["push", r, b], timeout=180)
            ok = proc.returncode == 0
            EnforcementMiddleware.audit_log(trace_id=trace_id, tool_name="git_write", status="ok" if ok else "failed",
                                            details={"op": op, "remote": r, "branch": b, "exit_code": proc.returncode})
            return _result("ok" if ok else "error", op, f"git push {r} {b} -> {'OK' if ok else 'GAGAL'}.",
                           exit_code=proc.returncode, stdout_tail=(proc.stdout or proc.stderr or "")[-800:])

        # create_pr
        if not confirm:
            return _result("rejected", op, "op 'create_pr' bersifat publik: set confirm=True untuk melanjutkan.")
        if not branch:
            return _result("rejected", op, "Parameter 'branch' wajib untuk op 'create_pr'.")
        b = validate_ref(branch, "branch")
        if shutil.which("gh") is None:
            return _result("unavailable", op, "GitHub CLI ('gh') tidak tersedia; PR bridge belum terpasang.")
        proc = subprocess.run(
            ["gh", "pr", "create", "--fill", "--head", b],
            cwd=str(WORKSPACE_ROOT), capture_output=True, text=True, timeout=180,
        )
        ok = proc.returncode == 0
        EnforcementMiddleware.audit_log(trace_id=trace_id, tool_name="git_write", status="ok" if ok else "failed",
                                        details={"op": op, "branch": b, "exit_code": proc.returncode})
        return _result("ok" if ok else "error", op, f"gh pr create --head {b} -> {'OK' if ok else 'GAGAL'}.",
                       exit_code=proc.returncode, stdout_tail=(proc.stdout or proc.stderr or "")[-800:])

    except EnforcementError as e:
        return _result("rejected", str(op), str(e))
    except subprocess.TimeoutExpired:
        return _result("error", str(op), "Operasi git melebihi batas waktu.")
    except Exception as e:
        return _result("error", str(op), f"{type(e).__name__}: {e}")
