"""
Mission Manager (The Soul) - Phase 5 Domain Specialization

Meta-agent yang mengkoordinasikan semua domain agents.
Responsibilities:
- Task decomposition across domains
- Domain agent selection
- Cross-domain workflow orchestration
- Goal tracking and reporting
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from .base import BaseAgent, AgentProfile, AgentCapability, agent_registry
from .orchestrator import AgentOrchestrator, ComplexTask, SubTask, CoordinationStrategy
from core.task import Task, TaskResult


@dataclass
class Mission:
    """High-level mission dengan cross-domain objectives."""
    description: str
    objectives: List[str]
    constraints: Dict[str, Any]
    priority: str = "normal"


class MissionManager:
    """
    The Soul - Central coordinator untuk semua domain agents.
    
    Tidak menggantikan AgentOrchestrator, tapi menggunakan orchestrator
    untuk eksekusi sementara manager handle high-level mission planning.
    """
    
    def __init__(self):
        self._orchestrator = AgentOrchestrator()
        self._active_missions: Dict[str, Mission] = {}
        self._mission_history: List[Dict] = []
    
    async def execute_mission(self, mission: Mission) -> Dict[str, Any]:
        """
        Execute high-level mission dengan cross-domain coordination.
        
        Args:
            mission: Mission dengan objectives dan constraints
            
        Returns:
            Dict dengan mission results dan execution summary
        """
        # Analyze mission dan decompose ke domain-specific tasks
        sub_tasks = self._decompose_mission(mission)
        
        # Create complex task untuk orchestrator
        complex_task = ComplexTask(
            description=mission.description,
            sub_tasks=sub_tasks
        )
        
        # Execute via orchestrator dengan pipeline strategy
        result = await self._orchestrator.execute(
            complex_task,
            strategy=CoordinationStrategy.PIPELINE
        )
        
        # Record mission history
        self._mission_history.append({
            "mission": mission.description,
            "success": result.success,
            "execution_time_ms": result.execution_time_ms,
            "sub_tasks_count": len(sub_tasks)
        })
        
        return {
            "success": result.success,
            "mission": mission.description,
            "results": result.sub_task_results,
            "execution_time_ms": result.execution_time_ms,
            "objectives_completed": len([r for r in result.sub_task_results if r.get("success")]),
            "total_objectives": len(sub_tasks)
        }
    
    def _decompose_mission(self, mission: Mission) -> List[SubTask]:
        """
        Decompose mission ke domain-specific sub-tasks.
        
        Ini adalah simplified version - dalam implementasi penuh,
        akan menggunakan LLM untuk intelligent decomposition.
        """
        sub_tasks = []
        
        # Simple heuristic-based decomposition
        for objective in mission.objectives:
            objective_lower = objective.lower()
            
            # Route ke appropriate domain
            if any(kw in objective_lower for kw in ["contract", "legal", "compliance", "regulation"]):
                sub_tasks.append(SubTask(
                    type="legal_task",
                    agent_domain="legal",
                    description=objective
                ))
            elif any(kw in objective_lower for kw in ["infra", "deploy", "server", "system", "monitor"]):
                sub_tasks.append(SubTask(
                    type="admin_task",
                    agent_domain="admin",
                    description=objective
                ))
            elif any(kw in objective_lower for kw in ["code", "refactor", "debug", "review"]):
                sub_tasks.append(SubTask(
                    type="code_task",
                    agent_domain="coding",
                    description=objective
                ))
            elif any(kw in objective_lower for kw in ["file", "directory", "filesystem"]):
                sub_tasks.append(SubTask(
                    type="filesystem_task",
                    agent_domain="filesystem",
                    description=objective
                ))
            elif any(kw in objective_lower for kw in ["research", "analyze", "gather"]):
                sub_tasks.append(SubTask(
                    type="research_task",
                    agent_domain="research",
                    description=objective
                ))
            else:
                # Default: assign ke most capable agent
                sub_tasks.append(SubTask(
                    type="general_task",
                    description=objective
                ))
        
        return sub_tasks
    
    def get_mission_history(self) -> List[Dict]:
        """Get history of executed missions."""
        return self._mission_history
    
    def get_available_domains(self) -> List[str]:
        """Get list of available agent domains."""
        domains = set()
        for agent in agent_registry._agents.values():
            domains.add(agent.domain)
        return list(domains)


# Global instance
mission_manager = MissionManager()
