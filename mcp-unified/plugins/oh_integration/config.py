"""
OpenHands Integration — Configuration

Environment variables untuk OpenHands SDK dan orchestrator.
"""

import os
from typing import Optional


class OpenHandsConfig:
    """
    Konfigurasi OpenHands integration.
    Semua nilai diambil dari environment variables.
    """

    # === LLM Backend ===
    # Model untuk OpenHands agent (format: provider/model_name)
    llm_model: str = os.getenv("OPENHANDS_LLM_MODEL", "anthropic/claude-sonnet-4-5-20250929")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_api_base: Optional[str] = os.getenv("LLM_API_BASE", None)

    # === Workspace ===
    # Base directory untuk workspace OpenHands
    workspace_base: str = os.getenv("OPENHANDS_WORKSPACE", "/tmp/openhands_workspaces")

    # === Timeouts & Limits ===
    # Timeout per task dalam detik (default: 30 menit)
    task_timeout_seconds: int = int(os.getenv("OPENHANDS_TIMEOUT", "1800"))
    # Max concurrent agents (default: 3)
    max_concurrent_agents: int = int(os.getenv("OPENHANDS_MAX_AGENTS", "3"))

    # === Redis ===
    # Redis key prefix untuk task state
    redis_prefix: str = os.getenv("OPENHANDS_REDIS_PREFIX", "openhands:task:")
    # Redis URL (fallback ke REDIS_URL utama)
    redis_url: str = os.getenv("OPENHANDS_REDIS_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))

    # === Sandbox ===
    # Gunakan sandbox Docker untuk isolation
    use_sandbox: bool = os.getenv("OPENHANDS_USE_SANDBOX", "true").lower() in ("true", "1", "yes")
    # Docker image untuk sandbox (default: Python slim)
    sandbox_image: str = os.getenv("OPENHANDS_SANDBOX_IMAGE", "python:3.12-slim")

    # === Logging ===
    # Enable detailed logging untuk debugging
    debug_logging: bool = os.getenv("OPENHANDS_DEBUG", "false").lower() in ("true", "1", "yes")

    def validate(self) -> list[str]:
        """
        Validasi konfigurasi. Returns list of error messages.
        """
        errors = []
        if not self.llm_model:
            errors.append("OPENHANDS_LLM_MODEL must be set")
        if not self.llm_api_key and not self.llm_api_base:
            errors.append("LLM_API_KEY or LLM_API_BASE must be set")
        if self.max_concurrent_agents < 1:
            errors.append("OPENHANDS_MAX_AGENTS must be >= 1")
        if self.task_timeout_seconds < 60:
            errors.append("OPENHANDS_TIMEOUT must be >= 60 seconds")
        return errors


# Singleton instance
config = OpenHandsConfig()