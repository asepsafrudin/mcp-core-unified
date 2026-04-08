"""
OpenHands Integration — Orchestrator (FASE 2: SDK Integration)

Wrapper di atas OpenHands SDK untuk mengelola lifecycle task:
submit → monitor → retrieve result.

FASE 2 mengubah orchestrator dari mock execution (TASK-034) menjadi
real SDK integration dengan OpenHands agent.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

import redis.asyncio as aioredis

from .config import config
from .schemas import CodingTaskRequest, TaskResult, TaskStatus, ActiveTaskInfo
from .prompt_templates import (
    OPENHANDS_BASE_SYSTEM_PROMPT,
    CODING_TASK_PROMPT,
)

logger = logging.getLogger(__name__)

# ─── OpenHands SDK Import dengan Fallback ─────────────────────────────
SDK_AVAILABLE = False
try:
    from openhands.sdk import LLM, Agent, Conversation, Tool
    from openhands.core.config import SandboxConfig, LLMConfig
    
    # Import tools
    from openhands.tools.file_editor import FileEditorTool
    from openhands.tools.terminal import TerminalTool
    _sdk_tools_available = True
    
    SDK_AVAILABLE = True
    logger.info("[OpenHands] SDK berhasil di-import (FASE 2: Modern SDK aktif)")
except ImportError as e:
    SDK_AVAILABLE = False
    _sdk_tools_available = False
    logger.warning(
        f"[OpenHands] SDK tidak tersedia, fallback ke FASE 1 mock mode. "
        f"Error: {e}"
    )


class OpenHandsOrchestrator:

    """
    Wrapper di atas OpenHands SDK.
    Mengelola lifecycle task: submit → monitor → retrieve result.
    
    FASE 2: SDK integration aktif bila SDK ter-install.
    FASE 1: Mock execution jika SDK belum tersedia.
    """

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self._semaphore = asyncio.Semaphore(config.max_concurrent_agents)
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._sdk_available = SDK_AVAILABLE

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    async def submit_task(self, request: CodingTaskRequest) -> str:
        """Submit task ke OpenHands agent. Returns task_id."""
        task_id = str(uuid.uuid4())[:8]
        workspace_path = self._create_workspace(task_id)

        initial_state = TaskResult.pending(task_id=task_id, workspace_path=str(workspace_path))
        await self._save_task(task_id, initial_state)

        # Simpan metadata tambahan untuk tracking
        await self.redis.set(
            f"{config.redis_prefix}{task_id}:metadata",
            json.dumps({
                "requested_by": request.requested_by,
                "priority": request.priority,
                "task_description": request.task_description,
            }),
            ex=86400,
        )

        # Jalankan di background agar tidak blocking MCP pipeline
        background_task = asyncio.create_task(
            self._run_agent(task_id, request, workspace_path)
        )
        self._running_tasks[task_id] = background_task
        background_task.add_done_callback(
            lambda t: self._running_tasks.pop(task_id, None)
        )

        mode = "SDK (FASE 2)" if self._sdk_available else "MOCK (FASE 1)"
        logger.info(
            f"[OpenHands] Task {task_id} submitted ({mode}), workspace: {workspace_path}",
        )
        return task_id

    async def get_status(self, task_id: str) -> Optional[TaskResult]:
        """Ambil status + hasil task dari Redis."""
        raw = await self.redis.get(f"{config.redis_prefix}{task_id}")
        if not raw:
            return None
        return TaskResult.from_dict(json.loads(raw))

    async def cancel_task(self, task_id: str) -> bool:
        """Set flag cancel di Redis; agent akan cek flag ini."""
        await self.redis.set(
            f"{config.redis_prefix}{task_id}:cancel", "1", ex=3600
        )
        # Jika ada running asyncio task, cancel juga
        if task_id in self._running_tasks:
            self._running_tasks[task_id].cancel()

        result = await self.get_status(task_id)
        if result:
            result.status = TaskStatus.CANCELLED
            result.completed_at = datetime.now(timezone.utc).isoformat()
            await self._save_task(task_id, result)
        return True

    async def list_active_tasks(self) -> List[ActiveTaskInfo]:
        """List semua task yang sedang running/pending."""
        tasks = []
        keys = await self.redis.keys(f"{config.redis_prefix}*")
        for key in keys:
            key_str = key if isinstance(key, str) else key.decode()
            if ":cancel" in key_str:
                continue
            if key_str.endswith(":metadata"):
                continue
            raw = await self.redis.get(key_str)
            if raw:
                try:
                    data = json.loads(raw)
                    status = data.get("status", "")
                    if status in ("pending", "running"):
                        task_id = data.get("task_id", "")
                        if not task_id:
                            task_id = key_str.replace(config.redis_prefix, "", 1)
                        metadata_raw = await self.redis.get(
                            f"{config.redis_prefix}{task_id}:metadata"
                        )
                        metadata = json.loads(metadata_raw) if metadata_raw else {}
                        tasks.append(ActiveTaskInfo(
                            task_id=task_id,
                            status=TaskStatus(status),
                            started_at=data.get("started_at"),
                            workspace_path=data.get("workspace_path", ""),
                            requested_by=metadata.get("requested_by", ""),
                            priority=metadata.get("priority", "medium"),
                        ))
                except (json.JSONDecodeError, ValueError):
                    continue
        return tasks

    @property
    def sdk_available(self) -> bool:
        """Check apakah SDK tersedia."""
        return self._sdk_available

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _create_workspace(self, task_id: str) -> Path:
        """Buat directory workspace untuk task ini."""
        workspace = Path(config.workspace_base) / task_id
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace

    async def _save_task(self, task_id: str, result: TaskResult):
        """Save task state ke Redis dengan TTL 24 jam."""
        await self.redis.set(
            f"{config.redis_prefix}{task_id}",
            json.dumps(result.to_dict()),
            ex=86400,
        )

    async def _run_agent(
        self,
        task_id: str,
        request: CodingTaskRequest,
        workspace_path: Path,
    ):
        """
        Jalankan OpenHands agent. Semaphore-limited.
        
        Jika SDK tersedia → gunakan OpenHands SDK
        Jika tidak → fallback ke FASE 1 mock execution
        """
        async with self._semaphore:
            # Update status → running
            result = await self.get_status(task_id)
            if result:
                result.status = TaskStatus.RUNNING
                await self._save_task(task_id, result)

            try:
                # ── Build prompts ────────────────────────────────────────
                full_prompt = CODING_TASK_PROMPT.format(
                    task_id=task_id,
                    requested_by=request.requested_by,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    task_description=request.task_description,
                    context=request.context or "-",
                    provided_files="\n".join(request.provided_files) or "-",
                    expected_output=request.expected_output,
                )

                system_prompt = OPENHANDS_BASE_SYSTEM_PROMPT.format(
                    workspace_path=str(workspace_path),
                )

                # ── Cek cancel flag ─────────────────────────────────────
                cancel_flag = await self.redis.get(
                    f"{config.redis_prefix}{task_id}:cancel"
                )
                if cancel_flag:
                    result.status = TaskStatus.CANCELLED
                    await self._save_task(task_id, result)
                    return

                # ── Route ke SDK atau mock ─────────────────────────────
                if self._sdk_available and config.use_sandbox:
                    await self._execute_with_sdk(
                        task_id=task_id,
                        request=request,
                        workspace_path=workspace_path,
                        system_prompt=system_prompt,
                        user_prompt=full_prompt,
                    )
                else:
                    await self._execute_mock(
                        task_id=task_id,
                        request=request,
                        workspace_path=workspace_path,
                    )

                # ── Parse RESULT.json ───────────────────────────────────
                result = await self.get_status(task_id)
                result_file = workspace_path / "RESULT.json"
                if result_file.exists():
                    agent_result = json.loads(result_file.read_text())
                    result.status = TaskStatus(agent_result.get("status", "success"))
                    result.summary = agent_result.get("summary", "")
                    result.files_created = agent_result.get("files_created", [])
                    result.files_modified = agent_result.get("files_modified", [])
                    result.errors = agent_result.get("errors", [])
                    result.next_steps = agent_result.get("next_steps", [])
                else:
                    result.status = TaskStatus.SUCCESS
                    result.summary = f"Task {task_id} selesai (RESULT.json tidak ditemukan)"

            except asyncio.CancelledError:
                result.status = TaskStatus.CANCELLED
                result.errors = ["Task dibatalkan oleh user/orchestrator"]
                logger.info(f"[OpenHands] Task {task_id} CANCELLED")

            except asyncio.TimeoutError:
                result.status = TaskStatus.TIMEOUT
                result.errors = [f"Task melebihi batas waktu {request.timeout_minutes} menit"]
                logger.warning(f"[OpenHands] Task {task_id} TIMEOUT")

            except Exception as e:
                result.status = TaskStatus.FAILED
                result.errors = [str(e)]
                logger.exception(f"[OpenHands] Task {task_id} FAILED: {e}")

            finally:
                if result:
                    result.completed_at = datetime.now(timezone.utc).isoformat()
                    await self._save_task(task_id, result)
                    logger.info(
                        f"[OpenHands] Task {task_id} completed with status: {result.status}"
                    )

    # ─── FASE 2: SDK Execution ──────────────────────────────────────────

    async def _execute_with_sdk(
        self,
        task_id: str,
        request: CodingTaskRequest,
        workspace_path: Path,
        system_prompt: str,
        user_prompt: str,
    ):
        """
        Execute menggunakan OpenHands SDK (FASE 2).
        
        Menggunakan LLM → Agent → Conversation pipeline dari SDK.
        """
        if not SDK_AVAILABLE:
            raise RuntimeError("OpenHands SDK tidak tersedia")

        def _run_sdk_sync():
            """Jalankan SDK di thread executor (blocking call)."""
            # Setup logging ke file agar bisa dibaca via Resource
            log_file = workspace_path / "agent.log"
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            
            oh_logger = logging.getLogger("openhands")
            oh_logger.addHandler(file_handler)
            oh_logger.setLevel(logging.DEBUG if config.debug_logging else logging.INFO)

            try:
                # Setup LLM
                llm_config_kwargs = {
                    "model": config.llm_model,
                }
                if config.llm_api_key:
                    llm_config_kwargs["api_key"] = config.llm_api_key
                if config.llm_api_base:
                    llm_config_kwargs["base_url"] = config.llm_api_base
                
                llm = LLM(config=LLMConfig(**llm_config_kwargs))

                # Setup tools (jika tersedia)
                tools = []
                if _sdk_tools_available:
                    try:
                        tools.append(TerminalTool())
                        tools.append(FileEditorTool())
                    except Exception as e:
                        logger.warning(f"[OpenHands] Failed to init SDK tools: {e}")

                # Setup agent
                agent = Agent(
                    llm=llm,
                    tools=tools,
                    system_prompt=system_prompt,
                )

                # Create conversation and run
                conversation = Conversation(
                    agent=agent, 
                    workspace=str(workspace_path)
                )
                conversation.send_message(user_prompt)
                
                # Run till completion
                result_obj = conversation.run()

                return result_obj
            except Exception as e:
                logger.exception(f"[OpenHands] SDK execution error: {e}")
                raise
            finally:
                oh_logger.removeHandler(file_handler)
                file_handler.close()


        # Jalankan di executor untuk menghindari blocking event loop
        loop = asyncio.get_event_loop()
        await asyncio.wait_for(
            loop.run_in_executor(None, _run_sdk_sync),
            timeout=request.timeout_minutes * 60,
        )

    # ─── FASE 1: Mock Execution (Fallback) ──────────────────────────────

    async def _execute_mock(
        self,
        task_id: str,
        request: CodingTaskRequest,
        workspace_path: Path,
    ):
        """
        Mock execution untuk testing tanpa SDK (FASE 1).
        Tetap menghasilkan RESULT.json yang valid.
        """
        mode = "SDK" if self._sdk_available else "MOCK"
        
        # Tulis task log
        task_log = workspace_path / "TASK_LOG.md"
        task_log.write_text(
            f"# Task Log: {task_id}\n\n"
            f"- **Dimulai**: {datetime.now(timezone.utc).isoformat()}\n"
            f"- **Mode**: {mode} execution\n"
            f"- **Deskripsi**: {request.task_description}\n"
            f"- **Expected**: {request.expected_output}\n"
            f"- **Requested by**: {request.requested_by}\n"
            f"- **Priority**: {request.priority}\n\n"
            f"## Execution\n\n"
            f"Task ini berjalan dalam {'SDK' if self._sdk_available else 'mock'} mode.\n"
        )

        # Simulasi delay singkat
        await asyncio.sleep(1)

        # Tulis RESULT.json sebagai bukti execution
        result_data = {
            "status": "success",
            "summary": f"Task {task_id} completed ({mode} execution)",
            "files_created": [str(task_log)],
            "files_modified": [],
            "next_steps": [
                "Review hasil kerja agent",
                "Lanjutkan ke subtask berikutnya" if self._sdk_available else "Install OpenHands SDK untuk real execution",
            ],
        }
        result_file = workspace_path / "RESULT.json"
        result_file.write_text(json.dumps(result_data, indent=2, ensure_ascii=False))

        logger.info(f"[OpenHands] Task {task_id} {mode} execution completed")