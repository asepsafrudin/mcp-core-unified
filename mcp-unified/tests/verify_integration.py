import os
"""
Integration Verification Script

Verifies bahwa Multi-Agent Architecture dengan Adapter Layer berfungsi dengan baik:
1. Semua base classes dapat di-import dan digunakan
2. Adapter layer dapat wrap legacy components
3. Registries dapat menangani hybrid components
4. Task execution pipeline berfungsi end-to-end

Usage:
    cd mcp-unified && python tests/verify_integration.py
"""

import asyncio
import sys
import time
from pathlib import Path
from typing import Dict, Any

import pytest

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================================
# Pytest Fixtures
# ============================================================================

@pytest.fixture
def verifier():
    """Fixture untuk menyediakan IntegrationVerifier."""
    return IntegrationVerifier()


# ============================================================================
# Verification Results
# ============================================================================

class VerificationResult:
    """Hasil verifikasi untuk satu test case."""
    
    def __init__(self, name: str, passed: bool, message: str = "", duration_ms: float = 0):
        self.name = name
        self.passed = passed
        self.message = message
        self.duration_ms = duration_ms
    
    def __str__(self):
        status = "✅ PASS" if self.passed else "❌ FAIL"
        return f"{status} | {self.name} | {self.duration_ms:.2f}ms"


class IntegrationVerifier:
    """Main verification runner."""
    
    def __init__(self):
        self.results: list[VerificationResult] = []
        self.start_time = time.time()
    
    def add_result(self, result: VerificationResult):
        """Add verification result."""
        self.results.append(result)
        print(f"  {result}")
    
    def print_summary(self):
        """Print verification summary."""
        elapsed = (time.time() - self.start_time) * 1000
        
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        
        print("\n" + "=" * 60)
        print("VERIFICATION SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {len(self.results)}")
        print(f"Passed: {passed} ✅")
        print(f"Failed: {failed} ❌")
        print(f"Total Time: {elapsed:.2f}ms")
        print("=" * 60)
        
        if failed > 0:
            print("\nFailed Tests:")
            for r in self.results:
                if not r.passed:
                    print(f"  ❌ {r.name}: {r.message}")
        
        return failed == 0


# ============================================================================
# Test Functions
# ============================================================================

def test_imports(verifier: IntegrationVerifier):
    """Test bahwa semua modules dapat di-import."""
    name = "Module Imports"
    start = time.time()
    
    try:
        from core.task import Task, TaskResult, TaskPriority, TaskContext
        from tools.base import BaseTool, ToolDefinition, ToolParameter, tool_registry
        from skills.base import BaseSkill, SkillDefinition, SkillComplexity, skill_registry
        from agents.base import BaseAgent, AgentProfile, AgentCapability, agent_registry
        
        from adapters.tool_adapter import ToolAdapter, LegacyToolWrapper, adapt_legacy_tool
        from adapters.skill_adapter import SkillAdapter, LegacySkillWrapper, adapt_legacy_skill
        from adapters.agent_adapter import AgentAdapter, LegacyAgentWrapper, adapt_legacy_agent
        
        duration = (time.time() - start) * 1000
        verifier.add_result(VerificationResult(name, True, "All imports successful", duration))
        return True
        
    except Exception as e:
        duration = (time.time() - start) * 1000
        verifier.add_result(VerificationResult(name, False, str(e), duration))
        return False


def test_task_schema(verifier: IntegrationVerifier):
    """Test Task schema functionality."""
    name = "Task Schema"
    start = time.time()
    
    try:
        from core.task import Task, TaskResult, TaskPriority, TaskContext
        
        # Create task
        task = Task(
            type="test_task",
            payload={"key": "value"},
            context=TaskContext(namespace="test", agent_id="agent1"),
            priority=TaskPriority.HIGH
        )
        
        # Verify serialization
        task_dict = task.to_dict()
        assert task_dict["type"] == "test_task"
        assert task_dict["payload"]["key"] == "value"
        
        # Test result factory
        result = TaskResult.success_result(task_id=task.id, data={"result": "ok"})
        assert result.success is True
        
        result_fail = TaskResult.failure_result(task_id=task.id, error="test error")
        assert result_fail.success is False
        
        duration = (time.time() - start) * 1000
        verifier.add_result(VerificationResult(name, True, "Task schema working", duration))
        return True
        
    except Exception as e:
        duration = (time.time() - start) * 1000
        verifier.add_result(VerificationResult(name, False, str(e), duration))
        return False


