"""
Admin Agent - System Administration Specialist

Domain: admin
Capabilities: Shell commands, system operations, maintenance
"""

import sys
from pathlib import Path

# Add parent to path untuk imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.base import BaseAgent, AgentProfile, AgentCapability, register_agent
from core.task import Task, TaskResult


@register_agent
class AdminAgent(BaseAgent):
    """
    Agent specialized untuk system administration tasks.
    
    Expertise (Phase 5 Enhanced):
        - Shell command execution
        - System maintenance
        - Process management
        - Environment setup
        - System monitoring
        - Security auditing
        - Infrastructure management
    """
    
    @property
    def profile(self) -> AgentProfile:
        return AgentProfile(
            name="admin_agent",
            description="System administration specialist",
            domain="admin",
            capabilities={
                AgentCapability.TOOL_USE,
                AgentCapability.SKILL_COMPOSITION,
            },
            preferred_skills=[
                "execute_with_healing",
            ],
            tools_whitelist=[
                # Admin tools
                "run_shell",
                "run_shell_sync",
                # Workspace tools
                "create_workspace",
                "cleanup_workspace",
                "list_workspaces",
                # System monitoring (Phase 5)
                "system_metrics",
                "process_monitor",
                # Security (Phase 5)
                "security_audit",
                "vulnerability_scan",
            ],
            max_concurrent_tasks=2,  # Lower concurrency for safety
            timeout_seconds=600.0  # Longer timeout untuk system ops
        )
    
    def can_handle(self, task: Task) -> bool:
        """
        Check if this agent can handle the task.
        
        Can handle tasks related to:
        - Shell commands
        - System operations
        - Workspace management
        - Process execution
        """
        task_type = task.type.lower()
        
        # Check task type
        admin_tasks = {
            "run_shell", "shell", "command", "execute",
            "workspace", "admin", "system", "process"
        }
        
        if any(at in task_type for at in admin_tasks):
            return True
        
        # Check payload untuk admin-related keywords
        payload_str = str(task.payload).lower()
        admin_keywords = {
            "shell", "command", "run", "execute", "system",
            "workspace", "admin", "pip", "install", "git"
        }
        
        return any(kw in payload_str for kw in admin_keywords)
    
    async def execute(self, task: Task) -> TaskResult:
        """
        Execute admin-related tasks.
        
        Delegates ke appropriate tools dengan safety checks.
        """
        from tools.admin import run_shell
        from environment.workspace import create_workspace, cleanup_workspace, list_workspaces
        
        task_type = task.type.lower()
        payload = task.payload
        
        try:
            # Phase 5: System Monitoring
            if "monitor" in task_type or "metrics" in task_type:
                return await self._system_monitoring(task)
            
            # Phase 5: Security Audit
            if "security" in task_type or "audit" in task_type or "vulnerability" in task_type:
                return await self._security_audit(task)
            
            # Route ke appropriate tool
            if "shell" in task_type or "command" in task_type or "run" in task_type:
                # Execute shell command
                command = payload.get("command") or payload.get("cmd")
                if command:
                    result = await run_shell(command)
                    return TaskResult.success_result(
                        task_id=task.id,
                        data=result,
                        context={"agent": self.name, "action": "shell_execution"}
                    )
            
            elif "workspace" in task_type:
                action = payload.get("action", "create")
                
                if action == "create":
                    name = payload.get("name")
                    result = await create_workspace(name)
                    return TaskResult.success_result(
                        task_id=task.id,
                        data=result,
                        context={"agent": self.name, "action": "create_workspace"}
                    )
                
                elif action == "cleanup":
                    name = payload.get("name")
                    result = await cleanup_workspace(name)
                    return TaskResult.success_result(
                        task_id=task.id,
                        data=result,
                        context={"agent": self.name, "action": "cleanup_workspace"}
                    )
                
                elif action == "list":
                    result = await list_workspaces()
                    return TaskResult.success_result(
                        task_id=task.id,
                        data=result,
                        context={"agent": self.name, "action": "list_workspaces"}
                    )
            
            # Default: try to execute as shell command
            command = payload.get("command") or payload.get("cmd")
            if command:
                result = await run_shell(command)
                return TaskResult.success_result(
                    task_id=task.id,
                    data=result,
                    context={"agent": self.name, "action": "default_shell"}
                )
            
            # Fallback: return error
            return TaskResult.failure_result(
                task_id=task.id,
                error="Could not determine how to process this admin task",
                error_code="UNKNOWN_ADMIN_TASK"
            )
            
        except Exception as e:
            return TaskResult.failure_result(
                task_id=task.id,
                error=str(e),
                error_code="ADMIN_AGENT_ERROR"
            )
    
    async def _system_monitoring(self, task: Task) -> TaskResult:
        """Phase 5: System monitoring capabilities."""
        import asyncio
        import subprocess
        
        try:
            # Get system metrics
            result = subprocess.run(
                ["top", "-b", "-n", "1"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            metrics = {
                "cpu_usage": "placeholder",
                "memory_usage": "placeholder",
                "disk_usage": "placeholder",
                "top_output": result.stdout[:1000] if result.returncode == 0 else "unavailable"
            }
            
            return TaskResult.success_result(
                task_id=task.id,
                data={
                    "success": True,
                    "metrics": metrics,
                    "status": "system_monitoring_active"
                },
                context={"agent": self.name, "action": "system_monitoring"}
            )
        except Exception as e:
            return TaskResult.failure_result(
                task_id=task.id,
                error=f"Monitoring failed: {str(e)}",
                error_code="MONITORING_ERROR"
            )
    
    async def _security_audit(self, task: Task) -> TaskResult:
        """Phase 5: Security auditing capabilities."""
        payload = task.payload
        audit_type = payload.get("audit_type", "basic")
        
        findings = []
        
        # Basic security checks
        if audit_type in ["basic", "full"]:
            findings.append({
                "severity": "info",
                "category": "configuration",
                "message": "Security audit initialized"
            })
        
        # Placeholder untuk vulnerability checks
        if audit_type == "full":
            findings.append({
                "severity": "low",
                "category": "scanning",
                "message": "Vulnerability scan placeholder - integrate with security tools"
            })
        
        return TaskResult.success_result(
            task_id=task.id,
            data={
                "success": True,
                "audit_type": audit_type,
                "findings": findings,
                "recommendations": [
                    "Implement automated security scanning",
                    "Regular dependency updates",
                    "Access control review"
                ]
            },
            context={"agent": self.name, "action": "security_audit"}
        )
