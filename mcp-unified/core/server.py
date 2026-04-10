from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from core.config import settings
from observability.logger import configure_logger, logger, set_correlation_id
import uuid
import time
import os
from contextlib import asynccontextmanager
from typing import Optional

from core.gateway import router as gateway_router
from memory.longterm import initialize_db, memory_list
from memory.working import working_memory
from messaging.queue_client import mq_client
from security.auth import auth_manager
from security.audit import audit_logger, AuditEventType, AuditSeverity

# Tool imports for SSE parity with stdio MCP server
from scheduler.tools import get_scheduler_tools
from integrations.gdrive.tools import (
    gdrive_list_files,
    gdrive_search_files,
    gdrive_get_file_info,
    gdrive_create_folder,
    gdrive_upload_file,
    gdrive_download_file,
    gdrive_delete_file,
)
from integrations.google_workspace.tools import (
    gmail_list_messages,
    gmail_send_message,
    calendar_list_events,
    people_list_contacts,
    people_search_contacts,
    sheets_read_values,
)
from integrations.whatsapp.tools import (
    whatsapp_get_status,
    whatsapp_send_message,
    whatsapp_get_qr,
    whatsapp_list_chats,
    whatsapp_get_messages,
)
from integrations.common.sync import (
    tool_sync_communications,
    tool_get_unified_history,
)
from knowledge.tools import (
    knowledge_search,
    knowledge_ingest_text,
    knowledge_ingest_spreadsheet,
    knowledge_ingest_googlesheet,
    knowledge_list_namespaces,
)


async def _audit(
    event_type: AuditEventType,
    resource: str,
    action: str,
    status: str = "success",
    severity: AuditSeverity = AuditSeverity.INFO,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[dict] = None,
):
    """Best-effort audit logging (never raises to request path)."""
    try:
        await audit_logger.log(
            event_type=event_type,
            resource=resource,
            action=action,
            status=status,
            severity=severity,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
        )
    except Exception:
        # Don't break request flow on audit failures
        return

# Security scheme for OpenAPI docs
security_scheme = HTTPBearer(auto_error=False)


