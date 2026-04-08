"""
App Developer Agent — Full Application Development Specialist

Domain: app_development
Capabilities: Full app development lifecycle (scaffolding, coding, testing, deployment)

This agent is designed to handle end-to-end app development tasks by delegating
to OpenHands agent for actual coding work.

Perbedaan dari code_agent:
- code_agent: fokus pada code analysis dan review
- app_developer_agent: fokus pada full app development lifecycle
"""

import sys
from pathlib import Path
from typing import Set

# Add parent to path untuk imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.base import BaseAgent, AgentProfile, AgentCapability, register_agent
from core.task import Task, TaskResult


@register_agent
class AppDeveloperAgent(BaseAgent):
    """
    Agent specialized untuk full application development.
    
    Berbeda dari code_agent yang fokus pada analysis/review, agent ini
    menangani seluruh lifecycle development dari awal hingga deployment.
    
    Expertise:
        - App scaffolding & boilerplate generation
        - CRUD API generation
        - Database schema design & creation
        - Full-stack development (backend + frontend)
        - Testing setup & generation
        - Deployment script generation
        - Documentation generation
    
    Workflow:
        1. Terima task dari user/Telegram/MCP
        2. Analisis requirement
        3. Delegate ke OpenHands untuk implementation
        4. Monitor progress
        5. Return hasil ke user
    """
    
    @property
    def profile(self) -> AgentProfile:
        return AgentProfile(
            name="app_developer_agent",
            description="Full application development specialist — dari scaffolding hingga deployment",
            domain="app_development",
            capabilities={
                AgentCapability.TOOL_USE,
                AgentCapability.SKILL_COMPOSITION,
                AgentCapability.REASONING,
                AgentCapability.PLANNING,
            },
            preferred_skills=[
                "run_coding_task",
                "get_task_status",
                "create_plan",
                "save_plan_experience",
            ],
            tools_whitelist=[
                # OpenHands tools
                "run_coding_task",
                "get_task_status",
                "list_active_agents",
                "cancel_coding_task",
                # File tools
                "read_file",
                "write_file",
                "list_dir",
                # Shell tools
                "run_shell",
                # Analysis tools
                "analyze_file",
                "analyze_project",
            ],
            max_concurrent_tasks=5,
            timeout_seconds=600.0  # 10 menit default timeout
        )
    
    def can_handle(self, task: Task) -> bool:
        """
        Check if this agent can handle the task.
        
        App Developer Agent menangani tasks yang terkait dengan:
        - App creation/scaffolding dari nol
        - CRUD implementation
        - Full-stack development
        - API development
        - Database setup
        - Deployment preparation
        """
        task_type = task.type.lower()
        
        # Task types yang ditangani
        app_dev_tasks = {
            "create_app", "scaffold", "generate_app", "build_app",
            "create_api", "build_api", "generate_api",
            "create_crud", "build_crud", "crud_api",
            "create_project", "generate_project", "build_project",
            "create_database", "setup_database", "migrate_database",
            "deploy", "deployment", "setup_deployment",
            "fullstack", "full_stack", "create_website", "build_website",
            "create_web_app", "build_web_app", "create_dashboard",
        }
        
        if any(t in task_type for t in app_dev_tasks):
            return True
        
        # Check payload untuk keywords
        payload_str = str(task.payload).lower()
        
        # Keywords yang mengindikasikan app development task
        app_dev_keywords = {
            "buatkan aplikasi", "buat aplikasi", "create application",
            "buatkan web", "buat web", "create web",
            "buatkan api", "buat api", "create api",
            "buatkan dashboard", "buat dashboard",
            "buatkan sistem", "buat sistem", "create system",
            "buatkan crm", "buat erp", "buatkan erp",
            "buatkan website", "buat website",
            "scaffold", "boilerplate", "setup project",
            "full stack", "fullstack", "end-to-end",
        }
        
        keyword_match = any(kw in payload_str for kw in app_dev_keywords)
        
        # Juga cek jika task membutuhkan multiple files/components
        multi_file_indicators = {
            "frontend", "backend", "database", "model", "controller",
            "view", "router", "middleware", "service", "repository",
        }
        multi_file_match = sum(1 for kw in multi_file_indicators if kw in payload_str) >= 2
        
        return keyword_match or multi_file_match
    
    async def execute(self, task: Task) -> TaskResult:
        """
        Execute app development task.
        
        Workflow:
        1. Analisis task dan buat plan
        2. Delegate implementation ke OpenHands
        3. Monitor progress
        4. Return hasil
        """
        task_type = task.type.lower()
        payload = task.payload
        
        # Extract task description dari payload
        task_description = self._extract_task_description(payload)
        expected_output = payload.get("expected_output", "Working application dengan struktur lengkap")
        context = payload.get("context", "")
        
        try:
            # Step 1: Analisis task dan buat plan (Local Reasoning/Planning)
            from intelligence.planner import create_plan, save_plan_experience
            
            plan_result = await create_plan(task_description, namespace="app_development")
            generated_plan = plan_result.get("plan", [])
            
            # Formatting plan untuk context
            plan_str = "\n".join([f"- Step {s['step']}: {s['description']}" for s in generated_plan])
            
            # Step 2: Submit ke OpenHands dengan context plan
            from execution.registry import registry
            
            enhanced_context = (
                f"[App Developer Agent Local Plan]\n{plan_str}\n\n"
                f"Original Context: {context}\n"
                f"Task Type: {task_type}"
            )
            
            result = await registry.execute("run_coding_task", {
                "task_description": task_description,
                "expected_output": expected_output,
                "context": enhanced_context,
                "requested_by": f"app_developer_agent:{task.id}",
                "priority": payload.get("priority", "medium"),
                "timeout_minutes": payload.get("timeout_minutes", 60),
            })
            
            task_id = result.get("task_id")
            
            if not task_id:
                return TaskResult.failure_result(
                    task_id=task.id,
                    error="Gagal submit task ke OpenHands",
                    error_code="SUBMISSION_FAILED",
                )
            
            # Step 3: Polling sampai selesai (dengan timeout)
            timeout_minutes = payload.get("timeout_minutes", 60)
            max_polls = timeout_minutes * 2  # Polling setiap 30 detik
            poll_count = 0
            
            while poll_count < max_polls:
                import asyncio
                await asyncio.sleep(30)
                poll_count += 1
                
                status_result = await registry.execute("get_task_status", {
                    "task_id": task_id,
                })
                
                current_status = status_result.get("status", "unknown")
                
                if current_status in ("success", "failed", "timeout", "cancelled"):
                    # Task selesai
                    if current_status == "success":
                        # Simpan pengalaman sukses ke LTM
                        await save_plan_experience(
                            request=task_description,
                            plan=generated_plan,
                            namespace="app_development"
                        )
                        
                        return TaskResult.success_result(
                            task_id=task.id,
                            data={
                                "task_id": task_id,
                                "status": current_status,
                                "summary": status_result.get("summary", ""),
                                "files_created": status_result.get("files_created", []),
                                "files_modified": status_result.get("files_modified", []),
                                "next_steps": status_result.get("next_steps", []),
                                "local_plan": generated_plan,
                            },
                            context={"agent": self.name, "action": "app_development"},
                        )

                    else:
                        return TaskResult.failure_result(
                            task_id=task.id,
                            error=f"Task {current_status}: {status_result.get('summary', '')}",
                            error_code=f"TASK_{current_status.upper()}",
                            data={
                                "task_id": task_id,
                                "errors": status_result.get("errors", []),
                            },
                        )
            
            # Timeout
            return TaskResult.failure_result(
                task_id=task.id,
                error=f"Task timeout setelah {timeout_minutes} menit",
                error_code="TASK_TIMEOUT",
                data={"task_id": task_id},
            )
            
        except Exception as e:
            return TaskResult.failure_result(
                task_id=task.id,
                error=str(e),
                error_code="APP_DEVELOPER_ERROR",
            )
    
    def _extract_task_description(self, payload: dict) -> str:
        """Extract task description dari payload."""
        # Coba berbagai kemungkinan field
        for key in ["task_description", "description", "task", "prompt", "request"]:
            if payload.get(key):
                return str(payload[key])
        
        # Fallback: convert seluruh payload ke string
        return str(payload)