def test_tool_adapter(verifier: IntegrationVerifier):
    """Test ToolAdapter functionality."""
    name = "Tool Adapter"
    start = time.time()
    
    try:
        from adapters.tool_adapter import ToolAdapter, LegacyToolWrapper
        from tools.base import tool_registry
        from core.task import Task
        
        # Clear registry
        tool_registry._tools.clear()
        
        # Define legacy function
        def legacy_read_file(path: str) -> dict:
            return {"path": path, "content": "test"}
        
        # Wrap it
        wrapper = ToolAdapter.wrap_legacy_tool(
            func=legacy_read_file,
            name="read_file",
            description="Read a file"
        )
        
        assert isinstance(wrapper, LegacyToolWrapper)
        assert wrapper.name == "read_file"
        assert "read_file" in tool_registry.list_tools()
        
        # Test execution
        task = Task(type="read_file", payload={"path": "/test.txt"})
        result = asyncio.run(wrapper.execute(task))
        
        assert result.success
        assert result.data["path"] == "/test.txt"
        
        duration = (time.time() - start) * 1000
        verifier.add_result(VerificationResult(name, True, "Tool adapter working", duration))
        return True
        
    except Exception as e:
        duration = (time.time() - start) * 1000
        verifier.add_result(VerificationResult(name, False, str(e), duration))
        return False


def test_skill_adapter(verifier: IntegrationVerifier):
    """Test SkillAdapter functionality."""
    name = "Skill Adapter"
    start = time.time()
    
    try:
        from adapters.skill_adapter import SkillAdapter, LegacySkillWrapper
        from skills.base import skill_registry, SkillComplexity
        from core.task import Task
        
        # Clear registry
        skill_registry._skills.clear()
        skill_registry._dependency_graph.clear()
        
        # Define legacy skill
        def legacy_analyze(data: dict) -> dict:
            return {"analysis": "completed", "input": data}
        
        # Wrap it
        wrapper = SkillAdapter.wrap_legacy_function(
            func=legacy_analyze,
            name="analyzer",
            complexity="MODERATE",
            tags=["analysis"]
        )
        
        assert isinstance(wrapper, LegacySkillWrapper)
        assert wrapper.name == "analyzer"
        assert "analyzer" in skill_registry.list_skills()
        
        # Test complexity
        assert wrapper.skill_definition.complexity == SkillComplexity.MODERATE
        
        # Test execution
        task = Task(type="analyzer", payload={"text": "sample"})
        result = asyncio.run(wrapper.execute(task))
        
        assert result.success
        
        duration = (time.time() - start) * 1000
        verifier.add_result(VerificationResult(name, True, "Skill adapter working", duration))
        return True
        
    except Exception as e:
        duration = (time.time() - start) * 1000
        verifier.add_result(VerificationResult(name, False, str(e), duration))
        return False


def test_agent_adapter(verifier: IntegrationVerifier):
    """Test AgentAdapter functionality."""
    name = "Agent Adapter"
    start = time.time()
    
    try:
        from adapters.agent_adapter import AgentAdapter, LegacyAgentWrapper
        from agents.base import agent_registry, AgentCapability
        from core.task import Task
        
        # Clear registry
        agent_registry._agents.clear()
        
        # Define legacy agent class
        class LegacyLegalAgent:
            def can_handle(self, task_type: str) -> bool:
                return task_type.startswith("legal")
            
            def execute(self, task_data: dict) -> dict:
                return {"reviewed": True, "data": task_data}
        
        # Wrap it
        wrapper = AgentAdapter.wrap_legacy_class(
            agent_class=LegacyLegalAgent,
            name="legal_agent",
            domain="legal",
            capabilities=["TOOL_USE", "REASONING"]
        )
        
        assert isinstance(wrapper, LegacyAgentWrapper)
        assert wrapper.name == "legal_agent"
        assert wrapper.domain == "legal"
        assert "legal_agent" in agent_registry.list_agents()
        
        # Test capabilities
        assert AgentCapability.TOOL_USE in wrapper.profile.capabilities
        
        # Test can_handle
        legal_task = Task(type="legal_review")
        assert wrapper.can_handle(legal_task) is True
        
        # Test execution
        result = asyncio.run(wrapper.execute(legal_task))
        assert result.success
        
        duration = (time.time() - start) * 1000
        verifier.add_result(VerificationResult(name, True, "Agent adapter working", duration))
        return True
        
    except Exception as e:
        duration = (time.time() - start) * 1000
        verifier.add_result(VerificationResult(name, False, str(e), duration))
        return False


