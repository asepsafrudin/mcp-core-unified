# shared/prompt_tiers.py
# Modular Prompt Tiers System (core/balanced/complete)
# Consumes config/prompt_config.json and MCP_PROMPT_LEVEL environment variable

import os
from typing import Any, Dict, Optional

from shared.config_loader import load_config

CONFIG_PATH = "config/prompt_config.json"


class PromptTiers:
    """Manages modular prompt tiers (core/balanced/complete) with vendor-neutral compatibility."""

    _levels: Dict[str, Dict[str, Any]] = {}
    _config: Optional[Dict[str, Any]] = None

    @classmethod
    def _ensure_loaded(cls) -> None:
        """Load configuration on first access."""
        if cls._config is not None:
            return
        try:
            cls._config = load_config(CONFIG_PATH)
        except FileNotFoundError:
            cls._config = None
            return
        cls._levels = cls._config.get("levels", {})

    @classmethod
    def _resolve_current_level(cls) -> Optional[str]:
        """Resolve the active prompt level: env var override, then config default, then fallback.

        This always reads the current environment (no caching) so that changes to
        ``MCP_PROMPT_LEVEL`` are picked up at any time.
        """
        env_level = os.environ.get("MCP_PROMPT_LEVEL", "").strip().lower()
        if env_level and env_level in cls._levels:
            return env_level
        if "balanced" in cls._levels:
            return "balanced"
        return None

    @classmethod
    def get_current_level(cls) -> Optional[str]:
        """Return the currently active prompt level (dynamic, respects MCP_PROMPT_LEVEL)."""
        cls._ensure_loaded()
        return cls._resolve_current_level()

    @classmethod
    def list_levels(cls) -> list[str]:
        """Return list of available prompt tier names."""
        cls._ensure_loaded()
        if cls._levels:
            return list(cls._levels.keys())
        return []

    @classmethod
    def get_level_info(cls, level: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Return configuration dict for a given level (or current level)."""
        cls._ensure_loaded()
        target = level or cls._resolve_current_level()
        if not target:
            return None
        return cls._levels.get(target)

    @classmethod
    def get_prompt(
        cls,
        level: Optional[str] = None,
        include_template: bool = False,
    ) -> str:
        """
        Return the prompt string for the given level.

        If `level` is None, uses the current level (from MCP_PROMPT_LEVEL env var
        or config default). Template paths are resolved relative to the project root.

        Args:
            level: One of 'core', 'balanced', 'complete'. If None, use current level.
            include_template: If True, prepend template marker referencing the template path.

        Returns:
            The prompt string content.
        """
        cls._ensure_loaded()

        target = level or cls._resolve_current_level()
        if not target or target not in cls._levels:
            # Fallback to 'balanced' if available, otherwise first available
            target = "balanced" if "balanced" in cls._levels else (
                next(iter(cls._levels), None) if cls._levels else None
            )
            if not target:
                return "No prompt tiers configured."

        info = cls._levels[target]
        max_tokens = info.get("max_tokens", 2000)
        prune_xml = info.get("prune_xml", True)
        prune_mcp_specific = info.get("prune_mcp_specific", False)
        include_examples = info.get("include_examples", True)

        # Build core prompt text
        prompt_parts = []

        # Tier description
        prompt_parts.append(f"=== Prompt Tier: {target} ===")
        prompt_parts.append(info.get("description", ""))

        # Token limit instruction
        prompt_parts.append(
            f"\n--- Token Limit: {max_tokens} tokens ---\n"
            "Keep the entire response within the token limit above. "
            "Truncate if necessary, prioritizing essential information."
        )

        # Pruning instructions
        if prune_xml:
            prompt_parts.append(
                "\n--- XML Pruning ---\n"
                "Strip all XML tags and MCP-specific structure from the output. "
                "Return only plain text or the minimal required structure. "
                "Do NOT include XML opening/closing tags, attributes, or self-closing syntax."
            )
        if prune_mcp_specific:
            prompt_parts.append(
                "\n--- MCP-Specific Pruning ---\n"
                "Remove any MCP framework references, server names, tool definitions, "
                "and internal path notations (e.g., /home/aseps/MCP/). "
                "Output must be vendor-neutral and independent of MCP implementation details."
            )

        # Example inclusion
        if include_examples:
            prompt_parts.append(
                "\n--- Examples (optional, included for balanced/complete) ---\n"
                "When providing examples, keep them concise and directly relevant. "
                "Do not over-extend with unnecessary context."
            )

        # Vendor-neutral directive
        prompt_parts.append(
            "\n--- Vendor Neutrality ---\n"
            "This prompt is designed to be vendor-neutral. "
            "It should work equally well with Gemini, Qwen, ChatGPT, Claude, and other LLMs. "
            "Avoid framework-specific instructions, tool calls, or syntax that only works with one provider."
        )

        # Template reference if requested
        if include_template:
            template_path = info.get("template", "")
            if template_path:
                prompt_parts.append(
                    f"\n--- Template Reference: {template_path} ---\n"
                    "(Consult the template file at the above path for the full structured prompt.)"
                )

        return "\n".join(prompt_parts)

    @classmethod
    def get_prompt_for_llm(
        cls,
        level: Optional[str] = None,
        system: bool = True,
        user: str = "",
    ) -> dict[str, str]:
        """
        Return a chat message dict suitable for passing to an LLM API.

        Args:
            level: Prompt tier level. If None, uses current level.
            system: If True, prepend as system message; if False, as user message.
            user: Custom user message to append/prepend.

        Returns:
            dict with 'role' and 'content' keys.
        """
        prompt = cls.get_prompt(level=level, include_template=False)
        if system:
            base = {"role": "system", "content": prompt}
        else:
            base = {"role": "user", "content": prompt}
        if user:
            if system:
                base["content"] += f"\n\nUser note: {user}"
            else:
                base["content"] += f"\n\n{user}"
        return base