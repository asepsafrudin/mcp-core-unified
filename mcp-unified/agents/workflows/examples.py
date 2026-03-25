"""
Multi-Agent Workflow Examples

Pre-built workflows untuk common multi-agent scenarios.
Each workflow demonstrates coordination antara multiple agents.
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass

# Add parent to path untuk imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from observability.logger import logger
from core.task import TaskContext
from ..orchestrator import AgentOrchestrator, ComplexTask, SubTask, CoordinationStrategy


@dataclass
class WorkflowResult:
    """Result dari workflow execution."""
    success: bool
    workflow_name: str
    result: Dict[str, Any]
    execution_time_ms: float
    error: Optional[str] = None


class CodeReviewWorkflow:
    """
    Workflow untuk code review otomatis.
    
    Agents involved:
    1. CodeAgent - Analyze code quality dan security
    2. FilesystemAgent - Read dan write files
    
    Steps:
    1. Read file content
    2. Analyze code (quality + security)
    3. Generate review report
    
    Usage:
        workflow = CodeReviewWorkflow()
        result = await workflow.execute(file_path="/path/to/file.py")
    """
    
    def __init__(self):
        self.orchestrator = AgentOrchestrator()
        self.name = "code_review"
    
    async def execute(self, file_path: str, context: TaskContext = None) -> WorkflowResult:
        """
        Execute code review workflow.
        
        Args:
            file_path: Path ke file yang akan direview
            context: Optional task context
        
        Returns:
            WorkflowResult dengan review report
        """
        import time
        start_time = time.time()
        
        logger.info("code_review_workflow_started", file_path=file_path)
        
        try:
            # Define sub-tasks
            sub_tasks = [
                SubTask(
                    type="read_file",
                    payload={"path": file_path},
                    agent_domain="filesystem",
                    description="Read file content"
                ),
                SubTask(
                    type="analyze_code",
                    payload={"file_path": file_path},
                    agent_domain="coding",
                    description="Analyze code quality"
                ),
                SubTask(
                    type="self_review",
                    payload={"file_path": file_path, "check_type": "security"},
                    agent_domain="coding",
                    description="Security review"
                )
            ]
            
            # Execute dengan pipeline strategy
            # (read → analyze → review)
            task = ComplexTask(
                description=f"Code review for {file_path}",
                sub_tasks=sub_tasks,
                context=context or TaskContext()
            )
            
            result = await self.orchestrator.execute(
                task,
                strategy=CoordinationStrategy.PIPELINE
            )
            
            execution_time = (time.time() - start_time) * 1000
            
            if result.success:
                logger.info("code_review_workflow_completed",
                           file_path=file_path,
                           execution_time_ms=execution_time)
                
                return WorkflowResult(
                    success=True,
                    workflow_name=self.name,
                    result={
                        "file_path": file_path,
                        "review_data": result.aggregated_data,
                        "sub_results": [
                            {"step": i+1, "success": r.success, "data": r.data}
                            for i, r in enumerate(result.sub_results)
                        ]
                    },
                    execution_time_ms=execution_time
                )
            else:
                logger.error("code_review_workflow_failed",
                           file_path=file_path,
                           errors=result.errors)
                
                return WorkflowResult(
                    success=False,
                    workflow_name=self.name,
                    result={},
                    execution_time_ms=execution_time,
                    error="; ".join(result.errors)
                )
                
        except Exception as e:
            logger.error("code_review_workflow_error",
                       file_path=file_path,
                       error=str(e))
            
            return WorkflowResult(
                success=False,
                workflow_name=self.name,
                result={},
                execution_time_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )


class ResearchAnalysisWorkflow:
    """
    Workflow untuk research dan analysis.
    
    Agents involved:
    1. ResearchAgent - Gather information
    2. CodeAgent - Analyze findings
    
    Steps:
    1. Research topic
    2. Analyze findings
    3. Generate summary report
    
    Usage:
        workflow = ResearchAnalysisWorkflow()
        result = await workflow.execute(topic="AI safety")
    """
    
    def __init__(self):
        self.orchestrator = AgentOrchestrator()
        self.name = "research_analysis"
    
    async def execute(self, topic: str, context: TaskContext = None) -> WorkflowResult:
        """
        Execute research dan analysis workflow.
        
        Args:
            topic: Topik untuk diresearch
            context: Optional task context
        
        Returns:
            WorkflowResult dengan analysis report
        """
        import time
        start_time = time.time()
        
        logger.info("research_analysis_workflow_started", topic=topic)
        
        try:
            # Define sub-tasks
            sub_tasks = [
                SubTask(
                    type="create_plan",
                    payload={"request": f"Research about {topic}"},
                    agent_domain="research",
                    description="Create research plan"
                ),
                SubTask(
                    type="analyze_code",
                    payload={"code": f"# Research context: {topic}"},
                    agent_domain="coding",
                    description="Analyze research context"
                )
            ]
            
            # Execute dengan sequential strategy
            task = ComplexTask(
                description=f"Research and analyze {topic}",
                sub_tasks=sub_tasks,
                context=context or TaskContext()
            )
            
            result = await self.orchestrator.execute(
                task,
                strategy=CoordinationStrategy.SEQUENTIAL
            )
            
            execution_time = (time.time() - start_time) * 1000
            
            if result.success:
                logger.info("research_analysis_workflow_completed",
                           topic=topic,
                           execution_time_ms=execution_time)
                
                return WorkflowResult(
                    success=True,
                    workflow_name=self.name,
                    result={
                        "topic": topic,
                        "analysis": result.aggregated_data,
                        "plan": result.sub_results[0].data if result.sub_results else None
                    },
                    execution_time_ms=execution_time
                )
            else:
                return WorkflowResult(
                    success=False,
                    workflow_name=self.name,
                    result={},
                    execution_time_ms=execution_time,
                    error="; ".join(result.errors)
                )
                
        except Exception as e:
            logger.error("research_analysis_workflow_error",
                       topic=topic,
                       error=str(e))
            
            return WorkflowResult(
                success=False,
                workflow_name=self.name,
                result={},
                execution_time_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )


class AdminAutomationWorkflow:
    """
    Workflow untuk admin automation tasks.
    
    Agents involved:
    1. AdminAgent - Execute admin commands
    2. FilesystemAgent - File operations
    
    Steps:
    1. List workspaces
    2. Cleanup old workspaces
    3. Generate report
    
    Usage:
        workflow = AdminAutomationWorkflow()
        result = await workflow.execute()
    """
    
    def __init__(self):
        self.orchestrator = AgentOrchestrator()
        self.name = "admin_automation"
    
    async def execute(self, context: TaskContext = None) -> WorkflowResult:
        """
        Execute admin automation workflow.
        
        Returns:
            WorkflowResult dengan admin report
        """
        import time
        start_time = time.time()
        
        logger.info("admin_automation_workflow_started")
        
        try:
            # Define sub-tasks
            sub_tasks = [
                SubTask(
                    type="list_workspaces",
                    payload={},
                    agent_domain="admin",
                    description="List all workspaces"
                ),
                SubTask(
                    type="list_dir",
                    payload={"path": "/tmp"},
                    agent_domain="filesystem",
                    description="Check temp directory"
                )
            ]
            
            # Execute dengan parallel strategy
            task = ComplexTask(
                description="Admin automation - cleanup and report",
                sub_tasks=sub_tasks,
                context=context or TaskContext()
            )
            
            result = await self.orchestrator.execute(
                task,
                strategy=CoordinationStrategy.PARALLEL
            )
            
            execution_time = (time.time() - start_time) * 1000
            
            if result.success:
                logger.info("admin_automation_workflow_completed",
                           execution_time_ms=execution_time)
                
                return WorkflowResult(
                    success=True,
                    workflow_name=self.name,
                    result={
                        "workspaces": result.aggregated_data,
                        "cleanup_status": "completed"
                    },
                    execution_time_ms=execution_time
                )
            else:
                return WorkflowResult(
                    success=False,
                    workflow_name=self.name,
                    result={},
                    execution_time_ms=execution_time,
                    error="; ".join(result.errors)
                )
                
        except Exception as e:
            logger.error("admin_automation_workflow_error", error=str(e))
            
            return WorkflowResult(
                success=False,
                workflow_name=self.name,
                result={},
                execution_time_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )


# Convenience functions untuk quick workflow execution
async def run_code_review(file_path: str) -> WorkflowResult:
    """Quick helper untuk run code review workflow."""
    workflow = CodeReviewWorkflow()
    return await workflow.execute(file_path)


async def run_research_analysis(topic: str) -> WorkflowResult:
    """Quick helper untuk run research analysis workflow."""
    workflow = ResearchAnalysisWorkflow()
    return await workflow.execute(topic)


async def run_admin_automation() -> WorkflowResult:
    """Quick helper untuk run admin automation workflow."""
    workflow = AdminAutomationWorkflow()
    return await workflow.execute()