# =========================================================================
# AUTHENTICATION DEPENDENCIES
# (Defined early because admin endpoints use them in default Depends(...))
# =========================================================================

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
) -> dict:
    """
    Dependency to authenticate requests.

    Supports:
    - X-API-Key header
    - Authorization: Bearer <token> header
    """
    # Try X-API-Key header first; in non-production also allow query param (?api_key=...)
    api_key = request.headers.get("X-API-Key")
    if not api_key and os.getenv("MCP_ENV", "development") != "production":
        api_key = request.query_params.get("api_key")
    if api_key:
        key_info = auth_manager.authenticate_api_key(api_key)
        if key_info:
            await _audit(
                event_type=AuditEventType.AUTH_LOGIN,
                resource="auth",
                action="api_key",
                status="success",
                severity=AuditSeverity.INFO,
                user_id=key_info.owner,
                ip_address=request.client.host if request.client else None,
                details={"method": "api_key"},
            )
            return {
                "user_id": key_info.owner,
                "role": key_info.role,
                "permissions": key_info.permissions,
                "auth_method": "api_key",
                "key_id": key_info.key_id,
            }

    # Try Bearer token
    if credentials and credentials.scheme == "Bearer":
        session = auth_manager.verify_session(credentials.credentials)
        if session:
            await _audit(
                event_type=AuditEventType.AUTH_LOGIN,
                resource="auth",
                action="jwt",
                status="success",
                severity=AuditSeverity.INFO,
                user_id=session.user_id,
                ip_address=request.client.host if request.client else None,
                details={"method": "jwt"},
            )
            return {
                "user_id": session.user_id,
                "role": session.role,
                "permissions": session.permissions,
                "auth_method": "jwt",
                "session_id": session.session_id,
            }

    # Log failed auth attempt
    await _audit(
        event_type=AuditEventType.AUTH_FAILURE,
        resource="auth",
        action="api_key_or_jwt",
        status="failure",
        severity=AuditSeverity.WARNING,
        ip_address=request.client.host if request.client else None,
        details={"reason": "Invalid credentials"},
    )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=os.getenv("DETAIL", "Authentication required. Provide X-API-Key header or Authorization Bearer token." if not os.getenv("CI") else "DUMMY"),
        headers={"WWW-Authenticate": "Bearer"},
    )


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Dependency to require admin role."""
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return user

# Environment detection
MCP_ENV = os.getenv("MCP_ENV", "development")
IS_PRODUCTION = MCP_ENV == "production"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    configure_logger()
    logger.info("server_startup", version=settings.VERSION)
    
    # Initialize database (optional - server can run without it)
    try:
        await initialize_db()
        logger.info("database_initialized")
    except Exception as e:
        logger.warning("database_unavailable", error=str(e))
        logger.info("continuing_without_database")
    
    # Initialize working memory (optional)
    try:
        await working_memory.connect()
        logger.info("working_memory_connected")
    except Exception as e:
        logger.warning("working_memory_unavailable", error=str(e))
    
    # Initialize message queue (optional)
    try:
        await mq_client.connect()
        logger.info("message_queue_connected")
    except Exception as e:
        logger.warning("message_queue_unavailable", error=str(e))
    
    # Register local tools for SSE runtime
    try:
        register_local_tools_for_sse()
        logger.info("local_tools_registered_for_sse")
    except Exception as e:
        logger.warning("local_tools_registration_failed", error=str(e))

    # Discover remote MCP tools
    try:
        # Lazy import to avoid circular dependency
        # execution.registry is not part of core layer
        from execution.registry import discover_remote_tools as _discover_remote
        await _discover_remote()
        logger.info("remote_tools_discovered")
    except Exception as e:
        logger.warning("remote_tools_discovery_failed", error=str(e))
    
    yield
    
    # Shutdown
    try:
        await mq_client.close()
    except:
        pass
    try:
        await working_memory.close()
    except:
        pass
    logger.info("server_shutdown")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    # Disable OpenAPI docs in production (information disclosure prevention)
    docs_url="/docs" if not IS_PRODUCTION else None,
    redoc_url="/redoc" if not IS_PRODUCTION else None,
    openapi_url="/openapi.json" if not IS_PRODUCTION else None
)

@app.middleware("http")
async def add_correlation_id_middleware(request: Request, call_next):
    # Generate or extract correlation ID
    cid = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    set_correlation_id(cid)
    
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    logger.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration=process_time
    )
    
    response.headers["X-Correlation-ID"] = cid
    return response

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.VERSION}


@app.get("/ltm/latest")
async def get_ltm_latest(
    namespace: str = "default",
    limit: int = 2,
    user: dict = Depends(get_current_user),
):
    """
    Ambil data LTM terbaru dari server dengan batas maksimal 2 item.
    """
    safe_limit = max(1, min(limit, 2))
    result = await memory_list(namespace=namespace, limit=safe_limit, offset=0)

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "Failed to fetch LTM data"),
        )

    return {
        "success": True,
        "namespace": namespace,
        "limit": safe_limit,
        "total": result.get("total", 0),
        "memories": result.get("memories", []),
    }

from observability.metrics import metrics
from services import service_controller

@app.get("/metrics/summary")
async def metrics_summary():
    return metrics.get_summary()

# ============================================================================
# SERVICE CONTROL UI (Admin only)
# ============================================================================

SERVICE_UI_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>MCP Service Controller</title>
    <style>
        body { font-family: Arial, sans-serif; background: #f6f7fb; margin: 0; padding: 0; }
        header { background: #1f2937; color: white; padding: 16px 24px; }
        header h1 { margin: 0; font-size: 20px; }
        .container { max-width: 900px; margin: 24px auto; padding: 0 16px; }
        .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.08); margin-bottom: 16px; }
        .card h2 { margin: 0 0 12px 0; font-size: 18px; }
        .status { display: flex; align-items: center; gap: 8px; font-size: 14px; margin-bottom: 12px; }
        .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
        .dot.running { background: #22c55e; }
        .dot.stopped { background: #ef4444; }
        .btn { padding: 8px 14px; border-radius: 6px; border: none; cursor: pointer; margin-right: 8px; }
        .btn.start { background: #22c55e; color: white; }
        .btn.stop { background: #ef4444; color: white; }
        .btn.restart { background: #f59e0b; color: white; }
        .log { font-size: 12px; color: #6b7280; }
        .log-view { background: #111827; color: #e5e7eb; padding: 12px; border-radius: 6px; white-space: pre-wrap; max-height: 260px; overflow-y: auto; font-size: 12px; }
        .log-line.error { background: rgba(239, 68, 68, 0.2); display: block; padding: 2px 4px; border-radius: 4px; margin-bottom: 2px; }
        .log-toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; }
        .log-toolbar label { font-size: 12px; color: #374151; }
        .btn.log { background: #3b82f6; color: white; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }
        .summary { background: #fff7ed; border: 1px solid #fed7aa; }
        .summary ul { list-style: none; padding: 0; margin: 0; }
        .summary li { padding: 6px 0; font-size: 13px; }
        .summary .count { font-weight: bold; color: #b45309; }
    </style>
</head>
<body>
    <header>
        <h1>🛠 MCP Service Controller</h1>
    </header>
    <div class="container">
        <div class="card">
            <h2>Status Overview</h2>
            <p>Gunakan tombol di bawah untuk start/stop/restart layanan.</p>
        </div>
        <div class="card summary">
            <h2>⚠️ Error Summary (last 200 lines)</h2>
            {% if error_summary %}
            <ul>
                {% for name, info in error_summary.items() %}
                {% if info.count > 0 %}
                <li>
                    <span class="count">{{ info.count }}</span> error(s) di {{ name }}
                    {% if info.latest %}
                    — <em>{{ info.latest }}</em>
                    {% endif %}
                </li>
                {% endif %}
                {% endfor %}
            </ul>
            {% else %}
            <p>Tidak ada error terdeteksi.</p>
            {% endif %}
        </div>
        <div class="grid">
            {% for name, info in services.items() %}
            <div class="card">
                <h2>{{ info.label if info.label else name|title }}</h2>
                <div class="status">
                    <span class="dot {{ 'running' if info.running else 'stopped' }}"></span>
                    <span>{{ 'Running' if info.running else 'Stopped' }}</span>
                </div>
                <div>
                    <button class="btn start" onclick="controlService('{{ name }}', 'start')">Start</button>
                    <button class="btn stop" onclick="controlService('{{ name }}', 'stop')">Stop</button>
                    <button class="btn restart" onclick="controlService('{{ name }}', 'restart')">Restart</button>
                    {% if info.log %}
                    <button class="btn log" onclick="viewLog('{{ name }}')">View Logs</button>
                    {% endif %}
                </div>
                {% if info.log %}
                <div class="log">Log: {{ info.log }}</div>
                {% endif %}
            </div>
            {% endfor %}
        </div>
    </div>
    <script>
        const urlParams = new URLSearchParams(window.location.search);
        const apiKey = urlParams.get('api_key');

        function withApiKey(url) {
            if (!apiKey) return url;
            const joiner = url.includes('?') ? '&' : '?';
            return `${url}${joiner}api_key=${encodeURIComponent(apiKey)}`;
        }

        async function controlService(service, action) {
            const resp = await fetch(withApiKey(`/admin/services/${service}/${action}`), { method: 'POST' });
            if (resp.ok) {
                location.reload();
            } else {
                const data = await resp.json();
                alert(data.error || 'Failed to perform action');
            }
        }

        function renderLogLines(lines, filterErrors) {
            const keywords = ['ERROR', 'EXCEPTION', 'Traceback'];
            return lines
                .filter(line => !filterErrors || keywords.some(keyword => line.includes(keyword)))
                .map(line => {
                    const escaped = line.replace(/</g, '&lt;');
                    const isError = keywords.some(keyword => line.includes(keyword));
                    return isError ? `<span class="log-line error">${escaped}</span>` : `${escaped}`;
                })
                .join('');
        }

        async function viewLog(service) {
            const win = window.open('', `_log_${service}`, 'width=900,height=700');
            win.document.title = `${service} logs`;
            win.document.body.innerHTML = `
                <div class="log-toolbar">
                    <label><input type="checkbox" id="filterErrors" checked> Filter ERROR/EXCEPTION/Traceback</label>
                    <label><input type="checkbox" id="autoRefresh" checked> Auto-refresh (10s)</label>
                    <button id="refreshBtn">Refresh</button>
                </div>
                <pre class="log-view" id="logContent">Loading...</pre>
            `;

            async function refreshLog() {
                const resp = await fetch(withApiKey(`/admin/services/${service}/logs?lines=200`));
                const data = await resp.json();
                if (!resp.ok || !data.success) {
                    win.document.getElementById('logContent').textContent = data.error || 'Failed to load logs';
                    return;
                }
                const filterErrors = win.document.getElementById('filterErrors').checked;
                win.document.getElementById('logContent').innerHTML = renderLogLines(data.lines, filterErrors);
            }

            win.document.getElementById('refreshBtn').addEventListener('click', refreshLog);
            win.document.getElementById('filterErrors').addEventListener('change', refreshLog);

            let interval = setInterval(() => {
                if (!win || win.closed) {
                    clearInterval(interval);
                    return;
                }
                const autoRefresh = win.document.getElementById('autoRefresh').checked;
                if (autoRefresh) {
                    refreshLog();
                }
            }, 10000);

            refreshLog();
        }
    </script>
</body>
</html>
"""


