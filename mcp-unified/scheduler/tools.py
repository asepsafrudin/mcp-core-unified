"""
MCP Tools untuk Autonomous Task Scheduler.

Tools ini di-register ke MCP server untuk memungkinkan
agen membuat dan mengelola scheduled jobs.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone

from scheduler.database import (
    create_job, get_job, get_job_by_name, list_jobs, update_job, delete_job,
    create_execution, update_execution, get_execution_history, get_due_jobs,
    init_schema
)
from scheduler.templates import (
    get_template, list_templates, create_job_from_template, get_categories
)
from scheduler.redis_queue import scheduler_queue, get_stats as get_queue_stats
from scheduler.pools import get_pool_stats
from observability.logger import logger


# ═══════════════════════════════════════════════════════════════════════════════
# Job Management Tools
# ═══════════════════════════════════════════════════════════════════════════════

async def scheduler_create_job(
    name: str,
    template: str,
    schedule: str,
    namespace: str = "default",
    custom_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a new scheduled job dari template.
    
    Args:
        name: Unique job name
        template: Template name (e.g., 'health_check', 'backup_full')
        schedule: Cron expression (e.g., '*/15 * * * *' for every 15 min)
        namespace: Job namespace untuk isolation
        custom_config: Optional custom task configuration
    
    Returns:
        Dict dengan job_id dan status
    
    Example:
        scheduler_create_job(
            name="daily_backup",
            template="backup_full",
            schedule="0 2 * * *",
            namespace="production"
        )
    """
    try:
        # Validate template exists
        tmpl = get_template(template)
        if not tmpl:
            return {
                "success": False,
                "error": f"Template '{template}' not found. Available: {list(list_templates().keys())}"
            }
        
        # Create job from template
        result = create_job_from_template(
            template_name=template,
            job_name=name,
            namespace=namespace,
            custom_schedule=schedule,
            custom_config=custom_config
        )
        
        if not result["success"]:
            return result
        
        config = result["config"]
        
        # Create in database
        db_result = await create_job(
            name=config["name"],
            job_type=config["job_type"],
            category=config["category"],
            schedule_type=config["schedule_type"],
            schedule_expr=config["schedule_expr"],
            task_config=config["task_config"],
            description=config.get("description", ""),
            priority=config["priority"],
            namespace=namespace,
            max_concurrent=config["max_concurrent"],
            exclusive_lock=config["exclusive_lock"],
            worker_pool=config["worker_pool"],
            max_retries=config["max_retries"],
            retry_delay_seconds=config["retry_delay_seconds"]
        )
        
        if db_result["success"]:
            logger.info("scheduler_tool_job_created",
                       job_id=db_result["job_id"],
                       name=name, template=template)
        
        return db_result
        
    except Exception as e:
        logger.error("scheduler_tool_create_failed", error=str(e))
        return {"success": False, "error": str(e)}


async def scheduler_list_jobs(
    namespace: str = "default",
    category: Optional[str] = None,
    is_enabled: Optional[bool] = None
) -> Dict[str, Any]:
    """
    List scheduled jobs dengan filtering.
    
    Args:
        namespace: Filter by namespace
        category: Filter by category (system_maintenance, monitoring, etc)
        is_enabled: Filter by enabled status
    
    Returns:
        List of jobs dengan metadata
    
    Example:
        scheduler_list_jobs(namespace="production", category="monitoring")
    """
    try:
        result = await list_jobs(
            namespace=namespace,
            category=category,
            is_enabled=is_enabled,
            limit=50
        )
        
        if result["success"]:
            # Add human-readable status
            for job in result["jobs"]:
                job["status_emoji"] = "🟢" if job["is_enabled"] else "🔴"
                if job["last_run_status"]:
                    job["status_emoji"] = {
                        "success": "✅",
                        "failed": "❌",
                        "timeout": "⏱️"
                    }.get(job["last_run_status"], "🟡")
        
        return result
        
    except Exception as e:
        logger.error("scheduler_tool_list_failed", error=str(e))
        return {"success": False, "error": str(e)}


async def scheduler_get_job(
    job_id: Optional[str] = None,
    name: Optional[str] = None,
    namespace: str = "default"
) -> Dict[str, Any]:
    """
    Get detailed job information.
    
    Args:
        job_id: Job UUID (optional jika name provided)
        name: Job name (optional jika job_id provided)
        namespace: Job namespace
    
    Returns:
        Job details dengan execution history
    
    Example:
        scheduler_get_job(name="daily_backup", namespace="production")
    """
    try:
        # Get job by ID or name
        if job_id:
            job = await get_job(job_id)
        elif name:
            job = await get_job_by_name(name, namespace)
        else:
            return {"success": False, "error": "Either job_id atau name must be provided"}
        
        if not job:
            return {"success": False, "error": "Job not found"}
        
        # Get execution history
        history = await get_execution_history(job_id=job["id"], limit=10)
        
        result = {
            "success": True,
            "job": job,
            "execution_history": history.get("executions", []) if history["success"] else [],
            "total_executions": history.get("total", 0) if history["success"] else 0
        }
        
        return result
        
    except Exception as e:
        logger.error("scheduler_tool_get_failed", error=str(e))
        return {"success": False, "error": str(e)}


