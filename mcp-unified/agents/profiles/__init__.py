"""
Agent Profiles - Concrete Agent Implementations

Phase 4: Agents Migration - Concrete agents untuk berbagai domains.

Agents:
    - CodeAgent: Code review, analysis, refactoring
    - AdminAgent: Administrative tasks, shell commands
    - ResearchAgent: Information gathering, analysis
    - FilesystemAgent: File operations, directory management

Usage:
    from agents.profiles import CodeAgent, AdminAgent
    
    # Agents auto-registered via @register_agent decorator
    from agents.base import agent_registry
    print(agent_registry.list_agents())
"""

from .code_agent import CodeAgent
from .admin_agent import AdminAgent
from .research_agent import ResearchAgent
from .filesystem_agent import FilesystemAgent
from .legal_agent import LegalAgent
from .office_admin_agent import OfficeAdminAgent
from .app_developer_agent import AppDeveloperAgent

__all__ = [
    "CodeAgent",
    "AdminAgent",
    "ResearchAgent",
    "FilesystemAgent",
    "LegalAgent",
    "OfficeAdminAgent",
    "AppDeveloperAgent",
]
