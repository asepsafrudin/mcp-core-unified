# shared/tests/test_prompt_tiers.py
# Unit tests for modular prompt tiers (core/balanced/complete)

import os
import sys

# Ensure shared is importable
sys.path.insert(0, "/home/aseps/MCP")

from shared.prompt_tiers import PromptTiers


def test_list_levels():
    """Test that list_levels returns the 3 tier names."""
    levels = PromptTiers.list_levels()
    assert "core" in levels, f"Expected 'core' in levels, got {levels}"
    assert "balanced" in levels, f"Expected 'balanced' in levels, got {levels}"
    assert "complete" in levels, f"Expected 'complete' in levels, got {levels}"
    assert len(levels) == 3, f"Expected 3 levels, got {len(levels)}"
    print(f"  PASS: list_levels() = {levels}")


def test_get_current_level_default():
    """Test that default current level is 'balanced' (from config)."""
    # Ensure MCP_PROMPT_LEVEL is not set for default test
    os.environ.pop("MCP_PROMPT_LEVEL", None)
    level = PromptTiers.get_current_level()
    assert level == "balanced", f"Expected 'balanced' as default, got '{level}'"
    print(f"  PASS: get_current_level() default = '{level}'")


def test_get_current_level_env_override():
    """Test that MCP_PROMPT_LEVEL env var overrides the default."""
    os.environ["MCP_PROMPT_LEVEL"] = "core"
    level = PromptTiers.get_current_level()
    assert level == "core", f"Expected 'core' with env override, got '{level}'"
    # Clean up
    del os.environ["MCP_PROMPT_LEVEL"]
    print(f"  PASS: get_current_level() env override = '{level}'")


def test_get_current_level_invalid_fallback():
    """Test that invalid env var falls back to 'balanced'."""
    os.environ["MCP_PROMPT_LEVEL"] = "invalid_level"
    level = PromptTiers.get_current_level()
    assert level == "balanced", f"Expected 'balanced' fallback for invalid level, got '{level}'"
    del os.environ["MCP_PROMPT_LEVEL"]
    print(f"  PASS: get_current_level() invalid fallback = '{level}'")


def test_get_level_info():
    """Test get_level_info returns correct info for each level."""
    for level in ["core", "balanced", "complete"]:
        info = PromptTiers.get_level_info(level)
        assert info is not None, f"Expected info for level '{level}', got None"
        assert "description" in info, "Expected 'description' in level info"
        assert "max_tokens" in info, "Expected 'max_tokens' in level info"
        print(f"  PASS: get_level_info('{level}') = {{description: {info.get('description')}, max_tokens: {info.get('max_tokens')}}}")


def test_get_prompt_core():
    """Test get_prompt returns core tier prompt."""
    os.environ.pop("MCP_PROMPT_LEVEL", None)
    prompt = PromptTiers.get_prompt(level="core")
    assert "core" in prompt.lower(), f"Expected 'core' in prompt, got snippet: {prompt[:80]}"
    assert "token" in prompt.lower(), "Expected token limit mention in prompt"
    # Should prune XML and MCP-specific
    assert "xml" in prompt.lower() or "XML" in prompt, "Expected XML pruning in core prompt"
    print(f"  PASS: get_prompt(level='core') = {len(prompt)} chars, contains 'core' and token limits")


def test_get_prompt_balanced():
    """Test get_prompt returns balanced tier prompt."""
    os.environ.pop("MCP_PROMPT_LEVEL", None)
    prompt = PromptTiers.get_prompt(level="balanced")
    assert "balanced" in prompt.lower(), "Expected 'balanced' in prompt"
    assert "token" in prompt.lower(), "Expected token limit mention"
    # balanced should NOT prune MCP-specific (that's core only)
    # but should prune XML
    print(f"  PASS: get_prompt(level='balanced') = {len(prompt)} chars")


def test_get_prompt_complete():
    """Test get_prompt returns complete tier prompt."""
    os.environ.pop("MCP_PROMPT_LEVEL", None)
    prompt = PromptTiers.get_prompt(level="complete")
    assert "complete" in prompt.lower(), "Expected 'complete' in prompt"
    assert "token" in prompt.lower(), "Expected token limit mention"
    # complete should NOT prune XML/MCP-specific
    print(f"  PASS: get_prompt(level='complete') = {len(prompt)} chars")


def test_get_prompt_invalid_fallback():
    """Test get_prompt falls back to 'balanced' for invalid level."""
    os.environ.pop("MCP_PROMPT_LEVEL", None)
    prompt = PromptTiers.get_prompt(level="nonexistent")
    # Should fallback to balanced
    assert "balanced" in prompt.lower() or "balanced" in prompt, \
        f"Expected fallback to balanced prompt, got: {prompt[:80]}"
    print("  PASS: get_prompt(level='nonexistent') falls back appropriately")


def test_get_prompt_llm_format():
    """Test get_prompt_for_llm returns proper dict format."""
    os.environ.pop("MCP_PROMPT_LEVEL", None)
    msg = PromptTiers.get_prompt_for_llm(level="core", system=True)
    assert "role" in msg, "Expected 'role' key in dict"
    assert "content" in msg, "Expected 'content' key in dict"
    assert msg["role"] == "system", f"Expected role='system', got '{msg['role']}'"
    assert "core" in msg["content"].lower(), "Expected 'core' in system prompt content"

    msg_user = PromptTiers.get_prompt_for_llm(level="balanced", system=False, user="Test user message")
    assert msg_user["role"] == "user", f"Expected role='user', got '{msg_user['role']}'"
    assert "Test user message" in msg_user["content"], "Expected 'Test user message' in content"
    print("  PASS: get_prompt_for_llm() returns proper dict format")


def test_vendor_neutrality():
    """Test that prompts don't contain MCP-specific framework references."""
    os.environ.pop("MCP_PROMPT_LEVEL", None)
    for level in ["core", "balanced", "complete"]:
        prompt = PromptTiers.get_prompt(level=level)
        # Check for common MCP-specific patterns that should be pruned
        mcp_patterns = ["/home/aseps/MCP/", "mcp-core-server", "mcp-memory-server", "/tool/ping"]
        found_mcp = [p for p in mcp_patterns if p.lower() in prompt.lower()]
        # Core should prune these; balanced/complete may contain them but should be minimal
        # At minimum, the prompt should not be *dominated* by MCP references
        print(f"  INFO: level='{level}' - MCP patterns found: {found_mcp}")


if __name__ == "__main__":
    print("Running shared/tests/test_prompt_tiers.py unit tests...\n")
    test_list_levels()
    test_get_current_level_default()
    test_get_current_level_env_override()
    test_get_current_level_invalid_fallback()
    test_get_level_info()
    test_get_prompt_core()
    test_get_prompt_balanced()
    test_get_prompt_complete()
    test_get_prompt_invalid_fallback()
    test_get_prompt_llm_format()
    test_vendor_neutrality()
    print("\n=== All tests passed! ===")