async def scheduler_update_job(
    job_id: str,
    is_enabled: Optional[bool] = None,
    schedule: Optional[str] = None,
    priority: Optional[int] = None
) -> Dict[str, Any]:
    """
    Update job configuration.
    
    Args:
        job_id: Job UUID
        is_enabled: Enable/disable job
        schedule: New cron expression
        priority: New priority (0-100)
    
    Returns:
        Update status
    
    Example:
        scheduler_update_job(
            job_id="...",
            is_enabled=False,
            schedule="0 */6 * * *"
        )
    """
    try:
        updates = {}
        
        if is_enabled is not None:
            updates["is_enabled"] = is_enabled
        if schedule:
            updates["schedule_expr"] = schedule
        if priority is not None:
            updates["priority"] = priority
        
        if not updates:
            return {"success": False, "error": "No updates provided"}
        
        result = await update_job(job_id, updates)
        return result
        
    except Exception as e:
        logger.error("scheduler_tool_update_failed", error=str(e))
        return {"success": False, "error": str(e)}


async def scheduler_delete_job(
    job_id: Optional[str] = None,
    name: Optional[str] = None,
    namespace: str = "default"
) -> Dict[str, Any]:
    """
    Delete scheduled job.
    
    Args:
        job_id: Job UUID
        name: Job name (alternative to job_id)
        namespace: Job namespace
    
    Returns:
        Deletion status
    
    Example:
        scheduler_delete_job(name="old_job", namespace="test")
    """
    try:
        # Resolve job_id dari name jika perlu
        if not job_id and name:
            job = await get_job_by_name(name, namespace)
            if not job:
                return {"success": False, "error": f"Job '{name}' not found in namespace '{namespace}'"}
            job_id = job["id"]
        
        if not job_id:
            return {"success": False, "error": "Either job_id atau name must be provided"}
        
        result = await delete_job(job_id)
        return result
        
    except Exception as e:
        logger.error("scheduler_tool_delete_failed", error=str(e))
        return {"success": False, "error": str(e)}


async def scheduler_run_job_now(
    job_id: Optional[str] = None,
    name: Optional[str] = None,
    namespace: str = "default"
) -> Dict[str, Any]:
    """
    Manually trigger job execution.
    
    Args:
        job_id: Job UUID
        name: Job name
        namespace: Job namespace
    
    Returns:
        Execution status
    
    Example:
        scheduler_run_job_now(name="daily_backup")
    """
    try:
        # Resolve job
        if not job_id and name:
            job = await get_job_by_name(name, namespace)
            if not job:
                return {"success": False, "error": f"Job '{name}' not found"}
            job_id = job["id"]
            job_data = job
        elif job_id:
            job_data = await get_job(job_id)
            if not job_data:
                return {"success": False, "error": f"Job '{job_id}' not found"}
        else:
            return {"success": False, "error": "Either job_id atau name must be provided"}
        
        # Create execution
        exec_result = await create_execution(
            job_id=job_id,
            job_name=job_data["name"],
            worker_node="manual"
        )
        
        if exec_result["success"]:
            # Enqueue untuk immediate execution
            await scheduler_queue.enqueue_job(
                job_id=job_id,
                job_name=job_data["name"],
                job_type=job_data["job_type"],
                priority=100,  # High priority untuk manual trigger
                execution_id=exec_result["execution_id"]
            )
            
            logger.info("scheduler_tool_job_triggered",
                       job_id=job_id,
                       execution_id=exec_result["execution_id"])
        
        return {
            "success": True,
            "message": f"Job '{job_data['name']}' triggered for execution",
            "execution_id": exec_result.get("execution_id"),
            "job_id": job_id
        }
        
    except Exception as e:
        logger.error("scheduler_tool_run_failed", error=str(e))
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# Template Tools
# ═══════════════════════════════════════════════════════════════════════════════

