"""
BaseAgent - Abstract base class untuk semua agents

Agents adalah domain-specific entities yang mengkomposisi skills
dan tools untuk menyelesaikan tasks dalam domain tertentu.

[REVIEWER] All agents MUST extend BaseAgent and implement can_handle().
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set, Type
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
import asyncio

from core.task import Task, TaskResult, TaskPriority, TaskContext, BaseTaskHandler
from skills.base import BaseSkill, skill_registry
from tools.base import BaseTool, tool_registry


class AgentCapability(Enum):
    """Capability types untuk agents."""
    TOOL_USE = auto()      # Can use tools
    SKILL_COMPOSITION = auto()  # Can compose skills
    PLANNING = auto()      # Can create execution plans
    REASONING = auto()     # Can perform reasoning
    LEARNING = auto()      # Can learn from experience
    COMMUNICATION = auto() # Can communicate with other agents


@dataclass
class AgentProfile:
    """
    Profile untuk agent identity dan capabilities.
    
    Agent profile mendefinisikan domain expertise, preferred skills,
    dan behavioral characteristics.
    """
    name: str
    description: str
    domain: str  # e.g., "legal", "admin", "coding", "research"
    capabilities: Set[AgentCapability] = field(default_factory=set)
    preferred_skills: List[str] = field(default_factory=list)
    tools_whitelist: List[str] = field(default_factory=list)  # Empty = all allowed
    max_concurrent_tasks: int = 3
    timeout_seconds: float = 300.0
    
    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = set()
        if self.preferred_skills is None:
            self.preferred_skills = []
        if self.tools_whitelist is None:
            self.tools_whitelist = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "domain": self.domain,
            "capabilities": [c.name for c in self.capabilities],
            "preferred_skills": self.preferred_skills,
            "tools_whitelist": self.tools_whitelist,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "timeout_seconds": self.timeout_seconds
        }


@dataclass
class AgentState:
    """
    Runtime state untuk agent.
    
    Menyimpan current status, active tasks, dan metrics.
    """
    status: str = "idle"  # idle, busy, error, shutdown
    active_tasks: Set[str] = field(default_factory=set)
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_execution_time_ms: float = 0.0
    last_active: Optional[datetime] = None
    error_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "active_tasks": list(self.active_tasks),
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "total_execution_time_ms": self.total_execution_time_ms,
            "last_active": self.last_active.isoformat() if self.last_active else None,
            "error_count": self.error_count
        }


class BaseAgent(BaseTaskHandler, ABC):
    """
    Abstract base class untuk semua agents.
    
    Agents adalah domain-specific entities yang mengkomposisi skills
