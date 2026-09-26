"""
Test Suite for MAF Phase 2 (Subtasks 132-C & 132-D)
Verifies bidirectional MCP agent server exposure (agent.as_mcp_server())
and MAFCodeAgent task execution capabilities.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure repo root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.agent_framework.bidirectional_server import build_specialist_agent
from core.agent_framework.code_agent import MAFCodeAgent


def test_bidirectional_mcp_exposure():
    print("Testing Bidirectional MCP Exposure (Subtask 132-C)...")
    
    # 1. Build Legal Specialist Agent
    legal_agent = build_specialist_agent("legal")
    assert legal_agent is not None, "Failed to build LegalSpecialistAgent"
    assert legal_agent.name == "LegalSpecialistAgent"
    print("  ✓ LegalSpecialistAgent built successfully")

    # 2. Convert to MCP Server via agent.as_mcp_server()
    mcp_server = legal_agent.as_mcp_server(
        server_name="maf-legal-agent",
        version="1.0.0",
        instructions=legal_agent.description,
    )
    assert mcp_server is not None, "Failed to expose agent as MCP Server"
    assert hasattr(mcp_server, "create_initialization_options")
    print("  ✓ agent.as_mcp_server() successfully created native MCP server")

    # 3. Verify server initialization options
    init_opts = mcp_server.create_initialization_options()
    assert init_opts is not None
    print(f"  ✓ Server name in protocol: {mcp_server.name}")


def test_code_agent_capabilities():
    print("Testing MAFCodeAgent Capabilities (Subtask 132-D)...")
    code_agent = MAFCodeAgent()

    # 1. Test safe command execution
    res = code_agent._execute_safe_command("python3 --version")
    assert res["exit_code"] == 0
    print(f"  ✓ Safe command output: {res['output'].strip()}")

    # 2. Test sudo rejection guardrail (Rule #1.5)
    sudo_res = code_agent._execute_safe_command("sudo ls /root")
    assert sudo_res["exit_code"] != 0
    assert "ERROR: sudo is strictly prohibited" in sudo_res["output"]
    print("  ✓ Sudo prevention guardrail strictly enforced")

    # 3. Test background task lifecycle
    task_id = code_agent.submit_task("Analyze code architecture")
    assert task_id is not None
    status = code_agent.get_task_status(task_id)
    assert status is not None
    assert status["task_id"] == task_id
    print(f"  ✓ Task lifecycle verified (ID: {task_id}, status: {status['status']})")


if __name__ == "__main__":
    print("=" * 60)
    print("RUNNING MAF PHASE 2 TEST SUITE")
    print("=" * 60)
    try:
        test_bidirectional_mcp_exposure()
        test_code_agent_capabilities()
        print("=" * 60)
        print("ALL PHASE 2 TESTS PASSED! Subtask 132-C & 132-D verified successfully.")
        print("=" * 60)
        sys.exit(0)
    except Exception as e:
        print(f"TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
