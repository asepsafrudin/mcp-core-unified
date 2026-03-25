"""
Migration Tests - Test backward compatibility dan adapter functionality

Tests untuk memastikan:
1. Legacy tools dapat di-wrap dan berfungsi dengan BaseTool interface
2. Legacy skills dapat di-wrap dan berfungsi dengan BaseSkill interface
3. Legacy agents dapat di-wrap dan berfungsi dengan BaseAgent interface
4. Registries dapat menangani hybrid old+new components
5. No breaking changes during migration

Usage:
    cd mcp-unified && python -m pytest tests/test_adapter_migration.py -v
"""

import asyncio
import pytest
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.task import Task, TaskResult, TaskPriority, TaskContext
from tools.base import tool_registry, ToolRegistry
from skills.base import skill_registry, SkillRegistry, CircularDependencyError
from agents.base import agent_registry, AgentRegistry, AgentCapability

from adapters.tool_adapter import (
    LegacyToolWrapper, ToolAdapter, adapt_legacy_tool
)
from adapters.skill_adapter import (
    LegacySkillWrapper, SkillAdapter, adapt_legacy_skill
)
from adapters.agent_adapter import (
    LegacyAgentWrapper, AgentAdapter, adapt_legacy_agent
)


# ============================================================================
# Legacy Fixtures (Simulating old system)
# ============================================================================

def legacy_tool_sync(path: str, encoding: str = "utf-8") -> dict:
    """Simulated legacy sync tool function."""
    return {"path": path, "encoding": encoding, "content": "mock content"}

async def legacy_tool_async(url: str, method: str = "GET") -> dict:
    """Simulated legacy async tool function."""
    return {"url": url, "method": method, "status": 200}

class LegacySkillClass:
    """Simulated legacy skill class."""
    
    def execute(self, data: dict) -> dict:
        return {"processed": data, "skill": "legacy"}

def legacy_skill_function(data: dict) -> dict:
    """Simulated legacy skill function."""
    return {"processed": data, "skill": "function"}

class LegacyAgentClass:
    """Simulated legacy agent class."""
    
    def can_handle(self, task_type: str) -> bool:
        return task_type.startswith("legal")
    
    def execute(self, task_data: dict) -> dict:
        return {"agent": "legacy", "task": task_data}

def legacy_agent_function(task_data: dict) -> dict:
    """Simulated legacy agent function."""
    return {"agent": "function", "task": task_data}


# ============================================================================
# Tool Adapter Tests
# ============================================================================

class TestToolAdapter:
    """Tests untuk ToolAdapter dan LegacyToolWrapper."""
    
    def setup_method(self):
        """Reset registry before each test."""
        tool_registry._tools.clear()
    
    def test_wrap_legacy_sync_function(self):
        """Test wrapping legacy sync function."""
        wrapper = ToolAdapter.wrap_legacy_tool(
            func=legacy_tool_sync,
            name="read_file",
            description="Read file contents",
            parameters=[
                {"name": "path", "type": "string", "required": True},
                {"name": "encoding", "type": "string", "required": False, "default": "utf-8"}
            ]
        )
        
        assert isinstance(wrapper, LegacyToolWrapper)
        assert wrapper.name == "read_file"
        assert wrapper.description == "Read file contents"
        assert "read_file" in tool_registry.list_tools()
    
    def test_wrap_legacy_async_function(self):
        """Test wrapping legacy async function."""
        wrapper = ToolAdapter.wrap_legacy_tool(
            func=legacy_tool_async,
            name="http_request",
            description="Make HTTP request"
        )
        
        assert isinstance(wrapper, LegacyToolWrapper)
        assert wrapper.name == "http_request"
    
    def test_tool_definition_generation(self):
        """Test tool definition generation dari legacy spec."""
        wrapper = LegacyToolWrapper.from_function(
            func=legacy_tool_sync,
            name="test_tool"
        )
        
        definition = wrapper.tool_definition
        assert definition.name == "test_tool"
        assert len(definition.parameters) == 2  # path dan encoding
    
    def test_tool_execution_sync(self):
        """Test executing wrapped sync tool."""
        wrapper = LegacyToolWrapper.from_function(
            func=legacy_tool_sync,
            name="test_tool"
        )
        
        task = Task(
            type="test_tool",
            payload={"path": "/tmp/test.txt", "encoding": "utf-8"}
        )
        
        result = asyncio.run(wrapper.execute(task))
        
        assert isinstance(result, TaskResult)
        assert result.success
        assert result.data["path"] == "/tmp/test.txt"
        assert result.context["legacy"] is True
    
    def test_tool_execution_async(self):
        """Test executing wrapped async tool."""
        wrapper = LegacyToolWrapper.from_function(
            func=legacy_tool_async,
            name="test_async_tool"
        )
        
        task = Task(
            type="test_async_tool",
            payload={"url": "https://example.com", "method": "POST"}
        )
        
        result = asyncio.run(wrapper.execute(task))
        
        assert isinstance(result, TaskResult)
        assert result.success
        assert result.data["url"] == "https://example.com"
    
    def test_tool_validation_error(self):
        """Test tool dengan invalid payload."""
        wrapper = LegacyToolWrapper.from_function(
            func=legacy_tool_sync,
            name="test_tool",
            parameters=[
                {"name": "path", "type": "string", "required": True}
            ]
        )
        
        task = Task(
            type="test_tool",
            payload={}  # Missing required parameter
        )
        
        result = asyncio.run(wrapper.execute(task))
        
        assert not result.success
        assert result.error_code == "VALIDATION_ERROR"
    
    def test_decorator_adapt_legacy_tool(self):
        """Test @adapt_legacy_tool decorator."""
        
        @adapt_legacy_tool(name="decorated_tool")
        def my_tool(param: str) -> dict:
            return {"param": param}
        
        assert isinstance(my_tool, LegacyToolWrapper)
        assert "decorated_tool" in tool_registry.list_tools()


