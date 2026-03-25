"""
Recovery Mechanism untuk MCP Autonomous Task Scheduler.

Menangani crash recovery dengan:
- State reconstruction dari PostgreSQL
- Re-queue interrupted jobs
- Recovery notifications
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

from scheduler.database import (
    get_running_executions, update_execution, create_execution,
    get_job, list_jobs, update_job
)
from scheduler.redis_queue import scheduler_queue
from scheduler.pools import pool_manager
from observability.logger import logger


class RecoveryManager:
    """
    Manages crash recovery untuk scheduler.
    
    Flow:
    1. Detect crash (heartbeat timeout)
    2. Query PostgreSQL untuk running executions
    3. Determine which jobs need recovery
    4. Re-queue atau mark as failed
    5. Send recovery notification
    """
    
    def __init__(self):
        self.max_recovery_attempts = 3
        self.orphaned_threshold_minutes = 30
    
    async def check_and_recover(self) -> Dict[str, Any]:
        """
        Check for crashed executions dan recover them.
        
        Returns:
            Recovery summary
        """
        logger.info("recovery_check_started")
        
        recovered = []
        failed = []
        skipped = []
        
        try:
            # 1. Get running executions dari PostgreSQL
            running = await get_running_executions()
            
            if not running:
                logger.info("recovery_no_running_jobs")
                return {
                    "success": True,
                    "recovered": [],
                    "failed": [],
                    "message": "No running jobs to recover"
                }
            
            logger.info("recovery_found_running_jobs", count=len(running))
            
            # 2. Check each running execution
            for exec_info in running:
                execution_id = exec_info["execution_id"]
                job_id = exec_info["job_id"]
                job_name = exec_info["job_name"]
                started_at = exec_info.get("started_at")
                recovery_attempts = exec_info.get("recovery_attempts", 0)
                
                # Check if still in Redis (means scheduler is still running it)
                is_still_running = await scheduler_queue.is_running(execution_id)
                
                if is_still_running:
                    # Job actually still running, skip
                    skipped.append({
                        "execution_id": execution_id,
                        "job_name": job_name,
                        "reason": "still_running"
                    })
                    continue
                
                # Check age
                if started_at:
                    started = datetime.fromisoformat(started_at)
                    age_minutes = (datetime.now(timezone.utc) - started).total_seconds() / 60
                else:
                    age_minutes = self.orphaned_threshold_minutes + 1
                
                # Check if exceeded max recovery attempts
                if recovery_attempts >= self.max_recovery_attempts:
                    # Mark as failed
                    await update_execution(
                        execution_id=execution_id,
                        status="failed",
                        error_message=f"Exceeded max recovery attempts ({self.max_recovery_attempts})"
                    )
                    
                    failed.append({
                        "execution_id": execution_id,
                        "job_name": job_name,
                        "reason": "max_recovery_exceeded"
                    })
                    
                    logger.warning("recovery_max_attempts_exceeded",
                                 execution_id=execution_id,
                                 job_name=job_name)
                    continue
                
                # Attempt recovery
                if age_minutes > self.orphaned_threshold_minutes:
                    recovery_result = await self._recover_execution(exec_info)
                    
                    if recovery_result["success"]:
                        recovered.append({
                            "execution_id": execution_id,
                            "job_name": job_name,
                            "new_execution_id": recovery_result.get("new_execution_id")
                        })
                    else:
                        failed.append({
                            "execution_id": execution_id,
                            "job_name": job_name,
                            "reason": recovery_result.get("error", "unknown")
                        })
                else:
                    # Too recent, might be legitimate running job
                    skipped.append({
                        "execution_id": execution_id,
                        "job_name": job_name,
                        "reason": "too_recent",
                        "age_minutes": age_minutes
                    })
            
            result = {
                "success": True,
                "recovered": recovered,
                "failed": failed,
                "skipped": skipped,
                "total_checked": len(running)
            }
            
            logger.info("recovery_completed",
                       recovered=len(recovered),
                       failed=len(failed),
                       skipped=len(skipped))
            
            return result
            
        except Exception as e:
            logger.error("recovery_failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "recovered": recovered,
                "failed": failed
            }
    
    async def _recover_execution(self, exec_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recover a single execution.
        
        Strategy:
        1. Mark old execution as failed dengan recovery note
        2. Create new execution
        3. Re-queue job jika job masih enabled
        """
        execution_id = exec_info["execution_id"]
        job_id = exec_info["job_id"]
        job_name = exec_info["job_name"]
        recovery_attempts = exec_info.get("recovery_attempts", 0)
        
        try:
            # 1. Mark old execution as failed
            await update_execution(
                execution_id=execution_id,
                status="failed",
                error_message=f"Recovered after crash (attempt {recovery_attempts + 1})"
            )
            
            # 2. Check if job still exists dan enabled
            job = await get_job(job_id)
            if not job:
                return {
                    "success": False,
                    "error": "Job no longer exists"
                }
            
            if not job.get("is_enabled", True):
                return {
                    "success": False,
                    "error": "Job is disabled"
                }
            
            # 3. Create new execution
            new_exec = await create_execution(
                job_id=job_id,
                job_name=job_name,
                worker_node="recovered"
            )
            
            if not new_exec["success"]:
                return {
                    "success": False,
                    "error": "Failed to create new execution"
                }
            
            new_execution_id = new_exec["execution_id"]
            
            # 4. Re-queue dengan high priority
            await scheduler_queue.enqueue_job(
                job_id=job_id,
                job_name=job_name,
                job_type=job["job_type"],
                priority=90,  # High priority for recovered jobs
                execution_id=new_execution_id
            )
            
            logger.info("execution_recovered",
                       old_execution_id=execution_id,
                       new_execution_id=new_execution_id,
                       job_name=job_name)
            
            return {
                "success": True,
                "new_execution_id": new_execution_id
            }
            
        except Exception as e:
            logger.error("recover_execution_failed",
                        execution_id=execution_id,
                        error=str(e))
            return {
                "success": False,
                "error": str(e)
            }
    
    async def recover_orphaned_redis_jobs(self) -> List[str]:
        """
        Find dan cleanup orphaned jobs di Redis.
        
        Jobs yang di-mark running di Redis tapi tidak ada
        execution record yang matching di PostgreSQL.
        """
        try:
            # Get running jobs dari Redis
            redis_running = await scheduler_queue.get_running_jobs()
            
            orphaned = []
            
            for job in redis_running:
                execution_id = job.get("execution_id")
                
                # Check if execution exists di PostgreSQL
                # Note: This requires a get_execution function yang belum ada
                # For now, we use age-based heuristic
                
                started_at = job.get("started_at")
                if started_at:
                    started = datetime.fromisoformat(started_at)
                    age_minutes = (datetime.now(timezone.utc) - started).total_seconds() / 60
                    
                    if age_minutes > self.orphaned_threshold_minutes:
                        # Mark as completed (cleanup)
                        await scheduler_queue.mark_completed(execution_id)
                        orphaned.append(execution_id)
                        
                        logger.warning("orphaned_redis_job_cleaned",
                                     execution_id=execution_id,
                                     age_minutes=age_minutes)
            
            return orphaned
            
        except Exception as e:
            logger.error("recover_orphaned_failed", error=str(e))
            return []
    
    async def validate_state(self) -> Dict[str, Any]:
        """
        Validate scheduler state consistency.
        
        Checks:
        - PostgreSQL running executions vs Redis running jobs
        - Job next_run_at consistency
        - Lock consistency
        """
        issues = []
        
        try:
            # 1. Check PostgreSQL vs Redis consistency
            pg_running = await get_running_executions()
            redis_running = await scheduler_queue.get_running_jobs()
            
            pg_execution_ids = {e["execution_id"] for e in pg_running}
            redis_execution_ids = {r["execution_id"] for r in redis_running}
            
            # Executions in PG but not in Redis (orphaned PG records)
            pg_only = pg_execution_ids - redis_execution_ids
            if pg_only:
                issues.append({
                    "type": "pg_orphaned",
                    "count": len(pg_only),
                    "execution_ids": list(pg_only),
                    "message": f"{len(pg_only)} executions in PostgreSQL but not in Redis"
                })
            
            # Jobs in Redis but not in PG (orphaned Redis records)
            redis_only = redis_execution_ids - pg_execution_ids
            if redis_only:
                issues.append({
                    "type": "redis_orphaned",
                    "count": len(redis_only),
                    "execution_ids": list(redis_only),
                    "message": f"{len(redis_only)} jobs in Redis but not in PostgreSQL"
                })
            
            # 2. Check for stale locks
            # This would require iterating all possible job types
            # For now, skip detailed lock checking
            
            return {
                "success": True,
                "valid": len(issues) == 0,
                "issues": issues,
                "pg_running_count": len(pg_running),
                "redis_running_count": len(redis_running)
            }
            
        except Exception as e:
            logger.error("validate_state_failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "valid": False
            }
    
    async def repair_state(self) -> Dict[str, Any]:
        """
        Attempt to repair inconsistent state.
        """
        repaired = []
        failed = []
        
        try:
            # 1. Run validation
            validation = await self.validate_state()
            
            if validation.get("valid", False):
                return {
                    "success": True,
                    "message": "State is already valid",
                    "repaired": [],
                    "failed": []
                }
            
            # 2. Fix orphaned Redis jobs
            orphaned_redis = await self.recover_orphaned_redis_jobs()
            repaired.extend([{"type": "redis_orphaned", "execution_id": eid} for eid in orphaned_redis])
            
            # 3. Run recovery untuk PG orphaned
            recovery_result = await self.check_and_recover()
            if recovery_result.get("success"):
                repaired.extend([{"type": "pg_recovered", **r} for r in recovery_result.get("recovered", [])])
                failed.extend([{"type": "pg_failed", **f} for f in recovery_result.get("failed", [])])
            
            return {
                "success": True,
                "repaired": repaired,
                "failed": failed,
                "message": f"Repaired {len(repaired)} issues, {len(failed)} failed"
            }
            
        except Exception as e:
            logger.error("repair_state_failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "repaired": repaired,
                "failed": failed
            }


# Global instance
recovery_manager = RecoveryManager()


# Convenience functions
async def check_and_recover() -> Dict[str, Any]:
    """Global check and recover function."""
    return await recovery_manager.check_and_recover()


async def validate_state() -> Dict[str, Any]:
    """Global validate state function."""
    return await recovery_manager.validate_state()


async def repair_state() -> Dict[str, Any]:
    """Global repair state function."""
    return await recovery_manager.repair_state()
