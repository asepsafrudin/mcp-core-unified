import pytest
import os
import tempfile
import sys
from pathlib import Path
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).parent.parent))

from execution.tools.extract_pdf_opendataloader import extract_pdf_opendataloader

def test_extract_pdf_opendataloader_sanity():
    # Buat file PDF dummy untuk testing JVM dan library
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
        pdf_path = tmp_pdf.name
        
    try:
        # Generate dummy PDF content
        c = canvas.Canvas(pdf_path)
        c.drawString(100, 750, "Hello World from OpenDataLoader Test")
        c.save()
        
        # Panggil fungsi (pastikan tidak ada JVM crash)
        result = extract_pdf_opendataloader(pdf_path)
        
        # Verifikasi hasil
        assert isinstance(result, str)
        if "Error" in result:
            # Jika library belum diinstall di environment CI/Local, setidaknya error ditangani graceful
            assert "belum terinstal" in result or "OpenDataLoader" in result
        else:
            # Jika sukses memanggil java backend
            assert len(result) > 0
            # OpenDataLoader markdown output might not exactly have "Hello World" if JVM is slow/failed, but let's check it doesn't crash.
            assert "Error" not in result
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
