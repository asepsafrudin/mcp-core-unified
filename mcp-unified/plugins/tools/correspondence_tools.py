
import sys
import os
import json
from typing import Optional, List, Dict, Any

PROJECT_ROOT = "/home/aseps/MCP/mcp-unified"
sys.path.insert(0, PROJECT_ROOT)

from execution.registry import registry
from services.correspondence_dashboard import CorrespondenceDashboard, format_search_results
from integrations.korespondensi.utils import parse_posisi

# Initialize shared dashboard service
dashboard = CorrespondenceDashboard()

@registry.register(name="search_korespondensi")
def search_korespondensi(query: str, category: Optional[str] = None):
    """
    Mencari data surat menyurat (internal atau eksternal) berdasarkan kata kunci.
    
    Args:
        query: Kata kunci pencarian (misal: nomor surat, perihal, atau pengirim)
        category: Kategori sumber (pilihan: 'internal', 'external'). Kosongkan untuk mencari di semua sumber.
    """
    namespace = None
    if category == "internal":
        namespace = "korespondensi_internal_pooling"
    elif category == "external":
        namespace = "korespondensi_sekretariat_dispo_puu"
        
    results = dashboard.search_letters(query, namespace)
    return format_search_results(results, query)

@registry.register(name="get_korespondensi_summary")
def get_korespondensi_summary():
    """
    Mendapatkan ringkasan surat masuk terbaru dari Dashboard PUU.
    Menampilkan data internal (posisi di PUU) dan eksternal (disposisi terbaru).
    """
    return dashboard.get_recent_summary()

@registry.register(name="parse_surat_status")
def parse_surat_status(posisi_str: str):
    """
    Menganalisis string 'POSISI' pada surat internal untuk menentukan tahapan progres.
    
    Args:
        posisi_str: String mentah dari kolom POSISI (contoh: 'SES 2/01 KOREKSI')
    """
    return parse_posisi(posisi_str)

@registry.register(name="sync_semua_surat")
async def sync_semua_surat():
    """
    Memicu sinkronisasi manual untuk seluruh sumber data Google Sheets korespondensi.
    Gunakan ini jika ada data baru di GSheet yang belum muncul di bot.
    """
    from knowledge.smart_sync import main as run_sync
    import io
    from contextlib import redirect_stdout
    
    f = io.StringIO()
    with redirect_stdout(f):
        await run_sync()
    
    return f"✅ Sinkronisasi Selesai.\n\nDetail:\n{f.getvalue()}"
