"""
Shell Execution Tool — pipeline-aware, anti-hang.

Perubahan kunci:
1. cwd dipaku ke WORKSPACE_ROOT, tidak lagi mewarisi cwd client (VS Code dir).
2. Semua eksekusi lewat ProcessGuard: stdin DEVNULL (tidak mencuri protokol
   JSON-RPC), start_new_session + killpg (tanpa zombie), PYTHONUNBUFFERED,
   PAGER=cat.
3. Eksekusi non-blocking terhadap event loop MCP (run_async).
4. Dukungan perintah berlapis (`|`, `&&`) dengan validasi whitelist per-segmen.
5. Output dipotong 64 KB agar payload JSON-RPC tidak meledak.
"""
import os
import shlex
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from observability.logger import logger
from tools.file.path_utils import is_safe_path
from execution import registry
from utils.process_guard import ProcessGuard

DEFAULT_TIMEOUT_SECONDS = 10
MAX_TIMEOUT_SECONDS = 120
MAX_OUTPUT_BYTES = 64 * 1024

WORKSPACE_ROOT = Path(os.getenv("MCP_WORKSPACE_ROOT", "/home/aseps/MCP")).resolve()

# [REVIEWER] Explicit whitelist — jangan tambahkan command tanpa review security
# Setiap penambahan command harus melalui security review
ALLOWED_COMMANDS = frozenset([
    # File system operations (read-only)
    "ls", "ls -la", "ls -l", "ls -lah",
    "pwd",
    "cat",
    "find",
    "grep", "grep -r", "grep -i", "grep -n", "grep -rn",

    # Information display
    "echo",
    "env",
    "whoami",
    "date",
    "df", "df -h",
    "free", "free -h",
    "uname", "uname -a",

    # Process monitoring with grep pipes (FIX: allow common agent debugging)
    "ps aux | grep", "ps aux | head",

    # Git operations (safe read-only)
    "git",
    "git status",
    "git log", "git log --oneline",
    "git diff",
    "git branch", "git branch -a",
    "git remote", "git remote -v",
    "git config --list",
    "git show",

    # Python tools
    "python3 --version",
    "python --version",
    "pip list",
    "pip show",
    "pip freeze",

    # Process info
    "ps", "ps aux",
    "top -b -n 1",

    # Directory navigation (for multi-command)
    "cd",
])

# [REVIEWER] Dangerous patterns that could lead to command injection.
# Catatan: '|' dan '&&' TIDAK ada di sini — keduanya dipecah lebih dulu oleh
# _split_pipeline() dan setiap segmen divalidasi terpisah sebagai whitelist.
DANGEROUS_PATTERNS = [
    ';',           # Command chaining
    '`',           # Backtick substitution
    '$(',          # Command substitution
    '${',          # Variable expansion
    '<(',          # Process substitution
    '>&',          # FD redirect
    '>',           # Output redirect
    '<',           # Input redirect
    '&',           # Background job / single ampersand
    '\x00',        # Null byte injection
    '../../',      # Multiple path traversal
]


def _contains_dangerous_patterns(command: str) -> bool:
    for pattern in DANGEROUS_PATTERNS:
        if pattern in command:
            logger.warning("dangerous_pattern_detected",
                           pattern=pattern,
                           command=command[:50])
            return True
    return False


def _translate_path(cmd: str) -> str:
    """Translate workspace paths to container paths if needed."""
    return cmd.replace("/workspace/", "/app/")


def resolve_cwd() -> str:
    """Working directory tool — selalu workspace, bukan cwd client."""
    if WORKSPACE_ROOT.is_dir():
        return str(WORKSPACE_ROOT)
    return os.getcwd()


def _truncate(text: str) -> str:
    if not text:
        return ""
    if len(text) <= MAX_OUTPUT_BYTES:
        return text
    return (
        text[:MAX_OUTPUT_BYTES]
        + f"\n... [OUTPUT DIPOTONG: melebihi {MAX_OUTPUT_BYTES // 1024} KB] ..."
    )


def _validate_path_args(parts: List[str]) -> Tuple[bool, str]:
    """
    Path absolut wajib berada di prefix aman; path relatif aman karena cwd
    sudah dipaku ke WORKSPACE_ROOT. '..' tetap ditolak.
    """
    for part in parts[1:]:
        if part.startswith("-"):
            continue
        if part.startswith("/"):
            if not is_safe_path(part):
                return False, f"Path argument '{part}' is outside allowed directories"
        elif ".." in part:
            return False, f"Path argument '{part}' is not allowed (path traversal)"
    return True, ""


def _validate_command(command: str) -> tuple[bool, str]:
    """Validasi SATU segmen perintah (tanpa pipe/&&) terhadap whitelist."""
    if _contains_dangerous_patterns(command):
        return False, "Command contains dangerous patterns that are not allowed"

    normalized_cmd = ' '.join(command.split())
    try:
        parts = shlex.split(normalized_cmd)
    except ValueError as exc:
        return False, f"Malformed command: {exc}"
    if not parts:
        return False, "Empty command"

    base_cmd = parts[0]

    if normalized_cmd in ALLOWED_COMMANDS:
        return _validate_path_args(parts)

    for allowed in ALLOWED_COMMANDS:
        if normalized_cmd.startswith(allowed + " ") or normalized_cmd == allowed:
            return _validate_path_args(parts)

    if base_cmd in [cmd.split()[0] for cmd in ALLOWED_COMMANDS if ' ' in cmd]:
        if base_cmd == "git" and len(parts) > 1:
            git_subcmd = f"git {parts[1]}"
            for allowed in ALLOWED_COMMANDS:
                if allowed.startswith(git_subcmd):
                    return True, ""

    if base_cmd in {"cat", "find", "grep", "ls", "git"}:
        ok, err = _validate_path_args(parts)
        if not ok:
            return False, err

    logger.warning("restricted_command_attempt",
                   command=base_cmd,
                   full_command=normalized_cmd[:100])
    return False, f"Command '{base_cmd}' is not in the allowed whitelist"


