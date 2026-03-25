"""
MCP Scheduler REST API

Provides HTTP endpoints untuk job management:
- GET  /api/v1/jobs              - List all jobs
- GET  /api/v1/jobs/{id}         - Get job details
- POST /api/v1/jobs              - Create new job
- PUT  /api/v1/jobs/{id}         - Update job
- DELETE /api/v1/jobs/{id}       - Delete job
- POST /api/v1/jobs/{id}/run     - Run job now
- GET  /api/v1/executions        - List executions
- GET  /api/v1/executions/{id}   - Get execution details
- GET  /api/v1/status            - Scheduler status
- GET  /api/v1/templates         - List job templates
- GET  /api/v1/metrics           - Prometheus metrics

Usage:
    python api.py              # Start API server (port 8080)
    python api.py --port 8081  # Start dengan custom port
"""

import os
import sys
import json
import argparse
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from aiohttp import web
from aiohttp.web import Request, Response

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from observability.logger import logger
from core.config import settings

# Scheduler components
from scheduler.database import (
    list_jobs, get_job, create_job, update_job, delete_job,
    get_execution_history, get_running_executions
)
from scheduler.templates import get_available_templates, get_template
from scheduler.executor import execute_job
from scheduler.redis_queue import scheduler_queue, get_stats as get_queue_stats
from scheduler.pools import pool_manager


# ═══════════════════════════════════════════════════════════════════════
# Routes
# ═══════════════════════════════════════════════════════════════════════

async def health_check(request: Request) -> Response:
    """Health check endpoint."""
    try:
        # Check Redis connection
        await scheduler_queue.update_heartbeat(node_id="api-server")
        heartbeat = await scheduler_queue.get_heartbeat()
        
        return web.json_response({
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scheduler_heartbeat": heartbeat,
            "version": "1.0.0"
        })
    except Exception as e:
        return web.json_response({
            "status": "unhealthy",
            "error": str(e)
        }, status=503)


async def get_jobs(request: Request) -> Response:
    """GET /api/v1/jobs - List all jobs."""
    try:
        namespace = request.query.get("namespace", "default")
        category = request.query.get("category")
        is_enabled = request.query.get("enabled")
        
        if is_enabled is not None:
            is_enabled = is_enabled.lower() == "true"
        
        limit = int(request.query.get("limit", 50))
        offset = int(request.query.get("offset", 0))
        
        result = await list_jobs(
            namespace=namespace,
            category=category,
            is_enabled=is_enabled,
            limit=limit,
            offset=offset
        )
        
        return web.json_response(result)
        
    except Exception as e:
        logger.error("api_get_jobs_failed", error=str(e))
        return web.json_response(
            {"success": False, "error": str(e)},
            status=500
        )


async def get_job_detail(request: Request) -> Response:
    """GET /api/v1/jobs/{id} - Get job details."""
    try:
        job_id = request.match_info["id"]
        job = await get_job(job_id)
        
        if not job:
            return web.json_response(
                {"success": False, "error": "Job not found"},
                status=404
            )
        
        return web.json_response({"success": True, "job": job})
        
    except Exception as e:
        logger.error("api_get_job_failed", error=str(e))
        return web.json_response(
            {"success": False, "error": str(e)},
            status=500
        )


async def create_new_job(request: Request) -> Response:
    """POST /api/v1/jobs - Create new job."""
    try:
        data = await request.json()
        
        required = ["name", "job_type", "category", "schedule_type", "schedule_expr"]
        missing = [f for f in required if f not in data]
        if missing:
            return web.json_response(
                {"success": False, "error": f"Missing fields: {missing}"},
                status=400
            )
        
        result = await create_job(
            name=data["name"],
            job_type=data["job_type"],
            category=data["category"],
            schedule_type=data["schedule_type"],
            schedule_expr=data["schedule_expr"],
            task_config=data.get("task_config", {}),
            description=data.get("description", ""),
            priority=data.get("priority", 50),
            namespace=data.get("namespace", "default"),
            max_concurrent=data.get("max_concurrent", 1),
            exclusive_lock=data.get("exclusive_lock", False),
            worker_pool=data.get("worker_pool", "default"),
            max_retries=data.get("max_retries", 3),
            retry_delay_seconds=data.get("retry_delay_seconds", 300),
            created_by=data.get("created_by", "api")
        )
        
        status = 201 if result.get("success") else 400
        return web.json_response(result, status=status)
        
    except json.JSONDecodeError:
        return web.json_response(
            {"success": False, "error": "Invalid JSON"},
            status=400
        )
    except Exception as e:
        logger.error("api_create_job_failed", error=str(e))
        return web.json_response(
            {"success": False, "error": str(e)},
            status=500
        )


