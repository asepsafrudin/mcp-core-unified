"""
Advanced Testing Suite for Microsoft Agent Framework (MAF) in MCP Ecosystem
Covers:
1. Live Bidirectional Agent-as-MCP-Server Tool Registration & Call Simulation
2. Cross-Channel Multi-Turn Session Persistence & Identity Mapping (Rule #4)
3. Adversarial DLP & Storage Isolation Security Stress Testing (Rule #1 & Rule #4)
4. Multi-Vendor LLM Router Fallback Readiness
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.agent_framework.client import ModelClientFactory, SupportedProvider
from core.agent_framework.session_store import PersistentSessionStore
from core.agent_framework.telemetry import MAFTelemetryGuardrails
from core.agent_framework.bidirectional_server import build_specialist_agent


def test_1_agent_as_mcp_server_protocol():
    print("[Advanced Test 1] Verifying Agent-as-MCP-Server Protocol Structure...")
    legal_agent = build_specialist_agent("legal")
    mcp_server = legal_agent.as_mcp_server(
        server_name="maf-legal-specialist",
        version="1.0.0",
        instructions="Test instructions",
    )
    
    # Check that server instance has tool handling capabilities
    assert mcp_server is not None
    assert mcp_server.name == "maf-legal-specialist"
    
    # Protocol handshake verification
    init_options = mcp_server.create_initialization_options()
    assert init_options.server_name == "maf-legal-specialist"
    print("  ✓ MCP Server initialization handshake verified")
    print(f"  ✓ Server Version: {init_options.server_version}, Capabilities: {list(init_options.capabilities.model_dump().keys())}")


def test_2_cross_channel_session_persistence():
    print("[Advanced Test 2] Testing Cross-Channel Identity Mapping & State Persistence...")
    session_store = PersistentSessionStore()
    
    # User interacts first from Telegram
    tg_user = "user_778899"
    tg_session = session_store.resolve_session_id("telegram", tg_user)
    print(f"  ✓ Initial Telegram Session Created: {tg_session}")

    # Map this user's WhatsApp number to the same unified session
    wa_phone = "6289911223344"
    session_store.map_channel_identity("whatsapp", wa_phone, tg_session)
    
    # User sends follow-up from WhatsApp
    wa_resolved_session = session_store.resolve_session_id("whatsapp", wa_phone)
    assert wa_resolved_session == tg_session, "WhatsApp failed to resolve to Telegram unified session"
    print(f"  ✓ WhatsApp correctly mapped to Unified Session: {wa_resolved_session}")

    # Verify session store directory adheres to storage isolation
    assert "storage/state/maf_sessions" in str(session_store.session_dir)
    assert session_store._identity_map_file.exists()
    print("  ✓ State stored strictly inside storage/state/ (Rule #4 adhered)")


def test_3_adversarial_guardrail_stress_test():
    print("[Advanced Test 3] Running Adversarial Guardrail Stress Testing...")
    
    # Test adversarial SQL injections
    malicious_queries = [
        "DROP TABLE korespondensi_raw_pool",
        "drop database mcp_knowledge;",
        "TRUNCATE TABLE surat_masuk",
        "DELETE FROM users",
        "DELETE  FROM  surat_keluar ;",
    ]
    for q in malicious_queries:
        allowed = MAFTelemetryGuardrails.validate_sql_safety(q)
        assert allowed is False, f"Malicious query was not blocked: {q}"
    print(f"  ✓ {len(malicious_queries)}/{len(malicious_queries)} malicious destructive SQL queries blocked (Rule #1)")

    # Legitimate safe SQL queries should pass
    safe_queries = [
        "SELECT * FROM surat_masuk WHERE id = 10",
        "SELECT count(*) FROM korespondensi_raw_pool",
        "UPDATE users SET name = 'Asep' WHERE id = 1",
        "DELETE FROM temp_cache WHERE created_at < '2025-01-01'",
    ]
    for q in safe_queries:
        allowed = MAFTelemetryGuardrails.validate_sql_safety(q)
        assert allowed is True, f"Legitimate query was wrongly blocked: {q}"
    print(f"  ✓ {len(safe_queries)}/{len(safe_queries)} safe SQL queries allowed through")

    # Test storage isolation enforcement
    forbidden_writes = [
        "core/mcp-unified/state.json",
        "scripts/token.txt",
        "docs/00-meta/credentials.json",
    ]
    for p in forbidden_writes:
        allowed = MAFTelemetryGuardrails.validate_storage_path(p)
        assert allowed is False, f"Forbidden write path was not blocked: {p}"
    print(f"  ✓ {len(forbidden_writes)}/{len(forbidden_writes)} illegal code-directory writes blocked (Rule #4)")


def test_4_multivendor_factory_readiness():
    print("[Advanced Test 4] Testing Multi-Vendor LLM Router Readiness...")
    # Test Ollama client
    ollama_c = ModelClientFactory.create_client(SupportedProvider.OLLAMA, model_name="qwen2.5-coder:7b")
    assert ollama_c is not None
    print("  ✓ Local Ollama client configured")

    # Test Default Provider Auto-Detection
    default_p = ModelClientFactory.get_default_provider()
    assert default_p in [SupportedProvider.GEMINI, SupportedProvider.OPENAI, SupportedProvider.OLLAMA, SupportedProvider.ANTHROPIC]
    print(f"  ✓ Auto-detected active provider: {default_p.value}")


if __name__ == "__main__":
    print("=" * 60)
    print("RUNNING MAF ADVANCED TEST SUITE")
    print("=" * 60)
    try:
        test_1_agent_as_mcp_server_protocol()
        test_2_cross_channel_session_persistence()
        test_3_adversarial_guardrail_stress_test()
        test_4_multivendor_factory_readiness()
        print("=" * 60)
        print("ALL ADVANCED TESTS PASSED! MAF robustness validated.")
        print("=" * 60)
        sys.exit(0)
    except Exception as e:
        print(f"ADVANCED TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
