"""
ProcessGuard - Subprocess Runner Tangguh & Anti-Hang untuk Ekosistem MCP.

Menangani:
1. Batas timeout ketat per eksekusi.
2. Isolasi Process Group (setsid) sehingga seluruh child proses mati bersih jika timeout (tanpa zombie).
3. Auto-injection PYTHONUNBUFFERED=1 untuk mencegah pipe lock.
4. Pembatasan ukuran buffer output (RAM protection).
5. Safe decoding UTF-8 errors="replace".
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Union


@dataclass
class GuardedProcessResult:
    stdout: str
    stderr: str
    returncode: int
    elapsed_seconds: float
    timed_out: bool
    command: str

    @property
    def success(self) -> bool:
        return self.returncode == 0 and not self.timed_out


class ProcessGuard:
    """Eksekutor proses eksternal dengan perlindungan terhadap deadlock dan hang."""

    DEFAULT_TIMEOUT: float = 30.0
    DEFAULT_MAX_OUTPUT_BYTES: int = 10 * 1024 * 1024  # 10 MB

    @staticmethod
    def _prepare_env(custom_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        env = dict(os.environ)
        # Cegah stdout/stderr buffering di Python child processes
        env["PYTHONUNBUFFERED"] = "1"
        env["PAGER"] = "cat"
        if custom_env:
            env.update(custom_env)
        return env

    @classmethod
    def run_sync(
        cls,
        cmd: Union[str, Sequence[str]],
        timeout: Optional[float] = None,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        max_output_bytes: Optional[int] = None,
        input_data: Optional[Union[str, bytes]] = None,
        shell: bool = False,
    ) -> GuardedProcessResult:
        """Menjalankan subprocess secara sinkron dengan isolasi process group dan batas timeout."""
        timeout_val = timeout if timeout is not None else cls.DEFAULT_TIMEOUT
        max_bytes = max_output_bytes if max_output_bytes is not None else cls.DEFAULT_MAX_OUTPUT_BYTES
        effective_env = cls._prepare_env(env)

        if isinstance(cmd, str) and not shell:
            import shlex
            cmd_args = shlex.split(cmd)
            cmd_str = cmd
        elif isinstance(cmd, Sequence) and not isinstance(cmd, str):
            cmd_args = list(cmd)
            cmd_str = " ".join(cmd_args)
        else:
            cmd_args = cmd
            cmd_str = str(cmd)

        start_time = time.time()
        timed_out = False
        returncode = -1
        stdout_bytes = b""
        stderr_bytes = b""

        # Inisialisasi stdin bytes jika ada
        stdin_bytes = None
        if input_data is not None:
            if isinstance(input_data, str):
                stdin_bytes = input_data.encode("utf-8", errors="replace")
            else:
                stdin_bytes = input_data

        proc = None
        try:
            # start_new_session=True membuat session baru sehingga seluruh process tree
            # dapat di-kill bersamaan via os.killpg
            proc = subprocess.Popen(
                cmd_args,
                cwd=cwd,
                env=effective_env,
                stdin=subprocess.PIPE if stdin_bytes is not None else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=shell,
                start_new_session=True,
            )

            try:
                stdout_bytes, stderr_bytes = proc.communicate(
                    input=stdin_bytes,
                    timeout=timeout_val,
                )
                returncode = proc.returncode
            except subprocess.TimeoutExpired:
                timed_out = True
                # Bunuh seluruh process group
                try:
                    pgid = os.getpgid(proc.pid)
                    os.killpg(pgid, signal.SIGTERM)
                    time.sleep(0.5)
                    # Jika masih hidup, paksa SIGKILL
                    os.killpg(pgid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
                
                # Baca sisa output jika ada
                try:
                    stdout_bytes, stderr_bytes = proc.communicate(timeout=1.0)
                except Exception:
                    pass
                returncode = -signal.SIGKILL

        except Exception as e:
            stderr_bytes = f"ProcessGuard Execution Error: {str(e)}".encode("utf-8")
            returncode = -1
        finally:
            elapsed = time.time() - start_time

        # Batasi output buffer
        if len(stdout_bytes) > max_bytes:
            stdout_bytes = stdout_bytes[:max_bytes] + b"\n... [OUTPUT DITRUNCASI KARENA MELEBIHI BATAS MAX BYTES] ..."
        if len(stderr_bytes) > max_bytes:
            stderr_bytes = stderr_bytes[:max_bytes] + b"\n... [STDERR DITRUNCASI] ..."

        stdout_str = stdout_bytes.decode("utf-8", errors="replace")
        stderr_str = stderr_bytes.decode("utf-8", errors="replace")

        return GuardedProcessResult(
            stdout=stdout_str,
            stderr=stderr_str,
            returncode=returncode,
            elapsed_seconds=elapsed,
            timed_out=timed_out,
            command=cmd_str,
        )

    @classmethod
    async def run_async(
        cls,
        cmd: Union[str, Sequence[str]],
        timeout: Optional[float] = None,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        max_output_bytes: Optional[int] = None,
        input_data: Optional[Union[str, bytes]] = None,
        shell: bool = False,
    ) -> GuardedProcessResult:
        """Menjalankan subprocess secara asinkron dengan non-blocking I/O dan timeout."""
        timeout_val = timeout if timeout is not None else cls.DEFAULT_TIMEOUT
        max_bytes = max_output_bytes if max_output_bytes is not None else cls.DEFAULT_MAX_OUTPUT_BYTES
        effective_env = cls._prepare_env(env)

        if isinstance(cmd, str) and not shell:
            import shlex
            cmd_args = shlex.split(cmd)
            cmd_str = cmd
        elif isinstance(cmd, Sequence) and not isinstance(cmd, str):
            cmd_args = list(cmd)
            cmd_str = " ".join(cmd_args)
        else:
            cmd_args = cmd
            cmd_str = str(cmd)

        start_time = time.time()
        timed_out = False
        returncode = -1
        stdout_bytes = b""
        stderr_bytes = b""

        stdin_bytes = None
        if input_data is not None:
            if isinstance(input_data, str):
                stdin_bytes = input_data.encode("utf-8", errors="replace")
            else:
                stdin_bytes = input_data

        proc = None
        try:
            if shell:
                proc = await asyncio.create_subprocess_shell(
                    cmd_str,
                    cwd=cwd,
                    env=effective_env,
                    stdin=asyncio.subprocess.PIPE if stdin_bytes is not None else None,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    start_new_session=True,
                )
            else:
                proc = await asyncio.create_subprocess_exec(
                    cmd_args[0],
                    *cmd_args[1:],
                    cwd=cwd,
                    env=effective_env,
                    stdin=asyncio.subprocess.PIPE if stdin_bytes is not None else None,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    start_new_session=True,
                )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(input=stdin_bytes),
                    timeout=timeout_val,
                )
                returncode = proc.returncode if proc.returncode is not None else 0
            except asyncio.TimeoutError:
                timed_out = True
                try:
                    pgid = os.getpgid(proc.pid)
                    os.killpg(pgid, signal.SIGTERM)
                    await asyncio.sleep(0.5)
                    os.killpg(pgid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
                returncode = -signal.SIGKILL

        except Exception as e:
            stderr_bytes = f"ProcessGuard Async Execution Error: {str(e)}".encode("utf-8")
            returncode = -1
        finally:
            elapsed = time.time() - start_time

        if len(stdout_bytes) > max_bytes:
            stdout_bytes = stdout_bytes[:max_bytes] + b"\n... [OUTPUT DITRUNCASI] ..."
        if len(stderr_bytes) > max_bytes:
            stderr_bytes = stderr_bytes[:max_bytes] + b"\n... [STDERR DITRUNCASI] ..."

        stdout_str = stdout_bytes.decode("utf-8", errors="replace")
        stderr_str = stderr_bytes.decode("utf-8", errors="replace")

        return GuardedProcessResult(
            stdout=stdout_str,
            stderr=stderr_str,
            returncode=returncode,
            elapsed_seconds=elapsed,
            timed_out=timed_out,
            command=cmd_str,
        )


def run_guarded_command(
    cmd: Union[str, Sequence[str]],
    timeout: float = 30.0,
    cwd: Optional[str] = None,
    shell: bool = False,
) -> GuardedProcessResult:
    """Helper fungsi cepat untuk menjalankan perintah terlindung."""
    return ProcessGuard.run_sync(cmd=cmd, timeout=timeout, cwd=cwd, shell=shell)
