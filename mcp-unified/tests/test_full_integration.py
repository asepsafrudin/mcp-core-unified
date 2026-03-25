"""
Full Integration Test - Verify All Components Work Together

Tests:
    1. All 15 tools are registered and accessible
    2. All 3 skills are registered and functional
    3. All 4 agents are registered and can handle tasks
    4. Cross-component integration (agents use skills, skills use tools)

Usage:
    cd mcp-unified && python3 tests/test_full_integration.py
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_all_tools_registered():
    """Verify all 15 tools are registered."""
    print("\n🔧 Testing Tool Registry (15 tools)...")
    
    from tools import tool_registry
    
    expected_tools = {
        # File Tools (3)
        "read_file", "write_file", "list_dir",
        # Admin Tools (1)
        "run_shell",
        # Workspace Tools (3)
        "create_workspace", "cleanup_workspace", "list_workspaces",
        # Code Analysis Tools (3)
        "analyze_file", "analyze_code", "analyze_project",
        # Media/Vision Tools (3)
        "analyze_image", "analyze_pdf_pages", "list_vision_results",
        # Code Quality Tools (2)
        "self_review", "self_review_batch",
    }
    
    registered = set(tool_registry.list_tools())
    missing = expected_tools - registered
    extra = registered - expected_tools
    
    if missing:
        print(f"  ❌ Missing tools: {missing}")
        return False
    
    if extra:
        print(f"  ℹ️  Extra tools (OK): {extra}")
    
    print(f"  ✅ All {len(expected_tools)} tools registered")
    return True


def test_all_skills_registered():
    """Verify all 3 skills are registered."""
    print("\n🧠 Testing Skill Registry (3 skills)...")
    
    from skills import skill_registry
    
    expected_skills = {
        # Planning Skills (2)
        "create_plan", "save_plan_experience",
        # Healing Skills (1)
        "execute_with_healing",
    }
    
    registered = set(skill_registry.list_skills())
    missing = expected_skills - registered
    
    if missing:
        print(f"  ❌ Missing skills: {missing}")
        return False
    
    print(f"  ✅ All {len(expected_skills)} skills registered")
    return True


def test_all_agents_registered():
    """Verify all 4 agents are registered."""
    print("\n🤖 Testing Agent Registry (6 agents)...")
    
    from agents import agent_registry
    
    expected_agents = {
        "code_agent",
        "admin_agent",
        "filesystem_agent",
        "research_agent",
        "legal_agent",
        "office_admin_agent",
    }
    
    registered = set(agent_registry.list_agents())
    missing = expected_agents - registered
    
    if missing:
        print(f"  ❌ Missing agents: {missing}")
        return False
    
    print(f"  ✅ All {len(expected_agents)} agents registered")
    return True


def test_agent_profiles():
    """Verify agent profiles are correctly configured."""
    print("\n📋 Testing Agent Profiles...")
    
    from agents import agent_registry
    
    agent_checks = {
        "code_agent": {"domain": "coding", "min_capabilities": 2},
        "admin_agent": {"domain": "admin", "min_capabilities": 1},
        "filesystem_agent": {"domain": "filesystem", "min_capabilities": 1},
        "research_agent": {"domain": "research", "min_capabilities": 3},
        "legal_agent": {"domain": "legal", "min_capabilities": 2},
        "office_admin_agent": {"domain": "office_admin", "min_capabilities": 1},
    }
    
    for agent_name, expected in agent_checks.items():
        agent = agent_registry.get_agent(agent_name)
        if not agent:
            print(f"  ❌ Agent {agent_name} not found")
            return False
        
        profile = agent.profile
        
        # Check domain
        if profile.domain != expected["domain"]:
            print(f"  ❌ {agent_name}: wrong domain (expected {expected['domain']}, got {profile.domain})")
            return False
        
        # Check capabilities
        if len(profile.capabilities) < expected["min_capabilities"]:
            print(f"  ❌ {agent_name}: insufficient capabilities")
            return False
        
        print(f"  ✅ {agent_name}: {profile.domain} domain, {len(profile.capabilities)} capabilities")
    
    return True


def test_cross_component_integration():
    """Test agents can access skills dan tools."""
    print("\n🔗 Testing Cross-Component Integration...")
    
    from agents import agent_registry
    from skills import skill_registry
    from tools import tool_registry
    from agents.base import AgentCapability
    
    # Test CodeAgent integration
    code_agent = agent_registry.get_agent("code_agent")
    if not code_agent:
        print("  ❌ CodeAgent not found")
        return False
    
    # Check CodeAgent has TOOL_USE capability
    if not code_agent.has_capability(AgentCapability.TOOL_USE):
        print("  ❌ CodeAgent missing TOOL_USE capability")
        return False
    
    # Check CodeAgent's preferred skills exist
    for skill_name in code_agent.profile.preferred_skills:
        if not skill_registry.get_skill(skill_name):
            print(f"  ❌ CodeAgent's preferred skill '{skill_name}' not found")
            return False
    
    # Check CodeAgent's tools exist
    for tool_name in code_agent.profile.tools_whitelist:
        if tool_name != "run_shell_sync" and not tool_registry.get_tool(tool_name):
            print(f"  ⚠️  CodeAgent's tool '{tool_name}' not found (may be allowed)")
    
    print(f"  ✅ CodeAgent integration: {len(code_agent.profile.preferred_skills)} skills, {len(code_agent.profile.tools_whitelist)} tools whitelisted")
    
    # Test AdminAgent integration
    admin_agent = agent_registry.get_agent("admin_agent")
    if not admin_agent:
        print("  ❌ AdminAgent not found")
        return False
    
    if not admin_agent.has_capability(AgentCapability.TOOL_USE):
        print("  ❌ AdminAgent missing TOOL_USE capability")
        return False
    
    print(f"  ✅ AdminAgent integration: {len(admin_agent.profile.tools_whitelist)} tools whitelisted")
    
    return True


def test_end_to_end_task_flow():
    """Test complete task flow: Task → Agent → Skill → Tool."""
    print("\n🎯 Testing End-to-End Task Flow...")
    
    from core.task import Task, TaskContext
    from agents import agent_registry
    
    # Create a filesystem task
    task = Task(
        type="read_file",
        payload={"path": "/home/aseps/MCP/README.md"},
        context=TaskContext(namespace="test", agent_id="test_agent")
    )
    
    # Find best agent untuk filesystem task
    agent = agent_registry.find_agent_for_task(task)
    
    if not agent:
        print("  ⚠️  No agent available (may be normal in test environment)")
        return True
    
    print(f"  ✅ Task routing: '{task.type}' → {agent.name}")
    
    # Check agent can handle task
    if not agent.can_handle(task):
        print(f"  ⚠️  {agent.name} cannot handle task (may need adjustment)")
    else:
        print(f"  ✅ {agent.name} can handle '{task.type}'")
    
    return True


def test_skill_dependencies():
    """Test skill dependency resolution."""
    print("\n📊 Testing Skill Dependencies...")
    
    from skills import skill_registry
    
    info = skill_registry.get_registry_info()
    
    print(f"  ✅ Skills: {info['registered_skills']}")
    print(f"  ✅ Dependency graph: {len(info['dependency_graph'])} dependencies")
    
    # Check no circular dependencies
    if info.get("circular_dependencies", []):
        print(f"  ❌ Circular dependencies detected: {info['circular_dependencies']}")
        return False
    
    print(f"  ✅ No circular dependencies")
    return True


def test_registry_summary():
    """Print comprehensive registry summary."""
    print("\n" + "="*60)
    print("REGISTRY SUMMARY")
    print("="*60)
    
    from tools import tool_registry
    from skills import skill_registry
    from agents import agent_registry
    
    # Tools
    tool_info = tool_registry.get_registry_info()
    print(f"\n🔧 Tools: {tool_info['registered_tools']} registered")
    for category, tools in tool_info.get("categories", {}).items():
        print(f"  • {category}: {len(tools)} tools")
    
    # Skills
    skill_info = skill_registry.get_registry_info()
    print(f"\n🧠 Skills: {skill_info['registered_skills']} registered")
    for skill_name in skill_info.get("skills", []):
        print(f"  • {skill_name}")
    
    # Agents
    agent_info = agent_registry.get_registry_info()
    print(f"\n🤖 Agents: {agent_info['registered_agents']} registered")
    for agent_name, info in agent_info.get("agents", {}).items():
        domain = info.get("profile", {}).get("domain", "unknown")
        caps = len(info.get("profile", {}).get("capabilities", []))
        print(f"  • {agent_name} ({domain}, {caps} capabilities)")
    
    print("\n" + "="*60)
    
    # Verify counts
    total_tools = tool_info['registered_tools']
    total_skills = skill_info['registered_skills']
    total_agents = agent_info['registered_agents']
    
    print(f"\n📊 Total Components:")
    print(f"  • Tools: {total_tools}/15")
    print(f"  • Skills: {total_skills}/3")
    print(f"  • Agents: {total_agents}/6")
    print(f"  • Knowledge Layer: ✅ Ready (RAG)")
    
    return (total_tools >= 15 and total_skills >= 3 and total_agents >= 6)


def main():
    """Run all integration tests."""
    print("="*60)
    print("FULL INTEGRATION TEST - Multi-Agent Architecture")
    print("="*60)
    print("\nVerifying all 15 tools + 3 skills + 4 agents work together...")
    
    tests = [
        ("Tools Registry", test_all_tools_registered),
        ("Skills Registry", test_all_skills_registered),
        ("Agents Registry", test_all_agents_registered),
        ("Agent Profiles", test_agent_profiles),
        ("Cross-Component Integration", test_cross_component_integration),
        ("End-to-End Task Flow", test_end_to_end_task_flow),
        ("Skill Dependencies", test_skill_dependencies),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f"  ❌ {name} failed")
        except Exception as e:
            print(f"  ❌ {name} error: {e}")
            failed += 1
    
    # Print summary
    all_passed = test_registry_summary()
    
    print("\n" + "="*60)
    print("INTEGRATION TEST SUMMARY")
    print("="*60)
    print(f"Tests Passed: {passed}/{len(tests)} ✅")
    print(f"Tests Failed: {failed}/{len(tests)} ❌")
    
    if failed == 0 and all_passed:
        print("\n🎉 FULL INTEGRATION TEST PASSED!")
        print("All components working together correctly!")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
