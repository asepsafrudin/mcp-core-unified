import os
"""
Research Agent - Information Gathering and Analysis Specialist

Domain: research
Capabilities: Information gathering, synthesis, RAG-based research, web scraping

Upgrade v2 (TASK-031):
  - Integrasi VaneConnector (SearxNG + Groq) sebagai primary search
  - Tool: vane_search, vane_legal_search, vane_deep_research, vane_gap_fill
  - Fallback ke JDIH/Peraturan scraper jika Vane tidak tersedia
"""

import sys
import asyncio
import logging
from pathlib import Path

# Add parent to path untuk imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.base import BaseAgent, AgentProfile, AgentCapability, register_agent
from core.task import Task, TaskResult
from .research.scrapers import JDIHScraper, PeraturanScraper

logger = logging.getLogger(__name__)

# Research tools are now handled via skills.research (Layer 3)
_vane_tools_available = True  # Skill layer handles availability check


@register_agent
class ResearchAgent(BaseAgent):
    """
    Agent specialized untuk research dan information gathering.
    
    Expertise:
        - Information retrieval (RAG)
        - Document analysis
        - Knowledge synthesis
        - Research planning
    """
    
    @property
    def profile(self) -> AgentProfile:
        return AgentProfile(
            name="research_agent",
            description="Information gathering and analysis specialist (powered by Vane AI Search)",
            domain="research",
            capabilities={
                AgentCapability.TOOL_USE,
                AgentCapability.SKILL_COMPOSITION,
                AgentCapability.PLANNING,
                AgentCapability.REASONING,
                AgentCapability.LEARNING,
            },
            preferred_skills=[
                "create_plan",
                "save_plan_experience",
                "execute_with_healing",
            ],
            tools_whitelist=[
                # === VANE AI SEARCH (Primary) ===
                "vane_search",          # Pencarian web + AI synthesis
                "vane_legal_search",    # Riset hukum Indonesia
                "vane_deep_research",   # Riset mendalam multi-query
                "vane_gap_fill",        # Isi gap data UU 23/2014
                # === Knowledge tools ===
                "knowledge_search",
                # === File tools ===
                "read_file",
                "list_dir",
                # === Vision tools ===
                "analyze_image",
                "analyze_pdf_pages",
                # === Code tools ===
                "analyze_file",
            ],
            max_concurrent_tasks=3,
            timeout_seconds=300.0
        )
    
    def can_handle(self, task: Task) -> bool:
        """
        Check if this agent can handle the task.
        
        Can handle tasks related to:
        - Research
        - Information gathering
        - Document analysis
        - Knowledge synthesis
        """
        task_type = task.type.lower()
        
        # Check task type
        research_tasks = {
            "research", "search", "find", "analyze", "investigate",
            "gather", "synthesize", "knowledge", "document"
        }
        
        if any(rt in task_type for rt in research_tasks):
            return True
        
        # Check payload untuk research keywords
        payload_str = str(task.payload).lower()
        research_keywords = {
            "research", "find", "search", "analyze", "investigate",
            "information", "knowledge", "document", "study", "review"
        }
        
        return any(kw in payload_str for kw in research_keywords)
    
    async def execute(self, task: Task) -> TaskResult:
        """
        Execute research-related tasks.
        
        Priority:
        1. Vane AI Search (SearxNG + Groq) — cepat, akurat, dengan sitasi
        2. JDIH/Peraturan scraper — fallback jika Vane tidak tersedia
        3. Research planning dengan create_plan
        """
        from skills.planning import create_plan
        
        task_type = task.type.lower()
        payload   = task.payload
        
        try:
            # ============================================
            # A. VANE AI SEARCH (primary path)
            # ============================================
            if _vane_tools_available and (
                "search" in task_type or "vane" in task_type or
                "research" in task_type or "legal" in task_type or
                "query" in task_type or "knowledge" in task_type
            ):
                from skills.research import vane_ai_research
                
                query = (
                    payload.get("query") or
                    payload.get("question") or
                    payload.get("topic") or
                    payload.get("keyword")
                )
                if query:
                    # Gap fill khusus
                    if "gap" in task_type or "fill" in task_type:
                        result = await vane_ai_research(
                            query=query, 
                            action="gap_fill",
                            sub_urusan=payload.get("sub_urusan", query),
                            bidang=payload.get("bidang", "Umum")
                        )
                        return TaskResult.success_result(
                            task_id=task.id,
                            data=result.get("data") if result.get("success") else result,
                            context={"agent": self.name, "action": "gap_fill"}
                        )

                    # Deep research multi-query
                    if "deep" in task_type or payload.get("deep", False):
                        result = await vane_ai_research(
                            query=query,
                            action="deep_research",
                            sub_queries=payload.get("sub_queries"),
                            namespace=payload.get("namespace", "legal_research_deep")
                        )
                        return TaskResult.success_result(
                            task_id=task.id,
                            data=result.get("data") if result.get("success") else result,
                            context={"agent": self.name, "action": "deep_research"}
                        )

                    # Legal search atau general search
                    is_legal = any(
                        kw in query.lower()
                        for kw in ["uu", "peraturan", "pasal", "jdih", "hukum",
                                   "kewenangan", "urusan", "spm", "pemerintah"]
                    )
                    
                    if is_legal:
                        result = await vane_ai_research(
                            query=query, 
                            action="legal", 
                            regulation=payload.get("regulation", "UU 23/2014")
                        )
                        action_name = "legal_research"
                    else:
                        result = await vane_ai_research(
                            query=query, 
                            action="search", 
                            mode=payload.get("mode", "balanced")
                        )
                        action_name = "web_research"

                    if result.get("success"):
                        return TaskResult.success_result(
                            task_id=task.id,
                            data=result.get("data"),
                            context={"agent": self.name, "action": action_name}
                        )

            # ============================================
            # B. SCRAPING LANGSUNG (fallback / explicit)
            # ============================================
            if "scrape" in task_type or "regulation" in task_type:
                keyword = payload.get("keyword") or payload.get("query")
                if not isinstance(keyword, str):
                    return TaskResult.failure_result(task.id, error="Keyword/query must be a string", error_code="INVALID_INPUT")
                    
                sources = payload.get("sources", ["jdih", "peraturan"])
                results = await self._scrape_regulations(keyword, sources)
                return TaskResult.success_result(
                    task_id=task.id,
                    data={
                        "keyword":     keyword,
                        "sources":     sources,
                        "results":     results,
                        "total_found": len(results)
                    },
                    context={"agent": self.name, "action": "regulation_scraping"}
                )
            
            # Default: try to create research plan
            query = payload.get("query") or payload.get("topic") or payload.get("question")
            if query:
                result = await create_plan(
                    request=f"Research: {query}",
                    namespace=payload.get("namespace", "default")
                )
                return TaskResult.success_result(
                    task_id=task.id,
                    data=result,
                    context={"agent": self.name, "action": "default_research"}
                )
            
            # Fallback
            return TaskResult.failure_result(
                task_id=task.id,
                error="Could not determine how to process this research task",
                error_code=os.getenv("ERROR_CODE", "UNKNOWN_RESEARCH_TASK" if not os.getenv("CI") else "DUMMY")
            )
            
        except Exception as e:
            return TaskResult.failure_result(
                task_id=task.id,
                error=str(e),
                error_code="RESEARCH_AGENT_ERROR"
            )
    
    async def _scrape_regulations(self, keyword: str, sources: list) -> list:
        """Scrape regulations from multiple sources."""
        results = []
        
        if "jdih" in sources:
            try:
                async with JDIHScraper() as scraper:
                    jdih_results = await scraper.search_regulations(keyword=keyword, limit=5)
                    results.extend(jdih_results)
            except Exception as e:
                print(f"JDIH scraping error: {e}")
        
        if "peraturan" in sources:
            try:
                async with PeraturanScraper() as scraper:
                    peraturan_results = await scraper.search_regulations(keyword=keyword, limit=5)
                    results.extend(peraturan_results)
            except Exception as e:
                print(f"Peraturan scraping error: {e}")
        
        return results