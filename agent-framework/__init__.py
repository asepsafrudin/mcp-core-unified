"""
Microsoft Agent Framework (MAF) Orchestrator Core Module
Provides unified multi-vendor LLM routing, bidirectional MCP agent exposure,
persistent session checkpointing, and OpenTelemetry guardrails.
"""

from .client import ModelClientFactory, SupportedProvider
from .mcp_registry import DynamicMCPRegistry
from .session_store import PersistentSessionStore
from .telemetry import MAFTelemetryGuardrails
from .prompt_builder import (
    DynamicPromptBuilder,
    UserRbacProfile,
    RbacRole,
    LegalTrack,
    LegalJenjang,
    LegalPersonaConfig
)
from .channel_router import (
    MultiChannelRouter,
    ChannelMessage,
    ChannelResponse,
    classify_legal_intent,
    generate_executive_summary
)

__all__ = [
    "ModelClientFactory",
    "SupportedProvider",
    "DynamicMCPRegistry",
    "PersistentSessionStore",
    "MAFTelemetryGuardrails",
    "DynamicPromptBuilder",
    "UserRbacProfile",
    "RbacRole",
    "LegalTrack",
    "LegalJenjang",
    "LegalPersonaConfig",
    "MultiChannelRouter",
    "ChannelMessage",
    "ChannelResponse",
    "classify_legal_intent",
    "generate_executive_summary",
]

__version__ = "1.2.0"