async def update_existing_job(request: Request) -> Response:
    """PUT /api/v1/jobs/{id} - Update job."""
    try:
        job_id = request.match_info["id"]
        data = await request.json()
        
        result = await update_job(job_id, data)
        
        status = 200 if result.get("success") else 400
        return web.json_response(result, status=status)
        
    except json.JSONDecodeError:
        return web.json_response(
            {"success": False, "error": "Invalid JSON"},
            status=400
        )
    except Exception as e:
        logger.error("api_update_job_failed", error=str(e))
        return web.json_response(
            {"success": False, "error": str(e)},
            status=500
        )


async def delete_existing_job(request: Request) -> Response:
    """DELETE /api/v1/jobs/{id} - Delete job."""
    try:
        job_id = request.match_info["id"]
        result = await delete_job(job_id)
        
        status = 200 if result.get("success") else 404
        return web.json_response(result, status=status)
        
    except Exception as e:
        logger.error("api_delete_job_failed", error=str(e))
        return web.json_response(
            {"success": False, "error": str(e)},
            status=500
        )


async def run_job_now(request: Request) -> Response:
    """POST /api/v1/jobs/{id}/run - Run job immediately."""
    try:
        job_id = request.match_info["id"]
        
        # Get job first
        job = await get_job(job_id)
        if not job:
            return web.json_response(
                {"success": False, "error": "Job not found"},
                status=404
            )
        
        # Execute job (async - returns immediately)
        asyncio.create_task(execute_job(job_id, trigger_type="manual"))
        
        return web.json_response({
            "success": True,
            "message": f"Job '{job['name']}' triggered for execution",
            "job_id": job_id
        })
        
    except Exception as e:
        logger.error("api_run_job_failed", error=str(e))
        return web.json_response(
            {"success": False, "error": str(e)},
            status=500
        )


async def get_executions(request: Request) -> Response:
    """GET /api/v1/executions - List executions."""
    try:
        job_id = request.query.get("job_id")
        status = request.query.get("status")
        limit = int(request.query.get("limit", 20))
        offset = int(request.query.get("offset", 0))
        
        result = await get_execution_history(
            job_id=job_id,
            status=status,
            limit=limit,
            offset=offset
        )
        
        return web.json_response(result)
        
    except Exception as e:
        logger.error("api_get_executions_failed", error=str(e))
        return web.json_response(
            {"success": False, "error": str(e)},
            status=500
        )


async def get_scheduler_status(request: Request) -> Response:
    """GET /api/v1/status - Get scheduler status."""
    try:
        # Get queue stats
        queue_stats = await get_queue_stats()
        
        # Get pool stats
        pool_stats = pool_manager.get_stats()
        
        # Get running executions dari DB
        running = await get_running_executions()
        
        # Get heartbeat
        heartbeat = await scheduler_queue.get_heartbeat()
        is_alive = await scheduler_queue.is_scheduler_alive()
        
        return web.json_response({
            "success": True,
            "status": {
                "healthy": is_alive,
                "heartbeat": heartbeat,
                "queue": queue_stats,
                "pools": pool_stats,
                "running_executions": len(running),
                "running_details": running[:5]  # Show first 5
            }
        })
        
    except Exception as e:
        logger.error("api_get_status_failed", error=str(e))
        return web.json_response(
            {"success": False, "error": str(e)},
            status=500
        )


async def get_job_templates(request: Request) -> Response:
    """GET /api/v1/templates - List job templates."""
    try:
        templates = get_available_templates()
        return web.json_response({
            "success": True,
            "templates": templates
        })
        
    except Exception as e:
        logger.error("api_get_templates_failed", error=str(e))
        return web.json_response(
            {"success": False, "error": str(e)},
            status=500
        )