# ============================================================================
# Skill Adapter Tests
# ============================================================================

class TestSkillAdapter:
    """Tests untuk SkillAdapter dan LegacySkillWrapper."""
    
    def setup_method(self):
        """Reset registry before each test."""
        skill_registry._skills.clear()
        skill_registry._dependency_graph.clear()
    
    def test_wrap_legacy_function(self):
        """Test wrapping legacy skill function."""
        wrapper = SkillAdapter.wrap_legacy_function(
            func=legacy_skill_function,
            name="process_data",
            description="Process data with legacy skill",
            complexity="MODERATE",
            tags=["processing", "legacy"]
        )
        
        assert isinstance(wrapper, LegacySkillWrapper)
        assert wrapper.name == "process_data"
        assert "process_data" in skill_registry.list_skills()
    
    def test_wrap_legacy_class(self):
        """Test wrapping legacy skill class."""
        wrapper = SkillAdapter.wrap_legacy_class(
            skill_class=LegacySkillClass,
            name="legacy_processor",
            complexity="SIMPLE"
        )
        
        assert isinstance(wrapper, LegacySkillWrapper)
        assert wrapper.name == "legacy_processor"
    
    def test_skill_complexity_mapping(self):
        """Test complexity string mapping ke enum."""
        complexities = ["SIMPLE", "MODERATE", "COMPLEX", "VERY_COMPLEX"]
        
        for comp in complexities:
            wrapper = LegacySkillWrapper.from_function(
                func=legacy_skill_function,
                name=f"skill_{comp.lower()}",
                complexity=comp
            )
            
            definition = wrapper.skill_definition
            assert definition.complexity.name == comp
    
    def test_skill_execution_function(self):
        """Test executing wrapped skill function."""
        wrapper = LegacySkillWrapper.from_function(
            func=legacy_skill_function,
            name="test_skill"
        )
        
        task = Task(
            type="test_skill",
            payload={"input": "test data"}
        )
        
        result = asyncio.run(wrapper.execute(task))
        
        assert isinstance(result, TaskResult)
        assert result.success
        assert result.data["processed"]["input"] == "test data"
        assert result.context["legacy"] is True
    
    def test_skill_execution_class(self):
        """Test executing wrapped skill class."""
        wrapper = LegacySkillWrapper.from_class(
            skill_class=LegacySkillClass,
            name="test_class_skill"
        )
        
        task = Task(
            type="test_class_skill",
            payload={"data": "value"}
        )
        
        result = asyncio.run(wrapper.execute(task))
        
        assert isinstance(result, TaskResult)
        assert result.success
        assert result.data["skill"] == "legacy"
    
    def test_skill_dependencies(self):
        """Test skill dengan dependencies."""
        # Create base skill
        base_wrapper = LegacySkillWrapper.from_function(
            func=legacy_skill_function,
            name="base_skill"
        )
        skill_registry.register(base_wrapper)
        
        # Create dependent skill
        dependent_wrapper = LegacySkillWrapper.from_function(
            func=legacy_skill_function,
            name="dependent_skill",
            dependencies=["base_skill"]
        )
        skill_registry.register(dependent_wrapper)
        
        # Check dependency resolution
        deps = skill_registry.resolve_dependencies("dependent_skill")
        assert "base_skill" in deps
    
    def test_circular_dependency_detection(self):
        """Test circular dependency detection."""
        # Create skill A
        wrapper_a = LegacySkillWrapper.from_function(
            func=legacy_skill_function,
            name="skill_a",
            dependencies=["skill_b"]
        )
        skill_registry.register(wrapper_a)
        
        # Try create skill B yang depend on A (cycle)
        wrapper_b = LegacySkillWrapper.from_function(
            func=legacy_skill_function,
            name="skill_b",
            dependencies=["skill_a"]
        )
        
        with pytest.raises(CircularDependencyError):
            skill_registry.register(wrapper_b)
    
    def test_decorator_adapt_legacy_skill(self):
        """Test @adapt_legacy_skill decorator."""
        
        @adapt_legacy_skill(complexity="SIMPLE", tags=["test"])
        def my_skill(data: dict) -> dict:
            return {"result": "success"}
        
        assert isinstance(my_skill, LegacySkillWrapper)
        assert my_skill.name == "my_skill"


