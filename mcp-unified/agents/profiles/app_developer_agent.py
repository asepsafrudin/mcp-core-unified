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
        1. Analisis task dan buat plan (intelligence.planner)
        2. Jika mode local / force_local, jalankan local scaffolding engine
        3. Jika tidak, submit ke OpenHands; jika gagal, graceful fallback ke local scaffolding
        4. Simpan plan experience ke LTM
        """
        task_type = task.type.lower()
        payload = task.payload
        
        # Extract task description dari payload
        task_description = self._extract_task_description(payload)
        expected_output = payload.get("expected_output", "Working application dengan struktur lengkap")
        context = payload.get("context", "")
        force_local = payload.get("local", False) or payload.get("force_local", False) or "local" in task_type
        
        try:
            # Step 1: Analisis task dan buat plan (Local Reasoning/Planning)
            from intelligence.planner import create_plan, save_plan_experience
            
            plan_result = await create_plan(task_description, namespace="app_development")
            generated_plan = plan_result.get("plan", [])
            
            # Formatting plan untuk context
            plan_str = "\n".join([f"- Step {s['step']}: {s['description']}" for s in generated_plan])

            # If user explicitly requested local scaffolding:
            if force_local:
                return await self._handle_local_scaffold(task_description, payload, generated_plan, task.id)
            
            # Step 2: Submit ke OpenHands dengan context plan
            from execution.registry import registry
            
            enhanced_context = (
                f"[App Developer Agent Local Plan]\n{plan_str}\n\n"
                f"Original Context: {context}\n"
                f"Task Type: {task_type}"
            )
            
            task_id = None
            try:
                result = await registry.execute("run_coding_task", {
                    "task_description": task_description,
                    "expected_output": expected_output,
                    "context": enhanced_context,
                    "requested_by": f"app_developer_agent:{task.id}",
                    "priority": payload.get("priority", "medium"),
                    "timeout_minutes": payload.get("timeout_minutes", 60),
                })
                task_id = result.get("task_id") if isinstance(result, dict) else None
            except Exception as e:
                logger.warning(f"[AppDeveloperAgent] OpenHands submission failed: {e}. Falling back to local scaffold.")

            # If submission failed, fallback to local scaffolding engine
            if not task_id:
                logger.info("[AppDeveloperAgent] Falling back to local scaffold engine.")
                return await self._handle_local_scaffold(task_description, payload, generated_plan, task.id, fallback_reason="OpenHands submission unavailable")
            
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
    
    async def _handle_local_scaffold(
        self,
        task_description: str,
        payload: dict,
        plan: list,
        task_id: str,
        fallback_reason: str = None
    ) -> TaskResult:
        """
        Local scaffolding engine: Generate app structure and boilerplate files directly.
        """
        from pathlib import Path
        from intelligence.planner import save_plan_experience
        import re

        # Determine app name
        app_name = payload.get("app_name") or payload.get("project_name")
        if not app_name:
            match = re.search(r'(?:aplikasi|proyek|project|app)\s+([a-zA-Z0-9_\-]+)', task_description, re.IGNORECASE)
            app_name = match.group(1).lower() if match else "my_app"
        app_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', app_name)

        # Target directory
        base_dir = Path(payload.get("target_dir") or f"/home/aseps/MCP/workspace/{app_name}")
        base_dir.mkdir(parents=True, exist_ok=True)

        desc_lower = task_description.lower()
        created_files = []

        # Detect stack
        is_fastapi = "fastapi" in desc_lower or "api" in desc_lower or "python" in desc_lower
        is_express = "express" in desc_lower or "node" in desc_lower or "javascript" in desc_lower
        is_nextjs = "next" in desc_lower or "react" in desc_lower or "frontend" in desc_lower

        if is_fastapi:
            # FastAPI Scaffold
            app_dir = base_dir / "app"
            app_dir.mkdir(exist_ok=True)
            (app_dir / "routers").mkdir(exist_ok=True)
            (app_dir / "models").mkdir(exist_ok=True)

            # main.py
            main_content = (
                '"""\n'
                f'{app_name} — FastAPI Application\n'
                '"""\n\n'
                'from fastapi import FastAPI\n'
                'from fastapi.middleware.cors import CORSMiddleware\n\n'
                f'app = FastAPI(title="{app_name}", version="1.0.0")\n\n'
                'app.add_middleware(\n'
                '    CORSMiddleware,\n'
                '    allow_origins=["*"],\n'
                '    allow_credentials=True,\n'
                '    allow_methods=["*"],\n'
                '    allow_headers=["*"],\n'
                ')\n\n'
                '@app.get("/health")\n'
                'async def health_check():\n'
                '    return {"status": "ok", "app": "' + app_name + '"}\n\n'
                '@app.get("/")\n'
                'async def root():\n'
                '    return {"message": "Welcome to ' + app_name + '"}\n'
            )
            (app_dir / "main.py").write_text(main_content)
            created_files.append(str(app_dir / "main.py"))

            # requirements.txt
            reqs = "fastapi>=0.100.0\nuvicorn[standard]>=0.23.0\npydantic>=2.0.0\npython-dotenv>=1.0.0\n"
            (base_dir / "requirements.txt").write_text(reqs)
            created_files.append(str(base_dir / "requirements.txt"))

        elif is_express:
            # Express.js Scaffold
            src_dir = base_dir / "src"
            src_dir.mkdir(exist_ok=True)
            (src_dir / "routes").mkdir(exist_ok=True)

            # index.js
            index_content = (
                'const express = require("express");\n'
                'const cors = require("cors");\n'
                'const app = express();\n'
                'const PORT = process.env.PORT || 3000;\n\n'
                'app.use(cors());\n'
                'app.use(express.json());\n\n'
                'app.get("/health", (req, res) => res.json({ status: "ok" }));\n'
                'app.get("/", (req, res) => res.json({ message: "Welcome to ' + app_name + '" }));\n\n'
                'app.listen(PORT, () => console.log(`Server running on port ${PORT}`));\n'
            )
            (src_dir / "index.js").write_text(index_content)
            created_files.append(str(src_dir / "index.js"))

            # package.json
            pkg = (
                '{\n'
                f'  "name": "{app_name}",\n'
                '  "version": "1.0.0",\n'
                '  "main": "src/index.js",\n'
                '  "scripts": { "start": "node src/index.js", "dev": "nodemon src/index.js" },\n'
                '  "dependencies": { "express": "^4.18.2", "cors": "^2.8.5" }\n'
                '}\n'
            )
            (base_dir / "package.json").write_text(pkg)
            created_files.append(str(base_dir / "package.json"))

        else:
            # Vanilla HTML/JS Scaffold
            html_content = (
                '<!DOCTYPE html>\n'
                '<html lang="id">\n'
                '<head>\n'
                '  <meta charset="UTF-8">\n'
                '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
                f'  <title>{app_name}</title>\n'
                '  <style>body { font-family: sans-serif; margin: 2rem; background: #f9fafb; color: #111827; }</style>\n'
                '</head>\n'
                '<body>\n'
                f'  <h1>{app_name}</h1>\n'
                f'  <p>{task_description}</p>\n'
                '</body>\n'
                '</html>\n'
            )
            (base_dir / "index.html").write_text(html_content)
            created_files.append(str(base_dir / "index.html"))

        # Common README & .env.example
        readme_content = (
            f'# {app_name}\n\n'
            f'> Generated by AppDeveloperAgent (Local Scaffold Engine)\n\n'
            f'**Task Description:** {task_description}\n\n'
            '## Execution Plan\n'
            + '\n'.join([f"- Step {s.get('step', i+1)}: {s.get('description', '')}" for i, s in enumerate(plan)]) + '\n\n'
            '## Getting Started\n'
            '1. Review generated boilerplate\n'
            '2. Install dependencies\n'
            '3. Run application\n'
        )
        (base_dir / "README.md").write_text(readme_content)
        created_files.append(str(base_dir / "README.md"))

        (base_dir / ".env.example").write_text(f"# {app_name} Environment Variables\nPORT=8000\nENV=development\n")
        created_files.append(str(base_dir / ".env.example"))

        # Save experience into LTM
        try:
            await save_plan_experience(
                request=task_description,
                plan=plan,
                namespace="app_development"
            )
        except Exception:
            pass

        return TaskResult.success_result(
            task_id=task_id,
            data={
                "status": "success",
                "engine": "local_scaffold_fallback",
                "app_name": app_name,
                "target_directory": str(base_dir),
                "files_created": created_files,
                "summary": f"Scaffolded {len(created_files)} files in {base_dir}",
                "plan": plan,
                "fallback_reason": fallback_reason,
            },
            context={"agent": self.name, "action": "local_scaffold"}
        )

    def _extract_task_description(self, payload: dict) -> str:
        """Extract task description dari payload."""
        # Coba berbagai kemungkinan field
        for key in ["task_description", "description", "task", "prompt", "request"]:
            if payload.get(key):
                return str(payload[key])
        
        # Fallback: convert seluruh payload ke string
        return str(payload)