@app.get("/admin/services", response_class=HTMLResponse)
async def admin_services_ui(admin: dict = Depends(require_admin)):
    """Simple admin UI for service control."""
    from jinja2 import Template
    services = service_controller.get_all_service_status()
    error_summary_all = service_controller.get_error_summary()
    # Only show services that have errors; template will show "Tidak ada error" if empty.
    error_summary = {
        name: info
        for name, info in (error_summary_all or {}).items()
        if (info or {}).get("count", 0) > 0
    }
    template = Template(SERVICE_UI_HTML)
    return template.render(services=services, error_summary=error_summary)


@app.get("/admin/services/status", response_class=JSONResponse)
async def admin_services_status(admin: dict = Depends(require_admin)):
    return {
        "services": service_controller.get_all_service_status(),
        # Keep both for API consumers: filtered (UI friendly) + full.
        "error_summary": {
            name: info
            for name, info in service_controller.get_error_summary().items()
            if info.get("count", 0) > 0
        },
        "error_summary_all": service_controller.get_error_summary(),
    }


@app.post("/admin/services/{service}/start", response_class=JSONResponse)
async def admin_service_start(service: str, admin: dict = Depends(require_admin)):
    return service_controller.start_service(service)


@app.post("/admin/services/{service}/stop", response_class=JSONResponse)
async def admin_service_stop(service: str, admin: dict = Depends(require_admin)):
    return service_controller.stop_service(service)


