import asyncio
import json
import re
import networkx as nx
from typing import List, Dict, Any, Optional
from intelligence.planner import SimplePlanner
from observability.logger import logger
from memory.longterm import memory_search, memory_save
from domains import __all__ as DOMAINS

class IntelligencePlannerV2:
    """
    Intelligence Planner v2 for MCP Multi-Talent System (TASK-033 Phase 4)
    Mendukung perencanaan tugas dengan >3 integrasi eksternal:
    - Gmail, WhatsApp, Calendar, Contacts, LTM, Knowledge Bridge
    - Dependency graph & parallel execution planning
    - Cross-domain linking (legal ↔ communications)
    """
    
    INTEGRATIONS_MAP = {
        'gmail': 'integrations.google_workspace',
        'calendar': 'integrations.google_workspace',
        'contacts': 'integrations.google_workspace',
        'whatsapp': 'integrations.whatsapp',
        'telegram': 'integrations.telegram',
        'gdrive': 'integrations.gdrive',
        'blackbox': 'integrations.blackbox',
        'knowledge': 'knowledge.rag_engine',
        'ltm': 'memory.longterm'
    }
    
    def __init__(self):
        self.simple_planner = SimplePlanner()
        self.graph = nx.DiGraph()
    
    async def plan_multi_integration(self, user_request: str, namespace: str = "mcp-multi-talent") -> Dict[str, Any]:
        """
        V2 Planning: Analyze request → Detect integrations → Build dependency graph → Generate plan
        """
        logger.info("planner_v2_start", request=user_request[:100], namespace=namespace)
        
        # Step 1: Detect required integrations & domains
        integrations_needed = self._detect_integrations(user_request)
        domains_needed = self._detect_domains(user_request)
        
        if len(integrations_needed) > 3:
            logger.info("planner_v2_multi_detected", integrations=len(integrations_needed), namespace=namespace)
            plan = await self._build_dependency_plan(integrations_needed, domains_needed, user_request, namespace)
        else:
            # Fallback to v1 for simple tasks
            plan = await self.simple_planner.plan(user_request, namespace)
        
        # Save experience
        await self.simple_planner.save_experience(user_request, plan, namespace)
        
        return {
            "success": True,
            "plan": plan,
            "integrations_used": integrations_needed,
            "domains": domains_needed,
            "version": "v2",
            "multi_integration": len(integrations_needed) > 3
        }
    
    def _detect_integrations(self, request: str) -> List[str]:
        """Detect integrations from request using keywords"""
        request_lower = request.lower()
        detected = []
        for key, _ in self.INTEGRATIONS_MAP.items():
            if key in request_lower:
                detected.append(key)
        return detected
    
    def _detect_domains(self, request: str) -> List[str]:
        """Detect domains from request"""
        request_lower = request.lower()
        detected = []
        for domain in DOMAINS:
            if domain.lower() in request_lower:
                detected.append(domain)
        return detected
    
    async def _build_dependency_plan(self, integrations: List[str], domains: List[str], 
                                   request: str, namespace: str) -> List[Dict[str, Any]]:
        """Build dependency graph & parallel plan"""
        self.graph.clear()
        
        # Define dependencies (contoh: knowledge sebelum gmail summary)
        deps = {
            'knowledge': [],
            'ltm': [],
            'gmail': ['knowledge'],
            'calendar': ['contacts'],
            'whatsapp': [],
            'blackbox': ['ltm'],
            'development': ['synthesis']
        }
        
        # Add nodes & edges
        for integ in integrations:
            self.graph.add_node(integ, type='integration')
            for dep in deps.get(integ, []):
                self.graph.add_edge(dep, integ)
        
        # Generate topological plan + parallel groups
        plan = []
        step_num = 1
        
        for node in nx.topological_sort(self.graph):
            plan.append({
                "step": step_num,
                "component": node,
                "description": f"Execute {node}: {self._get_component_action(node, request)}",
                "parallel_group": self._get_parallel_group(node),
                "dependencies": list(self.graph.predecessors(node))
            })
            step_num += 1
        
        # Add final synthesis step
        plan.append({
            "step": step_num,
            "component": "synthesis",
            "description": f"Synthesize results from {len(integrations)} integrations for: {request[:50]}",
            "parallel_group": "final"
        })
        
        return plan
    
    def _get_component_action(self, component: str, request: str) -> str:
        actions = {
            'gmail': 'Send summary email UU 23/2014',
            'calendar': 'Create meeting based on deadline',
            'knowledge': 'Search legal data UU 23/2014',
            'whatsapp': 'Notify via WhatsApp',
            'ltm': 'Save cross-domain experience',
            'development': 'Generate & deploy app (Application Factory)'
        }
        return actions.get(component, f'Process {component}')
    
    def _get_parallel_group(self, node: str) -> str:
        """Group independent nodes for parallel execution"""
        if node in ['whatsapp', 'blackbox']:
            return 'notifications'
        return 'core'

# Global instance
planner_v2 = IntelligencePlannerV2()

async def create_v2_plan(request: str, namespace: str = "mcp-multi-talent") -> Dict[str, Any]:
    return await planner_v2.plan_multi_integration(request, namespace)
