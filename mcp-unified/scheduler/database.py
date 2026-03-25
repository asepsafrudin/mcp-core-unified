"""
Database operations untuk MCP Autonomous Task Scheduler.

Tables:
- scheduler_jobs: Job definitions dan schedules
- scheduler_executions: Execution history
- scheduler_notifications: Notification log
"""

import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass

import psycopg
import psycopg_pool
from core.config import settings
from observability.logger import logger

# Database connection pool
_pool: Optional[psycopg_pool.AsyncConnectionPool] = None

# SQL Schema
SCHEDULER_SCHEMA = """
-- Job Definitions (Cold Storage)
CREATE TABLE IF NOT EXISTS scheduler_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT,
    job_type TEXT NOT NULL CHECK (job_type IN (
        'backup_full', 'backup_incremental', 'db_vacuum', 'log_rotate', 
        'disk_cleanup', 'cert_renewal', 'health_check', 'compliance_scan',
        'dependency_check', 'performance_report', 'cost_analysis',
        'git_sync_upstream', 'mirror_repos', 'sync_staging_prod', 'ltm_sync_remote',
        'auto_heal_review', 'smart_cleanup', 'doc_auto_update', 'test_auto_gen',
        'incident_response', 'failover_trigger', 'escalation_notify'
    )),
    category TEXT NOT NULL CHECK (category IN (
        'system_maintenance', 'monitoring', 'sync', 'autonomous', 'alert'
    )),
    priority INTEGER DEFAULT 50 CHECK (priority >= 0 AND priority <= 100),
    
    -- Schedule config
    schedule_type TEXT NOT NULL CHECK (schedule_type IN ('cron', 'interval', 'event', 'once')),
    schedule_expr TEXT NOT NULL,
    timezone TEXT DEFAULT 'Asia/Jakarta',
    
    -- Execution config
    task_config JSONB NOT NULL DEFAULT '{}',
    namespace TEXT DEFAULT 'default',
    
    -- Concurrency limits
    max_concurrent INTEGER DEFAULT 1,
    exclusive_lock BOOLEAN DEFAULT false,
    worker_pool TEXT DEFAULT 'default' CHECK (worker_pool IN ('default', 'cpu', 'io', 'network')),
    
    -- Status
    is_enabled BOOLEAN DEFAULT true,
    next_run_at TIMESTAMP WITH TIME ZONE,
    last_run_at TIMESTAMP WITH TIME ZONE,
    last_run_status TEXT CHECK (last_run_status IN ('success', 'failed', 'timeout')),
    last_run_output JSONB,
    
    -- Retry config
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    retry_delay_seconds INTEGER DEFAULT 300,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT DEFAULT 'system',
    
    UNIQUE(name, namespace)
);

-- Execution History
CREATE TABLE IF NOT EXISTS scheduler_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES scheduler_jobs(id) ON DELETE CASCADE,
    job_name TEXT NOT NULL,
    
    -- Timing
    scheduled_at TIMESTAMP WITH TIME ZONE,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_ms INTEGER,
    
    -- Status & Result
    status TEXT NOT NULL CHECK (status IN ('pending', 'queued', 'running', 'success', 'failed', 'timeout', 'cancelled')),
    exit_code INTEGER,
    output JSONB,
    error_message TEXT,
    
    -- Context
    execution_plan JSONB,
    context_used JSONB,
    ltm_references JSONB,
    worker_node TEXT,
    
    -- Recovery
    recovery_attempts INTEGER DEFAULT 0,
    original_execution_id UUID REFERENCES scheduler_executions(id),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Notifications Log
CREATE TABLE IF NOT EXISTS scheduler_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES scheduler_jobs(id) ON DELETE CASCADE,
    execution_id UUID REFERENCES scheduler_executions(id) ON DELETE CASCADE,
    channel TEXT NOT NULL CHECK (channel IN ('telegram', 'vscode', 'webhook')),
    notification_type TEXT NOT NULL CHECK (notification_type IN ('start', 'success', 'failure', 'recovery')),
    status TEXT NOT NULL CHECK (status IN ('pending', 'sent', 'failed')),
    content JSONB NOT NULL,
    sent_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_scheduler_jobs_next_run 
    ON scheduler_jobs(next_run_at) WHERE is_enabled = true;
CREATE INDEX IF NOT EXISTS idx_scheduler_jobs_type 
    ON scheduler_jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_scheduler_jobs_namespace 
    ON scheduler_jobs(namespace);
CREATE INDEX IF NOT EXISTS idx_executions_job_id 
    ON scheduler_executions(job_id);
CREATE INDEX IF NOT EXISTS idx_executions_status 
    ON scheduler_executions(status);
CREATE INDEX IF NOT EXISTS idx_executions_running 
    ON scheduler_executions(status) WHERE status = 'running';
CREATE INDEX IF NOT EXISTS idx_executions_started 
    ON scheduler_executions(started_at);
"""