def test_circular_dependency_detection(verifier: IntegrationVerifier):
    """Test circular dependency detection."""
    name = "Circular Dependency Detection"
    start = time.time()
    
    try:
        from adapters.skill_adapter import SkillAdapter, LegacySkillWrapper
        from skills.base import skill_registry, CircularDependencyError
        
        # Clear registry
        skill_registry._skills.clear()
        skill_registry._dependency_graph.clear()
        
        # Create skill A that depends on B
        def skill_a_func(data: dict) -> dict:
            return {"skill": "a"}
        
        wrapper_a = LegacySkillWrapper.from_function(
            func=skill_a_func,
            name="skill_a",
            dependencies=["skill_b"]
        )
        skill_registry.register(wrapper_a)
        
        # Try to create skill B that depends on A (cycle)
        def skill_b_func(data: dict) -> dict:
            return {"skill": "b"}
        
        wrapper_b = LegacySkillWrapper.from_function(
            func=skill_b_func,
            name="skill_b",
            dependencies=["skill_a"]
        )
        
        try:
            skill_registry.register(wrapper_b)
            # Should not reach here
            duration = (time.time() - start) * 1000
            verifier.add_result(VerificationResult(name, False, "Cycle not detected!", duration))
            return False
        except CircularDependencyError:
            # Expected
            duration = (time.time() - start) * 1000
            verifier.add_result(VerificationResult(name, True, "Cycle detected correctly", duration))
            return True
        
    except Exception as e:
        duration = (time.time() - start) * 1000
        verifier.add_result(VerificationResult(name, False, str(e), duration))
        return False


def test_end_to_end_pipeline(verifier: IntegrationVerifier):
    """Test end-to-end task execution pipeline."""
    name = "End-to-End Pipeline"
    start = time.time()
    
    try:
        from adapters.tool_adapter import ToolAdapter
        from adapters.skill_adapter import SkillAdapter
        from adapters.agent_adapter import AgentAdapter
        from tools.base import tool_registry
        from skills.base import skill_registry
        from agents.base import agent_registry
        from core.task import Task
        
        # Clear registries
        tool_registry._tools.clear()
        skill_registry._skills.clear()
        skill_registry._dependency_graph.clear()
        agent_registry._agents.clear()
        
        # 1. Create tool
        def file_tool(path: str) -> dict:
            return {"file": path, "size": 100}
        
        tool = ToolAdapter.wrap_legacy_tool(
            func=file_tool,
            name="file_reader"
        )
        
        # 2. Create skill
        def process_skill(data: dict) -> dict:
            return {"processed": data}
        
        skill = SkillAdapter.wrap_legacy_function(
            func=process_skill,
            name="document_processor",
            tags=["document"]
        )
        
        # 3. Create agent
        class DocumentAgent:
            def can_handle(self, task_type: str) -> bool:
                return task_type.startswith("document")
            
            def execute(self, task_data: dict) -> dict:
                return {"agent_result": task_data}
        
        agent = AgentAdapter.wrap_legacy_class(
            agent_class=DocumentAgent,
            name="doc_agent",
            domain="document",
            preferred_skills=["document_processor"]
        )
        
        # 4. Execute task through agent
        task = Task(type="document_process", payload={"doc": "test.pdf"})
        
        assert agent.can_handle(task)
        
        result = asyncio.run(agent.execute(task))
        assert result.success
        
        # 5. Verify registries
        assert len(tool_registry.list_tools()) == 1
        assert len(skill_registry.list_skills()) == 1
        assert len(agent_registry.list_agents()) == 1
        
        duration = (time.time() - start) * 1000
        verifier.add_result(VerificationResult(name, True, "Pipeline working end-to-end", duration))
        return True
        
    except Exception as e:
        duration = (time.time() - start) * 1000
        verifier.add_result(VerificationResult(name, False, str(e), duration))
        return False


