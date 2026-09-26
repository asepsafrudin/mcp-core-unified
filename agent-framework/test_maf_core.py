"""
Smoke Test for Core MAF Modules (Subtask 132-A & 132-B)
Verifies ModelClientFactory, DynamicMCPRegistry, PersistentSessionStore, and MAFTelemetryGuardrails.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.agent_framework.client import ModelClientFactory, SupportedProvider
from core.agent_framework.mcp_registry import DynamicMCPRegistry
from core.agent_framework.session_store import PersistentSessionStore
from core.agent_framework.telemetry import MAFTelemetryGuardrails


def test_model_client_factory():
    print("Testing ModelClientFactory...")
    # Test Ollama client creation
    ollama_client = ModelClientFactory.create_client(SupportedProvider.OLLAMA, model_name="qwen2.5-coder:7b")
    assert ollama_client is not None, "Failed to create OllamaChatClient"
    print("  ✓ OllamaChatClient instantiated successfully")

    # Test Agent creation
    agent = ModelClientFactory.create_agent(
        name="TestAgent",
        instructions="You are a test assistant.",
        provider=SupportedProvider.OLLAMA,
    )
    assert agent is not None, "Failed to create Agent"
    assert agent.name == "TestAgent"
    print("  ✓ Agent instantiated successfully")


def test_mcp_registry():
    print("Testing DynamicMCPRegistry...")
    registry = DynamicMCPRegistry()
    
    # Test stdio tool instantiation
    stdio_tool = registry.get_unified_stdio_tool(allowed_tools=["query_db", "describe_table"])
    assert stdio_tool is not None, "Failed to instantiate MCPStdioTool"
    assert stdio_tool.name == "mcp-unified"
    print("  ✓ MCPStdioTool configured for mcp-unified")

    # Test profile tools
    legal_tools = registry.get_tools_for_profile("legal")
    assert len(legal_tools) > 0
    print("  ✓ Profile tools retrieved for 'legal' profile")


def test_session_store():
    print("Testing PersistentSessionStore...")
    store = PersistentSessionStore()
    
    # Test session resolution
    session_id_tg = store.resolve_session_id("telegram", "user_9988")
    assert session_id_tg == "session_telegram_user_9988"
    print(f"  ✓ Resolved session: {session_id_tg}")

    # Test explicit identity linking
    store.map_channel_identity("whatsapp", "62812345678", session_id_tg)
    resolved_wa = store.resolve_session_id("whatsapp", "62812345678")
    assert resolved_wa == session_id_tg, "Cross-channel identity mapping failed"
    print(f"  ✓ Cross-channel identity mapped: whatsapp -> {resolved_wa}")


def test_telemetry_guardrails():
    print("Testing MAFTelemetryGuardrails...")
    # Safe SQL
    assert MAFTelemetryGuardrails.validate_sql_safety("SELECT * FROM surat_masuk WHERE id = 1") is True
    # Destructive SQL
    assert MAFTelemetryGuardrails.validate_sql_safety("DROP TABLE surat_masuk") is False
    assert MAFTelemetryGuardrails.validate_sql_safety("DELETE FROM surat_masuk") is False
    print("  ✓ SQL Safety Guardrails validated (Rule #1)")

    # Storage Isolation
    assert MAFTelemetryGuardrails.validate_storage_path("storage/reports/doc.pdf") is True
    assert MAFTelemetryGuardrails.validate_storage_path("core/mcp-unified/bad_state.json") is False
    print("  ✓ Storage Isolation Guardrails validated (Rule #4)")


if __name__ == "__main__":
    print("=" * 60)
    print("RUNNING MAF CORE TEST SUITE")
    print("=" * 60)
    try:
        test_model_client_factory()
        test_mcp_registry()
        test_session_store()
        test_telemetry_guardrails()
        print("=" * 60)
        print("ALL TESTS PASSED! Subtask 132-A & 132-B verified successfully.")
        print("=" * 60)
        sys.exit(0)
    except Exception as e:
        print(f"TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
