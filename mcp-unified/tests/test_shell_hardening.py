"""
Tests for Shell Tools hardening from TASK-002.
Covers: path validation, dangerous patterns, null byte injection.
"""
import pytest
from execution.tools.shell_tools import run_shell


@pytest.mark.asyncio
async def test_reject_path_outside_allowed_dirs():
    """cat /etc/passwd harus ditolak."""
    result = await run_shell("cat /etc/passwd")
    assert result["success"] is False
    error = result.get("error", "").lower()
    assert "outside allowed directories" in error or \
           "not in the allowed whitelist" in error or \
           "blocked for security" in error


@pytest.mark.asyncio
async def test_reject_sudo_commands():
    """sudo commands harus ditolak."""
    result = await run_shell("sudo ls /root")
    assert result["success"] is False
    error = result.get("error", "").lower()
    assert "sudo" in error or "blocked" in error


@pytest.mark.asyncio
async def test_reject_rm_rf():
    """rm -rf commands harus ditolak."""
    result = await run_shell("rm -rf /home/aseps/MCP")
    assert result["success"] is False
    error = result.get("error", "").lower()
    assert "rm" in error or "dangerous" in error or "blocked" in error


@pytest.mark.asyncio
async def test_reject_git_path_traversal():
    """git show dengan path traversal harus ditolak."""
    result = await run_shell("git show HEAD:../../../etc/shadow")
    assert result["success"] is False
    error = result.get("error", "").lower()
    # Command rejected due to dangerous pattern (../) — this is correct behavior
    assert "dangerous" in error or "blocked" in error or "outside" in error or "not allowed" in error


@pytest.mark.asyncio
async def test_reject_chmod_system():
    """chmod on system paths harus ditolak."""
    result = await run_shell("chmod 777 /etc")
    assert result["success"] is False


@pytest.mark.asyncio
async def test_reject_null_byte_injection():
    """Null byte harus ditolak."""
    result = await run_shell("ls\x00rm -rf /")
    assert result["success"] is False


@pytest.mark.asyncio
async def test_reject_path_traversal_dotdot():
    """Path dengan ../ harus ditolak."""
    result = await run_shell("cat ../.env")
    assert result["success"] is False


@pytest.mark.asyncio
async def test_accept_valid_ls_in_allowed_dir():
    """ls di direktori yang diizinkan harus diterima."""
    result = await run_shell("ls /home/aseps/MCP")
    # Hanya cek tidak ditolak karena path — mungkin fail karena alasan lain
    error = result.get("error", "")
    assert "outside allowed directories" not in error.lower()
    assert "not in the allowed whitelist" not in error.lower()


@pytest.mark.asyncio
async def test_accept_valid_cat_in_allowed_dir():
    """cat file di direktori yang diizinkan harus diterima."""
    result = await run_shell("cat /home/aseps/MCP/README.md")
    # Hanya cek tidak ditolak karena path
    error = result.get("error", "")
    assert "outside allowed directories" not in error.lower()
