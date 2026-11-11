"""
persona_router.py — Pengarah Persona Dinamis untuk SATRIA WhatsApp Bot.
Menentukan persona bot secara cerdas:
- 'personal_assistant' (DEFAULT): Untuk percakapan harian, sapaan, tanya-jawab taktis umum, koordinasi.
- 'admin_persuratan': Untuk kueri naskah dinas, tracking surat, dan disposisi pimpinan.
- 'legal_madya': Khusus bila pengguna secara eksplisit menuntut kajian/telaah yuridis mendalam atau audit PUU.
"""

from typing import Optional

def detect_satria_persona(query: str, intent: Optional[str] = None) -> str:
    """
    Menentukan persona bot secara dinamis berbasis konteks permintaan pengguna.
    Default diarahkan ke 'personal_assistant' agar bot luwes, ramah, dan to-the-point.
    """
    q_lower = (query or "").lower().strip()

    # 1. Prioritas Khusus: Jika eksplisit meminta sudut pandang PUU / Ahli Madya / Kajian Hukum Mendalam
    legal_explicit_keywords = [
        "substansi perundang-undangan", "perundang-undangan", "puu", "pendapat hukum",
        "analisis hukum", "analis hukum", "ahli madya", "telaah hukum", "kajian hukum",
        "legal opinion", "tinjauan yuridis", "sudut pandang hukum", "sudut pandang puu",
        "sebagai puu", "pandangan hukum", "pendapatmu sebagai ahli", "tanggapan hukum",
        "uji doktrin", "6 dimensi bphn", "ultra vires", "evaluasi raperda"
    ]
    if any(k in q_lower for k in legal_explicit_keywords):
        return "legal_madya"

    # 2. Tracking Persuratan & Disposisi
    if intent in ("cari_surat_korespondensi", "SEARCH_CORRESPONDENCE"):
        return "admin_persuratan"

    correspondence_keywords = [
        "lacak surat", "posisi berkas", "nomor nd", "nomor surat", "fasilitasi ranperda",
        "terima dirjen", "disposisi dirjen", "posisi surat", "nota dinas",
        "laporkan list surat", "daftar surat", "rekap surat", "agenda ula", "agenda ses"
    ]
    if any(k in q_lower for k in correspondence_keywords):
        return "admin_persuratan"

    # Jika hanya kata umum "surat" atau "disposisi" bersamaan dengan kata tanya persuratan spesifik
    if ("surat" in q_lower or "disposisi" in q_lower) and any(w in q_lower for w in ["ada", "cek", "cari", "masuk", "keluar", "status", "belum"]):
        return "admin_persuratan"

    # 3. Default: Personal Assistant (Human-First Companion)
    return "personal_assistant"

