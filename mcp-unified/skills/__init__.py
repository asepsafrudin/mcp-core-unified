"""
Skills module - Intelligence layer untuk MCP Multi-Agent Architecture.

Skills adalah reusable capabilities yang menentukan HOW to accomplish tasks:
- Planning: Break down complex tasks
- Research: Gather and synthesize information
- Communication: Summarize, translate, format
- Analysis: Data analysis and insights

Skills dapat memiliki dependencies pada skills lain. Registry akan secara
otomatis mendeteksi circular dependencies dan melakukan topological sort.

Usage:
    from skills.base import BaseSkill, SkillDefinition, SkillDependency
    from skills.base import skill_registry, register_skill
    
    @register_skill
    class MySkill(BaseSkill):
        @property
        def skill_definition(self) -> SkillDefinition:
            return SkillDefinition(
                name="my_skill",
                dependencies=[SkillDependency("other_skill")]
            )
        
        async def execute(self, task: Task) -> TaskResult:
            # Implementation
            pass
"""

from .base import (
    BaseSkill,
    SkillDefinition,
    SkillDependency,
    SkillComplexity,
    SkillRegistry,
    skill_registry,
    register_skill,
    CircularDependencyError,
)

__all__ = [
    "BaseSkill",
    "SkillDefinition",
    "SkillDependency",
    "SkillComplexity",
    "SkillRegistry",
    "skill_registry",
    "register_skill",
    "CircularDependencyError",
]

# Import migrated planning skills (auto-registered via @register_skill)
from .planning import (
    create_plan,
    save_plan_experience,
    planner,
    SimplePlannerCore,
)

# Extend __all__ with migrated planning skills
__all__.extend([
    "create_plan",
    "save_plan_experience",
    "planner",
    "SimplePlannerCore",
])

# Import migrated healing skills (auto-registered via @register_skill)
from .healing import (
    execute_with_healing,
    self_healing,
    PracticalSelfHealing,
    APPROVED_AUTO_INSTALL_PACKAGES,
)

# Extend __all__ with migrated healing skills
__all__.extend([
    "execute_with_healing",
    "self_healing",
    "PracticalSelfHealing",
    "APPROVED_AUTO_INSTALL_PACKAGES",
])
