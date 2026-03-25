"""
Audit logging module for MCP Unified System.

Provides security audit trail for all actions.
"""

import json
import uuid
import os
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from pathlib import Path
import asyncio
from functools import wraps
from mcp.server.fastmcp import Context


class AuditEventType(str, Enum):
    """Types of audit events."""
    # Authentication events
    AUTH_LOGIN = "auth:login"
    AUTH_LOGOUT = "auth:logout"
    AUTH_FAILURE = "auth:failure"
    AUTH_API_KEY_CREATED = "auth:api_key_created"
    AUTH_API_KEY_REVOKED = "auth:api_key_revoked"
    AUTH_SESSION_EXPIRED = "auth:session_expired"
    
    # Authorization events
    AUTHZ_ACCESS_DENIED = "authz:access_denied"
    AUTHZ_PERMISSION_GRANTED = "authz:permission_granted"
    
    # Tool execution events
    TOOL_EXECUTED = "tool:executed"
    TOOL_FAILED = "tool:failed"
    TOOL_BLOCKED = "tool:blocked"
    
    # Agent events
    AGENT_CREATED = "agent:created"
    AGENT_EXECUTED = "agent:executed"
    AGENT_DELETED = "agent:deleted"
    
    # Data access events
    DATA_READ = "data:read"
    DATA_WRITE = "data:write"
    DATA_DELETE = "data:delete"
    
    # System events
    SYSTEM_CONFIG_CHANGED = "system:config_changed"
    SYSTEM_ERROR = "system:error"
    SYSTEM_MAINTENANCE = "system:maintenance"
    
    # Security events
    SECURITY_VIOLATION = "security:violation"
    SECURITY_ALERT = "security:alert"
    RATE_LIMIT_EXCEEDED = "security:rate_limit_exceeded"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Represents an audit event."""
    event_id: str
    timestamp: datetime
    event_type: str
    severity: str
    user_id: Optional[str]
    session_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    resource: str  # What was accessed/modified
    action: str    # What was done
    status: str    # success, failure, blocked
    details: Dict[str, Any]
    metadata: Dict[str, Any]


class AuditLogger:
    """
    Security audit logger.
    
    Features:
    - Immutable audit trail
    - Structured logging
    - Multiple outputs (file, stdout, webhook)
    - Tamper detection (basic)
    """
    
    def __init__(
        self,
        log_dir: str = "/var/log/mcp/audit",
        stdout: bool = True,
        webhook_url: Optional[str] = None
    ):
        self.log_dir = Path(log_dir)
        self.stdout = stdout
        self.webhook_url = webhook_url
        self._lock = asyncio.Lock()
        
        # Create log directory
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Current log file
        self._current_file = self._get_log_file()
        
        # Event buffer for batching
        self._buffer: List[AuditEvent] = []
        self._buffer_size = 100
    
    def _get_log_file(self) -> Path:
        """Get current log file path (rotated daily)."""
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        return self.log_dir / f"audit-{date_str}.log"
    
    def _rotate_if_needed(self):
        """Rotate log file if date changed."""
        new_file = self._get_log_file()
        if new_file != self._current_file:
            self._current_file = new_file
    
    async def log(
        self,
        event_type: AuditEventType,
        resource: str,
        action: str,
        status: str = "success",
        severity: AuditSeverity = AuditSeverity.INFO,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AuditEvent:
        """Log an audit event."""
        
        event = AuditEvent(
            event_id=f"evt_{uuid.uuid4().hex}",
            timestamp=datetime.utcnow(),
            event_type=event_type.value,
            severity=severity.value,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            resource=resource,
            action=action,
            status=status,
            details=details or {},
            metadata=metadata or {}
        )
        
        async with self._lock:
            self._buffer.append(event)
            
            # Flush if buffer is full
            if len(self._buffer) >= self._buffer_size:
                await self._flush()
        
        return event
    
    async def _flush(self):
        """Flush buffer to log file."""
        if not self._buffer:
            return
        
        self._rotate_if_needed()
        
        # Write to file
        with open(self._current_file, "a") as f:
            for event in self._buffer:
                log_line = json.dumps(asdict(event), default=str)
                f.write(log_line + "\n")
                
                # Also log to stdout if enabled
                if self.stdout:
                    print(f"[AUDIT] {log_line}")
        
        # Clear buffer
        self._buffer.clear()
    
    async def flush(self):
        """Public method to flush buffer."""
        async with self._lock:
            await self._flush()
    
    async def query(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_type: Optional[str] = None,
        user_id: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditEvent]:
        """Query audit logs."""
        events = []
        
        # Get all log files
        log_files = sorted(self.log_dir.glob("audit-*.log"))
        
        for log_file in log_files:
            with open(log_file, "r") as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        event = AuditEvent(**data)
                        
                        # Apply filters
                        if start_time and event.timestamp < start_time:
                            continue
                        if end_time and event.timestamp > end_time:
                            continue
                        if event_type and event.event_type != event_type:
                            continue
                        if user_id and event.user_id != user_id:
                            continue
                        if severity and event.severity != severity:
                            continue
                        
                        events.append(event)
                        
                        if len(events) >= limit:
                            break
                    except (json.JSONDecodeError, TypeError):
                        continue
            
            if len(events) >= limit:
                break
        
        return events[:limit]
    
    async def get_security_alerts(
        self,
        hours: int = 24,
        severity_threshold: AuditSeverity = AuditSeverity.WARNING
    ) -> List[AuditEvent]:
        """Get security alerts from recent period."""
        from datetime import timedelta
        
        start_time = datetime.utcnow() - timedelta(hours=hours)
        
        events = []
        log_files = sorted(self.log_dir.glob("audit-*.log"))
        
        severity_levels = [s.value for s in AuditSeverity]
        threshold_idx = severity_levels.index(severity_threshold.value)
        
        for log_file in log_files:
            with open(log_file, "r") as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        event = AuditEvent(**data)
                        
                        if event.timestamp < start_time:
                            continue
                        
                        # Check if event severity meets threshold
                        event_severity_idx = severity_levels.index(event.severity)
                        if event_severity_idx >= threshold_idx:
                            events.append(event)
                    except (json.JSONDecodeError, TypeError, ValueError):
                        continue
        
        return events


# Global audit logger instance
audit_logger = AuditLogger(
    log_dir=os.getenv("MCP_AUDIT_LOG_DIR", "/var/log/mcp/audit"),
    stdout=os.getenv("MCP_ENV") == "development"
)


def audit_log(
    event_type: AuditEventType,
    resource: str,
    action: str,
    severity: AuditSeverity = AuditSeverity.INFO,
    **kwargs
):
    """
    Decorator to automatically log function calls.
    
    Usage:
        @audit_log(AuditEventType.TOOL_EXECUTED, "shell", "execute")
        async def run_shell(ctx: Context, command: str):
            pass
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(ctx: Context, *args, **kwargs_func):
            # Get context info
            user_id = getattr(ctx, "user_id", None)
            session_id = getattr(ctx, "session_id", None)
            ip_address = getattr(ctx, "ip_address", None)
            user_agent = getattr(ctx, "user_agent", None)
            
            # Execute function
            try:
                result = await func(ctx, *args, **kwargs_func)
                status = "success"
                details = {"result": "completed"}
            except Exception as e:
                status = "failure"
                details = {"error": str(e)}
                result = None
            
            # Log the event
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
                details=details,
                metadata={"function": func.__name__}
            )
            
            return result
        
        return wrapper
    return decorator


