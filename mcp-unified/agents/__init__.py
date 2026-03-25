"""
Agents module - Domain-specific entities untuk MCP Multi-Agent Architecture.

Agents adalah intelligent entities yang mengkomposisi skills dan tools untuk
menyelesaikan tasks dalam domain tertentu:
- LegalAgent: Legal document analysis, contract review
- AdminAgent: Scheduling, correspondence, mailroom
- CodeAgent: Code review, refactoring, debugging
- ResearchAgent: Information gathering, synthesis

Agents memiliki:
- Domain expertise
- Preferred skills
- Capability flags
- Concurrency control

Usage:
    from agents.base import BaseAgent, AgentProfile, AgentCapability
    from agents.base import agent_registry, register_agent
    
    @register_agent
    class MyAgent(BaseAgent):
        @property
        def profile(self) -> AgentProfile:
            return AgentProfile(
                name="my_agent",
                domain="my_domain",
                capabilities={AgentCapability.TOOL_USE}
            )
        
        def can_handle(self, task: Task) -> bool:
            # Domain-specific logic
            pass
        
        async def execute(self, task: Task) -> TaskResult:
            # Implementation
            pass
"""

from .base import (
    BaseAgent,
    AgentProfile,
    AgentState,
    AgentCapability,
    AgentRegistry,
    agent_registry,
    register_agent,
)

__all__ = [
    "BaseAgent",
    "AgentProfile",
    "AgentState",
    "AgentCapability",
    "AgentRegistry",
    "agent_registry",
    "register_agent",
]

# Import agent profiles (auto-registered via @register_agent)
from .profiles import (
    CodeAgent,
    AdminAgent,
    FilesystemAgent,
    ResearchAgent,
    LegalAgent,
    OfficeAdminAgent,
)

# Extend __all__ with agent profiles
__all__.extend([
    "CodeAgent",
    "AdminAgent",
    "FilesystemAgent",
    "ResearchAgent",
    "LegalAgent",
    "OfficeAdminAgent",
])

# Import orchestrator (for multi-agent coordination)
from .orchestrator import (
    AgentOrchestrator,
    ComplexTask,
    SubTask,
    CoordinationStrategy,
    OrchestrationResult,
    orchestrate,
)

# Extend __all__ with orchestrator
__all__.extend([
    "AgentOrchestrator",
    "ComplexTask",
    "SubTask",
    "CoordinationStrategy",
    "OrchestrationResult",
    "orchestrate",
])

# Import workflows (for common multi-agent patterns)
from .workflows import (
    CodeReviewWorkflow,
    ResearchAnalysisWorkflow,
    AdminAutomationWorkflow,
)

# Extend __all__ with workflows
__all__.extend([
    "CodeReviewWorkflow",
    "ResearchAnalysisWorkflow",
    "AdminAutomationWorkflow",
])

# Import Mission Manager (Phase 5 Domain Specialization)
from .mission_manager import (
    MissionManager,
    Mission,
    mission_manager,
)

# Extend __all__ with Mission Manager
__all__.extend([
    "MissionManager",
    "Mission",
    "mission_manager",
])
