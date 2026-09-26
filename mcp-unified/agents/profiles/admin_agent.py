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
        """Phase 5: Real system monitoring with psutil."""
        import psutil
        import shutil
        from datetime import datetime

        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()

            # Memory
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()

            # Disk
            disk = shutil.disk_usage("/home/aseps/MCP")

            # Network
            net_io = psutil.net_io_counters()

            # Top processes by CPU
            top_cpu = []
            for proc in sorted(psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']),
                               key=lambda p: p.info.get('cpu_percent') or 0, reverse=True)[:5]:
                top_cpu.append({
                    "pid": proc.info['pid'],
                    "name": proc.info['name'],
                    "cpu_percent": proc.info.get('cpu_percent', 0),
                    "memory_percent": round(proc.info.get('memory_percent', 0), 1),
                })

            # Uptime
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime_seconds = (datetime.now() - boot_time).total_seconds()
            uptime_hours = round(uptime_seconds / 3600, 1)

            metrics = {
                "cpu": {
                    "percent": cpu_percent,
                    "cores": cpu_count,
                    "freq_mhz": round(cpu_freq.current, 0) if cpu_freq else None,
                },
                "memory": {
                    "total_gb": round(mem.total / (1024**3), 2),
                    "used_gb": round(mem.used / (1024**3), 2),
                    "available_gb": round(mem.available / (1024**3), 2),
                    "percent": mem.percent,
                },
                "swap": {
                    "total_gb": round(swap.total / (1024**3), 2),
                    "used_gb": round(swap.used / (1024**3), 2),
                    "percent": swap.percent,
                },
                "disk_workspace": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "used_gb": round(disk.used / (1024**3), 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "percent": round(disk.used / disk.total * 100, 1),
                },
                "network": {
                    "bytes_sent_mb": round(net_io.bytes_sent / (1024**2), 1),
                    "bytes_recv_mb": round(net_io.bytes_recv / (1024**2), 1),
                },
                "top_processes_by_cpu": top_cpu,
                "uptime_hours": uptime_hours,
            }

            # Health status
            health = "healthy"
            warnings = []
            if cpu_percent > 90:
                health = "warning"
                warnings.append(f"CPU usage critical: {cpu_percent}%")
            if mem.percent > 85:
                health = "warning"
                warnings.append(f"Memory usage high: {mem.percent}%")
            if (disk.used / disk.total * 100) > 90:
                health = "critical"
                warnings.append(f"Disk space low: {round(disk.free / (1024**3), 1)}GB free")

            return TaskResult.success_result(
                task_id=task.id,
                data={
                    "success": True,
                    "health": health,
                    "warnings": warnings,
                    "metrics": metrics,
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
        """Phase 5: Real security auditing with actual system checks."""
        import psutil
        import subprocess
        from pathlib import Path

        payload = task.payload
        audit_type = payload.get("audit_type", "basic")
        workspace = Path("/home/aseps/MCP")

        findings = []

        # 1. Check for root-owned files in workspace
        try:
            result = subprocess.run(
                ["find", str(workspace), "-not", "-user", "aseps", "-maxdepth", "3"],
                capture_output=True, text=True, timeout=10
            )
            root_files = [l for l in result.stdout.strip().split("\n") if l]
            if root_files:
                findings.append({
                    "severity": "high",
                    "category": "file_ownership",
                    "message": f"Found {len(root_files)} files not owned by 'aseps' in workspace",
                    "detail": root_files[:10],
                    "fix": "Run: sudo chown -R aseps:aseps /home/aseps/MCP"
                })
            else:
                findings.append({
                    "severity": "info",
                    "category": "file_ownership",
                    "message": "All workspace files correctly owned by 'aseps'"
                })
        except Exception:
            findings.append({
                "severity": "warning",
                "category": "file_ownership",
                "message": "Could not check file ownership"
            })

        # 2. Check for exposed .env files (should not be world-readable)
        try:
            env_files = list(workspace.rglob(".env"))
            exposed = []
            for ef in env_files[:20]:
                if ef.stat().st_mode & 0o044:  # readable by group/others
                    exposed.append(str(ef))
            if exposed:
                findings.append({
                    "severity": "medium",
                    "category": "secrets_exposure",
                    "message": f"{len(exposed)} .env files are readable by group/others",
                    "detail": exposed[:5],
                    "fix": "Run: chmod 600 <file> for each"
                })
            else:
                findings.append({
                    "severity": "info",
                    "category": "secrets_exposure",
                    "message": f"All {len(env_files)} .env files have proper permissions"
                })
        except Exception:
            pass

        # 3. Check listening ports (network services)
        try:
            listening = []
            for conn in psutil.net_connections(kind='inet'):
                if conn.status == 'LISTEN':
                    listening.append({
                        "port": conn.laddr.port,
                        "address": conn.laddr.ip,
                        "pid": conn.pid
                    })
            findings.append({
                "severity": "info",
                "category": "network",
                "message": f"{len(listening)} ports listening",
                "detail": sorted(listening, key=lambda x: x["port"])[:15]
            })
        except (psutil.AccessDenied, PermissionError):
            findings.append({
                "severity": "warning",
                "category": "network",
                "message": "Cannot enumerate ports (permission denied, run without sudo is expected)"
            })

        # 4. Full audit: check pip packages for known vulnerabilities
        if audit_type == "full":
            try:
                result = subprocess.run(
                    [str(workspace / ".venv/bin/pip"), "audit", "--format=json"],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode != 0 and result.stdout:
                    import json as json_mod
                    try:
                        audit_data = json_mod.loads(result.stdout)
                        vuln_count = len(audit_data.get("vulnerabilities", []))
                        findings.append({
                            "severity": "high" if vuln_count > 0 else "info",
                            "category": "dependencies",
                            "message": f"pip audit: {vuln_count} known vulnerabilities",
                            "detail": audit_data.get("vulnerabilities", [])[:5]
                        })
                    except Exception:
                        pass
                else:
                    findings.append({
                        "severity": "info",
                        "category": "dependencies",
                        "message": "pip audit: no known vulnerabilities found"
                    })
            except FileNotFoundError:
                findings.append({
                    "severity": "info",
                    "category": "dependencies",
                    "message": "pip audit not available (pip version may not support 'audit' subcommand)"
                })
            except Exception as e:
                findings.append({
                    "severity": "warning",
                    "category": "dependencies",
                    "message": f"pip audit check failed: {str(e)}"
                })

        # Summary
        high_count = sum(1 for f in findings if f["severity"] in ("high", "critical"))
        medium_count = sum(1 for f in findings if f["severity"] == "medium")

        return TaskResult.success_result(
            task_id=task.id,
            data={
                "success": True,
                "audit_type": audit_type,
                "summary": {
                    "total_findings": len(findings),
                    "high_severity": high_count,
                    "medium_severity": medium_count,
                },
                "findings": findings,
                "recommendations": [
                    "Run full audit periodically: audit_type='full'",
                    "Fix high-severity findings immediately",
                    "Schedule automated security checks via scheduler",
                ]
            },
            context={"agent": self.name, "action": "security_audit"}
        )
