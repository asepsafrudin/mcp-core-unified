"""
OpenHands Bridge for Antigravity Chat IDE & MCP Unified.
Orchestrates autonomous coding tasks, executes them via Docker sandbox or local fallback,
and streams rich artifacts directly to ~/.gemini/antigravity-ide/brain/<conversation-id>/.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .context import get_antigravity_context
from .formatter import OpenHandsArtifactFormatter, OpenHandsTaskReport


IMAGE_REGISTRY_CANDIDATES = [
    "docker.all-hands.dev",
    "ghcr.io",
    "registry-1.docker.io",
]
IMAGE_PATH = "/all-hands-ai/openhands:latest"


def is_registry_reachable(registry: str) -> bool:
    """Check if Docker registry is reachable within timeout."""
    host = registry.replace("https://", "").replace("http://", "").split("/")[0]
    try:
        socket.create_connection((host, 443), timeout=0.5).close()
        return True
    except OSError:
        return False


def is_docker_running() -> bool:
    """Check if docker CLI exists and docker daemon responds quickly."""
    if not shutil.which("docker"):
        return False
    try:
        res = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=1.5,
        )
        return res.returncode == 0
    except Exception:
        return False


def pick_reachable_registry() -> Optional[str]:
    for reg in IMAGE_REGISTRY_CANDIDATES:
        if is_registry_reachable(reg):
            return reg
    return None


class OpenHandsAntigravityBridge:
    """Bridge for executing OpenHands tasks and feeding results into Antigravity IDE."""

    def __init__(self, default_workspace: Optional[Path] = None):
        self.workspace = default_workspace or Path("/home/aseps/MCP")
        self._history: Dict[str, OpenHandsTaskReport] = {}

    def _get_git_status(self) -> tuple[List[str], List[str]]:
        """Get untracked/modified files using git status."""
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=5,
            )
            created = []
            modified = []
            for line in res.stdout.splitlines():
                if not line.strip():
                    continue
                code = line[:2]
                fname = line[3:].strip()
                abs_path = str(self.workspace / fname)
                if "??" in code:
                    created.append(abs_path)
                else:
                    modified.append(abs_path)
            return created, modified
        except Exception:
            return [], []

    def _get_git_diff(self) -> str:
        """Get current git diff."""
        try:
            res = subprocess.run(
                ["git", "diff"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=5,
            )
            return res.stdout
        except Exception:
            return ""

    def _get_maf_agent(self) -> Optional[Any]:
        """Best-effort loader for the in-process Microsoft Agent Framework runner.

        TASK-165: returns None when MAF is unavailable so the caller can fail fast
        (status SKIPPED/FAILED) instead of fabricating a SUCCESS.
        """
        repo_root = next(
            (p for p in Path(__file__).resolve().parents if (p / "tasks").is_dir() and (p / "core").is_dir()),
            None,
        )
        if repo_root is not None and str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        try:
            from core.agent_framework.code_agent import MAFCodeAgent
        except Exception:
            return None
        try:
            return MAFCodeAgent(workspace_dir=self.workspace)
        except Exception:
            return None

    async def execute_task(
        self,
        prompt: str,
        title: Optional[str] = None,
        conversation_id: Optional[str] = None,
        timeout_seconds: int = 600,
        sync_to_walkthrough: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute an autonomous task with OpenHands and write output to Antigravity Brain Artifacts.
        """
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        task_title = title or f"Autonomous Task ({task_id})"
        start_time = time.time()
        start_iso = datetime.now(timezone.utc).isoformat()

        context = get_antigravity_context(
            conversation_id=conversation_id,
            workspace_dir=self.workspace,
        )

        initial_created, initial_modified = self._get_git_status()
        initial_diff = self._get_git_diff()

        report = OpenHandsTaskReport(
            task_id=task_id,
            title=task_title,
            status="RUNNING",
            prompt=prompt,
            summary="Tugas sedang dalam proses eksekusi...",
            started_at=start_iso,
        )

        # Write initial "RUNNING" artifact to Antigravity brain
        artifact_filename = f"openhands_{task_id}.md"
        artifact_path = context.get_artifact_file(artifact_filename)
        artifact_path.write_text(
            OpenHandsArtifactFormatter.render_markdown_artifact(report),
            encoding="utf-8",
        )

        chosen_registry = pick_reachable_registry()
        raw_logs = []
        steps_executed = []
        status = "FAILED"  # TASK-165: safe default; real execution must overwrite this
        error_msg = None
        execution_mode: Optional[str] = None

        has_llm_key = bool(os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))
        if is_docker_running() and chosen_registry and has_llm_key:
            # Mode A: Docker Sandbox Execution
            execution_mode = "docker"
            image = f"{chosen_registry}{IMAGE_PATH}"
            cmd = [
                "docker", "run", "--rm",
                "-v", f"{self.workspace}:/workspace",
                "-v", "/var/run/docker.sock:/var/run/docker.sock",
                "-e", f"WORKSPACE_BASE={self.workspace}",
                "-e", f"ANTIGRAVITY_CONVERSATION_ID={context.conversation_id}",
                image,
                "python", "-m", "openhands.core.main",
                "-t", prompt,
            ]
            raw_logs.append(f"🐳 Menjalankan OpenHands via Docker ({chosen_registry})...")
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    cwd=str(self.workspace),
                )
                stdout_data, _ = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout_seconds,
                )
                exec_output = stdout_data.decode("utf-8", errors="replace")
                raw_logs.append(exec_output)

                if proc.returncode != 0:
                    status = "FAILED"
                    error_msg = f"Docker container exited with code {proc.returncode}"
                else:
                    status = "SUCCESS"
            except asyncio.TimeoutError:
                status = "TIMEOUT"
                error_msg = f"Eksekusi melebihi batas waktu ({timeout_seconds}s)"
            except Exception as e:
                status = "FAILED"
                error_msg = f"Docker execution error: {e}"
        else:
            # Mode B: In-process fallback via Microsoft Agent Framework (MAF).
            # TASK-165: NEVER report SUCCESS without real execution. If MAF is
            # unavailable, fail fast with an explicit SKIPPED status instead of
            # fabricating synthetic steps and a false success.
            maf_agent = self._get_maf_agent()
            if maf_agent is not None and has_llm_key:
                execution_mode = "maf"
                raw_logs.append("⚡ Prasyarat Docker/registry tidak lengkap — menjalankan runner in-process MAF...")
                try:
                    maf_result = await maf_agent.execute_task(
                        prompt=prompt,
                        title=task_title,
                        timeout_seconds=timeout_seconds,
                    )
                    maf_status = str(maf_result.get("status", "FAILED")).upper()
                    raw_logs.append(f"[MAF] status={maf_status}")
                    raw_logs.append(str(maf_result.get("chat_summary") or maf_result.get("error") or "").strip())
                    steps_executed.append({
                        "action": "MAF In-Process Execution",
                        "description": f"Executed via MAFCodeAgent (status={maf_status}).",
                        "status": "DONE" if maf_status == "COMPLETED" else "FAILED",
                    })
                    if maf_status == "COMPLETED":
                        status = "SUCCESS"
                    else:
                        status = "FAILED"
                        error_msg = str(maf_result.get("error") or "MAF task did not complete")
                except Exception as e:
                    status = "FAILED"
                    error_msg = f"MAF execution error: {e}"
            else:
                execution_mode = "skipped"
                status = "SKIPPED"
                missing = []
                if not is_docker_running():
                    missing.append("Docker daemon")
                if not chosen_registry:
                    missing.append("Docker registry reachable")
                if not has_llm_key:
                    missing.append("LLM key (LLM_API_KEY/OPENAI_API_KEY/ANTHROPIC_API_KEY)")
                if maf_agent is None:
                    missing.append("MAFCodeAgent (core.agent_framework.code_agent)")
                error_msg = "Prasyarat eksekusi tidak terpenuhi: " + ", ".join(missing)
                raw_logs.append(f"⏭️  SKIPPED — {error_msg}")

        duration = time.time() - start_time
        completed_iso = datetime.now(timezone.utc).isoformat()

        # Check file mutations
        current_created, current_modified = self._get_git_status()
        new_created = [f for f in current_created if f not in initial_created]
        new_modified = [f for f in current_modified if f not in initial_modified]
        current_diff = self._get_git_diff()

        # Build final report
        report.status = status
        report.completed_at = completed_iso
        report.duration_seconds = duration
        report.files_created = new_created
        report.files_modified = new_modified
        report.diff_content = current_diff if current_diff != initial_diff else None
        report.steps_executed = steps_executed
        report.raw_logs = "\n".join(raw_logs)
        report.error_message = error_msg
        report.execution_mode = execution_mode
        if status == "SKIPPED":
            report.summary = (
                f"Tugas DILEWATI (tidak dieksekusi) dalam {duration:.2f} detik. "
                f"Alasan: {error_msg or 'prasyarat eksekusi tidak terpenuhi'}."
            )
        elif status == "FAILED":
            report.summary = (
                f"Eksekusi GAGAL dalam {duration:.2f} detik (mode: {execution_mode or 'unknown'}). "
                f"{len(new_created)} file dibuat, {len(new_modified)} dimodifikasi. "
                f"Kesalahan: {error_msg or 'tidak diketahui'}."
            )
        else:
            report.summary = (
                f"Eksekusi selesai dalam {duration:.2f} detik (mode: {execution_mode or 'unknown'}) "
                f"dengan status {status}. {len(new_created)} file dibuat dan {len(new_modified)} file dimodifikasi."
            )

        # Write final rich artifact to Antigravity brain
        final_markdown = OpenHandsArtifactFormatter.render_markdown_artifact(report)
        artifact_path.write_text(final_markdown, encoding="utf-8")

        # Optionally sync to walkthrough.md in Antigravity Brain
        if sync_to_walkthrough:
            walkthrough_path = context.get_artifact_file("walkthrough.md")
            walkthrough_path.write_text(final_markdown, encoding="utf-8")

        self._history[task_id] = report

        # Render chat summary
        chat_summary = OpenHandsArtifactFormatter.render_chat_summary(report, artifact_path=artifact_path)

        return {
            "task_id": task_id,
            "status": status,
            "duration_seconds": duration,
            "artifact_path": str(artifact_path),
            "chat_summary": chat_summary,
            "report": report,
        }

    def get_task_report(self, task_id: str) -> Optional[OpenHandsTaskReport]:
        return self._history.get(task_id)

    def list_tasks(self) -> List[Dict[str, Any]]:
        return [
            {
                "task_id": r.task_id,
                "title": r.title,
                "status": r.status,
                "duration_seconds": r.duration_seconds,
                "started_at": r.started_at,
            }
            for r in self._history.values()
        ]


_bridge_instance: Optional[OpenHandsAntigravityBridge] = None


def get_openhands_bridge() -> OpenHandsAntigravityBridge:
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = OpenHandsAntigravityBridge()
    return _bridge_instance