@app.post("/admin/services/{service}/restart", response_class=JSONResponse)
async def admin_service_restart(service: str, admin: dict = Depends(require_admin)):
    return service_controller.restart_service(service)


@app.get("/admin/services/{service}/logs", response_class=JSONResponse)
async def admin_service_logs(
    service: str,
    admin: dict = Depends(require_admin),
    lines: int = 200
):
    return service_controller.get_service_log(service, lines=lines)

# Lazy import to avoid circular dependency
# execution.registry is not part of core layer
_registry = None
_tools_registered = False

def get_registry():
    global _registry
    if _registry is None:
        from execution.registry import registry
        _registry = registry
    return _registry

def register_local_tools_for_sse():
    """Register local tools for SSE runtime to match stdio MCP registry."""
    global _tools_registered
    if _tools_registered:
        return

    registry = get_registry()

    # Scheduler tools
    try:
        scheduler_tools = get_scheduler_tools()
        for tool_func in scheduler_tools:
            registry.register(tool_func)
        logger.info("sse_registered_scheduler_tools", count=len(scheduler_tools))
    except Exception as e:
        logger.warning("sse_register_scheduler_tools_failed", error=str(e))

    # Google Drive tools
    try:
        gdrive_tools = [
            gdrive_list_files,
            gdrive_search_files,
            gdrive_get_file_info,
            gdrive_create_folder,
            gdrive_upload_file,
            gdrive_download_file,
            gdrive_delete_file,
        ]
        for tool_func in gdrive_tools:
            registry.register(tool_func)
        logger.info("sse_registered_gdrive_tools", count=len(gdrive_tools))
    except Exception as e:
        logger.warning("sse_register_gdrive_tools_failed", error=str(e))

    # Google Workspace tools
    try:
        gw_tools = [
            gmail_list_messages,
            gmail_send_message,
            calendar_list_events,
            people_list_contacts,
            people_search_contacts,
            sheets_read_values,
        ]
        for tool_func in gw_tools:
            registry.register(tool_func)
        logger.info("sse_registered_google_workspace_tools", count=len(gw_tools))
    except Exception as e:
        logger.warning("sse_register_google_workspace_tools_failed", error=str(e))

    # WhatsApp tools
    try:
        wa_tools = [
            whatsapp_get_status,
            whatsapp_send_message,
            whatsapp_get_qr,
            whatsapp_list_chats,
            whatsapp_get_messages,
        ]
        for tool_func in wa_tools:
            registry.register(tool_func)
        logger.info("sse_registered_whatsapp_tools", count=len(wa_tools))
    except Exception as e:
        logger.warning("sse_register_whatsapp_tools_failed", error=str(e))

    # Unified sync tools
    try:
        sync_tools = [
            tool_sync_communications,
            tool_get_unified_history,
        ]
        for tool_func in sync_tools:
            registry.register(tool_func)
        logger.info("sse_registered_sync_tools", count=len(sync_tools))
    except Exception as e:
        logger.warning("sse_register_sync_tools_failed", error=str(e))

    # Knowledge tools
    try:
        kn_tools = [
            knowledge_search,
            knowledge_ingest_text,
            knowledge_ingest_spreadsheet,
            knowledge_ingest_googlesheet,
            knowledge_list_namespaces,
        ]
        for tool_func in kn_tools:
            registry.register(tool_func)
        logger.info("sse_registered_knowledge_tools", count=len(kn_tools))
    except Exception as e:
        logger.warning("sse_register_knowledge_tools_failed", error=str(e))

    # Semantic tools (auto-registration)
    try:
        import tools.code.semantic_tools  # noqa: F401
        logger.info("sse_registered_semantic_tools")
    except Exception as e:
        logger.warning("sse_register_semantic_tools_failed", error=str(e))

    # Blackbox tools (auto-registration)
    try:
        import integrations.blackbox.tools  # noqa: F401
        logger.info("sse_registered_blackbox_tools")
    except Exception as e:
        logger.warning("sse_register_blackbox_tools_failed", error=str(e))

    # Monitoring tools (auto-registration)
    try:
        import core.monitoring.health_tools  # noqa: F401
        logger.info("sse_registered_monitoring_tools")
    except Exception as e:
        logger.warning("sse_register_monitoring_tools_failed", error=str(e))

    _tools_registered = True

