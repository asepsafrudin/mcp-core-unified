"""Tests untuk self_review_tool.py"""
import pytest
import tempfile
import os
import sys

# Add parent directory to path
sys.path.insert(0, '/home/aseps/MCP/mcp-unified')
from execution.tools.self_review_tool import self_review, self_review_batch


@pytest.mark.asyncio
async def test_detect_unused_import():
    """Tool harus mendeteksi import yang tidak dipakai."""
    code = """
import os
import re  # ini tidak dipakai

def hello():
    return os.getcwd()
"""
    with tempfile.NamedTemporaryFile(suffix='.py', dir='/tmp',
                                     mode='w', delete=False) as f:
        f.write(code)
        tmp = f.name
    try:
        result = await self_review(tmp, check_type="general")
        issues = result["issues"]
        unused = [i for i in issues if "re" in i["description"] and "tidak dipakai" in i["description"]]
        assert len(unused) > 0, "Harus mendeteksi 're' sebagai unused import"
    finally:
        os.unlink(tmp)


@pytest.mark.asyncio
async def test_detect_shell_true():
    """Tool harus mendeteksi subprocess dengan shell=True."""
    code = """
import subprocess

def run_cmd(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True)
    return result.stdout
"""
    with tempfile.NamedTemporaryFile(suffix='.py', dir='/tmp',
                                     mode='w', delete=False) as f:
        f.write(code)
        tmp = f.name
    try:
        result = await self_review(tmp, check_type="security")
        issues = result["issues"]
        shell_true = [i for i in issues if "shell=True" in i["description"]]
        assert len(shell_true) > 0, "Harus mendeteksi shell=True"
        assert result["passed"] is False, "Harus FAIL karena ada critical issue"
    finally:
        os.unlink(tmp)


@pytest.mark.asyncio
async def test_detect_path_validation_inconsistency():
    """Tool harus mendeteksi inkonsistensi kondisi validasi path."""
    code = '''
from execution.tools.path_utils import is_safe_path

def check(parts):
    for part in parts:
        # Blok 1 - lemah
        if "/" in part:
            if not is_safe_path(part):
                return False
    for part in parts:
        # Blok 2 - lebih ketat
        if "/" in part or ".." in part:
            if not is_safe_path(part):
                return False
    return True
'''
    with tempfile.NamedTemporaryFile(suffix='.py', dir='/tmp',
                                     mode='w', delete=False) as f:
        f.write(code)
        tmp = f.name
    try:
        result = await self_review(tmp, check_type="security")
        issues = result["issues"]
        inconsistent = [i for i in issues if "nkonsistensi" in i["description"]]
        assert len(inconsistent) > 0, "Harus mendeteksi inkonsistensi kondisi"
    finally:
        os.unlink(tmp)


@pytest.mark.asyncio
async def test_detect_memory_without_namespace():
    """Tool harus mendeteksi memory call tanpa namespace."""
    code = """
from memory.longterm import memory_save

async def save_data(content):
    # Namespace tidak disertakan
    await memory_save(key="test", content=content)
"""
    with tempfile.NamedTemporaryFile(suffix='.py', dir='/tmp',
                                     mode='w', delete=False) as f:
        f.write(code)
        tmp = f.name
    try:
        result = await self_review(tmp, check_type="memory")
        issues = result["issues"]
        ns_issues = [i for i in issues if "namespace" in i["description"].lower()]
        assert len(ns_issues) > 0, "Harus mendeteksi memory call tanpa namespace"
    finally:
        os.unlink(tmp)


@pytest.mark.asyncio
async def test_clean_file_passes():
    """File yang bersih harus PASSED."""
    code = '''
import os
from observability.logger import logger


async def process(file_path: str) -> dict:
    """Process a file safely."""
    try:
        content = os.path.exists(file_path)
        logger.info("processed", path=file_path)
        return {"success": True, "exists": content}
    except Exception as e:
        logger.error("failed", error=str(e))
        return {"success": False, "error": str(e)}
'''
    with tempfile.NamedTemporaryFile(suffix='.py', dir='/tmp',
                                     mode='w', delete=False) as f:
        f.write(code)
        tmp = f.name
    try:
        result = await self_review(tmp, check_type="general")
        assert result["passed"] is True, \
            f"File bersih harus PASSED, got issues: {result['issues']}"
    finally:
        os.unlink(tmp)


@pytest.mark.asyncio
async def test_reject_unsafe_path():
    """Tool tidak boleh bisa direview untuk file di luar allowed dirs."""
    result = await self_review("/etc/passwd")
    assert result["passed"] is False
    assert "Path" in result["summary"] or "BLOCKED" in result["summary"]
