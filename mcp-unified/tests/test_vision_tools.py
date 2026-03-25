"""Tests untuk vision_tools.py"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from execution.tools.vision_tools import analyze_image, analyze_pdf_pages
from execution.tools.path_utils import is_safe_path


class TestPathUtils:
    def test_reject_sensitive_path(self):
        assert is_safe_path("/etc/passwd") is False

    def test_reject_relative_path(self):
        assert is_safe_path("etc/passwd") is False

    def test_accept_allowed_path(self):
        assert is_safe_path("/home/aseps/MCP/README.md") is True

    def test_accept_tmp_path(self):
        assert is_safe_path("/tmp/test.png") is True


class TestAnalyzeImage:
    @pytest.mark.asyncio
    async def test_reject_unsafe_path(self):
        result = await analyze_image("/etc/secret.png")
        assert result["success"] is False
        assert "allowed" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_reject_unsupported_extension(self):
        result = await analyze_image("/tmp/document.pdf")
        assert result["success"] is False
        assert "Extension" in result["error"]

    @pytest.mark.asyncio
    async def test_file_not_found(self):
        result = await analyze_image("/tmp/nonexistent.png")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_ollama_unavailable_returns_clear_error(self):
        """Jika Ollama mati, error harus jelas bukan cryptic."""
        with patch('execution.tools.vision_tools._image_to_base64', return_value="fake_base64"):
            with patch('execution.tools.vision_tools._call_ollama_vision', return_value=None):
                import tempfile
                # Buat dummy file untuk melewati file existence check
                with tempfile.NamedTemporaryFile(suffix='.png', dir='/tmp', delete=False) as f:
                    f.write(b'fake')
                    tmp_path = f.name
                try:
                    result = await analyze_image(tmp_path)
                    assert result["success"] is False
                    assert "unavailable" in result["error"].lower() or \
                           "Ollama" in result["error"]
                finally:
                    os.unlink(tmp_path)


class TestAnalyzePdf:
    @pytest.mark.asyncio
    async def test_reject_unsafe_path(self):
        result = await analyze_pdf_pages("/etc/secret.pdf")
        assert result["success"] is False
        assert "allowed" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_reject_unsupported_extension(self):
        result = await analyze_pdf_pages("/tmp/document.png")
        assert result["success"] is False
        assert "Extension" in result["error"]

    @pytest.mark.asyncio
    async def test_file_not_found(self):
        result = await analyze_pdf_pages("/tmp/nonexistent.pdf")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_pymupdf_not_installed(self):
        """Jika PyMuPDF tidak ada, error harus jelas."""
        import builtins
        import tempfile
        
        # Simpan import asli
        original_import = builtins.__import__
        
        def mock_import(name, *args, **kwargs):
            if name == 'fitz':
                raise ImportError("No module named 'fitz'")
            return original_import(name, *args, **kwargs)
        
        # Buat dummy PDF file
        with tempfile.NamedTemporaryFile(suffix='.pdf', dir='/tmp', delete=False) as f:
            f.write(b'%PDF-1.4 fake pdf content')
            tmp_path = f.name
        
        try:
            # Patch __import__
            with patch.object(builtins, '__import__', side_effect=mock_import):
                result = await analyze_pdf_pages(tmp_path)
                assert result["success"] is False
                assert "PyMuPDF" in result["error"] or "pymupdf" in result["error"].lower()
        finally:
            os.unlink(tmp_path)