from pydantic import BaseModel

class ToolCall(BaseModel):
    name: str
    arguments: dict = {}

@app.post("/tools/list")
async def list_tools():
    return {"tools": get_registry().list_tools()}

from core.circuit_breaker import circuit_breaker, CircuitBreakerOpenError
from core.rate_limiter import budget_limiter, BudgetExceededError


# ============================================================================
# PROTECTED TOOL ENDPOINTS
# ============================================================================

@app.post("/tools/call")
async def call_tool(
    request: Request,
    call: ToolCall,
    user: dict = Depends(get_current_user),
):
    """Execute a tool with authentication."""
    start_time = time.time()
    try:
        # Check permission for tool execution
        tool_permission = f"tools:execute:{call.name}"
        user_permissions = user.get("permissions", [])

        # Admin bypass
        if user.get("role") == "admin":
            user_permissions = ["*"]
        
        # Allow if user has wildcard or specific permission
        has_permission = (
            "*" in user_permissions or
            tool_permission in user_permissions or
            "tools:execute:*" in user_permissions
        )
        
        if not has_permission:
            await _audit(
                event_type=AuditEventType.AUTHZ_ACCESS_DENIED,
                resource=f"tool:{call.name}",
                action="execute",
                status="failure",
                severity=AuditSeverity.WARNING,
                user_id=user.get("user_id"),
                ip_address=request.client.host if request.client else None,
                details={"tool": call.name, "required": tool_permission},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required: {tool_permission}"
            )
        
        # Rate limiting check
        estimated_cost = 100
        budget_limiter.check_and_consume(estimated_cost)
        
        # Execute tool
        result = await circuit_breaker.call(
            get_registry().execute,
            call.name,
            call.arguments,
        )
        
        duration = time.time() - start_time
        metrics.record_task(success=True, duration=duration)
        
        await _audit(
            event_type=AuditEventType.TOOL_EXECUTED,
            resource=f"tool:{call.name}",
            action="execute",
            status="success",
            severity=AuditSeverity.INFO,
            user_id=user.get("user_id"),
            ip_address=request.client.host if request.client else None,
        )
        
        logger.info(
            "tool_execution",
            tool=call.name,
            user=user.get("user_id"),
            success=True,
            duration=duration
        )
        return {"content": [{"type": "text", "text": str(result)}]}
        
    except HTTPException:
        raise
    except (BudgetExceededError, CircuitBreakerOpenError) as e:
        duration = time.time() - start_time
        metrics.record_task(success=False, duration=duration, error=type(e).__name__)
        logger.warning("execution_blocked", reason=str(e))
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"Blocked: {str(e)}"}]
        }
    except Exception as e:
        duration = time.time() - start_time
        metrics.record_task(success=False, duration=duration, error=type(e).__name__)
        logger.error("tool_failed", tool=call.name, error=str(e))
        await _audit(
            event_type=AuditEventType.TOOL_FAILED,
            resource=f"tool:{call.name}",
            action="execute",
            status="failure",
            severity=AuditSeverity.ERROR,
            user_id=user.get("user_id"),
            ip_address=request.client.host if request.client else None,
            details={"error": str(e)},
        )
        return {
            "isError": True,
            "content": [{"type": "text", "text": str(e)}]
        }


