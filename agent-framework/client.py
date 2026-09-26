"""
Model Client Factory for Microsoft Agent Framework (MAF)
Supports multi-vendor routing across Ollama (local), Gemini, OpenAI, and Anthropic.
Automatically sources credentials via scripts.load_env.
"""

from __future__ import annotations

import os
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

# Ensure official agent_framework from site-packages is loaded (prevent local shadowing)
if "agent_framework" not in sys.modules or not getattr(sys.modules["agent_framework"], "__file__", "").endswith("site-packages/agent_framework/__init__.py"):
    _saved_path = list(sys.path)
    try:
        sys.path = [p for p in sys.path if p != '/home/aseps/MCP/core' and not p.endswith('/core')]
        import agent_framework
    finally:
        sys.path = _saved_path

from agent_framework import Agent
from agent_framework.ollama import OllamaChatClient
from agent_framework.gemini import GeminiChatClient
from agent_framework.openai import OpenAIChatClient
from agent_framework.anthropic import AnthropicClient

# Ensure environment variables are loaded
try:
    from scripts.load_env import load_env
    load_env()
except Exception:
    pass


class SupportedProvider(str, Enum):
    OLLAMA = "ollama"
    GEMINI = "gemini"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class ModelClientFactory:
    """Factory for creating MAF-compatible model clients and agents."""

    @staticmethod
    def get_default_provider() -> SupportedProvider:
        """Determine default provider based on available environment variables."""
        if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
            return SupportedProvider.GEMINI
        if os.getenv("OPENAI_API_KEY"):
            return SupportedProvider.OPENAI
        if os.getenv("ANTHROPIC_API_KEY"):
            return SupportedProvider.ANTHROPIC
        return SupportedProvider.OLLAMA

    @classmethod
    def create_client(
        cls,
        provider: Optional[SupportedProvider | str] = None,
        model_name: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        """Create a chat client instance for the specified provider."""
        if provider is None:
            provider = cls.get_default_provider()
        elif isinstance(provider, str):
            provider = SupportedProvider(provider.lower())

        if provider == SupportedProvider.OLLAMA:
            host = kwargs.get("host") or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            model = model_name or os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
            return OllamaChatClient(host=host, model=model, **kwargs)

        elif provider == SupportedProvider.GEMINI:
            api_key = kwargs.get("api_key") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            model = model_name or os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
            return GeminiChatClient(api_key=api_key, model=model, **kwargs)

        elif provider == SupportedProvider.OPENAI:
            api_key = kwargs.get("api_key") or os.getenv("OPENAI_API_KEY")
            base_url = kwargs.get("base_url") or os.getenv("OPENAI_BASE_URL")
            model = model_name or os.getenv("OPENAI_MODEL", "gpt-4o")
            client_args = {"api_key": api_key, "model": model}
            if base_url:
                client_args["base_url"] = base_url
            client_args.update(kwargs)
            return OpenAIChatClient(**client_args)

        elif provider == SupportedProvider.ANTHROPIC:
            api_key = kwargs.get("api_key") or os.getenv("ANTHROPIC_API_KEY")
            model = model_name or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
            return AnthropicClient(api_key=api_key, model=model, **kwargs)

        raise ValueError(f"Unsupported provider: {provider}")

    @classmethod
    def create_agent(
        cls,
        name: str,
        instructions: str,
        tools: Optional[List[Any]] = None,
        provider: Optional[SupportedProvider | str] = None,
        model_name: Optional[str] = None,
        **kwargs: Any,
    ) -> Agent:
        """Create a complete MAF Agent configured with model and tools."""
        client = cls.create_client(provider=provider, model_name=model_name, **kwargs)
        return Agent(
            client=client,
            name=name,
            instructions=instructions,
            tools=tools or [],
        )
