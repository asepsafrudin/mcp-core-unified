"""
MCP Autonomous Task Scheduler

Module untuk scheduled job execution dengan integrasi ke komponen MCP:
- LTM (Long Term Memory)
- Planner (AI-driven execution planning)
- Self-Healing (Auto-fix pada failure)
- Tool Registry (Task execution)

Usage:
    from scheduler.manager import SchedulerManager
    from scheduler.executor import AutonomousExecutor
"""

__version__ = "1.0.0"
__author__ = "MCP System"

# Import main classes untuk convenience
# Note: These akan tersedia setelah implementasi
# from .manager import SchedulerManager
# from .executor import AutonomousExecutor
# from .templates import JOB_TEMPLATES

__all__ = [
    "__version__",
]
