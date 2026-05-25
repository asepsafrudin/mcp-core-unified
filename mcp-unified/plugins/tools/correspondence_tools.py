
import sys
import os
import json
import logging as _logging
from pathlib import Path
from typing import Optional, List, Dict, Any

# parents[0] = tools/, parents[1] = plugins/, parents[2] = core/mcp-unified/ ← BENAR
_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
_logger = _logging.getLogger(__name__)

if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Safe helper untuk mendapatkan path module
def _get_mod_path(mod):
    f = getattr(mod, '__file__', None)
    if f:
        return f
    p = getattr(mod, '__path__', None)
    if p:
        try:
            return str(list(p)[0])
        except Exception:
            return ''
    return ''

# Evict wrong-path versions dari sys.modules (dari /mcp-unified/ lama, bukan /core/mcp-unified/)
_correct_services = os.path.join(_PROJECT_ROOT, "services")
_correct_orchestration = os.path.join(_PROJECT_ROOT, "orchestration")
_correct_skills = os.path.join(_PROJECT_ROOT, "skills")
for _mod_name in list(sys.modules.keys()):
    _mod_path = _get_mod_path(sys.modules[_mod_name])
    if not _mod_path:
        continue
    if (_mod_name == "services" or _mod_name.startswith("services.")) and _correct_services not in _mod_path:
        del sys.modules[_mod_name]
    elif (_mod_name == "orchestration" or _mod_name.startswith("orchestration.")) and _correct_orchestration not in _mod_path:
        del sys.modules[_mod_name]
    elif (_mod_name == "skills" or _mod_name.startswith("skills.")) and _correct_skills not in _mod_path:
        del sys.modules[_mod_name]

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
        namespace=os.getenv("NAMESPACE", "korespondensi_internal_pooling" if not os.getenv("CI") else "DUMMY")
    elif category == "external":
        namespace=os.getenv("NAMESPACE", "korespondensi_sekretariat_dispo_puu" if not os.getenv("CI") else "DUMMY")
        
    results = dashboard.search_letters(query, namespace)
    return format_search_results(results, query)

@registry.register(name=os.getenv("NAME", "get_korespondensi_summary" if not os.getenv("CI") else "DUMMY"))
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