async def get_pool() -> psycopg_pool.AsyncConnectionPool:
    """Get or create database connection pool."""
    global _pool
    if _pool is None:
        db_params = {
            'host': settings.POSTGRES_SERVER,
            'port': settings.POSTGRES_PORT,
            'dbname': settings.POSTGRES_DB,
            'user': settings.POSTGRES_USER,
            'password': settings.POSTGRES_PASSWORD,
            'autocommit': True
        }
        _pool = psycopg_pool.AsyncConnectionPool(
            min_size=2, 
            max_size=10, 
            kwargs=db_params, 
            open=False
        )
        await _pool.open()
        logger.info("scheduler_db_pool_created")
    return _pool


async def init_schema():
    """Initialize database schema for scheduler."""
    pool = await get_pool()
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(SCHEDULER_SCHEMA)
        logger.info("scheduler_schema_initialized")
        return {"success": True, "message": "Schema initialized successfully"}
    except Exception as e:
        logger.error("scheduler_schema_init_failed", error=str(e))
        return {"success": False, "error": str(e)}


async def create_job(
    name: str,
    job_type: str,
    category: str,
    schedule_type: str,
    schedule_expr: str,
    task_config: Dict[str, Any],
    description: str = "",
    priority: int = 50,
    namespace: str = "default",
    max_concurrent: int = 1,
    exclusive_lock: bool = False,
    worker_pool: str = "default",
    max_retries: int = 3,
    retry_delay_seconds: int = 300,
    created_by: str = "system"
) -> Dict[str, Any]:
    """Create a new scheduled job."""
    pool = await get_pool()
    
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO scheduler_jobs (
                        name, job_type, category, schedule_type, schedule_expr,
                        task_config, description, priority, namespace,
                        max_concurrent, exclusive_lock, worker_pool,
                        max_retries, retry_delay_seconds, created_by
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    name, job_type, category, schedule_type, schedule_expr,
                    json.dumps(task_config), description, priority, namespace,
                    max_concurrent, exclusive_lock, worker_pool,
                    max_retries, retry_delay_seconds, created_by
                ))
                
                row = await cur.fetchone()
                job_id = str(row[0])
                
                logger.info("scheduler_job_created", 
                          job_id=job_id, name=name, type=job_type, namespace=namespace)
                
                return {
                    "success": True,
                    "job_id": job_id,
                    "name": name,
                    "message": f"Job '{name}' created successfully"
                }
                
    except psycopg.errors.UniqueViolation:
        logger.error("scheduler_job_duplicate", name=name, namespace=namespace)
        return {
            "success": False,
            "error": f"Job '{name}' already exists in namespace '{namespace}'"
        }
    except Exception as e:
        logger.error("scheduler_job_create_failed", error=str(e), name=name)
        return {"success": False, "error": str(e)}


async def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Get job by ID."""
    pool = await get_pool()
    
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT id, name, description, job_type, category, priority,
                           schedule_type, schedule_expr, timezone, task_config,
                           namespace, max_concurrent, exclusive_lock, worker_pool,
                           is_enabled, next_run_at, last_run_at, last_run_status,
                           retry_count, max_retries, created_at
                    FROM scheduler_jobs WHERE id = %s
                """, (job_id,))
                
                row = await cur.fetchone()
                if row:
                    return {
                        "id": str(row[0]),
                        "name": row[1],
                        "description": row[2],
                        "job_type": row[3],
                        "category": row[4],
                        "priority": row[5],
                        "schedule_type": row[6],
                        "schedule_expr": row[7],
                        "timezone": row[8],
                        "task_config": row[9] if isinstance(row[9], dict) else json.loads(row[9] or "{}"),
                        "namespace": row[10],
                        "max_concurrent": row[11],
                        "exclusive_lock": row[12],
                        "worker_pool": row[13],
                        "is_enabled": row[14],
                        "next_run_at": row[15].isoformat() if row[15] else None,
                        "last_run_at": row[16].isoformat() if row[16] else None,
                        "last_run_status": row[17],
                        "retry_count": row[18],
                        "max_retries": row[19],
                        "created_at": row[20].isoformat() if row[20] else None
                    }
                return None
                
    except Exception as e:
        logger.error("scheduler_job_get_failed", error=str(e), job_id=job_id)
        return None


