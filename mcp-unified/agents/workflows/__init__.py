"""
Multi-Agent Workflows - Example Use Cases

Provides pre-built workflows untuk common multi-agent scenarios:
- Code Review Workflow
- Research & Analysis Workflow  
- Admin Automation Workflow

Usage:
    from agents.workflows import CodeReviewWorkflow
    
    workflow = CodeReviewWorkflow()
    result = await workflow.execute(file_path="/path/to/file.py")
"""

from .examples import (
    CodeReviewWorkflow,
    ResearchAnalysisWorkflow,
    AdminAutomationWorkflow,
)

__all__ = [
    "CodeReviewWorkflow",
    "ResearchAnalysisWorkflow",
    "AdminAutomationWorkflow",
]