def test_concurrency_control(verifier: IntegrationVerifier):
    """Test agent concurrency control."""
    name = "Concurrency Control"
    start = time.time()
    
    try:
        from adapters.agent_adapter import LegacyAgentWrapper
        from agents.base import agent_registry
        
        # Clear registry
        agent_registry._agents.clear()
        
        # Create agent dengan low concurrency limit
        class TestAgent:
            def execute(self, task_data: dict) -> dict:
                return {"result": task_data}
        
        wrapper = LegacyAgentWrapper.from_class(
            agent_class=TestAgent,
            name=os.getenv("NAME", "concurrent_test_agent" if not os.getenv("CI") else "DUMMY"),
            max_concurrent_tasks=2
        )
        
        # Access profile to trigger initialization
        profile = wrapper.profile
        
        # Verify semaphore initialized
        assert wrapper._semaphore is not None, "Semaphore should be initialized"
        assert profile.max_concurrent_tasks == 2, f"Expected 2, got {profile.max_concurrent_tasks}"
        
        # Test availability
        assert wrapper.is_available() is True, "Agent should be available"
        
        duration = (time.time() - start) * 1000
        verifier.add_result(VerificationResult(name, True, "Concurrency control working", duration))
        return True
        
    except Exception as e:
        duration = (time.time() - start) * 1000
        verifier.add_result(VerificationResult(name, False, str(e), duration))
        return False


def test_registry_discovery(verifier: IntegrationVerifier):
    """Test registry discovery and info methods."""
    name = "Registry Discovery"
    start = time.time()
    
    try:
        from adapters.tool_adapter import ToolAdapter
        from adapters.skill_adapter import SkillAdapter
        from adapters.agent_adapter import AgentAdapter
        from tools.base import tool_registry
        from skills.base import skill_registry
        from agents.base import agent_registry
        
        # Clear registries
        tool_registry._tools.clear()
        skill_registry._skills.clear()
        skill_registry._dependency_graph.clear()
        agent_registry._agents.clear()
        
        # Register multiple components
        def tool1() -> dict:
            return {}
        
        def tool2() -> dict:
            return {}
        
        def skill1() -> dict:
            return {}
        
        class Agent1:
            def execute(self, data): return {}
        
        ToolAdapter.wrap_legacy_tool(func=tool1, name="tool1")
        ToolAdapter.wrap_legacy_tool(func=tool2, name="tool2")
        SkillAdapter.wrap_legacy_function(func=skill1, name="skill1")
        AgentAdapter.wrap_legacy_class(agent_class=Agent1, name="agent1", domain="test")
        
        # Get registry info
        tool_info = tool_registry.get_registry_info()
        skill_info = skill_registry.get_registry_info()
        agent_info = agent_registry.get_registry_info()
        
        assert tool_info["registered_tools"] == 2
        assert skill_info["registered_skills"] == 1
        assert agent_info["registered_agents"] == 1
        assert "test" in agent_info["domains"]
        
        duration = (time.time() - start) * 1000
        verifier.add_result(VerificationResult(name, True, "Registry discovery working", duration))
        return True
        
    except Exception as e:
        duration = (time.time() - start) * 1000
        verifier.add_result(VerificationResult(name, False, str(e), duration))
        return False


# ============================================================================
# Main
# ============================================================================

def main():
    """Run all verification tests."""
    print("=" * 60)
    print("MCP MULTI-AGENT ARCHITECTURE - INTEGRATION VERIFICATION")
    print("=" * 60)
    print()
    
    verifier = IntegrationVerifier()
    
    # Run all tests
    print("Running verification tests...\n")
    
    tests = [
        test_imports,
        test_task_schema,
        test_tool_adapter,
        test_skill_adapter,
        test_agent_adapter,
        test_circular_dependency_detection,
        test_end_to_end_pipeline,
        test_concurrency_control,
        test_registry_discovery,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test(verifier):
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ❌ UNEXPECTED ERROR in {test.__name__}: {e}")
            failed += 1
    
    # Print summary
    success = verifier.print_summary()
    
    if success:
        print("\n🎉 All verifications passed! System ready for migration.")
        return 0
    else:
        print("\n⚠️  Some verifications failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())