async def get_job_by_name(name: str, namespace: str = "default") -> Optional[Dict[str, Any]]:
    """Get job by name and namespace."""
    pool = await get_pool()
    
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT id FROM scheduler_jobs 
                    WHERE name = %s AND namespace = %s
                """, (name, namespace))
                
                row = await cur.fetchone()
                if row:
                    return await get_job(str(row[0]))
                return None
                
    except Exception as e:
        logger.error("scheduler_job_get_by_name_failed", error=str(e), name=name)
        return None


async def list_jobs(
    namespace: str = "default",
    category: Optional[str] = None,
    is_enabled: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    """List jobs dengan filtering."""
    pool = await get_pool()
    
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                # Build query
                where_clauses = ["namespace = %s"]
                params = [namespace]
                
                if category:
                    where_clauses.append("category = %s")
                    params.append(category)
                if is_enabled is not None:
                    where_clauses.append("is_enabled = %s")
                    params.append(is_enabled)
                
                where_sql = " AND ".join(where_clauses)
                
                # Get total count
                await cur.execute(f"""
                    SELECT COUNT(*) FROM scheduler_jobs WHERE {where_sql}
                """, tuple(params))
                total = (await cur.fetchone())[0]
                
                # Get jobs
                await cur.execute(f"""
                    SELECT id, name, job_type, category, priority, schedule_type,
                           schedule_expr, is_enabled, next_run_at, last_run_at, last_run_status
                    FROM scheduler_jobs 
                    WHERE {where_sql}
                    ORDER BY priority DESC, created_at DESC
                    LIMIT %s OFFSET %s
                """, tuple(params + [limit, offset]))
                
                jobs = []
                for row in await cur.fetchall():
                    jobs.append({
                        "id": str(row[0]),
                        "name": row[1],
                        "job_type": row[2],
                        "category": row[3],
                        "priority": row[4],
                        "schedule_type": row[5],
                        "schedule_expr": row[6],
                        "is_enabled": row[7],
                        "next_run_at": row[8].isoformat() if row[8] else None,
                        "last_run_at": row[9].isoformat() if row[9] else None,
                        "last_run_status": row[10]
                    })
                
                return {
                    "success": True,
                    "jobs": jobs,
                    "total": total,
                    "limit": limit,
                    "offset": offset
                }
                
    except Exception as e:
        logger.error("scheduler_jobs_list_failed", error=str(e))
        return {"success": False, "error": str(e)}


async def update_job(job_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update job configuration."""
    pool = await get_pool()
    
    allowed_fields = [
        "name", "description", "schedule_expr", "task_config", "priority",
        "is_enabled", "max_concurrent", "exclusive_lock", "max_retries",
        "retry_delay_seconds", "next_run_at"
    ]
    
    # Filter allowed fields
    update_fields = {k: v for k, v in updates.items() if k in allowed_fields}
    
    if not update_fields:
        return {"success": False, "error": "No valid fields to update"}
    
    try:
        # Build SET clause
        set_clauses = []
        params = []
        for field, value in update_fields.items():
            if field == "task_config":
                value = json.dumps(value)
            set_clauses.append(f"{field} = %s")
            params.append(value)
        
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        set_sql = ", ".join(set_clauses)
        params.append(job_id)
        
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"""
                    UPDATE scheduler_jobs 
                    SET {set_sql}
                    WHERE id = %s
                    RETURNING name
                """, tuple(params))
                
                row = await cur.fetchone()
                if row:
                    logger.info("scheduler_job_updated", job_id=job_id, fields=list(update_fields.keys()))
                    return {
                        "success": True,
                        "job_id": job_id,
                        "name": row[0],
                        "message": "Job updated successfully"
                    }
                else:
                    return {"success": False, "error": "Job not found"}
                    
    except Exception as e:
        logger.error("scheduler_job_update_failed", error=str(e), job_id=job_id)
        return {"success": False, "error": str(e)}


async def delete_job(job_id: str) -> Dict[str, Any]:
    """Delete job dan execution history."""
    pool = await get_pool()
    
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                # Get job name untuk logging
                await cur.execute("SELECT name FROM scheduler_jobs WHERE id = %s", (job_id,))
                row = await cur.fetchone()
                
                if not row:
                    return {"success": False, "error": "Job not found"}
                
                job_name = row[0]
                
                # Delete job (cascade akan hapus executions dan notifications)
                await cur.execute("DELETE FROM scheduler_jobs WHERE id = %s", (job_id,))
                
                logger.info("scheduler_job_deleted", job_id=job_id, name=job_name)
                return {
                    "success": True,
                    "job_id": job_id,
                    "name": job_name,
                    "message": f"Job '{job_name}' deleted successfully"
                }
                
    except Exception as e:
        logger.error("scheduler_job_delete_failed", error=str(e), job_id=job_id)
        return {"success": False, "error": str(e)}