async def scheduler_list_templates(category: Optional[str] = None) -> Dict[str, Any]:
    """
    List available job templates.
    
    Args:
        category: Filter by category
    
    Returns:
        List of templates dengan descriptions
    
    Example:
        scheduler_list_templates(category="monitoring")
    """
    try:
        templates = list_templates(category)
        categories = get_categories()
        
        result = {
            "success": True,
            "categories": categories,
            "templates": {}
        }
        
        for name, tmpl in templates.items():
            result["templates"][name] = {
                "description": tmpl.description,
                "category": tmpl.category,
                "priority": tmpl.priority,
                "schedule_type": tmpl.schedule_type,
                "default_schedule": tmpl.schedule_expr,
                "worker_pool": tmpl.worker_pool
            }
        
        return result
        
    except Exception as e:
        logger.error("scheduler_tool_templates_failed", error=str(e))
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# Status & Monitoring Tools
# ═══════════════════════════════════════════════════════════════════════════════

async def scheduler_get_status() -> Dict[str, Any]:
    """
    Get scheduler status dan statistics.
    
    Returns:
        Scheduler health, queue stats, pool stats
    
    Example:
        scheduler_get_status()
    """
    try:
        # Connect to queue jika belum
        if not scheduler_queue._redis:
            await scheduler_queue.connect()
        
        # Get various stats
        queue_stats = await get_queue_stats()
        pool_stats = get_pool_stats()
        
        # Get due jobs
        due = await get_due_jobs(datetime.now(timezone.utc))
        
        result = {
            "success": True,
            "status": "healthy" if queue_stats.get("heartbeat") else "unknown",
            "queue": queue_stats,
            "pools": pool_stats,
            "due_jobs_count": len(due),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return result
        
    except Exception as e:
        logger.error("scheduler_tool_status_failed", error=str(e))
        return {"success": False, "error": str(e)}


async def scheduler_get_execution_history(
    job_id: Optional[str] = None,
    name: Optional[str] = None,
    namespace: str = "default",
    limit: int = 20
) -> Dict[str, Any]:
    """
    Get execution history untuk job.
    
    Args:
        job_id: Job UUID
        name: Job name
        namespace: Job namespace
        limit: Max entries to return
    
    Returns:
        Execution history dengan details
    """
    try:
        # Resolve job_id
        if not job_id and name:
            job = await get_job_by_name(name, namespace)
            if job:
                job_id = job["id"]
        
        result = await get_execution_history(job_id=job_id, limit=limit)
        return result
        
    except Exception as e:
        logger.error("scheduler_tool_history_failed", error=str(e))
        return {"success": False, "error": str(e)}


async def scheduler_init() -> Dict[str, Any]:
    """
    Initialize scheduler database schema.
    
    Should be called once saat setup.
    
    Returns:
        Initialization status
    """
    try:
        result = await init_schema()
        return result
    except Exception as e:
        logger.error("scheduler_tool_init_failed", error=str(e))
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# Tool Registry Helper
# ═══════════════════════════════════════════════════════════════════════════════

def get_scheduler_tools() -> list:
    """
    Get list of all scheduler tools untuk registration.
    
    Usage di mcp_server.py:
        from scheduler.tools import get_scheduler_tools
        for tool in get_scheduler_tools():
            tool_registry.register(tool)
    """
    return [
        scheduler_create_job,
        scheduler_list_jobs,
        scheduler_get_job,
        scheduler_update_job,
        scheduler_delete_job,
        scheduler_run_job_now,
        scheduler_list_templates,
        scheduler_get_status,
        scheduler_get_execution_history,
        scheduler_init
    ]


# Tool descriptions untuk MCP
tool_descriptions = {
    "scheduler_create_job": {
        "description": "Create scheduled job dari template",
        "parameters": ["name", "template", "schedule", "namespace", "custom_config"]
    },
    "scheduler_list_jobs": {
        "description": "List scheduled jobs dengan filtering",
        "parameters": ["namespace", "category", "is_enabled"]
    },
    "scheduler_get_job": {
        "description": "Get detailed job information",
        "parameters": ["job_id", "name", "namespace"]
    },
    "scheduler_update_job": {
        "description": "Update job configuration",
        "parameters": ["job_id", "is_enabled", "schedule", "priority"]
    },
    "scheduler_delete_job": {
        "description": "Delete scheduled job",
        "parameters": ["job_id", "name", "namespace"]
    },
    "scheduler_run_job_now": {
        "description": "Manually trigger job execution",
        "parameters": ["job_id", "name", "namespace"]
    },
    "scheduler_list_templates": {
        "description": "List available job templates",
        "parameters": ["category"]
    },
    "scheduler_get_status": {
        "description": "Get scheduler status dan statistics",
        "parameters": []
    },
    "scheduler_get_execution_history": {
        "description": "Get execution history untuk job",
        "parameters": ["job_id", "name", "namespace", "limit"]
    },
    "scheduler_init": {
        "description": "Initialize scheduler database schema",
        "parameters": []
    }
}
