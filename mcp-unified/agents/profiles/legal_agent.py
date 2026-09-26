"""
Legal Domain Agent - Enhanced v3.0 (Multi-Dimension Reasoning Graph & Full Ecosystem Synergy)
UU 23/2014, SPM Processing, 6-Dimension BPHN & Doctrine Evaluation, Multi-Tier OCR,
Statutory RAG, Correspondence Alignment, Policy-as-Code & Lifecycle Monitoring.
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
from .legal.processors.bphn_evaluator import BPHNEvaluator


class LegalAgent(BaseAgent):
    """
    Enhanced Legal Agent dengan Multi-Dimension Reasoning Graph, Multi-tier Ingestion,
    Statutory RAG Verifier, Correspondence Alignment, Policy-as-Code, dan Alert Dispatcher.
    
    Capabilities:
    - Evaluasi Doktrin 6 Dimensi & Preseden (Two-Pass LangGraph Router)
    - One-Click Comprehensive Legal Audit (End-to-End Pipeline)
    - Multi-Tier Document Ingestion (Digital PDF ➔ docTR OCR ➔ Tesseract)
    - Statutory RAG & Ultra Vires Verifier (Authentic Statute Norms)
    - Historical Correspondence & Ministerial Circulars Alignment
    - Policy-as-Code Formula & Logic Verification
    - Transitional Provision & Lifecycle Deadline Monitoring
    - Instant High-Risk Legal Red Alert Dispatch (WhatsApp)
    - SPM Classification & Minimum Service Standards Verification
    - UU 23/2014 & Regional Government Compliance Checking
    """
    
    def __init__(self):
        super().__init__()
        self.llm = LLMConnector()
        self.kb = KBConnector()
        self.spm_processor = SPMProcessor()
        self.bphn_evaluator = BPHNEvaluator()
    
    @property
    def profile(self) -> AgentProfile:
        """Get agent profile dengan metadata dan whitelist tools lengkap."""
        return AgentProfile(
            name="legal_agent",
            description="Legal research, Multi-Dimension Doctrine Evaluation (6D), Statutory RAG, Policy-as-Code, SPM verification, UU 23/2014 compliance checking",
            domain="legal",
            capabilities={
                AgentCapability.TOOL_USE,
                AgentCapability.SKILL_COMPOSITION,
                AgentCapability.REASONING,
                AgentCapability.PLANNING
            },
            tools_whitelist=[
                "legal_comprehensive_audit",
                "legal_evaluate_doctrine",
                "legal_ingest_document",
                "legal_visualize_radar",
                "legal_verify_statutory",
                "legal_verify_correspondence",
                "legal_verify_policy_code",
                "legal_monitor_lifecycle",
                "legal_dispatch_alert",
                "legal_check_compliance",
                "legal_research",
                "legal_verify_spm"
            ],
            max_concurrent_tasks=3
        )
    
    def can_handle(self, task: Task) -> bool:
        """Check if this agent can handle the given task."""
        if hasattr(task, 'domain') and task.domain == "legal":
            return True
        
        legal_types = {
            'review_contract', 'check_compliance', 'legal_research', 
            'draft_document', 'verify_spm', 'spm_classification',
            'research_regulation', 'evaluate_regulation', 'bphn_evaluation',
            'evaluate_doctrine', 'comprehensive_audit', 'verify_statutory',
            'verify_correspondence', 'verify_policy_code', 'monitor_lifecycle'
        }
        if hasattr(task, 'type') and task.type in legal_types:
            return True
        
        if hasattr(task, 'payload') and isinstance(task.payload, dict):
            action = task.payload.get('action', '')
            legal_actions = {
                'review_contract', 'check_compliance', 'research', 'draft',
                'verify_spm', 'classify_spm', 'research_regulation',
                'evaluate_regulation_6_dimensions', 'evaluate_regulation',
                'evaluate_doctrine', 'comprehensive_audit', 'full_audit',
                'ingest_document', 'visualize_radar', 'verify_statutory',
                'verify_correspondence', 'verify_policy_code', 'monitor_lifecycle',
                'dispatch_alert'
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
            # 1. One-Click Comprehensive Full Audit Pipeline
            if action in ("comprehensive_audit", "full_audit"):
                from tools.legal_tools import legal_comprehensive_audit
                res = await legal_comprehensive_audit(
                    file_path_or_text=task.payload.get("file_path") or task.payload.get("text") or task.payload.get("document", ""),
                    regulation_title=task.payload.get("title", "Regulasi Teruji"),
                    metadata_override=task.payload.get("metadata"),
                    run_code_verifier=task.payload.get("run_code_verifier", True),
                    send_red_alert=task.payload.get("send_red_alert", True)
                )
                return TaskResult.success_result(
                    task_id=task.id,
                    data=res,
                    context={"agent": self.name, "action": "comprehensive_audit"}
                )

            # 2. Multi-Dimension Doctrine & Precedent Evaluation (with persistent/memory cache)
            elif action in ("evaluate_doctrine", "evaluate_regulation_6_dimensions", "evaluate_regulation"):
                import hashlib
                import json
                from pathlib import Path

                reg_text = task.payload.get("text") or task.payload.get("document", "")
                reg_title = task.payload.get("title", "Peraturan Perundang-Undangan")
                metadata_override = task.payload.get("metadata")
                use_cache = not (task.payload.get("force_refresh", False) or task.payload.get("no_cache", False))

                # Compute cache key from text and title
                cache_key = hashlib.sha256(f"{reg_title}:{reg_text[:2000]}".encode("utf-8")).hexdigest()
                cache_dir = Path("/home/aseps/MCP/storage/admin_data/legal_cache")
                cache_file = cache_dir / f"{cache_key}.json"

                cached_res = None
                if use_cache:
                    if hasattr(self, "_doctrine_cache") and cache_key in self._doctrine_cache:
                        cached_res = self._doctrine_cache[cache_key]
                    elif cache_file.exists():
                        try:
                            cached_res = json.loads(cache_file.read_text(encoding="utf-8"))
                        except Exception:
                            pass

                if cached_res:
                    cached_res["cached"] = True
                    return TaskResult.success_result(
                        task_id=task.id,
                        data=cached_res,
                        context={"agent": self.name, "action": "evaluate_doctrine", "cache_hit": True}
                    )

                from tools.legal_tools import legal_evaluate_doctrine
                res = await legal_evaluate_doctrine(
                    regulation_text_or_ref=reg_text,
                    regulation_title=reg_title,
                    metadata_override=metadata_override
                )

                # Store to cache
                if isinstance(res, dict) and res.get("status") != "error":
                    if not hasattr(self, "_doctrine_cache"):
                        self._doctrine_cache = {}
                    self._doctrine_cache[cache_key] = res
                    try:
                        cache_dir.mkdir(parents=True, exist_ok=True)
                        cache_file.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
                    except Exception as e:
                        logger.debug(f"[LegalAgent] Could not persist cache: {e}")

                return TaskResult.success_result(
                    task_id=task.id,
                    data=res,
                    context={"agent": self.name, "action": "evaluate_doctrine", "cache_hit": False}
                )

            # 3. Document Ingestion
            elif action == "ingest_document":
                from tools.legal_tools import legal_ingest_document
                res = legal_ingest_document(
                    file_path=task.payload.get("file_path", ""),
                    max_pages=task.payload.get("max_pages", 50),
                    force_ocr=task.payload.get("force_ocr", False),
                    use_cache=task.payload.get("use_cache", True)
                )
                return TaskResult.success_result(
                    task_id=task.id,
                    data=res,
                    context={"agent": self.name, "action": "ingest_document"}
                )

            # 4. Statutory RAG Verification
            elif action == "verify_statutory":
                from tools.legal_tools import legal_verify_statutory
                res = legal_verify_statutory(
                    parent_law_query=task.payload.get("parent_law_query", ""),
                    derived_regulation_clause=task.payload.get("derived_regulation_clause", "")
                )
                return TaskResult.success_result(
                    task_id=task.id,
                    data=res,
                    context={"agent": self.name, "action": "verify_statutory"}
                )

            # 5. Correspondence & Ministerial Memos Alignment
            elif action == "verify_correspondence":
                from tools.legal_tools import legal_verify_correspondence
                res = legal_verify_correspondence(
                    keywords=task.payload.get("keywords", []),
                    draft_title=task.payload.get("draft_title")
                )
                return TaskResult.success_result(
                    task_id=task.id,
                    data=res,
                    context={"agent": self.name, "action": "verify_correspondence"}
                )

            # 6. Policy-as-Code Formula Verification
            elif action == "verify_policy_code":
                from tools.legal_tools import legal_verify_policy_code
                res = legal_verify_policy_code(
                    regulation_text=task.payload.get("text", ""),
                    codebase_root=task.payload.get("codebase_root")
                )
                return TaskResult.success_result(
                    task_id=task.id,
                    data=res,
                    context={"agent": self.name, "action": "verify_policy_code"}
                )

            # 7. Lifecycle & Transitional Provisions Monitor
            elif action == "monitor_lifecycle":
                from tools.legal_tools import legal_monitor_lifecycle
                res = legal_monitor_lifecycle(
                    regulation_text=task.payload.get("text", ""),
                    regulation_title=task.payload.get("title", "Regulasi"),
                    base_date_str=task.payload.get("base_date")
                )
                return TaskResult.success_result(
                    task_id=task.id,
                    data=res,
                    context={"agent": self.name, "action": "monitor_lifecycle"}
                )

            # 8. Alert Dispatcher
            elif action == "dispatch_alert":
                from tools.legal_tools import legal_dispatch_alert
                res = legal_dispatch_alert(
                    regulation_title=task.payload.get("title", "Regulasi"),
                    dimension_findings=task.payload.get("findings", {}),
                    target_phone=task.payload.get("target_phone"),
                    force_send=task.payload.get("force_send", False)
                )
                return TaskResult.success_result(
                    task_id=task.id,
                    data=res,
                    context={"agent": self.name, "action": "dispatch_alert"}
                )

            # 9. SPM Processor
            elif action == "verify_spm":
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
            
            # 10. Legal Research
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
            
            # 11. Compliance Checking
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
        kb_results = self.kb.search_regulation(query)
        result = {
            "query": query,
            "local_results": kb_results,
            "web_results": None,
            "research_agent_status": None
        }
        if use_web:
            result["research_agent_status"] = {
                "note": "Kueri regulasi terhubung ke knowledge_search namespace 'legal_regulations'",
                "payload": {
                    "query": query,
                    "sources": ["jdih", "peraturan"]
                }
            }
        return result
    
    async def _check_compliance_uu23(self, document: str, regulation: str) -> Dict[str, Any]:
        """Check compliance terhadap UU 23/2014."""
        from tools.legal_tools import legal_check_compliance
        return await legal_check_compliance(document, regulation)


# Register agent
legal_agent = LegalAgent()
agent_registry.register(legal_agent)