async def create_execution(
    job_id: str,
    job_name: str,
    scheduled_at: Optional[datetime] = None,
    worker_node: str = "local"
) -> Dict[str, Any]:
    """Create execution record untuk job."""
    pool = await get_pool()
    
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO scheduler_executions (
                        job_id, job_name, scheduled_at, status, worker_node
                    ) VALUES (%s, %s, %s, 'pending', %s)
                    RETURNING id
                """, (job_id, job_name, scheduled_at, worker_node))
                
                row = await cur.fetchone()
                execution_id = str(row[0])
                
                logger.info("scheduler_execution_created", 
                          execution_id=execution_id, job_id=job_id, job_name=job_name)
                
                return {
                    "success": True,
                    "execution_id": execution_id,
                    "status": "pending"
                }
                
    except Exception as e:
        logger.error("scheduler_execution_create_failed", error=str(e), job_id=job_id)
        return {"success": False, "error": str(e)}


async def update_execution(
    execution_id: str,
    status: Optional[str] = None,
    output: Optional[Dict] = None,
    error_message: Optional[str] = None,
    execution_plan: Optional[Dict] = None,
    context_used: Optional[Dict] = None,
    exit_code: Optional[int] = None
) -> Dict[str, Any]:
    """Update execution record."""
    pool = await get_pool()
    
    try:
        update_fields = []
        params = []
        
        if status:
            update_fields.append("status = %s")
            params.append(status)
            
            # Update timestamps based on status
            if status == "running":
                update_fields.append("started_at = CURRENT_TIMESTAMP")
            elif status in ["success", "failed", "timeout", "cancelled"]:
                update_fields.append("completed_at = CURRENT_TIMESTAMP")
                update_fields.append("duration_ms = EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at)) * 1000")
        
        if output is not None:
            update_fields.append("output = %s")
            params.append(json.dumps(output))
        
        if error_message:
            update_fields.append("error_message = %s")
            params.append(error_message)
        
        if execution_plan:
            update_fields.append("execution_plan = %s")
            params.append(json.dumps(execution_plan))
        
        if context_used:
            update_fields.append("context_used = %s")
            params.append(json.dumps(context_used))
        
        if exit_code is not None:
            update_fields.append("exit_code = %s")
            params.append(exit_code)
        
        if not update_fields:
            return {"success": True, "message": "No fields to update"}
        
        params.append(execution_id)
        set_sql = ", ".join(update_fields)
        
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"""
                    UPDATE scheduler_executions 
                    SET {set_sql}
                    WHERE id = %s
                    RETURNING job_id, status
                """, tuple(params))
                
                row = await cur.fetchone()
                if row:
                    # Update job's last_run status
                    if status in ["success", "failed", "timeout"]:
                        await cur.execute("""
                            UPDATE scheduler_jobs 
                            SET last_run_at = CURRENT_TIMESTAMP,
                                last_run_status = %s,
                                last_run_output = %s,
                                retry_count = CASE WHEN %s = 'failed' THEN retry_count + 1 ELSE 0 END
                            WHERE id = %s
                        """, (status, json.dumps(output) if output else None, status, str(row[0])))
                    
                    logger.info("scheduler_execution_updated", 
                              execution_id=execution_id, status=status or row[1])
                    return {"success": True, "execution_id": execution_id}
                else:
                    return {"success": False, "error": "Execution not found"}
                    
    except Exception as e:
        logger.error("scheduler_execution_update_failed", error=str(e), execution_id=execution_id)
        return {"success": False, "error": str(e)}


async def get_running_executions() -> List[Dict[str, Any]]:
    """Get all running executions (untuk recovery)."""
    pool = await get_pool()
    
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT id, job_id, job_name, started_at, worker_node, recovery_attempts
                    FROM scheduler_executions 
                    WHERE status = 'running'
                    ORDER BY started_at ASC
                """)
                
                executions = []
                for row in await cur.fetchall():
                    executions.append({
                        "execution_id": str(row[0]),
                        "job_id": str(row[1]),
                        "job_name": row[2],
                        "started_at": row[3].isoformat() if row[3] else None,
                        "worker_node": row[4],
                        "recovery_attempts": row[5]
                    })
                
                return executions
                
    except Exception as e:
        logger.error("scheduler_get_running_failed", error=str(e))
        return []