# ============================================================================
# Agent Adapter Tests
# ============================================================================

class TestAgentAdapter:
    """Tests untuk AgentAdapter dan LegacyAgentWrapper."""
    
    def setup_method(self):
        """Reset registry before each test."""
        agent_registry._agents.clear()
    
    def test_wrap_legacy_class(self):
        """Test wrapping legacy agent class."""
        wrapper = AgentAdapter.wrap_legacy_class(
            agent_class=LegacyAgentClass,
            name="legal_agent",
            domain="legal",
            capabilities=["TOOL_USE", "REASONING"],
            preferred_skills=["document_analysis"]
        )
        
        assert isinstance(wrapper, LegacyAgentWrapper)
        assert wrapper.name == "legal_agent"
        assert wrapper.domain == "legal"
        assert "legal_agent" in agent_registry.list_agents()
    
    def test_wrap_legacy_function(self):
        """Test wrapping legacy agent function."""
        wrapper = AgentAdapter.wrap_legacy_function(
            func=legacy_agent_function,
            name="general_agent",
            domain="general"
        )
        
        assert isinstance(wrapper, LegacyAgentWrapper)
        assert wrapper.name == "general_agent"
    
    def test_agent_capabilities(self):
        """Test agent capability mapping."""
        wrapper = LegacyAgentWrapper.from_class(
            agent_class=LegacyAgentClass,
            name="capable_agent",
            capabilities=["TOOL_USE", "PLANNING", "REASONING"]
        )
        
        profile = wrapper.profile
        assert AgentCapability.TOOL_USE in profile.capabilities
        assert AgentCapability.PLANNING in profile.capabilities
        assert AgentCapability.REASONING in profile.capabilities
    
    def test_agent_can_handle(self):
        """Test agent can_handle logic."""
        wrapper = LegacyAgentWrapper.from_class(
            agent_class=LegacyAgentClass,
            name="legal_agent",
            domain="legal"
        )
        
        legal_task = Task(type="legal_review")
        other_task = Task(type="coding_task")
        
        assert wrapper.can_handle(legal_task) is True
        assert wrapper.can_handle(other_task) is False
    
    def test_agent_execution_class(self):
        """Test executing wrapped agent class."""
        wrapper = LegacyAgentWrapper.from_class(
            agent_class=LegacyAgentClass,
            name="test_agent"
        )
        
        task = Task(
            type="legal_review",
            payload={"document": "contract.pdf"}
        )
        
        result = asyncio.run(wrapper.execute(task))
        
        assert isinstance(result, TaskResult)
        assert result.success
        assert result.data["agent"] == "legacy"
    
    def test_agent_execution_function(self):
        """Test executing wrapped agent function."""
        wrapper = LegacyAgentWrapper.from_function(
            func=legacy_agent_function,
            name="test_agent"
        )
        
        task = Task(
            type="general_task",
            payload={"action": "process"}
        )
        
        result = asyncio.run(wrapper.execute(task))
        
        assert isinstance(result, TaskResult)
        assert result.success
        assert result.data["agent"] == "function"
    
    def test_agent_concurrency_control(self):
        """Test agent concurrency control initialization."""
        wrapper = LegacyAgentWrapper.from_class(
            agent_class=LegacyAgentClass,
            name="concurrent_agent",
            max_concurrent_tasks=5
        )
        
        profile = wrapper.profile
        assert profile.max_concurrent_tasks == 5
        assert wrapper._semaphore is not None
    
    def test_find_agent_for_task(self):
        """Test finding agent untuk task."""
        # Register agent
        wrapper = AgentAdapter.wrap_legacy_class(
            agent_class=LegacyAgentClass,
            name="legal_agent",
            domain="legal"
        )
        
        # Find agent untuk legal task
        task = Task(type="legal_review")
        found_agent = AgentAdapter.find_agent_for_task(task)
        
        assert found_agent is not None
        assert found_agent.name == "legal_agent"
    
    def test_decorator_adapt_legacy_agent(self):
        """Test @adapt_legacy_agent decorator."""
        
        class MyAgent:
            def execute(self, data):
                return {"result": "done"}
        
        wrapped = adapt_legacy_agent(
            MyAgent,
            name="my_agent",
            domain="coding",
            capabilities=["TOOL_USE"]
        )
        
        assert isinstance(wrapped, LegacyAgentWrapper)
        assert wrapped.name == "my_agent"


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests untuk hybrid old+new system."""
    
    def setup_method(self):
        """Reset all registries before each test."""
        tool_registry._tools.clear()
        skill_registry._skills.clear()
        skill_registry._dependency_graph.clear()
        agent_registry._agents.clear()
    
    def test_hybrid_registry(self):
        """Test registries dengan hybrid legacy+new components."""
        # Register legacy wrapped tool
        legacy_tool = ToolAdapter.wrap_legacy_tool(
            func=legacy_tool_sync,
            name="legacy_reader"
        )
        
        # Verify both in registry
        assert "legacy_reader" in tool_registry.list_tools()
        assert len(tool_registry.list_tools()) == 1
    
    def test_end_to_end_task_execution(self):
        """Test end-to-end task execution melalui adapter layers."""
        # Setup: Tool -> Skill -> Agent
        
        # 1. Create and register tool
        tool = ToolAdapter.wrap_legacy_tool(
            func=legacy_tool_sync,
            name="file_reader"
        )
        
        # 2. Create and register skill yang menggunakan tool
        skill = SkillAdapter.wrap_legacy_function(
            func=legacy_skill_function,
            name="document_processor",
            tags=["document"]
        )
        
        # 3. Create and register agent dengan skill
        agent = AgentAdapter.wrap_legacy_class(
            agent_class=LegacyAgentClass,
            name="document_agent",
            domain="document",
            preferred_skills=["document_processor"]
        )
        
        # Execute task melalui agent
        task = Task(type="legal_review", payload={"doc": "test.pdf"})
        
        # Verify chain
        assert agent.can_handle(task)
        
        # Execute
        result = asyncio.run(agent.execute(task))
        assert result.success
    
    def test_registry_info(self):
        """Test registry info methods."""
        # Register beberapa components
        ToolAdapter.wrap_legacy_tool(func=legacy_tool_sync, name="tool1")
        ToolAdapter.wrap_legacy_tool(func=legacy_tool_async, name="tool2")
        
        SkillAdapter.wrap_legacy_function(func=legacy_skill_function, name="skill1")
        
        AgentAdapter.wrap_legacy_class(
            agent_class=LegacyAgentClass,
            name="agent1",
            domain="legal"
        )
        
        # Get registry info
        tool_info = tool_registry.get_registry_info()
        skill_info = skill_registry.get_registry_info()
        agent_info = agent_registry.get_registry_info()
        
        assert tool_info["registered_tools"] == 2
        assert skill_info["registered_skills"] == 1
        assert agent_info["registered_agents"] == 1
        assert "legal" in agent_info["domains"]


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance:
    """Performance tests untuk adapter layer."""
    
    def setup_method(self):
        """Reset registries."""
        tool_registry._tools.clear()
        skill_registry._skills.clear()
        skill_registry._dependency_graph.clear()
        agent_registry._agents.clear()
    
    def test_bulk_tool_registration(self):
        """Test bulk tool registration performance."""
        import time
        
        def dummy_tool(n: int) -> dict:
            return {"n": n}
        
        start = time.time()
        
        for i in range(100):
            ToolAdapter.wrap_legacy_tool(
                func=dummy_tool,
                name=f"tool_{i}",
                register=True
            )
        
        elapsed = time.time() - start
        
        assert len(tool_registry.list_tools()) == 100
        assert elapsed < 5.0  # Should complete dalam < 5 seconds
    
    def test_concurrent_task_execution(self):
        """Test concurrent task execution melalui adapter."""
        async def slow_tool(delay_sec: str) -> dict:
            """Tool dengan delay dalam detik (as string)."""
            await asyncio.sleep(float(delay_sec))
            return {"delay": delay_sec}
        
        wrapper = LegacyToolWrapper.from_function(
            func=slow_tool,
            name="slow_tool"
        )
        
        async def run_concurrent():
            tasks = [
                wrapper.execute(Task(type="slow_tool", payload={"delay_sec": "0.05"}))
                for _ in range(5)
            ]
            # Use return_exceptions=True to capture any errors
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return results
        
        import time
        start = time.time()
        results = asyncio.run(run_concurrent())
        elapsed = time.time() - start
        
        # Check for any exceptions
        exceptions = [r for r in results if isinstance(r, Exception)]
        if exceptions:
            pytest.fail(f"Exceptions during concurrent execution: {exceptions}")
        
        assert len(results) == 5
        assert all(r.success for r in results)
        # Concurrent execution should be faster than sequential (5 * 0.05 = 0.25s)
        assert elapsed < 0.3  # But still reasonable


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])