def _split_pipeline(command: str) -> Optional[Tuple[List[str], List[str]]]:
    """
    Pecah perintah berlapis menjadi segmen + separator ('|' atau '&&').
    Quote-aware. Kembalikan None bila sintaks tidak didukung/dangling quote.
    """
    segments: List[str] = []
    separators: List[str] = []
    buf: List[str] = []
    quote: Optional[str] = None
    i = 0
    length = len(command)

    while i < length:
        char = command[i]
        if quote:
            buf.append(char)
            if char == quote:
                quote = None
            i += 1
            continue
        if char in ("'", '"'):
            quote = char
            buf.append(char)
            i += 1
            continue
        if char == "|":
            segment = "".join(buf).strip()
            if not segment:
                return None
            segments.append(segment)
            separators.append("|")
            buf = []
            i += 1
            continue
        if command.startswith("&&", i):
            segment = "".join(buf).strip()
            if not segment:
                return None
            segments.append(segment)
            separators.append("&&")
            buf = []
            i += 2
            continue
        buf.append(char)
        i += 1

    if quote:
        return None

    tail = "".join(buf).strip()
    if not tail:
        return None
    segments.append(tail)
    return segments, separators


def _validate_command_line(command: str) -> Tuple[bool, str]:
    """Validasi seluruh baris perintah, termasuk rantai pipe/&&."""
    if not command.strip():
        return False, "Empty command"
    if "\n" in command or "\r" in command:
        return False, "Multi-line commands are not allowed"

    parsed = _split_pipeline(command)
    if parsed is None:
        return False, "Unsupported shell syntax (only '|' and '&&' chains are allowed)"
    segments, _separators = parsed

    for segment in segments:
        ok, err = _validate_command(segment)
        if not ok:
            return False, err
    return True, ""


async def _run_shell_impl(
    command: str,
    user_context: str = "unknown",
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Core implementation — eksekusi aman, non-blocking, anti-hang."""
    logger.info("shell_command_attempt",
                command=command[:200],
                user_context=user_context)

    try:
        cmd = _translate_path(command)

        is_valid, error_msg = _validate_command_line(cmd)
        if not is_valid:
            logger.warning("shell_command_rejected",
                           command=command[:100],
                           reason=error_msg,
                           user_context=user_context)
            return {"success": False, "error": error_msg}

        timeout_val = max(1, min(int(timeout_seconds), MAX_TIMEOUT_SECONDS))
        cwd = resolve_cwd()

        parsed = _split_pipeline(cmd)
        if parsed is None:  # sudah divalidasi, jaga-jaga
            return {"success": False, "error": "Unsupported shell syntax"}
        segments, _separators = parsed

        if len(segments) == 1:
            args: List[str] = shlex.split(segments[0])
        else:
            # Perintah berlapis dieksekusi oleh bash -c agar pipe/&& nyata,
            # tetap di bawah ProcessGuard (process group + timeout).
            args = ["bash", "-c", cmd]

        logger.info("shell_command_executing",
                    command=cmd[:100],
                    user_context=user_context,
                    cwd=cwd,
                    timeout_seconds=timeout_val)

        result = await ProcessGuard.run_async(args, timeout=timeout_val, cwd=cwd)

        stdout = _truncate(result.stdout.strip())
        stderr = _truncate(result.stderr.strip())

        if result.timed_out:
            logger.error("shell_command_timeout",
                         command=command[:100],
                         user_context=user_context,
                         timeout_seconds=timeout_val)
            return {
                "success": False,
                "error": f"Command timed out after {timeout_val} seconds",
                "stdout": stdout,
                "stderr": stderr,
                "returncode": result.returncode,
                "cwd": cwd,
                "timed_out": True,
            }

        if result.success:
            logger.info("shell_command_success",
                        command=cmd[:100],
                        user_context=user_context,
                        stdout_length=len(result.stdout))
        else:
            logger.warning("shell_command_failed",
                           command=cmd[:100],
                           user_context=user_context,
                           returncode=result.returncode)

        return {
            "success": result.success,
            "stdout": stdout,
            "stderr": stderr,
            "returncode": result.returncode,
            "cwd": cwd,
        }

    except Exception as e:
        logger.error("shell_command_exception",
                     error=str(e),
                     command=command[:100],
                     user_context=user_context)
        return {"success": False, "error": str(e)}


@registry.register
async def run_shell(
    command: str,
    user_context: str = "unknown",
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """
    Execute a safe shell command with strict whitelist validation.

    Mendukung rantai `|` dan `&&` (validasi per-segmen), cwd dipaku ke
    WORKSPACE_ROOT, stdin DEVNULL, dan timeout yang membunuh seluruh
    process group.

    Args:
        command: Perintah shell (whitelist, boleh berlapis dengan | atau &&)
        user_context: Identifier pemanggil (audit log)
        timeout_seconds: Batas waktu eksekusi (1-120 detik, default 10)

    Returns:
        Dict dengan success, stdout, stderr, returncode, cwd
    """
    return await _run_shell_impl(command, user_context, timeout_seconds)


# Backward compatibility - wrapper function for sync calls
def run_shell_sync(command: str, user_context: str = "unknown") -> Dict[str, Any]:
    """Synchronous wrapper for run_shell."""
    import asyncio
    return asyncio.run(run_shell(command, user_context))
