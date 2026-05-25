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
import os
import shutil
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

import redis.asyncio as aioredis

from .config import config
from .schemas import CodingTaskRequest, TaskResult, TaskStatus, ActiveTaskInfo
from .prompt_templates import (
    OPENHANDS_BASE_SYSTEM_PROMPT,
    CODING_TASK_PROMPT,
)

# Ensure project root is in sys.path before importing orchestration and skills
import sys
import os
from pathlib import Path
# parents[0]=oh_integration/, parents[1]=plugins/, parents[2]=core/mcp-unified/
project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Evict any wrong-path versions of orchestration/skills from sys.modules
# (terjadi jika /home/aseps/MCP/mcp-unified/ masuk sys.path lebih dulu dari PYTHONPATH)
def _get_mod_path(mod):
    f = getattr(mod, '__file__', None)
    if f:
        return f
    p = getattr(mod, '__path__', None)
    if p:
        try:
            return str(list(p)[0])
        except Exception:
            return ''
    return ''

_correct_orchestration = os.path.join(project_root, "orchestration")
_correct_skills = os.path.join(project_root, "skills")
for _mn in list(sys.modules.keys()):
    _mp = _get_mod_path(sys.modules[_mn])
    if (_mn == "orchestration" or _mn.startswith("orchestration.")) and _mp and _correct_orchestration not in _mp:
        del sys.modules[_mn]
    elif (_mn == "skills" or _mn.startswith("skills.")) and _mp and _correct_skills not in _mp:
        del sys.modules[_mn]



# Antigravity Orchestration Layer Imports — dengan graceful fallback
try:
    from orchestration.antigravity_ledger import ledger
except ImportError as _e:
    import logging as _log_import
    _log_import.getLogger(__name__).warning(
        "orchestration.antigravity_ledger tidak tersedia: %s — ledger dinonaktifkan.", _e
    )
    ledger = None  # type: ignore

try:
    from skills.token_controller import token_controller
except ImportError as _e:
    import logging as _log_import2
    _log_import2.getLogger(__name__).warning(
        "skills.token_controller tidak tersedia: %s", _e
    )
    token_controller = None  # type: ignore

try:
    from skills.virtual_queue import virtual_queue
except ImportError as _e:
    import logging as _log_import3
    _log_import3.getLogger(__name__).warning(
        "skills.virtual_queue tidak tersedia: %s", _e
    )
    virtual_queue = None  # type: ignore



logger = logging.getLogger(__name__)

# ─── OpenHands SDK Import dengan Fallback ─────────────────────────────
SDK_AVAILABLE = False
try:
    from openhands.sdk import LLM, Agent, Conversation, Tool  # type: ignore
    from openhands.core.config import SandboxConfig, LLMConfig  # type: ignore
    
    # Import tools
    from openhands.tools.file_editor import FileEditorTool  # type: ignore
    from openhands.tools.terminal import TerminalTool  # type: ignore
    _sdk_tools_available = True
    
    SDK_AVAILABLE = True
    logger.info("[OpenHands] SDK berhasil di-import (FASE 2: Modern SDK aktif)")
