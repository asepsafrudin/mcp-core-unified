"""
Legal Domain Agent - Enhanced v2.0
UU 23/2014 & SPM Processing dengan Research Agent Integration
"""

import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ..base import BaseAgent, AgentProfile, AgentCapability, agent_registry
from core.task import Task, TaskResult
from .legal.connectors.llm_connector import LLMConnector
from .legal.connectors.kb_connector import KBConnector
from .legal.processors.spm_processor import SPMProcessor


class LegalAgent(BaseAgent):
    """
    Enhanced Legal Agent untuk UU 23/2014 dan SPM processing.
    
    Capabilities:
    - SPM classification dan verification
    - Legal research dengan KB + Research Agent
    - Compliance checking UU 23/2014
    - Document analysis
    """
    
    def __init__(self):
        super().__init__()
        self.llm = LLMConnector()
        self.kb = KBConnector()
        self.spm_processor = SPMProcessor()
    
    @property
    def profile(self) -> AgentProfile:
        """Get agent profile dengan metadata."""
        return AgentProfile(
            name="legal_agent",
            description="Legal research, SPM verification, UU 23/2014 compliance checking",
            domain="legal",
            capabilities={
                AgentCapability.TOOL_USE,
                AgentCapability.SKILL_COMPOSITION,
                AgentCapability.REASONING,
                AgentCapability.PLANNING
            },
            tools_whitelist=[
                "legal_verify_spm",
                "legal_research", 
                "legal_check_compliance"
            ],
            max_concurrent_tasks=3
        )
    
    def can_handle(self, task: Task) -> bool:
        """Check if this agent can handle the given task."""
        if hasattr(task, 'domain') and task.domain == "legal":
            return True
        
        if hasattr(task, 'type'):
            legal_types = {
                'review_contract', 'check_compliance', 'legal_research', 
                'draft_document', 'verify_spm', 'spm_classification',
                'research_regulation'
            }
            if task.type in legal_types:
                return True
        
        if hasattr(task, 'payload') and isinstance(task.payload, dict):
            action = task.payload.get('action', '')
            legal_actions = {
                'review_contract', 'check_compliance', 'research', 'draft',
                'verify_spm', 'classify_spm', 'research_regulation'
            }
            if action in legal_actions:
                return True
        
        return False
    
    async def execute(self, task: Task) -> TaskResult:
        """
        Execute legal domain tasks.
        
        Args:
            task: Task dengan payload berisi action dan parameters
        
        Returns:
            TaskResult dengan hasil analisis legal
        """
        action = task.payload.get("action")
        context = task.payload.get("context", {})
        
        try:
            if action == "verify_spm":
                result = await self.spm_processor.verify_spm(
                    task.payload.get("spm_data", {})
                )
                return TaskResult.success_result(
                    task_id=task.id,
                    data=result,
                    context={"agent": self.name, "action": "verify_spm"}
                )
            
            elif action == "classify_spm":
                result = await self.spm_processor.classify_spm(
                    task.payload.get("deskripsi", ""),
                    task.payload.get("bidang_hint")
                )
                return TaskResult.success_result(
                    task_id=task.id,
                    data=result,
                    context={"agent": self.name, "action": "classify_spm"}
                )
            
            elif action == "research_regulation":
                result = await self._research_regulation(
                    task.payload.get("query"),
                    task.payload.get("use_web", True)
                )
                return TaskResult.success_result(
                    task_id=task.id,
                    data=result,
                    context={"agent": self.name, "action": "research_regulation"}
                )
            
            elif action == "check_compliance":
                result = await self._check_compliance_uu23(
                    task.payload.get("document", ""),
                    task.payload.get("regulation", "UU 23/2014")
                )
                return TaskResult.success_result(
                    task_id=task.id,
                    data=result,
                    context={"agent": self.name, "action": "check_compliance"}
                )
            
            else:
                return TaskResult.failure_result(
                    task_id=task.id,
                    error=f"Unknown action: {action}",
                    error_code="UNKNOWN_ACTION"
                )
        
        except Exception as e:
            return TaskResult.failure_result(
                task_id=task.id,
                error=str(e),
                error_code="LEGAL_AGENT_ERROR"
            )
    
    async def _research_regulation(self, query: str, use_web: bool = True) -> Dict[str, Any]:
        """Research regulasi dengan KB + optional Research Agent."""
        # Search local KB
        kb_results = self.kb.search_regulation(query)
        
        result = {
            "query": query,
            "local_results": kb_results,
            "web_results": None,
            "research_agent_status": None
        }
        
        # Delegate ke Research Agent jika use_web=True
        if use_web:
            result["research_agent_status"] = {
                "note": "Delegate to research_agent dengan task type 'legal_research'",
                "payload": {
                    "query": query,
                    "sources": ["jdih", "peraturan"]
                }
            }
        
        return result
    
    async def _check_compliance_uu23(self, document: str, regulation: str) -> Dict[str, Any]:
        """Check compliance terhadap UU 23/2014."""
        system_prompt = f"""Anda adalah compliance checker untuk {regulation}.
        Analisis dokumen dan berikan penilaian compliance."""
        
        prompt = f"""Analisis compliance dokumen:
        
        {document[:3000]}...
        
        Berikan hasil dalam JSON dengan fields:
        compliance_score, is_compliant, issues, recommendations"""
        
        llm_result = await self.llm.generate(prompt, system_prompt)
        
        if llm_result['success']:
            try:
                import json
                analysis = json.loads(llm_result['content'])
                return {
                    "success": True,
                    "compliance": analysis,
                    "regulation": regulation,
                    "model_used": llm_result['model_used']
                }
            except:
                return {
                    "success": False,
                    "error": "Parse error",
                    "raw": llm_result['content']
                }
        
        return {"success": False, "error": llm_result.get('error')}


# Register agent
legal_agent = LegalAgent()
agent_registry.register(legal_agent)
