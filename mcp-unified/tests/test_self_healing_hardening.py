"""
Tests for Self-Healing hardening from TASK-002.
Covers: APPROVED_AUTO_INSTALL_PACKAGES whitelist, fix_syntax raises immediately.
"""
import pytest
from unittest.mock import patch, AsyncMock
from intelligence.self_healing import PracticalSelfHealing, APPROVED_AUTO_INSTALL_PACKAGES


@pytest.mark.asyncio
async def test_auto_install_blocked_for_unknown_package():
    """
    Verifikasi: ModuleNotFoundError untuk package tidak dikenal
    raises immediately tanpa pip install.
    """
    healer = PracticalSelfHealing()
    
    with patch('asyncio.create_subprocess_exec') as mock_exec:
        error = ModuleNotFoundError("No module named 'malicious_package'")
        
        # Should raise immediately for blocked packages
        with pytest.raises(ModuleNotFoundError):
            await healer.fix_imports(error)
        
        # pip install should NOT have been called
        mock_exec.assert_not_called()


def test_approved_packages_starts_empty():
    """
    Verifikasi: whitelist dimulai kosong — semua auto-install diblokir
    sampai ada keputusan eksplisit.
    """
    assert len(APPROVED_AUTO_INSTALL_PACKAGES) == 0, \
        "APPROVED_AUTO_INSTALL_PACKAGES should be empty until explicitly reviewed"


@pytest.mark.asyncio
async def test_syntax_error_raises_immediately():
    """
    Verifikasi: SyntaxError tidak diretry 3x — raise immediately.
    """
    healer = PracticalSelfHealing()
    call_count = 0
    
    async def always_fails():
        nonlocal call_count
        call_count += 1
        raise SyntaxError("invalid syntax")
    
    with pytest.raises(SyntaxError):
        await healer.execute_with_healing(always_fails)
    
    # Should not retry 3 times — fix_syntax raises immediately
    assert call_count == 1, f"Expected 1 call, got {call_count} — retry happening unnecessarily"


@pytest.mark.asyncio
async def test_import_error_not_retried_if_not_fixable():
    """
    Verifikasi: ImportError untuk package tidak di-whitelist
    tidak menyebabkan retry.
    """
    healer = PracticalSelfHealing()
    call_count = 0
    
    async def always_fails():
        nonlocal call_count
        call_count += 1
        raise ImportError("No module named 'unknown_lib'")
    
    with pytest.raises(ImportError):
        await healer.execute_with_healing(always_fails)
    
    # Should not retry since package is not in whitelist
    assert call_count == 1, f"Expected 1 call, got {call_count}"
