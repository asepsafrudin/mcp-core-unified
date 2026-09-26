"""
Bidirectional MCP Agent Server for Microsoft Agent Framework (MAF)
Allows exposing specialist sub-agents (Legal, Coding, Memory, ND-Laporan)
as first-class MCP Servers via agent.as_mcp_server() over stdio or SSE.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from core.agent_framework.client import ModelClientFactory, SupportedProvider
    from core.agent_framework.mcp_registry import DynamicMCPRegistry
    from core.agent_framework.session_store import PersistentSessionStore
    from core.agent_framework.telemetry import MAFTelemetryGuardrails
except (ImportError, ModuleNotFoundError):
    try:
        from .client import ModelClientFactory, SupportedProvider
        from .mcp_registry import DynamicMCPRegistry
        from .session_store import PersistentSessionStore
        from .telemetry import MAFTelemetryGuardrails
    except (ImportError, ValueError):
        from client import ModelClientFactory, SupportedProvider
        from mcp_registry import DynamicMCPRegistry
        from session_store import PersistentSessionStore
        from telemetry import MAFTelemetryGuardrails



def build_specialist_agent(
    agent_type: str,
    provider: Optional[str] = None,
    legal_track: str = "counsel",
    legal_jenjang: str = "Ahli Madya"
) -> Any:
    """Build specialist agent based on requested profile."""
    registry = DynamicMCPRegistry()
    guardrails = MAFTelemetryGuardrails.create_safety_middleware()

    if agent_type in ("legal", "legal_drafting", "legal_counsel"):
        try:
            from core.agent_framework.prompt_builder import (
                DynamicPromptBuilder,
                LegalTrack,
                LegalJenjang
            )
        except (ImportError, ModuleNotFoundError):
            try:
                from .prompt_builder import (
                    DynamicPromptBuilder,
                    LegalTrack,
                    LegalJenjang
                )
            except (ImportError, ValueError):
                from prompt_builder import (
                    DynamicPromptBuilder,
                    LegalTrack,
                    LegalJenjang
                )

        if agent_type == "legal_drafting":
            persona_key = "PERANCANG_PUU_AHLI_MADYA"
            tools = registry.get_tools_for_profile("legal_drafting")
            name = "LegislativeDrafterAgent"
        elif agent_type == "legal_counsel":
            persona_key = "ANALIS_HUKUM_AHLI_MADYA"
            tools = registry.get_tools_for_profile("legal_counsel")
            name = "LegalCounselAgent"
        else:
            is_drafting = "perancang" in legal_track.lower() or "draft" in legal_track.lower()
            persona_key = "PERANCANG_PUU_AHLI_MADYA" if is_drafting else "ANALIS_HUKUM_AHLI_MADYA"
            tools = registry.get_tools_for_profile("legal")
            name = "LegalSpecialistAgent"


        instructions = DynamicPromptBuilder.build_legal_persona_prompt(persona_key=persona_key)


    elif agent_type == "memory":
        instructions = (
            "Anda adalah Memory & Knowledge Manager untuk ekosistem MCP Unified. "
            "Tugas Anda mengelola penyimpanan LTM (Long Term Memory), pengindeksan dokumen, "
            "dan query semantik dengan mematuhi protokol isolasi namespace."
        )
        tools = registry.get_tools_for_profile("admin")
        name = "MemoryKnowledgeAgent"

    elif agent_type == "coding":
        instructions = (
            "Anda adalah MAF Code & Task Specialist. Tugas Anda membaca, menganalisis struktur kode, "
            "dan melakukan debugging/refactoring dengan aman tanpa merusak integritas sistem."
        )
        tools = registry.get_tools_for_profile("coding")
        name = "MAFCodeSpecialistAgent"

    else:
        instructions = "Anda adalah General Assistant di ekosistem MCP Unified."
        tools = registry.get_tools_for_profile("full")
        name = "GeneralAssistantAgent"

    agent = ModelClientFactory.create_agent(
        name=name,
        instructions=instructions,
        tools=tools,
        provider=provider,
    )
    return agent



async def run_stdio_server(agent: Any, server_name: str) -> None:
    """Run the agent as an MCP server using stdio transport."""
    from mcp.server.stdio import stdio_server

    server = agent.as_mcp_server(
        server_name=server_name,
        version="1.0.0",
        instructions=agent.description,
    )

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    parser = argparse.ArgumentParser(description="MAF Bidirectional MCP Agent Server")
    parser.add_argument(
        "--agent",
        choices=["legal", "memory", "coding", "general"],
        default="legal",
        help="Specialist agent type to expose as MCP server",
    )
    parser.add_argument(
        "--provider",
        choices=["ollama", "gemini", "openai", "anthropic"],
        default=None,
        help="Underlying LLM provider (default: auto-detected)",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio"],
        default="stdio",
        help="MCP transport to run server on",
    )
    args = parser.parse_args()

    agent = build_specialist_agent(args.agent, provider=args.provider)
    server_name = f"maf-{args.agent}-agent"

    if args.transport == "stdio":
        try:
            asyncio.run(run_stdio_server(agent, server_name))
        except (KeyboardInterrupt, BrokenPipeError):
            pass


if __name__ == "__main__":
    main()
