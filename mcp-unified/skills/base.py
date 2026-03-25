"""
BaseSkill - Abstract base class untuk semua skills

Skills adalah intelligence layer yang menentukan HOW to think.
Mereka mengkomposisi tools untuk mencapai goals yang lebih kompleks.

[REVIEWER] All skills MUST extend BaseSkill and implement execute().
Skills can depend on other skills - registry akan detect circular deps.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set, Type
from dataclasses import dataclass, field
from enum import Enum, auto
import asyncio

from core.task import Task, TaskResult, BaseTaskHandler


class SkillComplexity(Enum):
    """Complexity levels untuk skill estimation."""
    SIMPLE = auto()      # Single tool call
    MODERATE = auto()    # Multiple tool calls, no branching
    COMPLEX = auto()     # Conditional logic, multiple paths
    VERY_COMPLEX = auto()  # Multi-step, stateful, error recovery


@dataclass
class SkillDependency:
    """Definition untuk skill dependency."""
    skill_name: str
    required: bool = True  # If False, soft dependency (optional enhancement)
    version_constraint: Optional[str] = None  # Semver constraint
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "required": self.required,
            "version_constraint": self.version_constraint
        }


@dataclass
class SkillDefinition:
    """Definition untuk skill metadata."""
    name: str
    description: str
    complexity: SkillComplexity
    dependencies: List[SkillDependency] = field(default_factory=list)
    estimated_duration_ms: Optional[int] = None
    tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.dependencies is None:
            self.dependencies = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "complexity": self.complexity.name,
            "dependencies": [d.to_dict() for d in self.dependencies],
            "estimated_duration_ms": self.estimated_duration_ms,
            "tags": self.tags
        }


class BaseSkill(BaseTaskHandler, ABC):
    """
    Abstract base class untuk semua skills.
    
    Skills adalah intelligence layer yang menentukan HOW to accomplish tasks.
    Mereka mengkomposisi tools dan skills lain untuk mencapai goals.
    
    Examples:
        - PlanningSkill: Break down complex tasks
        - ResearchSkill: Gather and synthesize information
        - CommunicationSkill: Summarize, translate, format
        - AnalysisSkill: Data analysis and insights
    
    [REVIEWER] Implementers MUST:
    1. Override skill_definition property
    2. Override execute() method
    3. Declare dependencies via skill_definition
    """
    
    def __init__(self):
        self._execution_count = 0
        self._error_count = 0
        self._avg_execution_time_ms = 0.0
    
    @property
    @abstractmethod
    def skill_definition(self) -> SkillDefinition:
        """
        Get skill definition dengan metadata.
        
        Returns:
            SkillDefinition dengan skill metadata
        """
        pass
    
    @property
    def name(self) -> str:
        """Get skill name dari definition."""
        return self.skill_definition.name
    
    @property
    def description(self) -> str:
        """Get skill description dari definition."""
        return self.skill_definition.description
    
    @property
    def dependencies(self) -> List[SkillDependency]:
        """Get skill dependencies."""
        return self.skill_definition.dependencies
    
    def can_handle(self, task: Task) -> bool:
        """
        Check if this skill can handle the given task.
        
        Skill dapat handle task jika task.type sama dengan skill name
        atau jika task.type ada di skill tags.
        """
        if task.type == self.name:
            return True
        return task.type in self.skill_definition.tags
    
    @abstractmethod
    async def execute(self, task: Task) -> TaskResult:
        """
        Execute skill dengan task payload.
        
        Args:
            task: Task dengan skill parameters di payload
            
        Returns:
            TaskResult dengan execution outcome
        """
        pass
    
    def get_capabilities(self) -> List[str]:
        """Get skill capabilities."""
        caps = [f"skill:{self.name}"]
        caps.extend([f"skill:{tag}" for tag in self.skill_definition.tags])
        return caps
    
    def get_handler_info(self) -> Dict[str, Any]:
        """Get skill handler info dengan definition."""
        info = super().get_handler_info()
        info["skill_definition"] = self.skill_definition.to_dict()
        info["execution_count"] = self._execution_count
        info["error_count"] = self._error_count
        info["avg_execution_time_ms"] = self._avg_execution_time_ms
        return info
    
    def _update_metrics(self, execution_time_ms: float, success: bool):
        """Update execution metrics."""
        self._execution_count += 1
        if not success:
            self._error_count += 1
        # Rolling average
        if self._execution_count == 1:
            self._avg_execution_time_ms = execution_time_ms
        else:
            self._avg_execution_time_ms = (
                (self._avg_execution_time_ms * (self._execution_count - 1) + execution_time_ms)
                / self._execution_count
            )


class CircularDependencyError(Exception):
    """Raised when circular dependency detected di skill graph."""
    pass


class SkillRegistry:
    """
    Registry untuk managing dan discovering skills.
    
    SkillRegistry menyimpan semua registered skills dan menyediakan:
    - Discovery mechanism untuk agents
    - Circular dependency detection
    - Dependency resolution
    """
    
    def __init__(self):
        self._skills: Dict[str, BaseSkill] = {}
        self._dependency_graph: Dict[str, Set[str]] = {}
    
    def register(self, skill: BaseSkill) -> None:
        """
        Register a skill ke registry.
        
        Args:
            skill: Skill instance untuk diregister
            
        Raises:
            ValueError: Jika skill dengan nama sama sudah diregister
            CircularDependencyError: Jika dependency graph akan memiliki cycle
        """
        if skill.name in self._skills:
            raise ValueError(f"Skill '{skill.name}' is already registered")
        
        # Check for circular dependencies
        self._check_circular_dependencies(skill)
        
        # Add to dependency graph
        dep_names = {d.skill_name for d in skill.dependencies if d.required}
        self._dependency_graph[skill.name] = dep_names
        
        self._skills[skill.name] = skill
    
    def unregister(self, skill_name: str) -> None:
        """
        Unregister a skill dari registry.
        
        Args:
            skill_name: Name of skill to unregister
        """
        if skill_name in self._skills:
            del self._skills[skill_name]
            del self._dependency_graph[skill_name]
    
    def _check_circular_dependencies(self, skill: BaseSkill) -> None:
        """
        Check if adding this skill would create circular dependency.
        
        Args:
            skill: Skill to check
            
        Raises:
            CircularDependencyError: Jika circular dependency terdeteksi
        """
        visited = set()
        rec_stack = set()
        
        def has_cycle(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            
            # Get dependencies dari node (existing + new skill)
            if node == skill.name:
                deps = {d.skill_name for d in skill.dependencies if d.required}
            else:
                deps = self._dependency_graph.get(node, set())
            
            for neighbor in deps:
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        # Check from new skill
        if has_cycle(skill.name):
            raise CircularDependencyError(
                f"Registering '{skill.name}' would create circular dependency"
            )
        
        # Also check if any existing skill depends on this new skill
        # (which would create cycle if new skill depends on existing)
        for existing_name, existing_deps in self._dependency_graph.items():
            if skill.name in existing_deps:
                # Check if new skill depends on existing (cycle!)
                new_deps = {d.skill_name for d in skill.dependencies if d.required}
                if existing_name in new_deps:
                    raise CircularDependencyError(
                        f"Circular dependency: '{skill.name}' <-> '{existing_name}'"
                    )
    
    def get_skill(self, skill_name: str) -> Optional[BaseSkill]:
        """
        Get skill by name.
        
        Args:
            skill_name: Name of skill to retrieve
            
        Returns:
            Skill instance atau None jika tidak ditemukan
        """
        return self._skills.get(skill_name)
    
    def list_skills(self) -> List[str]:
        """
        List all registered skill names.
        
        Returns:
            List of skill names
        """
        return list(self._skills.keys())
    
    def get_all_definitions(self) -> List[Dict[str, Any]]:
        """
        Get definitions untuk semua registered skills.
        
        Returns:
            List of skill definitions
        """
        return [
            skill.skill_definition.to_dict()
            for skill in self._skills.values()
        ]
    
    def find_skill_for_task(self, task: Task) -> Optional[BaseSkill]:
        """
        Find skill yang bisa handle given task.
        
        Args:
            task: Task untuk dicari handler
            
        Returns:
            Skill instance atau None
        """
        for skill in self._skills.values():
            if skill.can_handle(task):
                return skill
        return None
    
    def resolve_dependencies(self, skill_name: str) -> List[str]:
        """
        Resolve dependencies untuk skill dalam topological order.
        
        Args:
            skill_name: Name of skill to resolve
            
        Returns:
            List of skill names dalam dependency order (dependencies first)
            
        Raises:
            ValueError: Jika skill tidak ditemukan
        """
        if skill_name not in self._skills:
            raise ValueError(f"Skill '{skill_name}' not found")
        
        # Topological sort
        visited = set()
        result = []
        
        def visit(node: str):
            if node in visited:
                return
            visited.add(node)
            
            for dep in self._dependency_graph.get(node, set()):
                visit(dep)
            
            result.append(node)
        
        visit(skill_name)
        return result[:-1]  # Exclude the skill itself, return only dependencies
    
    def get_dependency_graph(self) -> Dict[str, List[str]]:
        """
        Get full dependency graph.
        
        Returns:
            Dictionary mapping skill names ke list of dependencies
        """
        return {name: list(deps) for name, deps in self._dependency_graph.items()}
    
    def get_registry_info(self) -> Dict[str, Any]:
        """
        Get registry metadata.
        
        Returns:
            Dictionary dengan registry info
        """
        return {
            "registered_skills": len(self._skills),
            "skill_names": self.list_skills(),
            "dependency_graph": self.get_dependency_graph(),
            "skills": {
                name: skill.get_handler_info()
                for name, skill in self._skills.items()
            }
        }


# Global registry instance
skill_registry = SkillRegistry()


def register_skill(skill_class: Type[BaseSkill]) -> Type[BaseSkill]:
    """
    Decorator untuk register skill class ke global registry.
    
    Usage:
        @register_skill
        class MySkill(BaseSkill):
            ...
    """
    skill_instance = skill_class()
    skill_registry.register(skill_instance)
    return skill_class
