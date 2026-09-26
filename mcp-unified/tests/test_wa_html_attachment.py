"""
tests/test_wa_html_attachment.py — Verifikasi Fitur HTML Report Attachment WhatsApp Bot AI
Menguji logika threshold karakter, pembuatan file HTML otomatis, dan format pengiriman attachment.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
import pytest

WORKSPACE_ROOT = Path("/home/aseps/MCP").resolve()
REPORT_OUTPUT_DIR = WORKSPACE_ROOT / "storage" / "reports" / "wa_reports"

def test_report_generator_js_logic():
    """Test modul report_generator.js via Node.js CLI."""
    node_script = """
    const rg = require('./services/whatsapp-bot-ai/report_generator.js');
    const assert = require('assert');

    // 1. Uji Teks Pendek
    const shortText = 'Halo, apa kabar? Ini jawaban singkat.';
    assert.strictEqual(rg.shouldAttachHtmlReport(shortText, null, 2000), false, 'Teks pendek tidak boleh attach berkas');

    // 2. Uji Teks Panjang
    const longText = 'A'.repeat(2500);
    assert.strictEqual(rg.shouldAttachHtmlReport(longText, null, 2000), true, 'Teks panjang (> 2000) wajib attach berkas');

    // 3. Uji Dokumen Eksplisit
    const dummyPath = '/home/aseps/MCP/storage/reports/architecture_diagram.html';
    assert.strictEqual(rg.shouldAttachHtmlReport('Singkat', dummyPath, 2000), true, 'Eksplisit file wajib attach berkas');

    // 4. Uji Generate HTML
    const sampleReport = `
# Laporan Analisis UU 23/2014
Telaahan yuridis pembagian urusan pemerintahan daerah:

| No | Bidang Urusan | Kewenangan Pusat | Kewenangan Daerah | Status |
|---|---|---|---|---|
| 1 | Pendidikan | Standar Nasional, Kurikulum | Pengelolaan SD & SMP | Sesuai |
| 2 | Kesehatan | Akreditasi RS, Registrasi Nakes | Puskesmas, RSUD Kab/Kota | Sesuai |
| 3 | Tata Ruang | RTRW Nasional | RTRW Kabupaten/Kota | Perlu Revisi |

Kesimpulan: Perlu harmonisasi dengan NSPK terbaru.
    `;
    const genPath = rg.generateHtmlReportFromText(sampleReport, {
        title: 'Uji Coba Laporan SATRIA Bangda',
        request_id: 'test-unit-001'
    });

    const fs = require('fs');
    assert.ok(fs.existsSync(genPath), 'File HTML harus berhasil dibuat di disk');
    const content = fs.readFileSync(genPath, 'utf8');
    assert.ok(content.includes('Uji Coba Laporan SATRIA Bangda'), 'Judul harus ada di dalam HTML');
    assert.ok(content.includes('report-table'), 'Tabel HTML harus di-render dengan class report-table');
    assert.ok(content.includes('badge-warning'), 'Status Perlu Revisi harus mendapat badge-warning');

    // 5. Uji Pembuatan Preview Text
    const preview = rg.createWhatsAppPreviewText(sampleReport, 'Laporan_Uji.html', 300);
    assert.ok(preview.includes('Laporan Lengkap Terlampir'), 'Preview harus mencantumkan notifikasi lampiran');
    assert.ok(preview.includes('Laporan_Uji.html'), 'Preview harus menyebutkan nama berkas');

    console.log(JSON.stringify({ status: 'success', generated_path: genPath }));
    """

    res = subprocess.run(
        ["node", "-e", node_script],
        cwd=str(WORKSPACE_ROOT),
        capture_output=True,
        text=True,
        check=True
    )
    lines = [l for l in res.stdout.strip().split('\n') if l.strip().startswith('{')]
    data = json.loads(lines[-1])
    assert data["status"] == "success"
    assert os.path.exists(data["generated_path"])
    print(f"\n✅ JS Report Generator Test PASSED: {data['generated_path']}")

def test_python_whatsapp_client_document_payload():
    """Test WhatsAppClient di core/mcp-unified/integrations/whatsapp/client.py."""
    sys.path.insert(0, str(WORKSPACE_ROOT / "core" / "mcp-unified"))
    from integrations.whatsapp.client import WhatsAppClient

    client = WhatsAppClient(base_url="http://127.0.0.1:3001")
    
    # Verifikasi method send_message dan send_document tersedia
    assert hasattr(client, "send_message")
    assert hasattr(client, "send_document")
    print("✅ WhatsAppClient document methods verified successfully.")

if __name__ == "__main__":
    test_report_generator_js_logic()
    test_python_whatsapp_client_document_payload()
    print("🎉 ALL TESTS PASSED SUCCESSFULLY!")
