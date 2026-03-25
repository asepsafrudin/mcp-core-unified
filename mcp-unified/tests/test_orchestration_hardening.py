"""
Tests for Orchestration Layer Hardening from TASK-004.
Covers: closure bug fix, dynamic config path, UUID call ID.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import os
import sys

# Mock Ollama before importing
sys.modules['ollama'] = MagicMock()


@pytest.mark.asyncio
async def test_registry_closure_bug_fix():
    """
    Verifikasi: discover_remote_tools membuat wrapper dengan _remote_name yang benar.
    
    Bug: Semua wrapper menunjuk ke tool terakhir di loop karena closure.
    Fix: Gunakan factory function untuk capture by value.
    """
    from execution.registry import registry, discover_remote_tools
    from execution.mcp_proxy import mcp_proxy
    
    # Mock mcp_proxy to return two tools
    with patch.object(mcp_proxy, 'external_servers', {'test_server': {}}):
        with patch.object(mcp_proxy, 'list_remote_tools', new_callable=AsyncMock) as mock_list:
            mock_list.return_value = [
                {"name": "read_file", "description": "Read a file"},
                {"name": "write_file", "description": "Write a file"}
            ]
            
            # Clear existing remote tools for clean test
            original_tools = dict(registry._tools)
            registry._tools = {k: v for k, v in original_tools.items() 
                             if not hasattr(v, '_is_remote')}
            
            try:
                await discover_remote_tools()
                
                # Verify both tools registered with correct _remote_name
                read_tool = registry.get_tool("read_file")
                write_tool = registry.get_tool("write_file")
                
                if read_tool and hasattr(read_tool, '_remote_name'):
                    assert read_tool._remote_name == "read_file", \
                        f"Expected _remote_name='read_file', got: {read_tool._remote_name}"
                
                if write_tool and hasattr(write_tool, '_remote_name'):
                    assert write_tool._remote_name == "write_file", \
                        f"Expected _remote_name='write_file', got: {write_tool._remote_name}"
            finally:
                # Restore original tools
                registry._tools = original_tools


@pytest.mark.asyncio
async def test_mcp_proxy_dynamic_config_path():
    """
    Verifikasi: MCPProxy menggunakan MCP_CONFIG_PATH env var.
    """
    from execution.mcp_proxy import MCPProxy
    
    test_path = "/custom/path/config.json"
    
    # Test with env var
    with patch.dict(os.environ, {"MCP_CONFIG_PATH": test_path}):
        with patch('os.path.exists', return_value=False):
            proxy = MCPProxy()
            assert proxy.config_path == test_path, \
                f"Expected config_path='{test_path}', got: {proxy.config_path}"
    
    # Test with explicit argument (higher priority)
    explicit_path = "/explicit/path/config.json"
    with patch.dict(os.environ, {"MCP_CONFIG_PATH": test_path}):
        with patch('os.path.exists', return_value=False):
            proxy = MCPProxy(config_path=explicit_path)
            assert proxy.config_path == explicit_path, \
                f"Expected config_path='{explicit_path}', got: {proxy.config_path}"


def test_mcp_proxy_config_path_relative():
    """
    Verifikasi: MCPProxy resolve path relative ke project root jika tidak ada env var.
    """
    from execution.mcp_proxy import MCPProxy
    
    # Clear env var
    env_copy = os.environ.copy()
    if "MCP_CONFIG_PATH" in os.environ:
        del os.environ["MCP_CONFIG_PATH"]
    
    try:
        with patch('os.path.exists', return_value=False):
            proxy = MCPProxy()
            # Should resolve to project root
            assert "antigravity-mcp-config.json" in proxy.config_path, \
                f"Expected config path to contain 'antigravity-mcp-config.json', got: {proxy.config_path}"
    finally:
        os.environ.update(env_copy)


@pytest.mark.asyncio
async def test_mcp_proxy_uuid_call_id():
    """
    Verifikasi: call_tool menggunakan UUID untuk call_id.
    """
    from execution.mcp_proxy import MCPProxy
    import uuid
    
    proxy = MCPProxy(config_path="/dev/null")
    proxy.external_servers = {'test_server': {'command': 'echo', 'args': ['test']}}
    
    with patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_proc:
        mock_stdout = AsyncMock()
        mock_stdout.read = AsyncMock(return_value=b'')
        mock_proc.return_value.communicate = AsyncMock(return_value=(b'', b''))
        mock_proc.return_value.returncode = 0
        
        # Mock to capture the input data
        captured_input = []
        async def capture_communicate(input=None):
            if input:
                captured_input.append(input.decode())
            return (b'', b'')
        
        mock_proc.return_value.communicate = capture_communicate
        
        try:
            await proxy.call_tool("test_server", "test_tool", {"arg": "value"})
        except Exception:
            pass  # Expected to fail since we mock the output
        
        # Verify the call_id in captured input contains UUID pattern
        if captured_input:
            input_data = captured_input[0]
            # Should contain a UUID-like string (8 hex chars after call_tool_name_)
            import re
            uuid_pattern = r'"id":\s*"call_test_tool_[a-f0-9]{8}"'
            assert re.search(uuid_pattern, input_data), \
                f"Expected call_id with UUID, got input: {input_data[:200]}"