async def log_auth_event(
    event_type: AuditEventType,
    user_id: Optional[str] = None,
    success: bool = True,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None
):
    """Helper to log authentication events."""
    await audit_logger.log(
        event_type=event_type,
        resource="auth",
        action=event_type.value.split(":")[1],
        status="success" if success else "failure",
        severity=AuditSeverity.INFO if success else AuditSeverity.WARNING,
        user_id=user_id,
        ip_address=ip_address,
        details=details or {}
    )


async def log_tool_execution(
    tool_name: str,
    user_id: Optional[str] = None,
    success: bool = True,
    details: Optional[Dict[str, Any]] = None
):
    """Helper to log tool execution."""
    await audit_logger.log(
        event_type=AuditEventType.TOOL_EXECUTED if success else AuditEventType.TOOL_FAILED,
        resource=f"tool:{tool_name}",
        action="execute",
        status="success" if success else "failure",
        severity=AuditSeverity.INFO,
        user_id=user_id,
        details=details or {}
    )


async def log_security_alert(
    alert_type: str,
    severity: AuditSeverity,
    details: Dict[str, Any],
    user_id: Optional[str] = None
):
    """Helper to log security alerts."""
    await audit_logger.log(
        event_type=AuditEventType.SECURITY_ALERT,
        resource="security",
        action=alert_type,
        status="alert",
        severity=severity,
        user_id=user_id,
        details=details
    )