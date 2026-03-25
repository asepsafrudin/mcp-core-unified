"""
Job Executor untuk MCP Autonomous Task Scheduler.

Mengeksekusi scheduled jobs dengan integrasi ke:
- LTM (Long Term Memory) untuk context retrieval
- Planner untuk autonomous task execution
- Self-Healing untuk error recovery
- Tool Registry untuk actual execution
"""

import json
import asyncio
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from scheduler.database import (
    get_job, update_execution, create_execution,
    update_job_next_run, get_due_jobs
)
from scheduler.pools import pool_manager
from scheduler.redis_queue import scheduler_queue
from observability.logger import logger

# Import komponen MCP existing (akan tersedia saat runtime)
try:
    from memory.longterm import memory_search, memory_save
    from execution.registry import ToolRegistry
    LTM_AVAILABLE = True
except ImportError:
    LTM_AVAILABLE = False
    logger.warning("executor_ltm_not_available")

try:
    from intelligence.planner import create_plan
    PLANNER_AVAILABLE = True
except ImportError:
    PLANNER_AVAILABLE = False
    logger.warning("executor_planner_not_available")

try:
    from intelligence.self_healing import PracticalSelfHealing
    HEALING_AVAILABLE = True
except ImportError:
    HEALING_AVAILABLE = False
    logger.warning("executor_healing_not_available")