async def get_template_detail(request: Request) -> Response:
    """GET /api/v1/templates/{name} - Get template details."""
    try:
        template_name = request.match_info["name"]
        template = get_template(template_name)
        
        if not template:
            return web.json_response(
                {"success": False, "error": "Template not found"},
                status=404
            )
        
        return web.json_response({
            "success": True,
            "template": template
        })
        
    except Exception as e:
        logger.error("api_get_template_detail_failed", error=str(e))
        return web.json_response(
            {"success": False, "error": str(e)},
            status=500
        )


async def get_metrics(request: Request) -> Response:
    """GET /api/v1/metrics - Prometheus-compatible metrics."""
    try:
        queue_stats = await get_queue_stats()
        pool_stats = pool_manager.get_stats()
        
        metrics = f"""# MCP Scheduler Metrics
# HELP mcp_scheduler_pending_jobs Number of pending jobs
# TYPE mcp_scheduler_pending_jobs gauge
mcp_scheduler_pending_jobs {queue_stats.get("pending_jobs", 0)}

# HELP mcp_scheduler_running_jobs Number of running jobs
# TYPE mcp_scheduler_running_jobs gauge
mcp_scheduler_running_jobs {queue_stats.get("running_jobs", 0)}

# HELP mcp_scheduler_available_slots Number of available execution slots
# TYPE mcp_scheduler_available_slots gauge
mcp_scheduler_available_slots {pool_stats.get("available_slots", 0)}

# HELP mcp_scheduler_running_executions Total running executions count
# TYPE mcp_scheduler_running_executions gauge
mcp_scheduler_running_executions {pool_stats.get("running_jobs", 0)}
"""
        
        return web.Response(
            text=metrics,
            content_type="text/plain"
        )
        
    except Exception as e:
        logger.error("api_get_metrics_failed", error=str(e))
        return web.Response(
            text=f"# Error\n# {str(e)}",
            content_type="text/plain",
            status=500
        )


# ═══════════════════════════════════════════════════════════════════════
# CORS Middleware
# ═══════════════════════════════════════════════════════════════════════

@web.middleware
async def cors_middleware(request: Request, handler):
    """Add CORS headers."""
    if request.method == "OPTIONS":
        response = web.Response()
    else:
        response = await handler(request)
    
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    
    return response


# ═══════════════════════════════════════════════════════════════════════
# Application Factory
# ═══════════════════════════════════════════════════════════════════════

def create_app() -> web.Application:
    """Create and configure the API application."""
    app = web.Application(middlewares=[cors_middleware])
    
    # Add routes
    app.router.add_get("/health", health_check)
    app.router.add_get("/api/v1/jobs", get_jobs)
    app.router.add_get("/api/v1/jobs/{id}", get_job_detail)
    app.router.add_post("/api/v1/jobs", create_new_job)
    app.router.add_put("/api/v1/jobs/{id}", update_existing_job)
    app.router.add_delete("/api/v1/jobs/{id}", delete_existing_job)
    app.router.add_post("/api/v1/jobs/{id}/run", run_job_now)
    app.router.add_get("/api/v1/executions", get_executions)
    app.router.add_get("/api/v1/status", get_scheduler_status)
    app.router.add_get("/api/v1/templates", get_job_templates)
    app.router.add_get("/api/v1/templates/{name}", get_template_detail)
    app.router.add_get("/api/v1/metrics", get_metrics)
    
    return app


# ═══════════════════════════════════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════════════════════════════════

async def init_scheduler_queue(app: web.Application):
    """Startup: Connect to Redis."""
    await scheduler_queue.connect()
    logger.info("api_scheduler_queue_connected")


async def close_scheduler_queue(app: web.Application):
    """Cleanup: Disconnect from Redis."""
    await scheduler_queue.disconnect()
    logger.info("api_scheduler_queue_disconnected")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="MCP Scheduler REST API")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind (default: 8080)")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes")
    
    args = parser.parse_args()
    
    # Create app
    app = create_app()
    
    # Register lifecycle callbacks
    app.on_startup.append(init_scheduler_queue)
    app.on_cleanup.append(close_scheduler_queue)
    
    # Run
    logger.info("api_server_starting", host=args.host, port=args.port)
    print(f"🚀 MCP Scheduler API Server")
    print(f"   URL: http://{args.host}:{args.port}")
    print(f"   Health: http://{args.host}:{args.port}/health")
    print(f"   API Docs: http://{args.host}:{args.port}/api/v1/status")
    print(f"   Press Ctrl+C to stop")
    
    web.run_app(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