# ============================================================================
# KEY MANAGEMENT ENDPOINTS (Admin only)
# ============================================================================

class CreateKeyRequest(BaseModel):
    name: str
    owner: str
    role: str = "developer"
    expires_days: Optional[int] = None

class CreateKeyResponse(BaseModel):
    key_id: str
    api_key: str
    message: str

@app.post("/admin/keys", response_model=CreateKeyResponse)
async def create_api_key(
    request: CreateKeyRequest,
    admin: dict = Depends(require_admin)
):
    """Create a new API key (admin only)."""
    key_id, raw_key = auth_manager.create_api_key(
        name=request.name,
        owner=request.owner,
        role=request.role,
        expires_days=request.expires_days
    )
    
    await _audit(
        event_type=AuditEventType.AUTH_API_KEY_CREATED,
        resource="auth",
        action="api_key_created",
        status="success",
        severity=AuditSeverity.INFO,
        user_id=admin.get("user_id"),
        details={
            "key_id": key_id,
            "owner": request.owner,
            "role": request.role,
        },
    )
    
    logger.info(
        "api_key_created",
        key_id=key_id,
        owner=request.owner,
        role=request.role,
        admin=admin.get("user_id")
    )
    
    return CreateKeyResponse(
        key_id=key_id,
        api_key=raw_key,
        message="API key created successfully. Store this key securely - it will not be shown again."
    )


@app.get("/admin/keys")
async def list_api_keys(
    admin: dict = Depends(require_admin),
    owner: Optional[str] = None
):
    """List all API keys (admin only)."""
    keys = auth_manager.list_api_keys(owner=owner)
    return {"keys": keys}


@app.delete("/admin/keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    admin: dict = Depends(require_admin)
):
    """Revoke an API key (admin only)."""
    success = auth_manager.revoke_api_key(key_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key {key_id} not found"
        )
    
    await _audit(
        event_type=AuditEventType.AUTH_API_KEY_REVOKED,
        resource="auth",
        action="api_key_revoked",
        status="success",
        severity=AuditSeverity.INFO,
        user_id=admin.get("user_id"),
        details={"key_id": key_id},
    )
    
    logger.info("api_key_revoked", key_id=key_id, admin=admin.get("user_id"))
    
    return {"message": f"API key {key_id} revoked successfully"}


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

class LoginRequest(BaseModel):
    api_key: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    role: str

@app.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Login with API key to get JWT session token."""
    key_info = auth_manager.authenticate_api_key(request.api_key)
    
    if not key_info:
        await _audit(
            event_type=AuditEventType.AUTH_FAILURE,
            resource="auth",
            action="api_key",
            status="failure",
            severity=AuditSeverity.WARNING,
            details={"reason": "Invalid API key"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    
    # Create session
    token = auth_manager.create_session(
        user_id=key_info.owner,
        role=key_info.role,
        permissions=key_info.permissions,
        expires_hours=24
    )
    
    await _audit(
        event_type=AuditEventType.AUTH_LOGIN,
        resource="auth",
        action="login",
        status="success",
        severity=AuditSeverity.INFO,
        user_id=key_info.owner,
        details={"method": "api_key"},
    )
    
    logger.info("user_login", user_id=key_info.owner, role=key_info.role)
    
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        expires_in=86400,  # 24 hours
        user_id=key_info.owner,
        role=key_info.role
    )


@app.get("/auth/me")
async def get_current_user_info(user: dict = Depends(get_current_user)):
    """Get current user information."""
    return {
        "user_id": user.get("user_id"),
        "role": user.get("role"),
        "permissions": user.get("permissions"),
        "auth_method": user.get("auth_method")
    }

# Gateway Router Inclusion
app.include_router(gateway_router)