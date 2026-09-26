"""
MAF Safe Code & Task Agent
Drop-in replacement for OpenHands (run_coding_task) using Microsoft Agent Framework.
Runs lightweight, containerless, safe coding loops with telemetry and guardrails.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.agent_framework.client import ModelClientFactory, SupportedProvider
from core.agent_framework.mcp_registry import DynamicMCPRegistry
from core.agent_framework.telemetry import MAFTelemetryGuardrails


@dataclass
class CodingTaskState:
    task_id: str
    prompt: str
    status: str  # PENDING, RUNNING, COMPLETED, FAILED, CANCELLED
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[str] = None
    error: Optional[str] = None
    logs: List[str] = field(default_factory=list)


class MAFCodeAgent:
    """Safe Code & Task Execution Agent powered by Microsoft Agent Framework."""

    def __init__(
        self,
        workspace_dir: Optional[Path] = None,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.workspace_dir = workspace_dir or REPO_ROOT
        self.provider = provider
        self.model_name = model_name
        self.registry = DynamicMCPRegistry(self.workspace_dir)
        self.guardrails = MAFTelemetryGuardrails()
        self._tasks: Dict[str, CodingTaskState] = {}

    def _execute_safe_command(self, cmd: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute shell command safely as user aseps without sudo."""
        if "sudo " in cmd:
            return {"exit_code": 1, "output": "ERROR: sudo is strictly prohibited in workspace (Rule #1.5)"}

        try:
            res = subprocess.run(
                cmd,
                shell=True,
                cwd=str(self.workspace_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
            )
            return {"exit_code": res.returncode, "output": res.stdout}
        except subprocess.TimeoutExpired:
            return {"exit_code": -1, "output": f"Command timed out after {timeout} seconds"}
        except Exception as e:
            return {"exit_code": 1, "output": str(e)}

    async def execute_task(
        self,
        prompt: str,
        title: Optional[str] = None,
        timeout_seconds: int = 300,
    ) -> Dict[str, Any]:
        """Execute a coding/refactoring task asynchronously."""
        start_time = time.time()
        task_id = str(uuid.uuid4())[:8]
        state = CodingTaskState(task_id=task_id, prompt=prompt, status="RUNNING", started_at=start_time)
        self._tasks[task_id] = state

        # Create MAF agent instance
        instructions = (
            f"You are a Senior Software Engineer executing a coding task in workspace: {self.workspace_dir}.\n"
            f"Rule 1: NEVER run sudo or elevate privileges.\n"
            f"Rule 2: Keep code clean, preserve documentation, follow existing patterns.\n"
            f"Rule 3: Adhere to storage isolation (write data/reports to storage/ only)."
        )
        
        tools = self.registry.get_tools_for_profile("coding")
        agent = ModelClientFactory.create_agent(
            name=f"MAF-Coder-{task_id}",
            instructions=instructions,
            tools=tools,
            provider=self.provider,
            model_name=self.model_name,
        )

        try:
            # Run agent session
            response = await agent.run(prompt)
            duration = time.time() - start_time
            state.status = "COMPLETED"
            state.completed_at = time.time()
            state.result = str(response.text if hasattr(response, "text") else response)

            return {
                "task_id": task_id,
                "status": "COMPLETED",
                "title": title or "MAF Coding Task",
                "duration_seconds": duration,
                "chat_summary": state.result[:1000] if state.result else "Task completed successfully",
                "logs": state.logs,
            }
        except Exception as e:
            duration = time.time() - start_time
            state.status = "FAILED"
            state.error = str(e)
            return {
                "task_id": task_id,
                "status": "FAILED",
                "title": title or "MAF Coding Task",
                "duration_seconds": duration,
                "error": str(e),
            }

    def submit_task(self, prompt: str, title: Optional[str] = None) -> str:
        """Submit background task and return task_id (mimics run_coding_task API)."""
        task_id = str(uuid.uuid4())[:8]
        state = CodingTaskState(task_id=task_id, prompt=prompt, status="PENDING")
        self._tasks[task_id] = state
        
        # Fire in background if loop is running
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.execute_task(prompt, title=title))
        except RuntimeError:
            # If called from sync environment without loop, state remains PENDING
            pass
        return task_id

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Query status of a submitted coding task."""
        state = self._tasks.get(task_id)
        if not state:
            return None
        return {
            "task_id": state.task_id,
            "status": state.status,
            "result": state.result,
            "error": state.error,
            "duration": (state.completed_at - state.started_at) if (state.completed_at and state.started_at) else None,
        }

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        state = self._tasks.get(task_id)
        if state and state.status in ("PENDING", "RUNNING"):
            state.status = "CANCELLED"
            return True
        return False
