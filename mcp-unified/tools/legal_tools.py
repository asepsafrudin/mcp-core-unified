"""
MCP Tools for Legal Agent
"""

from typing import Dict, Any, Optional
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.profiles.legal.connectors.llm_connector import LLMConnector
from agents.profiles.legal.connectors.kb_connector import KBConnector
from agents.profiles.legal.processors.spm_processor import SPMProcessor


class LegalTools:
    """MCP Tools untuk Legal Agent."""
    
    def __init__(self):
        self.llm = LLMConnector()
        self.kb = KBConnector()
        self.spm_processor = SPMProcessor()
    
    async def verify_spm_classification(self, spm_data: Dict) -> Dict[str, Any]:
        """
        Tool: Verifikasi klasifikasi SPM.
        
        Args:
            spm_data: Data SPM yang akan diverifikasi
        
        Returns:
            Verification result
        """
        return await self.spm_processor.verify_spm(spm_data)
    
    async def research_regulation(self, query: str, use_web: bool = True) -> Dict[str, Any]:
        """
        Tool: Riset regulasi dari KB dan web.
        
        Args:
            query: Kata kunci pencarian
            use_web: Gunakan web scraping (Research Agent)
        
        Returns:
            Research results
        """
        # Search local KB
        kb_results = self.kb.search_regulation(query)
        
        result = {
            "query": query,
            "local_results": kb_results,
            "web_results": None
        }
        
        # If web search enabled, delegate to Research Agent
        if use_web:
            try:
                # This would be called via agent communication
                result["web_results"] = {
                    "status": "pending",
                    "note": "Use research_agent task delegation"
                }
            except Exception as e:
                result["web_error"] = str(e)
        
        return result
    
    async def check_compliance(self, document: str, regulation: str = "UU 23/2014") -> Dict[str, Any]:
        """
        Tool: Check dokumen compliance.
        
        Args:
            document: Isi dokumen
            regulation: Regulasi yang dijadikan referensi
        
        Returns:
            Compliance report
        """
        system_prompt = f"""Anda adalah compliance checker untuk regulasi {regulation}.
        Analisis dokumen dan identifikasi:
        1. Bagian yang compliant
        2. Bagian yang tidak compliant
        3. Missing requirements
        4. Rekomendasi perbaikan"""
        
        prompt = f"""Analisis compliance dokumen berikut terhadap {regulation}:
        
        Dokumen:
        {document[:3000]}...
        
        Berikan hasil dalam format JSON:
        {{
            "compliance_score": 0.0-1.0,
            "is_compliant": true/false,
            "compliant_items": ["..."],
            "non_compliant_items": ["..."],
            "missing_requirements": ["..."],
            "recommendations": ["..."]
        }}
        """
        
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
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "error": "Failed to parse LLM response",
                    "raw": llm_result['content']
                }
        
        return {
            "success": False,
            "error": llm_result.get('error', 'LLM failed')
        }


# Tool instances untuk registration
legal_tools = LegalTools()


async def legal_verify_spm(spm_data: Dict) -> Dict[str, Any]:
    """MCP Tool: Verify SPM classification."""
    return await legal_tools.verify_spm_classification(spm_data)


async def legal_research(query: str, use_web: bool = True) -> Dict[str, Any]:
    """MCP Tool: Research regulation."""
    return await legal_tools.research_regulation(query, use_web)


async def legal_check_compliance(document: str, regulation: str = "UU 23/2014") -> Dict[str, Any]:
    """MCP Tool: Check document compliance."""
    return await legal_tools.check_compliance(document, regulation)