dan tools untuk menyelesaikan tasks. Mereka memiliki:
    - Domain expertise (legal, admin, coding, dll)
    - Preferred skills untuk domain tersebut
    - Capability untuk memutuskan CAN they handle a task
    
    Examples:
        - LegalAgent: Legal document analysis, contract review
        - AdminAgent: Scheduling, correspondence, mailroom
        - CodeAgent: Code review, refactoring, debugging
        - ResearchAgent: Information gathering, synthesis
    
    [REVIEWER] Implementers MUST:
    1. Override profile property
    2. Override can_handle() method
    3. Override execute() method
    """
    
    def __init__(self):
        self._profile: Optional[AgentProfile] = None
        self._state = AgentState()
        self._semaphore: Optional[asyncio.Semaphore] = None
    
    @property
    @abstractmethod
    def profile(self) -> AgentProfile:
        """
        Get agent profile dengan metadata.
        
        Returns:
            AgentProfile dengan agent identity dan capabilities
        """
        pass
    
    def _ensure_initialized(self):
        """Lazy initialization untuk semaphore setelah profile tersedia."""
        if self._semaphore is None:
            profile = self.profile  # Ensure profile is loaded
            self._semaphore = asyncio.Semaphore(profile.max_concurrent_tasks)
    
    @property
    def name(self) -> str:
        """Get agent name dari profile."""
        return self.profile.name
    
    @property
    def domain(self) -> str:
        """Get agent domain dari profile."""
        return self.profile.domain
    
    @property
    def state(self) -> AgentState:
        """Get current agent state."""
        return self._state
    
    @abstractmethod
    def can_handle(self, task: Task) -> bool:
        """
        Determine whether this agent can handle the given task.
        
        Agents should evaluate berdasarkan:
        - Task type/domain relevance
        - Required capabilities
        - Current load/state
        
        Args:
            task: The task to evaluate
            
        Returns:
            True if this agent can execute the task
        """
        pass
    
    @abstractmethod
    async def execute(self, task: Task) -> TaskResult:
        """
        Execute task menggunakan komposisi skills dan tools.
        
        Args:
            task: The task to execute
            
        Returns:
            TaskResult dengan execution outcome
        """
        pass
    
    def get_capabilities(self) -> List[str]:
        """Get agent capabilities."""
        caps = [f"agent:{self.name}", f"domain:{self.domain}"]
        caps.extend([f"capability:{c.name}" for c in self.profile.capabilities])
        return caps
    
    def get_handler_info(self) -> Dict[str, Any]:
        """Get agent handler info dengan profile dan state."""
        return {
            "handler_type": self.__class__.__name__,
            "handler_module": self.__class__.__module__,
            "profile": self.profile.to_dict(),
            "state": self._state.to_dict(),
            "capabilities": self.get_capabilities()
        }
    
    async def execute_with_concurrency_control(
        self, 
        task: Task
    ) -> TaskResult:
        """
        Execute task dengan concurrency control.
        
        Ensures agent tidak melebihi max_concurrent_tasks.
        
        Args:
            task: Task untuk dieksekusi
            
        Returns:
            TaskResult dengan execution outcome
        """
        self._ensure_initialized()
        
        async with self._semaphore:
            self._state.active_tasks.add(task.id)
            self._state.status = "busy"
            self._state.last_active = datetime.utcnow()
            
            start_time = datetime.utcnow()
            try:
                result = await self.execute(task)
                
                # Update metrics
                execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                self._state.completed_tasks += 1
                self._state.total_execution_time_ms += execution_time
                
                return result
                
            except Exception as e:
                self._state.failed_tasks += 1
                self._state.error_count += 1
                return TaskResult.failure_result(
                    task_id=task.id,
                    error=str(e),
                    error_code="AGENT_EXECUTION_ERROR"
                )
            finally:
                self._state.active_tasks.discard(task.id)
                if not self._state.active_tasks:
                    self._state.status = "idle"
    
    def has_capability(self, capability: AgentCapability) -> bool:
        """Check if agent has specific capability."""
        return capability in self.profile.capabilities
    
    def can_use_tool(self, tool_name: str) -> bool:
        """
        Check if agent is allowed to use specific tool.
        
        Args:
            tool_name: Name of tool to check
            
        Returns:
            True if agent can use the tool
        """
        whitelist = self.profile.tools_whitelist
        return len(whitelist) == 0 or tool_name in whitelist
    
    def get_preferred_skills(self) -> List[BaseSkill]:
        """
        Get skill instances untuk preferred skills.
        
        Returns:
            List of skill instances
        """
        skills = []
        for skill_name in self.profile.preferred_skills:
            skill = skill_registry.get_skill(skill_name)
            if skill:
                skills.append(skill)
        return skills
    
    def is_available(self) -> bool:
        """
        Check if agent is available untuk new tasks.
        
        Returns:
            True if agent can accept new tasks
        """
        return (
            self._state.status != "error" and
            self._state.status != "shutdown" and
            len(self._state.active_tasks) < self.profile.max_concurrent_tasks
        )


class AgentRegistry:
    """
    Registry untuk managing dan discovering agents.
    
    AgentRegistry menyimpan semua registered agents dan menyediakan
    discovery mechanism untuk task delegation.
    """
    
    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}
    
    def register(self, agent: BaseAgent) -> None:
        """
        Register an agent ke registry.
        
        Args:
            agent: Agent instance untuk diregister
            
        Raises:
            ValueError: Jika agent dengan nama sama sudah diregister
        """
        if agent.name in self._agents:
            raise ValueError(f"Agent '{agent.name}' is already registered")
        
        self._agents[agent.name] = agent
    
    def unregister(self, agent_name: str) -> None:
        """
        Unregister an agent dari registry.
        
        Args:
            agent_name: Name of agent to unregister
        """
        if agent_name in self._agents:
            del self._agents[agent_name]
    
    def get_agent(self, agent_name: str) -> Optional[BaseAgent]:
        """
        Get agent by name.
        
        Args:
            agent_name: Name of agent to retrieve
            
        Returns:
            Agent instance atau None jika tidak ditemukan
        """
        return self._agents.get(agent_name)
    
    def list_agents(self) -> List[str]:
        """
        List all registered agent names.
        
        Returns:
            List of agent names
        """
        return list(self._agents.keys())
    
    def list_agents_by_domain(self, domain: str) -> List[BaseAgent]:
        """
        List agents untuk specific domain.
        
        Args:
            domain: Domain to filter by
            
        Returns:
            List of agent instances
        """
        return [
            agent for agent in self._agents.values()
            if agent.domain == domain
        ]
    
    def find_agent_for_task(self, task: Task) -> Optional[BaseAgent]:
        """
        Find best agent yang bisa handle given task.
        
        Args:
            task: Task untuk dicari handler
            
        Returns:
            Agent instance atau None
        """
        available_agents = [
            agent for agent in self._agents.values()
            if agent.is_available() and agent.can_handle(task)
        ]
        
        if not available_agents:
            return None
        
        # Score agents based on current load (prefer less loaded)
        def score_agent(agent: BaseAgent) -> float:
            active = len(agent.state.active_tasks)
            max_concurrent = agent.profile.max_concurrent_tasks
            load_ratio = active / max_concurrent if max_concurrent > 0 else 1.0
            return 1.0 - load_ratio  # Higher score = less loaded
        
        return max(available_agents, key=score_agent)
    
    def get_available_agents(self) -> List[BaseAgent]:
        """
        Get all agents yang available untuk new tasks.
        
        Returns:
            List of available agent instances
        """
        return [
            agent for agent in self._agents.values()
            if agent.is_available()
        ]
    
    def get_registry_info(self) -> Dict[str, Any]:
        """
        Get registry metadata.
        
        Returns:
            Dictionary dengan registry info
        """
        return {
            "registered_agents": len(self._agents),
            "agent_names": self.list_agents(),
            "domains": list(set(a.domain for a in self._agents.values())),
            "available_agents": len(self.get_available_agents()),
            "agents": {
                name: agent.get_handler_info()
                for name, agent in self._agents.items()
            }
        }


# Global registry instance
agent_registry = AgentRegistry()


def register_agent(agent_class: Type[BaseAgent]) -> Type[BaseAgent]:
    """
    Decorator untuk register agent class ke global registry.
    
    Usage:
        @register_agent
        class MyAgent(BaseAgent):
            ...
    """
    agent_instance = agent_class()
    agent_registry.register(agent_instance)
    return agent_class