async def get_execution_history(
    job_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0
) -> Dict[str, Any]:
    """Get execution history dengan filtering."""
    pool = await get_pool()
    
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                where_clauses = []
                params = []
                
                if job_id:
                    where_clauses.append("job_id = %s")
                    params.append(job_id)
                if status:
                    where_clauses.append("status = %s")
                    params.append(status)
                
                where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
                
                # Get total
                await cur.execute(f"""
                    SELECT COUNT(*) FROM scheduler_executions WHERE {where_sql}
                """, tuple(params))
                total = (await cur.fetchone())[0]
                
                # Get executions
                await cur.execute(f"""
                    SELECT id, job_id, job_name, status, scheduled_at, started_at, 
                           completed_at, duration_ms, exit_code, error_message, created_at
                    FROM scheduler_executions 
                    WHERE {where_sql}
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                """, tuple(params + [limit, offset]))
                
                executions = []
                for row in await cur.fetchall():
                    executions.append({
                        "execution_id": str(row[0]),
                        "job_id": str(row[1]),
                        "job_name": row[2],
                        "status": row[3],
                        "scheduled_at": row[4].isoformat() if row[4] else None,
                        "started_at": row[5].isoformat() if row[5] else None,
                        "completed_at": row[6].isoformat() if row[6] else None,
                        "duration_ms": row[7],
                        "exit_code": row[8],
                        "error_message": row[9],
                        "created_at": row[10].isoformat() if row[10] else None
                    })
                
                return {
                    "success": True,
                    "executions": executions,
                    "total": total,
                    "limit": limit,
                    "offset": offset
                }
                
    except Exception as e:
        logger.error("scheduler_execution_history_failed", error=str(e))
        return {"success": False, "error": str(e)}


async def log_notification(
    job_id: str,
    execution_id: str,
    channel: str,
    notification_type: str,
    content: Dict[str, Any]
) -> Dict[str, Any]:
    """Log notification attempt."""
    pool = await get_pool()
    
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO scheduler_notifications (
                        job_id, execution_id, channel, notification_type, 
                        status, content
                    ) VALUES (%s, %s, %s, %s, 'pending', %s)
                    RETURNING id
                """, (job_id, execution_id, channel, notification_type, json.dumps(content)))
                
                row = await cur.fetchone()
                notification_id = str(row[0])
                
                return {
                    "success": True,
                    "notification_id": notification_id
                }
                
    except Exception as e:
        logger.error("scheduler_notification_log_failed", error=str(e))
        return {"success": False, "error": str(e)}


async def update_notification_status(
    notification_id: str,
    status: str,
    error_message: str = None
) -> Dict[str, Any]:
    """Update notification status."""
    pool = await get_pool()
    
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    UPDATE scheduler_notifications 
                    SET status = %s, 
                        sent_at = CASE WHEN %s = 'sent' THEN CURRENT_TIMESTAMP ELSE sent_at END,
                        error_message = %s
                    WHERE id = %s
                """, (status, status, error_message, notification_id))
                
                return {"success": True}
                
    except Exception as e:
        logger.error("scheduler_notification_update_failed", error=str(e))
        return {"success": False, "error": str(e)}


async def get_due_jobs(now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Get jobs yang sudah due untuk execution."""
    pool = await get_pool()
    now = now or datetime.now(timezone.utc)
    
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT id, name, job_type, priority, namespace,
                           max_concurrent, exclusive_lock, worker_pool
                    FROM scheduler_jobs 
                    WHERE is_enabled = true 
                      AND next_run_at <= %s
                    ORDER BY priority DESC, next_run_at ASC
                """, (now,))
                
                jobs = []
                for row in await cur.fetchall():
                    jobs.append({
                        "job_id": str(row[0]),
                        "name": row[1],
                        "job_type": row[2],
                        "priority": row[3],
                        "namespace": row[4],
                        "max_concurrent": row[5],
                        "exclusive_lock": row[6],
                        "worker_pool": row[7]
                    })
                
                return jobs
                
    except Exception as e:
        logger.error("scheduler_get_due_jobs_failed", error=str(e))
        return []


async def update_job_next_run(job_id: str, next_run_at: Optional[datetime] = None):
    """Update next_run_at untuk job."""
    pool = await get_pool()
    
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    UPDATE scheduler_jobs 
                    SET next_run_at = %s
                    WHERE id = %s
                """, (next_run_at, job_id))
                
    except Exception as e:
        logger.error("scheduler_update_next_run_failed", error=str(e), job_id=job_id)