except ImportError as e:
    SDK_AVAILABLE = False
    _sdk_tools_available = False
    logger.debug(
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
        
        # Cleanup workspaces lama di background
        asyncio.create_task(self._cleanup_old_workspaces())

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    async def submit_task(self, request: CodingTaskRequest) -> str:
        """Submit task ke OpenHands agent. Returns task_id."""
        task_id = str(uuid.uuid4())[:8]
        workspace_path = self._create_workspace(task_id)
        self._write_env_context(workspace_path)

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

        # --- Antigravity Pre-Flight Check ---
        estimated_tokens = await token_controller.estimate_files(request.provided_files)
        logger.info(f"[Antigravity] Pre-flight estimation: {estimated_tokens} tokens for {len(request.provided_files)} files")
        
        # Jalankan di background agar tidak blocking MCP pipeline
        background_task = asyncio.create_task(
            self._run_agent(task_id, request, workspace_path, estimated_tokens)
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

    def _write_env_context(self, workspace_path: Path):
        """
        Tulis konteks environment yang aman untuk membantu agent memahami
        koneksi database yang tersedia tanpa menanam secret mentah ke file.
        """
        env_context = workspace_path / "ENV_CONTEXT.md"
        lines = [
            "# Runtime Environment Context",
            "",
            "Gunakan konteks ini sebelum menjalankan query ke PostgreSQL atau knowledge base.",
            "",
            "## Runtime variables",
            f"- PG_HOST: {os.getenv('PG_HOST', '-')}",
            f"- PG_PORT: {os.getenv('PG_PORT', '-')}",
            f"- PG_DATABASE: {os.getenv('PG_DATABASE', '-')}",
            f"- PG_USER: {os.getenv('PG_USER', '-')}",
            f"- DATABASE_URL: {os.getenv('DATABASE_URL', '-')}",
            "",
            "## Instructions",
            "- Jangan asumsi localhost default benar tanpa verifikasi.",
            "- Jika  ***REMOVED_DB_URL***kosong, gunakan PG_* yang disediakan runtime.",
            "- Jangan hardcode credential baru ke file workspace.",
        ]
        env_context.write_text("\n".join(lines) + "\n", encoding="utf-8")

    async def _cleanup_old_workspaces(self, days: int = 7):
        """Hapus workspace yang lebih lama dari N hari."""
        try:
            base_path = Path(config.workspace_base)
            if not base_path.exists():
                return

            now = time.time()
            max_age = days * 24 * 3600
            count = 0

            for item in base_path.iterdir():
                if item.is_dir():
                    mtime = item.stat().st_mtime
                    if (now - mtime) > max_age:
                        shutil.rmtree(item)
                        count += 1
            
            if count > 0:
                logger.info(f"[OpenHands] Cleaned up {count} old workspaces.")
        except Exception as e:
            logger.warning(f"[OpenHands] Workspace cleanup failed: {e}")

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
        estimated_tokens: int = 0
    ):
        """
        Jalankan OpenHands agent. Semaphore-limited.
        
        Jika SDK tersedia → gunakan OpenHands SDK
        Jika tidak → fallback ke FASE 1 mock execution
        """
        async with self._semaphore:
            # --- Antigravity Traffic Control (Virtual Queue) ---
            await virtual_queue.wait_for_quota(estimated_tokens)
            
            # Update status → running
            result = await self.get_status(task_id)
            if result:
                result.status = TaskStatus.RUNNING
                await self._save_task(task_id, result)

            try:
                # ── Copy provided files ke workspace ───────────────────
                for file_path_str in request.provided_files:
                    try:
                        src = Path(file_path_str)
                        if not src.is_absolute():
                            src = Path("/home/aseps/MCP") / src
                        
                        if src.exists():
                            try:
                                rel_path = src.relative_to("/home/aseps/MCP")
                                dest = workspace_path / rel_path
                            except ValueError:
                                dest = workspace_path / src.name
                                
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            if src.is_file():
                                shutil.copy2(src, dest)
                            elif src.is_dir():
                                shutil.copytree(src, dest, dirs_exist_ok=True)
                            logger.info(f"[OpenHands] Copied {src} to workspace.")
                    except Exception as e:
                        logger.warning(f"[OpenHands] Failed to copy {file_path_str} to workspace: {e}")

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
                env_context = workspace_path / "ENV_CONTEXT.md"
                if env_context.exists():
                    system_prompt = (
                        system_prompt
                        + "\n\n## Runtime Environment Snapshot\n"
                        + env_context.read_text(encoding="utf-8")
                    )

                # ── Cek cancel flag ─────────────────────────────────────
                cancel_flag = await self.redis.get(f"{config.redis_prefix}{task_id}:cancel")
                if result and cancel_flag:
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

                if result:
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
                if result:
                    result.status = TaskStatus.CANCELLED
                    result.errors = ["Task dibatalkan oleh user/orchestrator"]
                logger.info(f"[OpenHands] Task {task_id} CANCELLED")

            except asyncio.TimeoutError:
                if result:
                    result.status = TaskStatus.TIMEOUT
                    result.errors = [f"Task melebihi batas waktu {request.timeout_minutes} menit"]
                logger.warning(f"[OpenHands] Task {task_id} TIMEOUT")

            except Exception as e:
                if result:
                    result.status = TaskStatus.FAILED
                    result.errors = [str(e)]
                logger.exception(f"[OpenHands] Task {task_id} FAILED: {e}")

            finally:
                if result:
                    result.completed_at = datetime.now(timezone.utc).isoformat()
                    
                    # ── Sync back changes jika sukses ─────────────────────────
                    if result.status == TaskStatus.SUCCESS:
                        logger.info(f"[OpenHands] Syncing back changes for Task {task_id}...")
                        for file_path_str in request.provided_files:
                            try:
                                src_rel = Path(file_path_str)
                                if src_rel.is_absolute():
                                    try:
                                        src_rel = src_rel.relative_to("/home/aseps/MCP")
                                    except ValueError:
                                        continue
                                
                                src_in_ws = workspace_path / src_rel
                                dest_in_repo = Path("/home/aseps/MCP") / src_rel
                                
                                if src_in_ws.exists() and src_in_ws.is_file():
                                    # Auto-Fix Indentation/Style jika Python
                                    if src_in_ws.suffix == ".py":
                                        await self._format_file(src_in_ws)

                                    if not dest_in_repo.exists() or src_in_ws.read_bytes() != dest_in_repo.read_bytes():
                                        dest_in_repo.parent.mkdir(parents=True, exist_ok=True)
                                        shutil.copy2(src_in_ws, dest_in_repo)
                                        logger.info(f"[OpenHands] Synced back {src_rel} to repo.")
                            except Exception as e:
                                logger.warning(f"[OpenHands] Failed to sync back {file_path_str}: {e}")

                    # Simpan hasil akhir
                    await self._save_task(task_id, result)
                    
                    # Sync to LTM
                    metadata_raw = await self.redis.get(f"{config.redis_prefix}{task_id}:metadata")
                    metadata = json.loads(metadata_raw) if metadata_raw else {}
                    await self._sync_to_ltm(result, metadata)
                    
                    logger.info(f"[OpenHands] Task {task_id} completed with status: {result.status}")

    async def _format_file(self, file_path: Path):
        """Format Python file using Black if available."""
        try:
            import subprocess
            # Gunakan black dari .venv
            venv_path = os.getenv("VIRTUAL_ENV", "/home/aseps/MCP/.venv")
            black_path = os.path.join(venv_path, "bin/black")
            
            if os.path.exists(black_path):
                result = subprocess.run(
                    [black_path, str(file_path)],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    logger.debug(f"[OpenHands] Auto-formatted {file_path}")
                else:
                    logger.warning(f"[OpenHands] Black formatting failed for {file_path}: {result.stderr}")
        except Exception as e:
            logger.warning(f"[OpenHands] Failed to run Black for {file_path}: {e}")

    async def _sync_to_ltm(self, result: TaskResult, metadata: Dict[str, Any]):
        """Sinkronisasi hasil kerja agent ke Long-Term Memory (LTM)."""
        try:
            # Import registry secara lokal untuk menghindari circular dependency
            from execution.registry import registry
            
            # Buat konten pengalaman
            experience = {
                "task_id": result.task_id,
                "description": metadata.get("task_description", ""),
                "summary": result.summary,
                "status": result.status.value,
                "files_modified": result.files_modified,
                "files_created": result.files_created,
                "errors": result.errors,
                "completed_at": result.completed_at
            }
            
            # Simpan ke LTM menggunakan namespace 'openhands_experience'
            if registry.get_tool("memory_save"):
                await registry.execute("memory_save", {
                    "key": f"task:{result.task_id}",
                    "content": json.dumps(experience, ensure_ascii=False),
                    "namespace": "openhands_experience",
                    "metadata": {
                        "type": "agent_execution",
                        "agent": "openhands",
                        "requested_by": metadata.get("requested_by", "mcp_orchestrator")
                    }
                })
                logger.info(f"[OpenHands] Task {result.task_id} synced to LTM.")
            else:
                logger.warning(f"[OpenHands] Tool 'memory_save' not found. Skipping LTM sync for {result.task_id}.")
        except Exception as e:
            logger.warning(f"[OpenHands] Failed to sync task {result.task_id} to LTM: {e}")

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

            # Suppress banner
            os.environ["OPENHANDS_SUPPRESS_BANNER"] = "1"

            try:
                # Setup LLM
                llm_kwargs = {
                    "model": config.llm_model,
                    "api_key": config.llm_api_key,
                    "base_url": config.llm_api_base,
                }
                
                # Fix untuk model reasoning di Groq (qwen3)
                if "qwen3" in config.llm_model.lower():
                    llm_kwargs["reasoning_effort"] = "none"
                    llm_kwargs["max_tokens"] = "4096"
                    llm_kwargs["extra_body"] = json.dumps({"max_tokens": 4096})
                
                llm = LLM(**llm_kwargs)

                # Setup tools (jika tersedia)
                tools = []
                if _sdk_tools_available:
                    try:
                        # Di v1.15.0+ tool harus di-wrap dalam Tool spec
                        tools.append(Tool(name=TerminalTool.name))
                        tools.append(Tool(name=FileEditorTool.name))
                    except Exception as e:
                        logger.warning(f"[OpenHands] Failed to init SDK tools: {e}")

                # Setup agent
                agent = Agent(
                    llm=llm,
                    tools=tools,
                    system_prompt=system_prompt,
                    critic=None,
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
        result_obj = await asyncio.wait_for(
            loop.run_in_executor(None, _run_sdk_sync),
            timeout=request.timeout_minutes * 60,
        )

        # --- Antigravity: Record Usage ---
        try:
            # Note: Usage metadata extraction depends on SDK version
            # If result_obj has usage info, record it
            if hasattr(result_obj, 'usage') and result_obj.usage:
                await token_controller.record_usage(
                    usage_metadata=result_obj.usage,
                    task_id=task_id,
                    model=config.llm_model
                )
            else:
                # Fallback: estimate based on result length if possible
                result_text = str(result_obj)
                est_tokens = token_controller.estimate_tokens(result_text)
                await token_controller.record_usage(
                    usage_metadata={"prompt_tokens": 0, "completion_tokens": est_tokens},
                    task_id=task_id,
                    model=config.llm_model
                )
                logger.info(f"[Antigravity] Recorded estimated usage: {est_tokens} tokens for task {task_id}")
        except Exception as e:
            logger.warning(f"[Antigravity] Failed to record usage: {e}")

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