class JobExecutor:
    """
    Executes scheduled jobs dengan full MCP integration.
    
    Flow:
    1. Load job configuration
    2. Retrieve context dari LTM
    3. Generate execution plan (untuk autonomous tasks)
    4. Execute via Tool Registry
    5. Apply self-healing jika error
    6. Save results ke LTM
    """
    
    def __init__(self):
        self.running_executions: Dict[str, Dict] = {}
        self._shutdown_event = asyncio.Event()
        self.tool_registry = None
        self.healing_engine = None
        
        if HEALING_AVAILABLE:
            self.healing_engine = PracticalSelfHealing()
    
    async def initialize(self):
        """Initialize executor dan connect ke dependencies."""
        # Connect to Redis queue
        await scheduler_queue.connect()
        
        # Initialize tool registry jika available
        if ToolRegistry:
            self.tool_registry = ToolRegistry()
        
        logger.info("executor_initialized", 
                   ltm_available=LTM_AVAILABLE,
                   planner_available=PLANNER_AVAILABLE,
                   healing_available=HEALING_AVAILABLE)
    
    async def shutdown(self):
        """Graceful shutdown."""
        self._shutdown_event.set()
        await scheduler_queue.disconnect()
        logger.info("executor_shutdown")
    
    async def execute_job(
        self,
        job_id: str,
        execution_id: Optional[str] = None,
        trigger_type: str = "scheduled"  # scheduled, manual, event
    ) -> Dict[str, Any]:
        """
        Execute a job dengan full lifecycle management.
        
        Args:
            job_id: Job ID to execute
            execution_id: Optional existing execution ID
            trigger_type: How the job was triggered
        
        Returns:
            Execution result
        """
        start_time = time.time()
        
        # 1. Load job configuration
        job = await get_job(job_id)
        if not job:
            return {"success": False, "error": f"Job {job_id} not found"}
        
        job_name = job["name"]
        job_type = job["job_type"]
        task_config = job.get("task_config", {})
        namespace = job.get("namespace", "default")
        priority = job.get("priority", 50)
        
        logger.info("executor_starting_job",
                   job_id=job_id,
                   job_name=job_name,
                   job_type=job_type,
                   trigger=trigger_type)
        
        # 2. Create atau update execution record
        if not execution_id:
            exec_result = await create_execution(
                job_id=job_id,
                job_name=job_name,
                worker_node="local"
            )
            if not exec_result["success"]:
                return exec_result
            execution_id = exec_result["execution_id"]
        
        self.running_executions[execution_id] = {
            "job_id": job_id,
            "job_name": job_name,
            "started_at": datetime.now(timezone.utc),
            "status": "running"
        }
        
        # 3. Update execution status to running
        await update_execution(execution_id, status="running")
        await scheduler_queue.mark_running(
            execution_id=execution_id,
            job_id=job_id,
            job_name=job_name,
            job_type=job_type,
            priority=priority
        )
        
        try:
            # 4. Retrieve context dari LTM (jika available)
            ltm_context = None
            if LTM_AVAILABLE and task_config.get("use_context", True):
                ltm_context = await self._retrieve_context(
                    query=job.get("description", job_name),
                    namespace=namespace
                )
            
            # 5. Generate execution plan (untuk autonomous tasks)
            execution_plan = None
            if PLANNER_AVAILABLE and task_config.get("use_planner", False):
                execution_plan = await self._create_execution_plan(
                    objective=task_config.get("prompt", job_name),
                    context=ltm_context,
                    namespace=namespace
                )
            
            # 6. Execute task steps
            steps = task_config.get("steps", [])
            results = []
            
            for step_idx, step in enumerate(steps):
                step_result = await self._execute_step(
                    step=step,
                    step_idx=step_idx,
                    execution_id=execution_id,
                    job_id=job_id,
                    namespace=namespace
                )
                results.append(step_result)
                
                # Stop jika step failed dan tidak ada retry
                if not step_result.get("success") and not task_config.get("continue_on_error"):
                    break
            
            # 7. Determine overall success
            all_success = all(r.get("success", False) for r in results)
            final_status = "success" if all_success else "failed"
            
            # 8. Save results ke LTM
            if LTM_AVAILABLE:
                await self._save_execution_result(
                    execution_id=execution_id,
                    job_id=job_id,
                    job_name=job_name,
                    results=results,
                    status=final_status,
                    namespace=namespace
                )
            
            # 9. Update execution record
            duration_ms = int((time.time() - start_time) * 1000)
            await update_execution(
                execution_id=execution_id,
                status=final_status,
                output={
                    "results": results,
                    "duration_ms": duration_ms,
                    "steps_completed": len(results),
                    "steps_total": len(steps)
                },
                execution_plan=execution_plan,
                context_used=ltm_context
            )
            
            # 10. Update job's next_run_at
            await self._schedule_next_run(job_id, job)
            
            # 11. Cleanup
            await scheduler_queue.mark_completed(execution_id)
            if execution_id in self.running_executions:
                del self.running_executions[execution_id]
            
            logger.info("executor_job_completed",
                        execution_id=execution_id,
                        job_id=job_id,
                        status=final_status,
                        duration_ms=duration_ms)
            
            return {
                "success": all_success,
                "execution_id": execution_id,
                "job_id": job_id,
                "job_name": job_name,
                "status": final_status,
                "results": results,
                "duration_ms": duration_ms
            }
            
        except Exception as e:
            logger.error("executor_job_failed",
                        execution_id=execution_id,
                        job_id=job_id,
                        error=str(e))
            
            # Mark as failed
            await update_execution(
                execution_id=execution_id,
                status="failed",
                error_message=str(e)
            )
            
            await scheduler_queue.mark_completed(execution_id)
            if execution_id in self.running_executions:
                del self.running_executions[execution_id]
            
            return {
                "success": False,
                "execution_id": execution_id,
                "error": str(e)
            }
    
    async def _retrieve_context(
        self,
        query: str,
        namespace: str = "default",
        limit: int = 5
    ) -> Optional[List[Dict]]:
        """Retrieve relevant context dari LTM."""
        if not LTM_AVAILABLE:
            return None
        
        try:
            result = await memory_search(
                query=query,
                namespace=namespace,
                limit=limit
            )
            
            if result.get("success"):
                contexts = result.get("results", [])
                logger.info("executor_context_retrieved",
                           query=query[:50],
                           count=len(contexts))
                return contexts
            
        except Exception as e:
            logger.warning("executor_context_failed", error=str(e))
        
        return None
    
    async def _create_execution_plan(
        self,
        objective: str,
        context: Optional[List[Dict]],
        namespace: str = "default"
    ) -> Optional[Dict]:
        """Create execution plan menggunakan Planner."""
        if not PLANNER_AVAILABLE:
            return None
        
        try:
            # Build context string dari LTM results
            context_str = ""
            if context:
                context_str = "\n\nRelevant context:\n"
                for ctx in context:
                    context_str += f"- {ctx.get('content', '')[:200]}\n"
            
            full_prompt = f"{objective}{context_str}"
            
            plan_result = await create_plan(
                request=full_prompt,
                namespace=namespace
            )
            
            if plan_result.get("success"):
                logger.info("executor_plan_created",
                           objective=objective[:50],
                           steps=len(plan_result.get("plan", [])))
                return plan_result.get("plan")
            
        except Exception as e:
            logger.error("executor_planning_failed", error=str(e))
        
        return None
    
    async def _execute_step(
        self,
        step: Dict[str, Any],
        step_idx: int,
        job_id: str,
        execution_id: str,
        namespace: str = "default"
    ) -> Dict[str, Any]:
        """
        Execute a single step dalam job.
        
        Supports:
        - run_shell: Execute shell command
        - memory_save: Save ke LTM
        - memory_search: Search LTM
        - create_plan: Use planner
        - self_heal: Use self-healing
        """
        step_name = step.get("name", f"step_{step_idx}")
        tool = step.get("tool", "run_shell")
        timeout = step.get("timeout", 300)
        
        logger.info("executor_executing_step",
   
                   step=step_name,
                   tool=tool)
        
        try:
            if tool == "run_shell":
                result = await self._execute_shell_step(step, timeout)
            
            elif tool == "memory_save" and LTM_AVAILABLE:
                result = await self._execute_memory_save_step(step, namespace)
            
            elif tool == "memory_search" and LTM_AVAILABLE:
                result = await self._execute_memory_search_step(step, namespace)
            
            elif tool == "create_plan" and PLANNER_AVAILABLE:
                result = await self._execute_plan_step(step, namespace)
            
            elif tool == "self_heal" and HEALING_AVAILABLE:
                result = await self._execute_heal_step(step)
            
            else:
                result = {
                    "success": False,
                    "error": f"Unknown or unavailable tool: {tool}"
                }
            
            # Apply self-healing jika failed dan healing available
            if not result.get("success") and HEALING_AVAILABLE and step.get("heal_on_error", True):
                result = await self._attempt_healing(step, result, step_name)
            
            return result
            
        except Exception as e:
            logger.error("executor_step_failed",
                        step=step_name,
                        error=str(e))
            return {
                "success": False,
                "step": step_name,
                "error": str(e)
            }
    
    async def _execute_shell_step(
        self,
        step: Dict[str, Any],
        timeout: int
    ) -> Dict[str, Any]:
        """Execute shell command step."""
        command = step.get("command", "")
        
        if not command:
            return {"success": False, "error": "No command provided"}
        
        try:
            # Create subprocess
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Wait dengan timeout
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout
            )
            
            success = proc.returncode == 0
            
            return {
                "success": success,
                "stdout": stdout.decode() if stdout else "",
                "stderr": stderr.decode() if stderr else "",
                "exit_code": proc.returncode
            }
            
        except asyncio.TimeoutError:
            proc.kill()
            return {
                "success": False,
                "error": f"Command timed out after {timeout}s"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _execute_memory_save_step(
        self,
        step: Dict[str, Any],
        namespace: str
    ) -> Dict[str, Any]:
        """Execute memory save step."""
        key = step.get("key", "")
        content = step.get("content", "")
        
        if not key or not content:
            return {"success": False, "error": "Key and content required"}
        
        # Replace placeholders
        key = key.replace("{timestamp}", datetime.now().strftime("%Y%m%d_%H%M%S"))
        content = content.replace("{timestamp}", datetime.now().isoformat())
        
        result = await memory_save(
            key=key,
            content=content,
            namespace=namespace
        )
        
        return result
    
    async def _execute_memory_search_step(
        self,
        step: Dict[str, Any],
        namespace: str
    ) -> Dict[str, Any]:
        """Execute memory search step."""
        query = step.get("query", "")
        limit = step.get("limit", 5)
        
        if not query:
            return {"success": False, "error": "Query required"}
        
        result = await memory_search(
            query=query,
            namespace=namespace,
            limit=limit
        )
        
        return result
    
    async def _execute_plan_step(
        self,
        step: Dict[str, Any],
        namespace: str
    ) -> Dict[str, Any]:
        """Execute planner step."""
        objective = step.get("objective", "")
        
        if not objective:
            return {"success": False, "error": "Objective required"}
        
        result = await create_plan(
            request=objective,
            namespace=namespace
        )
        
        return result
    
    async def _execute_heal_step(
        self,
        step: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute self-healing step menggunakan PracticalSelfHealing.
        
        Args:
            step: Step configuration dengan healing parameters
        
        Returns:
            Healing result dengan status dan actions taken
        """
        mode = step.get("mode", "auto")
        
        if not HEALING_AVAILABLE or not self.healing_engine:
            return {
                "success": False,
                "mode": mode,
                "message": "Self-healing engine not available",
                "actions": []
            }
        
        try:
            # Get healing configuration dari step
            max_retries = step.get("max_retries", 3)
            retry_delay = step.get("retry_delay", 5)
            command = step.get("command", "")
            
            logger.info("executor_healing_started",
                       mode=mode,
                       max_retries=max_retries)
            
            # Use healing engine untuk execute dengan healing
            # PracticalSelfHealing.execute_with_healing akan:
            # 1. Execute command
            # 2. Jika gagal, analyze error
            # 3. Apply healing strategies
            # 4. Retry dengan exponential backoff
            
            async def healing_wrapper():
                """Wrapper untuk healing execution."""
                for attempt in range(max_retries):
                    try:
                        # Try to execute the command
                        result = await self._execute_shell_step(
                            {"command": command},
                            step.get("timeout", 300)
                        )
            
                        
                        if result.get("success"):
                            return {
                                "success": True,
                                "attempt": attempt + 1,
                                "result": result
                            }
                        
                        # If failed and not last attempt, try healing
                        if attempt < max_retries - 1:
                            logger.info("executor_healing_attempt",
                                       attempt=attempt + 1,
                                       error=result.get("stderr", "")[:100])
                            
                            # Apply healing delay
                            await asyncio.sleep(retry_delay * (2 ** attempt))
                        
                    except Exception as e:
                        logger.error("executor_healing_error", error=str(e))
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay * (2 ** attempt))
                
                return {
                    "success": False,
                    "attempts": max_retries,
                    "message": f"Healing failed after {max_retries} attempts"
                }
            
            # Execute dengan healing
            healing_result = await healing_wrapper()
            
            return {
                "success": healing_result.get("success", False),
                "mode": mode,
                "attempts": healing_result.get("attempt", healing_result.get("attempts", 1)),
                "message": "Self-healing completed" if healing_result.get("success") else "Self-healing exhausted all retries",
                "details": healing_result
            }
            
        except Exception as e:
            logger.error("executor_healing_failed", error=str(e))
            return {
                "success": False,
                "mode": mode,
                "message": f"Self-healing error: {str(e)}",
                "actions": []
            }
    
    async def _attempt_healing(
        self,
        step: Dict[str, Any],
        error_result: Dict[str, Any],
        step_name: str
    ) -> Dict[str, Any]:
        """Attempt to heal a failed step."""
        if not self.healing_engine:
            return error_result
        
        try:
            logger.info("executor_attempting_heal", step=step_name)
            
            # Use healing engine untuk fix error
            healed_result = await self.healing_engine.execute_with_healing(
                self._execute_shell_step,
                step,
                step.get("timeout", 300)
            )
            
            if healed_result.get("success"):
                logger.info("executor_heal_successful", step=step_name)
                return healed_result
            else:
                logger.warning("executor_heal_failed", step=step_name)
                return error_result
                
        except Exception as e:
            logger.error("executor_heal_error", step=step_name, error=str(e))
            return error_result
    
    async def _save_execution_result(
        self,
        job_id: str,
        job_name: str,
        execution_id: str,
        results: List[Dict],
        status: str,
        namespace: str = "default"
    ):
        """Save execution summary ke LTM."""
        if not LTM_AVAILABLE:
            return
        
        try:
            # Build summary
            success_count = sum(1 for r in results if r.get("success"))
            total_count = len(results)
            
            content = f"""
Job Execution Summary:
- Job: {job_name}
- Status: {status}
- Steps: {success_count}/{total_count} successful
- Completed: {datetime.now(timezone.utc).isoformat()}
""".strip()
            
            await memory_save(
                key=f"execution:{job_id}:{execution_id}",
                content=content,
                metadata={
                    "type": "job_execution",
                    "job_id": job_id,
                    "execution_id": execution_id,
                    "status": status,
                    "success_rate": success_count / total_count if total_count > 0 else 0
                },
                namespace=namespace
            )
            
        except Exception as e:
            logger.warning("executor_save_result_failed", error=str(e))
    
    async def _schedule_next_run(self, job_id: str, job: Dict[str, Any]):
        """Calculate dan update next_run_at untuk job."""
        try:
            schedule_type = job.get("schedule_type", "cron")
            schedule_expr = job.get("schedule_expr", "")
            
            if schedule_type == "cron":
                # Parse cron dan calculate next run
                # TODO: Implement proper cron parsing
                # For now, use simple interval estimation
                next_run = datetime.now(timezone.utc) + self._estimate_cron_interval(schedule_expr)
            elif schedule_type == "interval":
                # Parse interval (e.g., "3600" untuk 1 hour)
                try:
                    seconds = int(schedule_expr)
                    next_run = datetime.now(timezone.utc) + __import__('datetime').timedelta(seconds=seconds)
                except:
                    next_run = None
            elif schedule_type == "once":
                # One-time job, disable after execution
                from scheduler.database import update_job
                await update_job(job_id, {"is_enabled": False})
                return
            else:
                next_run = None
            
            if next_run:
                await update_job_next_run(job_id, next_run)
                
        except Exception as e:
            logger.warning("executor_schedule_next_failed",
         
                         error=str(e))
    
    def _estimate_cron_interval(self, cron_expr: str) -> __import__('datetime').timedelta:
        """
        Calculate next run time dari cron expression.
        
        Supports standard cron format:
        - * * * * * (minute hour day month weekday)
        - */n untuk step values
        - L untuk last day of month
        - W untuk weekday
        """
        try:
            # Try to import croniter, fallback to simplified if not available
            try:
                from croniter import croniter
                CRONITER_AVAILABLE = True
            except ImportError:
                CRONITER_AVAILABLE = False
            
            if CRONITER_AVAILABLE:
                # Use croniter untuk accurate next execution time
                itr = croniter(cron_expr, datetime.now(timezone.utc))
                next_run = itr.get_next(datetime)
                now = datetime.now(timezone.utc)
                
                # Return timedelta to next run
                if next_run > now:
                    return next_run - now
                else:
                    # Fallback jika next_run di masa lalu
                    return __import__('datetime').timedelta(hours=1)
            else:
                # Simplified estimation sebagai fallback
                return self._simplified_cron_estimate(cron_expr)
                
        except Exception as e:
            logger.warning("cron_parse_failed", cron_expr=cron_expr, error=str(e))
            # Default: 1 hour
            return __import__('datetime').timedelta(hours=1)
    
    def _simplified_cron_estimate(self, cron_expr: str) -> __import__('datetime').timedelta:
        """Simplified cron estimation sebagai fallback."""
        parts = cron_expr.split()
        
        if len(parts) >= 2:
            minute = parts[0]
            hour = parts[1]
            
            # */15 * * * * -> 15 minutes
            if minute.startswith("*/"):
                try:
                    mins = int(minute[2:])
                    return __import__('datetime').timedelta(minutes=mins)
                except:
                    pass
            
            # 0 */6 * * * -> 6 hours
            if hour.startswith("*/"):
                try:
                    hrs = int(hour[2:])
                    return __import__('datetime').timedelta(hours=hrs)
                except:
                    pass
            
            # 0 2 * * * -> 24 hours (daily)
            if hour != "*" and minute != "*":
                return __import__('datetime').timedelta(hours=24)
        
        # Default: 1 hour
        return __import__('datetime').timedelta(hours=1)
    
    def get_next_run_time(self, cron_expr: str, base_time: Optional[datetime] = None) -> Optional[datetime]:
        """
        Get exact next run time untuk cron expression.
        
        Args:
            cron_expr: Cron expression
            base_time: Base time untuk calculation (default: now)
        
        Returns:
            Next run time atau None jika parsing fails
        """
        try:
            from croniter import croniter
            
            if base_time is None:
                base_time = datetime.now(timezone.utc)
            
            itr = croniter(cron_expr, base_time)
            return itr.get_next(datetime)
            
        except ImportError:
            logger.warning("croniter_not_available")
            return None
        except Exception as e:
            logger.error("cron_calculation_failed", error=str(e))
            return None
    
    async def process_due_jobs(self) -> List[str]:
        """Process all jobs yang sudah due."""
        due_jobs = await get_due_jobs(datetime.now(timezone.utc))
        execution_ids = []
        
        for job in due_jobs:
            job_id = job["job_id"]
            
            # Execute job asynchronously
            # Note: execute_job will handle execution_id creation (UUID)
            asyncio.create_task(
                self.execute_job(job_id, None, trigger_type="scheduled")
            )
            execution_ids.append(job_id)
        
        return execution_ids


# Global executor instance
executor = JobExecutor()


# Convenience functions
async def execute_job(job_id: str, execution_id: Optional[str] = None) -> Dict[str, Any]:
    """Global execute job function."""
    return await executor.execute_job(job_id, execution_id)


async def process_due_jobs() -> List[str]:
    """Global process due jobs function."""
    return await executor.process_due_jobs()
